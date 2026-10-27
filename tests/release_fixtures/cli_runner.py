from __future__ import annotations

import subprocess
import sys
from contextlib import chdir, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from airlock.cli import main

HTTP_CLIENT = httpx.Client


def run_cli(root: Path, env: dict[str, str], args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    with HTTP_CLIENT(base_url=env["AIRLOCK_TEST_ENDPOINT"], trust_env=False, timeout=60) as relay:

        def fetch(request: httpx.Request) -> httpx.Response:
            reply = relay.post(
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

        def execute(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
            response = relay.post(
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
            return HTTP_CLIENT(transport=httpx.MockTransport(fetch), timeout=timeout, follow_redirects=follow_redirects)

        stdout, stderr = StringIO(), StringIO()
        with (
            chdir(root),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            patch.dict("os.environ", env, clear=True),
            patch.object(sys, "argv", ["airlock", *args]),
            patch("airlock.registries.httpx.Client", side_effect=create_client),
            patch("airlock.proc.subprocess.run", side_effect=execute),
            patch("airlock.registries.time"),
            patch("airlock.actions.time"),
            pytest.raises(SystemExit) as termination,
        ):
            main()
        exit_code = termination.value.code
        assert isinstance(exit_code, int)
        return subprocess.CompletedProcess(args, exit_code, stdout.getvalue(), stderr.getvalue())
