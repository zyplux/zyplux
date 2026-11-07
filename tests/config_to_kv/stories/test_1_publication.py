from copy import deepcopy
from unittest.mock import patch

import pytest
from config_to_kv.publish import publish_config, verify_bindings


def test_1_1_publishes_validator_snapshot_without_reading_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("GITHUB_SHA", "commit")
    snapshot = {
        "revision": "revision",
        "settings": {"requires_validator": "^9.0.0"},
        "requiredSecrets": {"identity": ["KEY"]},
    }
    writes: list[object] = []

    def request(_path: str, **kwargs: object) -> dict[str, bool] | None:
        if kwargs.get("method") == "PUT":
            writes.append(kwargs["body"])
            return {"success": True}
        return None

    with (
        patch("config_to_kv.publish.load_snapshot", return_value=deepcopy(snapshot)),
        patch("config_to_kv.publish.find_namespace", return_value="namespace"),
        patch("config_to_kv.publish.list_worker_bindings", return_value=[]),
        patch("config_to_kv.publish.request_cloudflare", side_effect=request),
    ):
        publish_config()
    assert writes == [{**snapshot, "commit": "commit"}]


def test_1_2_rejects_unbound_credentials_before_publication() -> None:
    bindings = [
        {"name": "CONFIG", "namespace_id": "namespace"},
        {"name": "CONFIG_VALIDATOR_VERSION", "text": "8.1.0"},
    ]
    with (
        patch("config_to_kv.publish.load_snapshot") as validator,
        pytest.raises(RuntimeError, match="needs the KEY binding"),
    ):
        verify_bindings(bindings, "namespace", ["KEY"], "staging", "identity")
    validator.assert_called_once_with("8.1.0")
    bindings.append({"name": "KEY", "type": "secrets_store_secret", "secret_name": "staging_KEY"})
    with patch("config_to_kv.publish.load_snapshot"):
        verify_bindings(bindings, "namespace", ["KEY"], "staging", "identity")


def test_1_3_skips_unchanged_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("GITHUB_SHA", "commit")
    with (
        patch("config_to_kv.publish.load_snapshot", return_value={"revision": "same", "requiredSecrets": {}}),
        patch("config_to_kv.publish.find_namespace", return_value="namespace"),
        patch("config_to_kv.publish.request_cloudflare", return_value={"revision": "same", "requiredSecrets": {}}),
        patch("config_to_kv.publish.list_worker_bindings", return_value=[]) as fetch,
    ):
        publish_config()
    fetch.assert_called_once_with("zyploop-staging", [])


def test_1_4_bootstrap_follows_successful_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_ENVIRONMENT", "staging")
    monkeypatch.setenv("GITHUB_SHA", "commit")
    secret_names: list[str] = []
    snapshot = {"revision": "revision", "requiredSecrets": {"email": secret_names}}
    steps: list[str] = []

    def request(_path: str, **kwargs: object) -> dict[str, bool] | None:
        if kwargs.get("method") == "PUT":
            steps.append("publish")
            return {"success": True}
        return None

    def notify(urls: list[str], revision: str) -> None:
        assert urls == ["https://email.test/bootstrap"]
        assert revision == "revision"
        steps.append("bootstrap")

    bindings = [
        {"name": "CONFIG", "namespace_id": "namespace"},
        {"name": "CONFIG_VALIDATOR_VERSION", "text": "9.0.0"},
        {"name": "BOOTSTRAP_URL", "text": "https://email.test/bootstrap"},
    ]
    with (
        patch("config_to_kv.publish.load_snapshot", return_value=snapshot),
        patch("config_to_kv.publish.find_namespace", return_value="namespace"),
        patch("config_to_kv.publish.list_worker_bindings", return_value=[("email", bindings)]),
        patch("config_to_kv.publish.request_cloudflare", side_effect=request),
        patch("config_to_kv.publish.notify_workers", side_effect=notify),
    ):
        publish_config()
    assert steps == ["publish", "bootstrap"]
