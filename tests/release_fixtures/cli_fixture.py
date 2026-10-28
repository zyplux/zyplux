from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from subprocess import run as run_native
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from wsgiref.simple_server import WSGIServer, make_server

from cli_runner import run_cli

if TYPE_CHECKING:
    from collections.abc import Callable
    from wsgiref.types import StartResponse, WSGIEnvironment

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Command:
    program: str
    argv: list[str]
    cwd: str
    stdin: str = ""
    env: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join([self.program, *self.argv])


@dataclass
class Reply:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass
class Request:
    url: str
    method: str
    headers: dict[str, str]


@dataclass
class Response:
    body: Any = None
    status: int = 200
    error: str = ""


type CommandReply = str | Reply | Callable[[Command], str | Reply]
type NetworkReply = Response | Callable[[Request], Response]


@dataclass
class CliFixture:
    root: Path
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    native_env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    calls: list[Command] = field(default_factory=list)
    requests: list[Request] = field(default_factory=list)
    commands: list[tuple[str | re.Pattern[str], CommandReply]] = field(default_factory=list)
    routes: list[tuple[str, NetworkReply]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    endpoint: str = ""
    credential: str = field(default_factory=lambda: uuid4().hex)

    def write(self, relative: str, text: str) -> None:
        file = self.root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text(encoding="utf-8")

    def write_json(self, relative: str, contents: object) -> None:
        self.write(relative, json.dumps(contents))

    def on(self, prefix: str | re.Pattern[str], reply: CommandReply = "") -> None:
        self.commands.append((prefix, reply))

    def serve(self, prefix: str, reply: NetworkReply) -> None:
        self.routes.append((prefix, reply))

    def matching(self, pattern: str) -> list[Command]:
        return [call for call in self.calls if re.search(pattern, call.text)]

    def execute(self, call: Command) -> Reply:
        self.calls.append(call)
        for prefix, reply in reversed(self.commands):
            if call.text.startswith(prefix) if isinstance(prefix, str) else prefix.search(call.text):
                answer = reply(call) if callable(reply) else reply
                return Reply(stdout=answer) if isinstance(answer, str) else answer
        self.failures.append(f"Unexpected command: {call.text}")
        return Reply(stderr=self.failures[-1], exit_code=1)

    def respond(self, request: Request) -> Response:
        self.requests.append(request)
        for prefix, reply in reversed(self.routes):
            if request.url.startswith(prefix):
                return reply(request) if callable(reply) else reply
        self.failures.append(f"Unexpected request: {request.method} {request.url}")
        return Response(status=500)

    def run(self, *args: str, error: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        execution = run_cli(self.root, {**self.env, "AIRLOCK_TEST_ENDPOINT": self.endpoint}, args)
        assert not self.failures, "\n".join(self.failures)
        if not check:
            return execution
        if error is None:
            assert execution.returncode == 0, execution.stdout + execution.stderr
        else:
            assert execution.returncode != 0, execution.stdout
            assert error in execution.stdout + execution.stderr
        return execution

    def run_real(self, call: Command) -> Reply:
        execution = run_native(
            [call.program, *call.argv],
            cwd=call.cwd,
            env=self.native_env,
            capture_output=True,
            text=True,
            check=False,
        )
        return Reply(execution.stdout, execution.stderr, execution.returncode)

    def start(self) -> tuple[WSGIServer, threading.Thread]:
        def respond(environ: WSGIEnvironment) -> Response:
            if environ["PATH_INFO"] == "/command":
                payload = json.loads(environ["wsgi.input"].read(int(environ["CONTENT_LENGTH"])))
                reply = self.execute(Command(**payload))
                return Response({"stdout": reply.stdout, "stderr": reply.stderr, "exit_code": reply.exit_code})
            headers = {
                name.removeprefix("HTTP_").lower().replace("_", "-"): value
                for name, value in environ.items()
                if name.startswith("HTTP_") and not name.startswith("HTTP_X_AIRLOCK_")
            }
            return self.respond(Request(environ["HTTP_X_AIRLOCK_URL"], environ["HTTP_X_AIRLOCK_METHOD"], headers))

        def app(environ: WSGIEnvironment, start_response: StartResponse) -> list[bytes]:
            try:
                response = respond(environ)
            except (AssertionError, LookupError, OSError, TypeError, ValueError) as exc:
                self.failures.append(f"Fixture failed: {exc}")
                response = Response(str(exc), 500)
            encoded = b"" if response.body is None else json.dumps(response.body).encode()
            headers = [("Content-Length", str(len(encoded)))]
            if response.error:
                headers.append(("x-airlock-error", response.error))
            start_response(f"{response.status} {HTTPStatus(response.status).phrase}", headers)
            return [encoded]

        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.endpoint = f"http://127.0.0.1:{server.server_port}"
        binaries = self.root / "bin"
        binaries.mkdir()
        executable = binaries / "command"
        stub = Path(__file__).with_name("command_stub.py").read_text(encoding="utf-8")
        executable.write_text(f"#!{sys.executable}\n{stub}", encoding="utf-8")
        executable.chmod(0o755)
        for program in ("git", "gh", "pnpm", "uv", "podman", "tar"):
            (binaries / program).symlink_to(executable)
        self.env["PATH"] = f"{binaries}{os.pathsep}{os.environ['PATH']}"
        for name in (
            "NODE_AUTH_TOKEN",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "GITHUB_ACTOR",
            "GITHUB_BASE_REF",
            "GITHUB_OUTPUT",
            "GITHUB_STEP_SUMMARY",
            "pnpm_config__auth",
            "PNPM_CONFIG__AUTH",
        ):
            self.env.pop(name, None)
        return server, thread
