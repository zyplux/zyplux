from __future__ import annotations

import io
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from cli_fixture import Command

if TYPE_CHECKING:
    from release_fixture import ReleaseFixture


def write_tar(
    archive: Path, files: dict[str, bytes], *, mtime: int = 0, mode: int = 0o644, compresslevel: int = 9
) -> None:
    with tarfile.open(archive, "w:gz", compresslevel=compresslevel) as package:
        for name, contents in files.items():
            member = tarfile.TarInfo(name)
            member.size, member.mtime, member.mode = len(contents), mtime, mode
            package.addfile(member, io.BytesIO(contents))


def write_wheel(
    archive: Path,
    files: dict[str, bytes],
    *,
    timestamp: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0),
    compression: int = zipfile.ZIP_STORED,
) -> None:
    with zipfile.ZipFile(archive, "w", compression=compression) as wheel:
        for name, contents in files.items():
            member = zipfile.ZipInfo(name, date_time=timestamp)
            wheel.writestr(member, contents, compress_type=compression)


def stage_packagers(release: ReleaseFixture) -> None:
    def pack(call: Command) -> str:
        directory = Path(call.cwd)
        contents = {
            f"package/{path.relative_to(directory)}": path.read_bytes()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        }
        write_tar(Path(call.argv[call.argv.index("--out") + 1]), contents)
        return ""

    def build(call: Command) -> str:
        directory = Path(call.argv[call.argv.index("--out-dir") + 1])
        source = Path(call.cwd)
        contents = {
            str(path.relative_to(source)): path.read_bytes() for path in sorted(source.rglob("*")) if path.is_file()
        }
        project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        requirements = [
            *project.get("dependencies", []),
            *(requirement for group in project.get("optional-dependencies", {}).values() for requirement in group),
        ]
        metadata = f"Metadata-Version: 2.4\nName: {project['name']}\nVersion: {project['version']}\n" + "".join(
            f"Requires-Dist: {requirement}\n" for requirement in requirements
        )
        write_wheel(directory / "cerberus.whl", {**contents, "package.dist-info/METADATA": metadata.encode()})
        write_tar(directory / "cerberus.tar.gz", {f"cerberus/{path}": contents for path, contents in contents.items()})
        return ""

    release.on("pnpm pack", pack)
    release.on("uv build", build)


def hash_archives(release: ReleaseFixture, archives: list[Path]) -> str:
    release.use_package()
    if archives[0].suffix != ".tgz":
        release.configure("npm", 'kind = "pypi"\nlabel = "zyplux-util"')

    def build(call: Command) -> str:
        if "--out" in call.argv:
            shutil.copyfile(archives[0], call.argv[call.argv.index("--out") + 1])
        else:
            directory = Path(call.argv[call.argv.index("--out-dir") + 1])
            for archive in archives:
                destination = directory / archive.name
                shutil.copyfile(archive, destination)
                if archive.suffix == ".whl":
                    with zipfile.ZipFile(destination, "a") as wheel:
                        if not any(name.endswith(".dist-info/METADATA") for name in wheel.namelist()):
                            wheel.writestr(
                                zipfile.ZipInfo("package.dist-info/METADATA"),
                                b"Metadata-Version: 2.4\nName: zyplux-util\nVersion: 1.2.3\n",
                            )
        return ""

    release.on("pnpm pack", build)
    release.on("uv build", build)
    release.run("prepare")
    return tomllib.loads(release.read("airlock-targets.toml"))["util"]["content_hash"]


def stage_git(release: ReleaseFixture) -> None:
    assert release.run_real(Command("git", ["init", "--quiet"], str(release.root))).exit_code == 0
    release.on("git ls-files", release.run_real)
