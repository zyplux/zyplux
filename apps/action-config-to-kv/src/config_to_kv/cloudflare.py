"""Read and publish Cloudflare account resources."""

import json
import os
from http import HTTPStatus
from http.client import HTTPSConnection
from typing import Any, cast


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
    if not response["success"]:
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


def list_worker_bindings(deployment: str, kinds: list[str]) -> list[tuple[str, list[dict[str, Any]]]]:
    workers = []
    for kind in kinds:
        script = f"workers/scripts/{deployment}-{kind}"
        deployments = fetch_result(f"{script}/deployments", allow_missing=True)
        versions = deployments["deployments"][0]["versions"] if deployments and deployments["deployments"] else []
        for version in versions:
            details = fetch_result(f"{script}/versions/{version['version_id']}")
            if details is None:
                message = "Missing Worker version"
                raise RuntimeError(message)
            workers.append((kind, details["resources"]["bindings"]))
    return workers


def list_bootstrap_urls(workers: list[tuple[str, list[dict[str, Any]]]]) -> list[str]:
    return sorted({
        binding["text"] for _, bindings in workers for binding in bindings if binding["name"] == "BOOTSTRAP_URL"
    })
