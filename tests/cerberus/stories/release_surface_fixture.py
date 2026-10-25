from __future__ import annotations

import os
from functools import partial
from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx
from cerberus import config
from cerberus.context import local_context
from cerberus.model import Repo
from cerberus.release_surface import check_release_surface
from cli_fixture import Request

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def check_surface(fixture: ReleaseFixture, base: str | None = None) -> list[dict[str, str]]:
    client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        reply = fixture.respond(Request(str(request.url), request.method, dict(request.headers)))
        if reply.error:
            raise httpx.ReadTimeout(reply.error, request=request)
        return httpx.Response(reply.status, json=reply.body, request=request)

    with (
        patch.dict(os.environ, {**fixture.env, "AIRLOCK_TEST_ENDPOINT": fixture.endpoint}, clear=True),
        patch(
            "airlock.registries.httpx.Client",
            side_effect=partial(client, transport=httpx.MockTransport(respond)),
        ),
    ):
        return [
            {"message": finding.message, "status": finding.status.name.lower()}
            for finding in check_release_surface(Repo("demo"), local_context(config.load(), fixture.root), base=base)
        ]
