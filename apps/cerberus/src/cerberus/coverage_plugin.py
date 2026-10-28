from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from airlock.proc import find_root
from coverage import CoveragePlugin

from cerberus import config as cerberus_config
from cerberus import context

if TYPE_CHECKING:
    from coverage.plugin_support import Plugins
    from coverage.types import TConfigurable

PLUGIN = "cerberus.coverage_plugin"
__all__ = ["coverage_init"]


class SourceCoverage(CoveragePlugin):
    @override
    def configure(self, config: TConfigurable) -> None:
        root = find_root(Path.cwd())
        ctx = context.local_context(cerberus_config.load(repo_root=root), root)
        scope = ctx.config.source
        paths = ctx.paths(ctx.repos()[0])
        eligible = [root / path for path in paths if path.endswith(".py") and scope.classify(path).requires_tests]
        parents = {path.parent for path in eligible}
        directories = sorted(
            parent for parent in parents if not any(ancestor in parents for ancestor in parent.parents)
        )
        config.set_option("run:source", [str(path) for path in directories] or [str(root)])
        config.set_option("run:source_dirs", [])
        config.set_option("run:source_pkgs", [])
        config.set_option("run:include", [])
        config.set_option(
            "run:omit",
            [str(root / path) for path in paths if path.endswith(".py") and not scope.classify(path).requires_tests]
            if eligible
            else ["*"],
        )
        config.set_option("report:include_namespace_packages", value=True)
        config.set_option("report:include", [str(path) for path in eligible])
        # Children inherit resolved selections; their startup can precede editable package setup.
        plugins = config.get_option("run:plugins")
        if isinstance(plugins, list):
            config.set_option("run:plugins", [plugin for plugin in plugins if plugin != PLUGIN])


def coverage_init(reg: Plugins, _options: dict[str, str]) -> None:
    reg.add_configurer(SourceCoverage())
