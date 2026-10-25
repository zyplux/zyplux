from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import httpx
from airlock.cli import main

HTTP_CLIENT = httpx.Client


def relay_request(request: httpx.Request) -> httpx.Response:
    reply = relay_client.post(
        "/fetch",
        headers={
            **dict(request.headers),
            "x-airlock-url": str(request.url),
            "x-airlock-method": request.method,
        },
    )
    if reply.headers.get("x-airlock-error"):
        raise httpx.ReadTimeout(reply.headers["x-airlock-error"], request=request)
    return httpx.Response(reply.status_code, content=reply.content, request=request)


def relay_command(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
    response = relay_client.post(
        "/command",
        json={
            "program": Path(argv[0]).name,
            "argv": argv[1:],
            "cwd": str(options.get("cwd") or Path.cwd()),
            "stdin": options.get("input") or "",
        },
    )
    response.raise_for_status()
    reply = response.json()
    return subprocess.CompletedProcess(argv, reply["exit_code"], reply["stdout"], reply["stderr"])


def create_client(*, timeout: float, follow_redirects: bool) -> httpx.Client:
    return HTTP_CLIENT(transport=httpx.MockTransport(relay_request), timeout=timeout, follow_redirects=follow_redirects)


def skip_wait(seconds: float) -> None:
    pass


with (
    HTTP_CLIENT(base_url=os.environ["AIRLOCK_TEST_ENDPOINT"], trust_env=False, timeout=60) as relay_client,
    patch("airlock.registries.httpx.Client", side_effect=create_client),
    patch("airlock.proc.subprocess.run", side_effect=relay_command),
    patch("time.sleep", skip_wait),
):
    main()
