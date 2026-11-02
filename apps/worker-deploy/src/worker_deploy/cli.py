"""Deploy one Worker and emit a verified JSON receipt on stdout."""

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import httpx


class DeploymentError(Exception):
    """Deployment could not be verified."""


def fetch_cloudflare(path: str, token: str) -> object:
    try:
        response = httpx.get(
            f"https://api.cloudflare.com/client/v4/{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        envelope = response.json()
    except (httpx.HTTPError, ValueError) as error:
        message = "Cloudflare account access check failed; check token permissions and account"
        raise DeploymentError(message) from error
    if not isinstance(envelope, dict) or envelope.get("success") is not True:
        message = "Cloudflare rejected the account access check"
        raise DeploymentError(message)
    return envelope.get("result")


def validate_secrets(path: Path) -> None:
    if not path.is_file() or path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        message = "Secret bindings must be a regular owner-only file (chmod 600)"
        raise DeploymentError(message)
    try:
        bindings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        message = "Secret bindings must be a JSON object of strings"
        raise DeploymentError(message) from error
    if not isinstance(bindings, dict) or not all(isinstance(item, str) for item in bindings.values()):
        message = "Secret bindings must be a JSON object of strings"
        raise DeploymentError(message)


def load_upload(path: Path, name: str) -> str:
    message = "Wrangler did not identify exactly one matching Worker upload and version ID"
    try:
        entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as error:
        raise DeploymentError(message) from error
    uploads = [entry for entry in entries if isinstance(entry, dict) and entry.get("type") == "deploy"]
    if len(uploads) != 1 or uploads[0].get("version") != 1 or uploads[0].get("worker_name") != name:
        raise DeploymentError(message)
    try:
        return str(UUID(uploads[0]["version_id"]))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise DeploymentError(message) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Exact intended Worker name, including environment suffix")
    parser.add_argument("--source-commit", required=True, help="Full source Git commit of the deployed artifact")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--wrangler", default="pnpm exec wrangler", help="Caller-pinned executable command; no shell")
    parser.add_argument("--config", type=Path, help="Omit to preserve Wrangler/Vite configuration discovery")
    parser.add_argument("--env", help="Wrangler environment; select Vite environments at build time instead")
    parser.add_argument("--bundle", type=Path, help="Published entry point; requires --config, disables bundling")
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--var", action="append", default=[], help="Public KEY:VALUE binding; never supply secrets")
    parser.add_argument("--secrets-file", type=Path, help="Owner-only JSON string bindings; omitted in dry runs")
    parser.add_argument("--tag")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Compile/package only; does not authenticate")
    return parser


def validate_inputs(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", args.name):
        message = "Invalid Worker name"
        raise DeploymentError(message)
    if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", args.source_commit):
        message = "Source commit must be a full Git commit hash"
        raise DeploymentError(message)
    if not args.cwd.is_dir():
        message = "Deployment working directory does not exist"
        raise DeploymentError(message)
    if args.bundle is not None and args.config is None:
        message = "Prebuilt bundles require an explicit Wrangler config"
        raise DeploymentError(message)


def build_command(args: argparse.Namespace) -> list[str]:
    validate_inputs(args)
    command = shlex.split(args.wrangler)
    if not command:
        message = "Wrangler command is empty"
        raise DeploymentError(message)
    command.append("deploy")
    if args.bundle is not None:
        command.extend([str(args.bundle), "--no-bundle"])
    command.extend(["--name", args.name])
    for flag, option in (("--config", args.config), ("--env", args.env), ("--tag", args.tag)):
        if option is not None:
            command.extend([flag, str(option)])
    for flag, options in (("--domain", args.domain), ("--var", args.var)):
        for option in options:
            command.extend([flag, option])
    if args.strict:
        command.append("--strict")
    if args.dry_run:
        command.append("--dry-run")
    elif args.secrets_file is not None:
        command.extend(["--secrets-file", str(args.secrets_file.resolve())])
    return command


def build_environment(args: argparse.Namespace) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({"CI": "true", "WRANGLER_SEND_METRICS": "false", "WRANGLER_LOG": "none"})
    account = environment.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = environment.get("CLOUDFLARE_API_TOKEN", "")
    if args.dry_run:
        for key in list(environment):
            if key.startswith(("CLOUDFLARE_", "CF_")):
                del environment[key]
    else:
        if not re.fullmatch(r"[a-fA-F0-9]{32}", account) or not token:
            message = "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN for deployment"
            raise DeploymentError(message)
        if args.secrets_file is not None:
            validate_secrets(args.secrets_file)
        fetch_cloudflare(f"accounts/{account}/workers/scripts", token)
    return environment


def deploy(args: argparse.Namespace) -> dict[str, object]:
    command = build_command(args)
    environment = build_environment(args)
    with TemporaryDirectory(prefix="worker-deploy-") as directory:
        scratch = Path(directory)
        upload_path = scratch / "upload.ndjson"
        environment.update({"WRANGLER_OUTPUT_FILE_PATH": str(upload_path), "WRANGLER_LOG_PATH": str(scratch / "logs")})
        try:
            completed = subprocess.run(
                command,
                cwd=args.cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError as error:
            message = "Cannot execute the caller's Wrangler command"
            raise DeploymentError(message) from error
        if completed.returncode:
            sys.stderr.write(
                f"worker-deploy: Wrangler failed (exit {completed.returncode}); output withheld to protect bindings\n"
            )
            raise SystemExit(completed.returncode if completed.returncode > 0 else 1)
        if args.dry_run:
            return {"status": "dry_run", "worker_name": args.name, "source_commit": args.source_commit}
        version = load_upload(upload_path, args.name)
        # Config account_id takes precedence over the environment in Wrangler.
        observed = fetch_cloudflare(
            f"accounts/{environment['CLOUDFLARE_ACCOUNT_ID']}/workers/scripts/{args.name}/versions/{version}",
            environment["CLOUDFLARE_API_TOKEN"],
        )
        if not isinstance(observed, dict) or observed.get("id") != version:
            message = "Uploaded version could not be verified in the selected account"
            raise DeploymentError(message)
        return {
            "status": "deployed",
            "worker_name": args.name,
            "version_id": version,
            "source_commit": args.source_commit,
        }


def main() -> None:
    args = build_parser().parse_args()
    try:
        receipt = deploy(args)
    except (DeploymentError, ValueError) as error:
        message = str(error) if isinstance(error, DeploymentError) else "Invalid deployment input"
        sys.stderr.write(f"worker-deploy: {message}\n")
        raise SystemExit(1) from None
    sys.stdout.write(json.dumps(receipt, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
