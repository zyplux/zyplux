"""Notify declared Worker bootstrap endpoints using GitHub Actions OIDC."""

import json
import os
from http import HTTPStatus
from http.client import HTTPSConnection
from time import monotonic, sleep
from urllib.parse import urlencode, urlsplit

from config_to_kv.cloudflare import find_namespace, list_bootstrap_urls, list_worker_bindings, request_cloudflare

CONFIG_WAIT_SECONDS = 120
RETRY_SECONDS = 5


def request_https(url: str, headers: dict[str, str], method: str = "GET") -> tuple[int, bytes]:
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname or target.username or target.password:
        message = "Worker bootstrap requires HTTPS URLs without credentials"
        raise ValueError(message)
    connection = HTTPSConnection(target.hostname, target.port, timeout=120)
    try:
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def notify_workers(urls: list[str], revision: str) -> None:
    for url in urls:
        token_url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&" + urlencode({"audience": url})
        status, payload = request_https(
            token_url, {"Authorization": f"Bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}"}
        )
        if status != HTTPStatus.OK:
            message = f"GitHub OIDC returned HTTP {status}"
            raise RuntimeError(message)
        token = json.loads(payload)["value"]
        headers = {"Authorization": f"Bearer {token}", "X-Worker-Config-Revision": revision}
        deadline = monotonic() + CONFIG_WAIT_SECONDS
        while True:
            status, _ = request_https(url, headers, "POST")
            if status == HTTPStatus.NO_CONTENT:
                break
            if status != HTTPStatus.CONFLICT or monotonic() >= deadline:
                message = f"Bootstrap at {url} returned HTTP {status}"
                raise RuntimeError(message)
            sleep(RETRY_SECONDS)


def bootstrap_deployment() -> None:
    environment = os.environ["DEPLOYMENT_ENVIRONMENT"]
    if environment not in {"production", "staging"}:
        message = "Select production or staging"
        raise ValueError(message)
    deployment = f"zyploop-{environment}"
    namespace = find_namespace(f"{deployment}-config")
    snapshot = request_cloudflare(f"storage/kv/namespaces/{namespace}/values/current")
    if snapshot is None:
        message = "Publish Worker config before bootstrap"
        raise RuntimeError(message)
    workers = list_worker_bindings(deployment, list(snapshot["requiredSecrets"]))
    notify_workers(list_bootstrap_urls(workers), snapshot["revision"])


if __name__ == "__main__":
    bootstrap_deployment()
