"""Latest-release lookups for the registries the org publishes to.

`_fetch_json` is the single HTTPS boundary — every registry call goes through
it, so tests fake it and never touch the network. `HTTPSConnection` pins the
scheme by construction, leaving no way to smuggle in a non-https URL.
"""

from __future__ import annotations

import http.client
import json
import re
import urllib.parse

_REQUEST_TIMEOUT_SECONDS = 10.0
_HTTP_OK = 200
_VERSION_TAG = re.compile(r"\d+(?:\.\d+)*")


class RegistryLookupError(RuntimeError):
    pass


def _parse_payload(url: str, response: http.client.HTTPResponse) -> object:
    body = response.read()
    if response.status != _HTTP_OK:
        failure = f"{url}: HTTP {response.status}"
        raise RegistryLookupError(failure)
    return json.loads(body)


def _fetch_json(host: str, path: str, headers: dict[str, str] | None = None) -> object:
    connection = http.client.HTTPSConnection(host, timeout=_REQUEST_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers=headers or {})
        return _parse_payload(f"https://{host}{path}", connection.getresponse())
    except (OSError, ValueError, http.client.HTTPException) as err:
        failure = f"https://{host}{path}: {err}"
        raise RegistryLookupError(failure) from err
    finally:
        connection.close()


def _extract(payload: object, *keys: str, source: str) -> object:
    for key in keys:
        if not isinstance(payload, dict) or key not in payload:
            failure = f"{source}: response carries no `{'.'.join(keys)}`"
            raise RegistryLookupError(failure)
        payload = payload[key]
    return payload


def fetch_latest_npm(package: str) -> str:
    path = "/" + urllib.parse.quote(package, safe="@")
    payload = _fetch_json("registry.npmjs.org", path)
    return str(_extract(payload, "dist-tags", "latest", source=package))


def fetch_latest_pypi(distribution: str) -> str:
    payload = _fetch_json("pypi.org", f"/pypi/{distribution}/json")
    return str(_extract(payload, "info", "version", source=distribution))


def _version_sort_key(tag: str) -> tuple[int, ...]:
    return tuple(int(part) for part in tag.split("."))


def fetch_latest_ghcr(image: str) -> str:
    token_payload = _fetch_json("ghcr.io", f"/token?scope=repository:{image}:pull")
    token = str(_extract(token_payload, "token", source=image))
    tags_payload = _fetch_json("ghcr.io", f"/v2/{image}/tags/list", {"Authorization": f"Bearer {token}"})
    tags = _extract(tags_payload, "tags", source=image)
    if not isinstance(tags, list):
        failure = f"{image}: tag list is not a list"
        raise RegistryLookupError(failure)
    version_tags = [tag for tag in tags if isinstance(tag, str) and _VERSION_TAG.fullmatch(tag)]
    if not version_tags:
        failure = f"{image}: no version tags published"
        raise RegistryLookupError(failure)
    return max(version_tags, key=_version_sort_key)
