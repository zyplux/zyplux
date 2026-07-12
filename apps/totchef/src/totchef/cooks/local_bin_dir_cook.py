(
    """VersionedCook for [local_bin_dir] — auto-discovers every PATH-installable script (the same """
    """`__version__`/`--version`/`--help` contract a [local_bin] entry requires) across one or more local """
    """directories, and installs each into ~/.local/bin, keyed and version-diffed by its own filename stem. """
    """Point this at a scripts folder under active development — a new conforming script lands on PATH on """
    """the next `up` with no recipe edit; one that stops conforming, or disappears from the folder, simply """
    """drops out of the report (its previously-installed binary is left alone, never removed)."""
)

from pathlib import Path
from typing import TYPE_CHECKING, override

from loguru import logger
from pydantic import Field

from totchef import harness
from totchef.cook_base import EntrySpec, SyncOutcome, VersionedCook
from totchef.cooks.bin_cook_base import EXECUTABLE_MODE, find_contract_problems, find_embedded_version

if TYPE_CHECKING:
    from totchef.recipe_types import RecipeConfig

LOCAL_BIN_DIR = "~/.local/bin"


class LocalBinDirConfig(EntrySpec):
    dirs: list[str] = Field(default_factory=list)


def resolve_dir(raw: str) -> Path:
    (
        """A configured dir: `~`/absolute expands directly; otherwise resolves relative to totchef_files/ — """
        """the same convention a bundled [local_bin] `source` follows."""
    )
    expanded = Path(raw).expanduser()
    return expanded if expanded.is_absolute() else harness.files_dir() / raw


def discover_scripts(dirs: list[str]) -> dict[str, Path]:
    (
        """Every qualifying script across the configured dirs, keyed by filename stem. A missing dir, or a """
        """script failing the bin contract, is logged and skipped — never a hard failure for the whole cook."""
    )
    scripts: dict[str, Path] = {}
    for raw in dirs:
        directory = resolve_dir(raw)
        if not directory.is_dir():
            logger.warning("[local_bin_dir] {directory} does not exist — skipping", directory=directory)
            continue
        for path in sorted(directory.glob("*.py")):
            if path.stem.startswith("_"):
                continue
            if problems := find_contract_problems(path):
                logger.warning("[local_bin_dir] {path} skipped: {problems}", path=path, problems="; ".join(problems))
                continue
            scripts[path.stem] = path
    return scripts


def target_path(name: str) -> Path:
    return Path(LOCAL_BIN_DIR).expanduser() / name


class LocalBinDirCook(VersionedCook):
    entry_model = LocalBinDirConfig

    def __init__(self, section: RecipeConfig) -> None:
        super().__init__(section)
        config = LocalBinDirConfig.model_validate(section)
        self.dirs = config.dirs
        self.hooks = (config.pre_hook, config.post_hook)

    def _scripts(self) -> dict[str, Path]:
        return discover_scripts(self.dirs)

    @override
    def list_requested(self) -> list[str]:
        return sorted(self._scripts())

    @override
    def get_hooks(self) -> tuple[str | None, str | None]:
        return self.hooks

    @override
    def list_installed(self) -> dict[str, str]:
        installed: dict[str, str] = {}
        for name in self._scripts():
            target = target_path(name)
            if target.is_file():
                version = find_embedded_version(target.read_text(encoding="utf-8", errors="replace"))
                installed[name] = version or "unversioned"
        return installed

    @override
    def find_latest(self, names: list[str]) -> dict[str, str | None]:
        scripts = self._scripts()
        return {
            name: find_embedded_version(scripts[name].read_text(encoding="utf-8", errors="replace"))
            for name in names
            if name in scripts
        }

    @override
    def sync(self, to_install: list[str], to_upgrade: list[str]) -> SyncOutcome:
        scripts = self._scripts()
        changed: list[str] = []
        for name in to_install + to_upgrade:
            source = scripts.get(name)
            if source is None:
                continue
            if harness.write_if_changed(target_path(name), source.read_bytes(), EXECUTABLE_MODE, note=name):
                changed.append(name)
        return SyncOutcome("ok", f"installed/updated: {', '.join(changed)}" if changed else "")
