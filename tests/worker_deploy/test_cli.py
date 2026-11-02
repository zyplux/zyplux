import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from worker_deploy import cli

COMMIT = "a" * 40
VERSION = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    fake = tmp_path / "wrangler.py"
    fake.write_text("""import json, os, sys
from pathlib import Path
Path("invocation.json").write_text(json.dumps({"args": sys.argv[1:], "token": os.getenv("CLOUDFLARE_API_TOKEN")}))
print("sensitive-binding")
print("sensitive-binding", file=sys.stderr)
if os.getenv("FAKE_EXIT"):
    sys.exit(int(os.environ["FAKE_EXIT"]))
if os.getenv("FAKE_RECEIPT", "valid") != "missing":
    receipt = {"type": "deploy", "version": 1, "worker_name": "example",
               "version_id": "11111111-1111-4111-8111-111111111111"}
    if os.getenv("FAKE_RECEIPT") == "mismatch": receipt["worker_name"] = "wrong"
    if os.getenv("FAKE_RECEIPT") == "no-version": receipt.pop("version_id")
    Path(os.environ["WRANGLER_OUTPUT_FILE_PATH"]).write_text(json.dumps(receipt) + "\\n")
""")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "b" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "private-token")
    return ["worker-deploy", "--name", "example", "--source-commit", COMMIT, "--wrangler", f"{sys.executable} {fake}"]


def invoke(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *options: str
) -> dict[str, object]:
    monkeypatch.setattr(sys, "argv", [*command, *options])
    cli.main()
    return json.loads(capsys.readouterr().out)


def test_project_dry_run_preserves_discovery_without_credentials(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "fetch_cloudflare", Mock(side_effect=AssertionError("network")))
    receipt = invoke(command, monkeypatch, capsys, "--dry-run", "--secrets-file", "nonexistent.json")
    invocation = json.loads(Path("invocation.json").read_text(encoding="utf-8"))
    assert invocation["token"] is None
    assert invocation["args"] == ["deploy", "--name", "example", "--dry-run"]
    assert receipt == {"status": "dry_run", "worker_name": "example", "source_commit": COMMIT}


def test_prebuilt_deployment_returns_exact_verified_receipt(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    check = Mock(side_effect=[[], {"id": VERSION}])
    monkeypatch.setattr(cli, "fetch_cloudflare", check)
    secrets = Path("bindings.json")
    secrets.write_text('{"SECRET": "sensitive-binding"}', encoding="utf-8")
    secrets.chmod(0o600)
    receipt = invoke(
        command,
        monkeypatch,
        capsys,
        "--bundle",
        "index.js",
        "--config",
        "deploy.json",
        "--strict",
        "--tag",
        "release-v1",
        "--secrets-file",
        str(secrets),
        "--var",
        "PUBLIC:yes",
        "--domain",
        "example.com",
    )
    assert receipt == {"status": "deployed", "worker_name": "example", "version_id": VERSION, "source_commit": COMMIT}
    args = json.loads(Path("invocation.json").read_text(encoding="utf-8"))["args"]
    assert args[:4] == ["deploy", "index.js", "--no-bundle", "--name"]
    assert "sensitive-binding" not in " ".join(args)
    assert check.call_args_list[0].args[0] == f"accounts/{'b' * 32}/workers/scripts"
    assert check.call_args_list[1].args[0].endswith(f"/example/versions/{VERSION}")


@pytest.mark.parametrize("receipt", ["missing", "mismatch", "no-version"])
def test_invalid_upload_fails_without_exposing_output(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], receipt: str
) -> None:
    monkeypatch.setattr(cli, "fetch_cloudflare", Mock(return_value=[]))
    monkeypatch.setenv("FAKE_RECEIPT", receipt)
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys)
    captured = capsys.readouterr()
    assert not captured.out
    assert "sensitive-binding" not in captured.err
    assert "matching Worker upload" in captured.err


def test_wrangler_failure_propagates_exit_code(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FAKE_EXIT", "7")
    with pytest.raises(SystemExit, match="7"):
        invoke(command, monkeypatch, capsys, "--dry-run")
    assert "sensitive-binding" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "options",
    [
        ["--bundle", "index.js"],
        ["--name", "INVALID"],
        ["--source-commit", "HEAD"],
        ["--cwd", "/nonexistent"],
        ["--wrangler", ""],
        ["--wrangler", "'"],
    ],
)
def test_bad_inputs_fail_before_execution(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], options: list[str]
) -> None:
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys, "--dry-run", *options)
    assert not Path("invocation.json").exists()


def test_missing_credentials_fail_before_execution(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys)
    assert not Path("invocation.json").exists()


@pytest.mark.parametrize(
    ("content", "mode"), [("{}", 0o644), ("invalid-sensitive-binding", 0o600), ("[]", 0o600), ('{"KEY": 7}', 0o600)]
)
def test_unprotected_or_invalid_secrets_fail_safely(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], content: str, mode: int
) -> None:
    path = Path("bindings.json")
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys, "--secrets-file", str(path))
    assert not Path("invocation.json").exists()
    assert "sensitive-binding" not in capsys.readouterr().err


def test_wrong_account_version_is_not_reported_as_success(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "fetch_cloudflare", Mock(side_effect=[[], {"id": "wrong"}]))
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys)
    assert "selected account" in capsys.readouterr().err


def test_unavailable_wrangler_fails_clearly(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys, "--dry-run", "--wrangler", "/missing/wrangler")
    assert "Cannot execute" in capsys.readouterr().err


@pytest.mark.parametrize("envelope", [{"success": True, "result": []}, {"success": False}, []])
def test_account_api_uses_bearer_auth(monkeypatch: pytest.MonkeyPatch, envelope: object) -> None:
    request = Mock(
        return_value=cli.httpx.Response(200, json=envelope, request=cli.httpx.Request("GET", "https://example.com"))
    )
    monkeypatch.setattr(cli.httpx, "get", request)
    if isinstance(envelope, dict) and envelope.get("success"):
        assert cli.fetch_cloudflare("accounts/example/workers/scripts", "private") == []
    else:
        with pytest.raises(cli.DeploymentError):
            cli.fetch_cloudflare("accounts/example/workers/scripts", "private")
    assert request.call_args.kwargs["headers"] == {"Authorization": "Bearer private"}


def test_account_api_errors_do_not_echo_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.httpx, "get", Mock(side_effect=cli.httpx.ConnectError("private-token")))
    with pytest.raises(cli.DeploymentError, match="account access check failed") as error:
        cli.fetch_cloudflare("accounts/example/workers/scripts", "private-token")
    assert "private-token" not in str(error.value)


def test_secret_symlinks_are_rejected_before_execution(
    command: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = Path("bindings.json")
    target.write_text('{"KEY":"private-binding"}', encoding="utf-8")
    target.chmod(0o600)
    link = Path("bindings-link.json")
    link.symlink_to(target)
    with pytest.raises(SystemExit, match="1"):
        invoke(command, monkeypatch, capsys, "--secrets-file", str(link))
    assert not Path("invocation.json").exists()
    assert "regular owner-only file" in capsys.readouterr().err
