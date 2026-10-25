from __future__ import annotations

import base64
import os
import time
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

import httpx
import typer
from semantic_version import Version

from airlock import proc
from airlock.actions import is_action_published
from airlock.contracts import (
    GhcrTags,
    GhcrToken,
    GithubUser,
    NpmArtifact,
    NpmHistory,
    NpmLatest,
    NpmPackage,
    NpmVersions,
    PypiFiles,
    PypiLatest,
)
from airlock.targets import parse_stable_version

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from airlock.contracts import PypiFile, ReleaseTarget

REQUEST_TIMEOUT = 10
DEPENDENCY_POLL_ATTEMPTS = 61
MANIFEST_MEDIA_TYPES = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.oci.image.manifest.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)


def validate_response(response: httpx.Response) -> None:
    if not response.is_success:
        msg = f"fetch {response.url} failed: {response.status_code}"
        raise httpx.HTTPStatusError(msg, request=response.request, response=response)


def fetch_json[Model: BaseModel](url: str, schema: type[Model], headers: dict[str, str] | None = None) -> Model:
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        validate_response(response)
        return schema.model_validate_json(response.content)


def load_github_token(*preferred: str | None) -> str | None:
    candidate = next((token for token in (*preferred, os.getenv("GH_TOKEN"), os.getenv("GITHUB_TOKEN")) if token), None)
    if candidate:
        return candidate
    try:
        return proc.run("gh", "auth", "token", "--hostname", "github.com") or None
    except OSError, proc.CommandError:
        return None


def fetch_ghcr_token(image: str) -> str:
    credential = load_github_token(os.getenv("GH_TOKEN"), os.getenv("NODE_AUTH_TOKEN"))
    headers = {}
    if credential:
        actor = (
            os.getenv("GITHUB_ACTOR")
            or fetch_json(
                "https://api.github.com/user",
                GithubUser,
                {"Authorization": f"Bearer {credential}", "User-Agent": "zyplux-airlock"},
            ).login
        )
        encoded = base64.b64encode(f"{actor}:{credential}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    return fetch_json(f"https://ghcr.io/token?service=ghcr.io&scope=repository:{image}:pull", GhcrToken, headers).token


def load_npm_registry(directory: Path, label: str) -> str:
    package = NpmPackage.model_validate_json((directory / "package.json").read_text(encoding="utf-8"))
    registry_key = f"{label.split('/', 1)[0]}:registry" if label.startswith("@") else "registry"
    configured = package.publish_config.get(
        registry_key, package.publish_config.get("registry", "https://registry.npmjs.org")
    )
    return validate_npm_registry(configured)


def validate_npm_registry(registry: object) -> str:
    if not isinstance(registry, str) or registry.rstrip("/") not in {
        "https://registry.npmjs.org",
        "https://npm.pkg.github.com",
    }:
        msg = f"unsupported npm registry {registry!r}"
        raise ValueError(msg)
    return registry.rstrip("/")


def load_npm_request(directory: Path, label: str) -> tuple[str, dict[str, str]]:
    return build_npm_request(label, load_npm_registry(directory, label))


def build_npm_request(label: str, registry: str = "https://registry.npmjs.org") -> tuple[str, dict[str, str]]:
    registry = validate_npm_registry(registry)
    headers = {}
    if registry == "https://npm.pkg.github.com":
        credential = load_github_token(os.getenv("NODE_AUTH_TOKEN"))
        if not credential:
            msg = (
                "GitHub Packages requires authentication: run gh auth login --scopes read:packages "
                "or supply NODE_AUTH_TOKEN"
            )
            raise ValueError(msg)
        headers["Authorization"] = f"Bearer {credential}"
    return f"{registry}/{quote(label, safe='')}", headers


def fetch_latest_npm(
    label: str, registry: str = "https://registry.npmjs.org", *, minimum_age: timedelta | None = None
) -> str:
    url, headers = build_npm_request(label, registry)
    if minimum_age is None:
        return fetch_json(url, NpmLatest, headers).tags.latest
    history = fetch_json(url, NpmHistory, headers)
    latest = Version(history.tags.latest)
    published_before = datetime.now(UTC) - minimum_age
    eligible = []
    for name in history.versions:
        try:
            version = parse_stable_version(name)
        except ValueError:
            continue
        if not version.build and version <= latest and history.time[name] <= published_before:
            eligible.append(version)
    if not eligible:
        msg = f"{label}: no stable release is old enough to install"
        raise ValueError(msg)
    return str(max(eligible))


def fetch_latest_pypi(label: str) -> str:
    return fetch_json(f"https://pypi.org/pypi/{label}/json", PypiLatest).info.version


def fetch_latest_ghcr(label: str) -> str | None:
    image = label.removeprefix("ghcr.io/")
    credential = fetch_ghcr_token(image)
    tags = fetch_json(f"https://ghcr.io/v2/{image}/tags/list", GhcrTags, {"Authorization": f"Bearer {credential}"}).tags
    versions = []
    for tag in tags or []:
        try:
            version = parse_stable_version(tag)
        except ValueError:
            continue
        versions.append(version)
    return str(max(versions)) if versions else None


def fetch_npm_availability(target: ReleaseTarget) -> bool:
    url, headers = load_npm_request(target.directory, target.spec.label)
    metadata = fetch_json(url, NpmVersions, headers)
    if target.version not in metadata.versions:
        return False
    archive = NpmArtifact.model_validate(metadata.versions[target.version])
    tarball = str(archive.dist.tarball)
    auth = (
        headers
        if urlsplit(url).netloc == urlsplit(tarball).netloc and urlsplit(url).scheme == urlsplit(tarball).scheme
        else {}
    )
    with (
        httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client,
        client.stream("GET", tarball, headers=auth) as response,
    ):
        validate_response(response)
        return True


def is_package_available(target: ReleaseTarget) -> bool:
    try:
        return fetch_npm_availability(target) if target.spec.kind == "npm" else is_published(target)
    except httpx.HTTPStatusError as exc:
        if (
            exc.response.status_code in {HTTPStatus.NOT_FOUND, HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.TOO_MANY_REQUESTS}
            or exc.response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            return False
        raise
    except httpx.TimeoutException:
        return False


def wait_for_dependencies(dependencies: list[ReleaseTarget]) -> None:
    if not dependencies:
        return
    pending = dependencies
    kind = pending[0].spec.kind
    typer.echo(
        f"Waiting for {kind} dependencies: " + ", ".join(f"{target.spec.label}@{target.version}" for target in pending)
    )
    for attempt in range(DEPENDENCY_POLL_ATTEMPTS):
        pending = [target for target in pending if not is_package_available(target)]
        if not pending:
            return
        if attempt < DEPENDENCY_POLL_ATTEMPTS - 1:
            time.sleep(10)
    raise ValueError(
        f"{kind} dependencies did not become available: "
        + ", ".join(f"{target.spec.label}@{target.version}" for target in pending)
    )


def is_container_available(label: str, reference: str) -> bool:
    image = label.removeprefix("ghcr.io/")
    try:
        credential = fetch_ghcr_token(image)
        headers = {"Accept": MANIFEST_MEDIA_TYPES, "Authorization": f"Bearer {credential}"}
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            validate_response(client.head(f"https://ghcr.io/v2/{image}/manifests/{reference}", headers=headers))
            return True
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == HTTPStatus.NOT_FOUND:
            return False
        raise


def fetch_pypi_files(target: ReleaseTarget) -> list[PypiFile]:
    try:
        return fetch_json(f"https://pypi.org/pypi/{target.spec.label}/{target.version}/json", PypiFiles).urls
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == HTTPStatus.NOT_FOUND:
            return []
        raise


def has_package_artifacts(target: ReleaseTarget) -> bool:
    return bool(fetch_pypi_files(target)) if target.spec.kind == "pypi" else is_published(target)


def is_published(target: ReleaseTarget) -> bool:
    if target.spec.kind == "action":
        return is_action_published(target)
    try:
        if target.spec.kind == "npm":
            url, headers = load_npm_request(target.directory, target.spec.label)
            return target.version in fetch_json(url, NpmVersions, headers).versions
        if target.spec.kind == "pypi":
            return {"bdist_wheel", "sdist"}.issubset(file.packagetype for file in fetch_pypi_files(target))
        return is_container_available(target.spec.label, target.version)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == HTTPStatus.NOT_FOUND:
            return False
        raise
