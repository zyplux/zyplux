from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from release_fixture import ContainerPublication, ReleaseFixture

if TYPE_CHECKING:
    from collections.abc import Iterator

    from cli_fixture import Command


@pytest.fixture
def release(tmp_path: Path) -> Iterator[ReleaseFixture]:
    fixture = ReleaseFixture(tmp_path)
    server, thread = fixture.start()
    fixture.seed()
    try:
        yield fixture
        assert not fixture.failures, "\n".join(fixture.failures)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture
def container(release: ReleaseFixture) -> ContainerPublication:
    publication = ContainerPublication(release.container())

    def push(call: Command) -> str:
        publication.builds += 1
        digest = publication.digest

        Path(call.argv[call.argv.index("--digestfile") + 1]).write_text(
            digest if digest is not None else f"sha256:{str(publication.builds) * 64}\n", encoding="utf-8"
        )
        release.published(ghcr=publication.is_published)
        return ""

    def upload(call: Command) -> str:

        publication.manifest = Path(call.argv[3]).read_text(encoding="utf-8")
        return ""

    release.on("podman push --digestfile", push)
    release.on("gh release upload", upload)
    return publication
