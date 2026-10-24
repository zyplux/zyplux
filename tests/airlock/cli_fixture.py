from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any, override
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Command:
    program: str
    argv: list[str]
    cwd: str
    stdin: str = ""

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

    def run(
        self, *args: str, error: str | None = None, stdin: str = "", check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        execution = subprocess.run(
            [
                "node",
                "--import",
                str(Path(__file__).with_name("preload.ts")),
                str(REPO_ROOT / "apps/airlock/src/index.ts"),
                *args,
            ],
            cwd=self.root,
            env={**self.env, "AIRLOCK_TEST_ENDPOINT": self.endpoint},
            input=stdin,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert not self.failures, "\n".join(self.failures)
        if not check:
            return execution
        if error is None:
            assert execution.returncode == 0, execution.stdout + execution.stderr
        else:
            assert execution.returncode != 0, execution.stdout
            assert error in execution.stdout + execution.stderr
        return execution

    @staticmethod
    def run_real(call: Command) -> Reply:
        execution = subprocess.run(
            [call.program, *call.argv],
            cwd=call.cwd,
            env=os.environ,
            capture_output=True,
            text=True,
            check=False,
        )
        return Reply(execution.stdout, execution.stderr, execution.returncode)

    def start(self) -> tuple[ThreadingHTTPServer, threading.Thread]:
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            @override
            def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
                pass

            def build_response(self) -> Response:
                if self.path == "/command":
                    payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    reply = fixture.execute(Command(**payload))
                    return Response({
                        "stdout": reply.stdout,
                        "stderr": reply.stderr,
                        "exit_code": reply.exit_code,
                    })
                headers = {
                    key.lower(): value
                    for key, value in self.headers.items()
                    if not key.lower().startswith("x-airlock-")
                }
                return fixture.respond(
                    Request(self.headers["x-airlock-url"], self.headers["x-airlock-method"], headers)
                )

            def do_POST(self) -> None:
                try:
                    response = self.build_response()
                except (AssertionError, LookupError, OSError, TypeError, ValueError) as exc:
                    fixture.failures.append(f"Fixture failed: {exc}")
                    response = Response(str(exc), 500)
                encoded = b"" if response.body is None else json.dumps(response.body).encode()
                self.send_response(response.status)
                if response.error:
                    self.send_header("x-airlock-error", response.error)
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
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
        ):
            self.env.pop(name, None)
        return server, thread
