from __future__ import annotations

import os
from unittest.mock import patch

import httpx
from airlock.cli import main

HTTP_CLIENT = httpx.Client


def relay_request(request: httpx.Request) -> httpx.Response:
    with HTTP_CLIENT() as client:
        reply = client.post(
            f"{os.environ['AIRLOCK_TEST_ENDPOINT']}/fetch",
            headers={
                **dict(request.headers),
                "x-airlock-url": str(request.url),
                "x-airlock-method": request.method,
            },
        )
    if reply.headers.get("x-airlock-error"):
        raise httpx.ReadTimeout(reply.headers["x-airlock-error"], request=request)
    return httpx.Response(reply.status_code, content=reply.content, request=request)


def create_client(*, timeout: float, follow_redirects: bool) -> httpx.Client:
    return HTTP_CLIENT(transport=httpx.MockTransport(relay_request), timeout=timeout, follow_redirects=follow_redirects)


def skip_wait(seconds: float) -> None:
    pass


with patch("airlock.registries.httpx.Client", side_effect=create_client), patch("time.sleep", skip_wait):
    main()
