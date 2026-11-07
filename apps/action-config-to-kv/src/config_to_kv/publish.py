"""Publish config snapshots using the config repository's pinned validator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from http import HTTPStatus
from http.client import HTTPSConnection
from typing import Any, cast

HOURS_PER_DAY = 24


def request_cloudflare(
    path: str, *, method: str = "GET", body: object = None, allow_missing: bool = False
) -> dict[str, Any] | None:
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    connection = HTTPSConnection("api.cloudflare.com", timeout=30)
    try:
        connection.request(
            method,
            f"/client/v4/accounts/{account}/{path}",
            body=None if body is None else json.dumps(body),
            headers={
                "Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
                "Content-Type": "application/json",
            },
        )
        response = connection.getresponse()
        if allow_missing and response.status == HTTPStatus.NOT_FOUND:
            return None
        if not HTTPStatus.OK <= response.status < HTTPStatus.MULTIPLE_CHOICES:
            message = f"Cloudflare {method} {path} returned HTTP {response.status}"
            raise RuntimeError(message)
        return json.loads(response.read())
    finally:
        connection.close()


def fetch_result(path: str, *, allow_missing: bool = False) -> dict[str, Any] | None:
    response = request_cloudflare(path, allow_missing=allow_missing)
    if response is None:
        return None
    if response is None or not response["success"]:
        message = f"Cloudflare could not read {path}"
        raise RuntimeError(message)
    return response["result"]


def find_namespace(title: str) -> str:
    page = 1
    page_size = 50
    while True:
        response = request_cloudflare(f"storage/kv/namespaces?per_page={page_size}&page={page}")
        if response is None or not response["success"]:
            message = "Cannot list KV namespaces"
            raise RuntimeError(message)
        namespaces = cast("list[dict[str, Any]]", response["result"])
        for namespace in namespaces:
            if namespace["title"] == title:
                return namespace["id"]
        if len(namespaces) < page_size:
            message = f"Provision the {title} KV namespace before publishing"
            raise RuntimeError(message)
        page += 1


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


def verify_workers(snapshot: dict[str, Any], deployment: str, namespace: str, environment: str) -> str | None:
    email_worker = None
    for kind, secrets in snapshot["requiredSecrets"].items():
        worker = f"{deployment}-{kind}"
        script = f"workers/scripts/{worker}"
        deployments = fetch_result(f"{script}/deployments", allow_missing=True)
        versions = deployments["deployments"][0]["versions"] if deployments and deployments["deployments"] else []
        for version in versions:
            version_info = fetch_result(f"{script}/versions/{version['version_id']}")
            if version_info is None:
                message = "Missing Worker version"
                raise RuntimeError(message)
            resources = version_info["resources"]
            verify_bindings(resources["bindings"], namespace, secrets, environment, worker)
        if kind == "email" and versions:
            email_worker = script
    return email_worker


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
    if (
        published
        and published["revision"] == snapshot["revision"]
        and published.get("requiredSecrets") == snapshot["requiredSecrets"]
    ):
        sys.stdout.write(f"Worker config {snapshot['revision']} is already published\n")
        return
    email_worker = verify_workers(snapshot, deployment, namespace, environment)
    hours = snapshot["settings"]["email_maintenance_hours"]
    if email_worker and (not published or published["settings"]["email_maintenance_hours"] != hours):
        cron_hours = "0" if hours == HOURS_PER_DAY else f"*/{hours}"
        response = request_cloudflare(
            f"{email_worker}/schedules", method="PUT", body=[{"cron": f"0 {cron_hours} * * *"}]
        )
        if response is None or not response["success"]:
            message = "Cloudflare refused the Email Worker schedule"
            raise RuntimeError(message)
    response = request_cloudflare(key, method="PUT", body=snapshot)
    if response is None or not response["success"]:
        message = "Cloudflare refused Worker config publication"
        raise RuntimeError(message)
    sys.stdout.write(
        f"Published Worker config {snapshot['revision']} from {snapshot['commit']} to {deployment}-config\n"
    )


if __name__ == "__main__":
    publish_config()
