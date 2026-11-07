"""Publish config snapshots using the config repository's pinned validator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from config_to_kv.bootstrap import notify_workers
from config_to_kv.cloudflare import find_namespace, list_bootstrap_urls, list_worker_bindings, request_cloudflare


def load_snapshot(validator_version: str | None = None) -> dict[str, Any]:
    command = ["pnpm", "exec", "zyploop-config-validate", ".", "--worker-snapshot"]
    if validator_version is not None:
        command.extend(("--validator-version", validator_version))
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def verify_bindings(
    bindings: list[dict[str, Any]], namespace: str, secrets: list[str], environment: str, worker: str
) -> None:
    if not any(binding["name"] == "CONFIG" and binding.get("namespace_id") == namespace for binding in bindings):
        message = f"{worker} must use its environment's config KV namespace"
        raise RuntimeError(message)
    validator = next(
        (binding.get("text") for binding in bindings if binding["name"] == "CONFIG_VALIDATOR_VERSION"), None
    )
    if not validator:
        message = f"{worker} is missing its config validator version"
        raise RuntimeError(message)
    load_snapshot(validator)
    for secret in secrets:
        if not any(
            binding["name"] == secret
            and binding.get("type") == "secrets_store_secret"
            and binding.get("secret_name") == f"{environment}_{secret}"
            for binding in bindings
        ):
            message = f"{worker} needs the {secret} binding before publishing this config"
            raise RuntimeError(message)


def verify_workers(snapshot: dict[str, Any], deployment: str, namespace: str, environment: str) -> list[str]:
    workers = list_worker_bindings(deployment, list(snapshot["requiredSecrets"]))
    for kind, bindings in workers:
        verify_bindings(bindings, namespace, snapshot["requiredSecrets"][kind], environment, f"{deployment}-{kind}")
    return list_bootstrap_urls(workers)


def publish_config() -> None:
    environment = os.environ["DEPLOYMENT_ENVIRONMENT"]
    if environment not in {"production", "staging"}:
        message = "Select production or staging for Worker config publication"
        raise ValueError(message)
    snapshot = load_snapshot()
    snapshot["commit"] = os.environ["GITHUB_SHA"]
    deployment = f"zyploop-{environment}"
    namespace = find_namespace(f"{deployment}-config")
    key = f"storage/kv/namespaces/{namespace}/values/current"
    published = request_cloudflare(key, allow_missing=True)
    bootstrap_urls = verify_workers(snapshot, deployment, namespace, environment)
    if (
        published
        and published["revision"] == snapshot["revision"]
        and published.get("requiredSecrets") == snapshot["requiredSecrets"]
    ):
        sys.stdout.write(f"Worker config {snapshot['revision']} is already published\n")
        notify_workers(bootstrap_urls, snapshot["revision"])
        return
    response = request_cloudflare(key, method="PUT", body=snapshot)
    if response is None or not response["success"]:
        message = "Cloudflare refused Worker config publication"
        raise RuntimeError(message)
    notify_workers(bootstrap_urls, snapshot["revision"])
    sys.stdout.write(
        f"Published Worker config {snapshot['revision']} from {snapshot['commit']} to {deployment}-config\n"
    )


if __name__ == "__main__":
    publish_config()
