"""Shared machinery for the `cli_py_test_seam`/`lib_py_test_seam` bites.

Python packaging has no manifest-level equivalent of npm's `exports` map —
there is no declared, enforceable "this is the only importable surface" field
in `pyproject.toml`. So unlike `cli_ts_test_seam`/`lib_ts_test_seam` (which additionally
validate a manifest-declared export surface via `test_seam._check_exports_surface`),
these checks can only police *what a package's story tests actually import* —
a deliberate, honest scope reduction, not an oversight.

A package's seam is the set of dotted module paths its story tests may import
from: always its own root module (the top-level import name resolved by
`resolve_root_module`, the Python analogue of the TS root export `.`), plus —
for cli apps only — every module named on the left of `:` in a
`[project.scripts]` entry (e.g. `"cerberus.cli:app"` contributes `cerberus.cli`).
That extra allowance exists because testing a Click/Typer/argparse app
in-process (`CliRunner().invoke(app, [...])`) requires importing the exact
module the entry point lives in; without whitelisting it, every CLI-testing
story test in existence would trivially fail the seam check, which does not
match real-world convention. Libraries — packages with no `[project.scripts]`
— get no extra modules, just the root.

Story test files are found by `story_docs.PY_TEST_NAME` under a `stories/`
directory belonging to the package (`story_docs.under_package`); `conftest.py`
is deliberately never scanned. This mirrors the TS design's trust of the alias
target: the TS check verifies a story test only reaches product code through a
`#` alias and that the alias's target does not escape the package, but never
inspects what the target file itself imports. The Python equivalent of that
trusted indirection layer is a `conftest.py` fixture — a story test that takes
a fixture by parameter name has no import statement at all (pytest's normal
mechanism), and a `conftest.py` that does the internals-importing on tests'
behalf is the *sanctioned remediation path* for any package this check flags,
not a loophole to close.

Each story test file is parsed with `ast` and every `Import`/`ImportFrom`
found by a full tree walk is checked (not just top-level statements — a test
function's local import counts too). An import guarded inside an
`if TYPE_CHECKING:` block's body is exempt (but its `else:` branch is not,
since that one does execute at runtime) — a deliberate divergence from the TS
reference, whose regex-based static-import matcher does not special-case
`import type`. This codebase's own check modules universally guard their
`Context`/`Repo`/`CheckResult` imports the same way, so penalizing story tests
for that idiom would be inconsistent.

Any relative import (`level > 0`) is always outside the seam, mirroring the TS
check's blanket rule for path specifiers. Everything else is judged by whether
the imported module is "package-relative" (equal to the root module, or
prefixed with `root + "."`): non-package-relative modules (stdlib, third
party) are always fine; a package-relative module that isn't exactly a seam
module is flagged; a package-relative module that *is* exactly a seam module
has each individually-imported name checked against that module's own public
surface (`__all__`'s literal elements if declared, else every non-underscore
top-level binding). `import a.b.c` (no `from`) is checked at the module-path
level only, since it binds the whole module rather than individual names.

Known, accepted limitation (shared with the TS reference, which has the same
gap for dynamic `import()`): a bare `import pkg` followed by chasing
attributes (`pkg.internal.deep.thing`) is not traced — this works at
import-statement granularity, not dataflow.
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cerberus.bites import story_docs

if TYPE_CHECKING:
    from collections.abc import Callable

    from cerberus.context import Context
    from cerberus.model import CheckResult, Repo

_INIT_PY_SUFFIX = "/__init__.py"
_MIN_PATH_SEGMENTS = 2  # a package-relative match needs at least "<name>/<file>"


def _parse_toml(content: str | None) -> dict[str, Any]:
    if content is None:
        return {}
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _manifest_path(package: str) -> str:
    return f"{package}/pyproject.toml" if package else "pyproject.toml"


def _project_scripts(manifest: dict[str, Any]) -> dict[str, str]:
    project = manifest.get("project")
    scripts = project.get("scripts") if isinstance(project, dict) else None
    if not isinstance(scripts, dict):
        return {}
    return {name: target for name, target in scripts.items() if isinstance(target, str)}


def is_cli_app(manifest: dict[str, Any]) -> bool:
    return bool(_project_scripts(manifest))


def _script_modules(manifest: dict[str, Any]) -> frozenset[str]:
    modules = (target.split(":", 1)[0].strip() for target in _project_scripts(manifest).values())
    return frozenset(module for module in modules if module)


def _build_backend_module_name(manifest: dict[str, Any]) -> str | None:
    tool = manifest.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    backend = uv.get("build-backend") if isinstance(uv, dict) else None
    name = backend.get("module-name") if isinstance(backend, dict) else None
    return name if isinstance(name, str) and name else None


def _shallowest_init(package: str, paths: list[str], dir_name: str | None) -> tuple[str, str] | None:
    """Find the shallowest `__init__.py` under `package`, as `(parent dir name, parent dir path)`.

    When `dir_name` is given, only an `__init__.py` whose immediate parent
    directory is named `dir_name` is considered.
    """
    prefix = f"{package}/" if package else ""
    best: tuple[int, str, str] | None = None
    for path in paths:
        if not path.startswith(prefix) or not path.endswith(_INIT_PY_SUFFIX):
            continue
        parts = path[len(prefix) :].split("/")
        if len(parts) < _MIN_PATH_SEGMENTS or (dir_name is not None and parts[-2] != dir_name):
            continue
        depth = len(parts)
        if best is None or depth < best[0]:
            best = (depth, parts[-2], path[: -len(_INIT_PY_SUFFIX)])
    return (best[1], best[2]) if best else None


def _root_module_from_sources(package: str, paths: list[str]) -> str | None:
    found = _shallowest_init(package, paths, dir_name=None)
    return found[0] if found else None


def resolve_root_module(package: str, manifest: dict[str, Any], paths: list[str]) -> str | None:
    return _build_backend_module_name(manifest) or _root_module_from_sources(package, paths)


def _root_module_dir(package: str, paths: list[str], root: str) -> str | None:
    found = _shallowest_init(package, paths, dir_name=root)
    return found[1] if found else None


def _module_source_path(root: str, root_dir: str, paths: list[str], module: str) -> str | None:
    if module == root:
        init_path = f"{root_dir}{_INIT_PY_SUFFIX}"
        return init_path if init_path in paths else None

    anchor = f"{root_dir}/{module[len(root) + 1 :].replace('.', '/')}"
    flat_module = f"{anchor}.py"
    package_init = f"{anchor}{_INIT_PY_SUFFIX}"
    if flat_module in paths:
        return flat_module
    if package_init in paths:
        return package_init
    return None


def _all_literal_elements(node: ast.Assign) -> set[str] | None:
    if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "__all__"):
        return None
    if not isinstance(node.value, (ast.List, ast.Tuple)):
        return None
    return {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)}


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _bound_names(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name} if _is_public(node.name) else set()
    if isinstance(node, ast.Assign):
        return {target.id for target in node.targets if isinstance(target, ast.Name) and _is_public(target.id)}
    if isinstance(node, ast.AnnAssign):
        return {node.target.id} if isinstance(node.target, ast.Name) and _is_public(node.target.id) else set()
    if isinstance(node, ast.Import):
        return {bound for alias in node.names if _is_public(bound := alias.asname or alias.name.split(".")[0])}
    if isinstance(node, ast.ImportFrom):
        return {bound for alias in node.names if alias.name != "*" and _is_public(bound := alias.asname or alias.name)}
    return set()


def _public_names(source: str) -> set[str] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign) and (declared := _all_literal_elements(node)) is not None:
            return declared

    names: set[str] = set()
    for node in tree.body:
        names.update(_bound_names(node))
    return names


def _is_type_checking_test(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return (
        isinstance(test, ast.Attribute)
        and test.attr == "TYPE_CHECKING"
        and isinstance(test.value, ast.Name)
        and test.value.id == "typing"
    )


def _type_checking_exempt_ids(tree: ast.AST) -> set[int]:
    exempt: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            for stmt in node.body:
                exempt.update(id(n) for n in ast.walk(stmt))
    return exempt


def _story_test_files(package: str, paths: list[str]) -> list[str]:
    files = []
    for path in paths:
        parts = path.split("/")
        if len(parts) < _MIN_PATH_SEGMENTS or parts[-2] != "stories":
            continue
        if story_docs.PY_TEST_NAME.match(parts[-1]) and story_docs.under_package(path, package):
            files.append(path)
    return sorted(files)


def _is_package_relative(module: str, root: str) -> bool:
    return module == root or module.startswith(f"{root}.")


@dataclass(frozen=True)
class _PackageSeam:
    package: str
    root: str
    root_dir: str | None
    modules: frozenset[str]


def _check_import(res: CheckResult, story_file: str, node: ast.Import, pkg_seam: _PackageSeam) -> None:
    for alias in node.names:
        module = alias.name
        if _is_package_relative(module, pkg_seam.root) and module not in pkg_seam.modules:
            res.fail(f"{story_file}: story test imports outside the seam — {module!r}")


@dataclass(frozen=True)
class Seam:
    repo: Repo
    ctx: Context
    paths: list[str]

    @classmethod
    def from_paths(cls, repo: Repo, ctx: Context, paths: list[str]) -> Seam:
        return cls(repo, ctx, paths)

    def load_manifest(self, package: str) -> dict[str, Any]:
        return _parse_toml(self.ctx.file(self.repo, _manifest_path(package)))

    def check_package(self, res: CheckResult, package: str) -> None:
        manifest = self.load_manifest(package)
        root = resolve_root_module(package, manifest, self.paths)
        if root is None:
            res.error(f"{package or '.'}: could not determine the package's import root")
            return

        root_dir = _root_module_dir(package, self.paths, root)
        pkg_seam = _PackageSeam(package, root, root_dir, frozenset({root}) | _script_modules(manifest))
        for story_file in _story_test_files(package, self.paths):
            self._check_story_file(res, story_file, pkg_seam)

    def _check_story_file(self, res: CheckResult, story_file: str, pkg_seam: _PackageSeam) -> None:
        content = self.ctx.file(self.repo, story_file)
        if content is None:
            return
        try:
            tree = ast.parse(content)
        except SyntaxError:
            res.error(f"{story_file}: could not parse for import analysis")
            return

        exempt = _type_checking_exempt_ids(tree)
        for node in ast.walk(tree):
            if id(node) in exempt:
                continue
            if isinstance(node, ast.ImportFrom):
                self._check_import_from(res, story_file, node, pkg_seam)
            elif isinstance(node, ast.Import):
                _check_import(res, story_file, node, pkg_seam)

    def _check_import_from(
        self, res: CheckResult, story_file: str, node: ast.ImportFrom, pkg_seam: _PackageSeam
    ) -> None:
        if node.level > 0:
            spec = f"{'.' * node.level}{node.module or ''}"
            res.fail(f"{story_file}: story test imports outside the seam — {spec!r}")
            return

        module = node.module
        if module is None or not _is_package_relative(module, pkg_seam.root):
            return
        if module not in pkg_seam.modules:
            res.fail(f"{story_file}: story test imports outside the seam — {module!r}")
            return
        self._check_names(res, story_file, pkg_seam, module, node.names)

    def _check_names(
        self, res: CheckResult, story_file: str, pkg_seam: _PackageSeam, module: str, aliases: list[ast.alias]
    ) -> None:
        if pkg_seam.root_dir is None:
            return
        source_path = _module_source_path(pkg_seam.root, pkg_seam.root_dir, self.paths, module)
        if source_path is None:
            return
        content = self.ctx.file(self.repo, source_path)
        if content is None:
            return
        public = _public_names(content)
        if public is None:
            return

        for alias in aliases:
            if alias.name != "*" and alias.name not in public:
                res.fail(f"{story_file}: story test imports non-public name {alias.name!r} from seam module {module!r}")


@dataclass(frozen=True)
class SeamGroup:
    """One side of the cli-app/library split: how to select its packages and word its verdicts."""

    label: str
    ok_message: str
    includes: Callable[[dict[str, Any]], bool]


def _is_library(manifest: dict[str, Any]) -> bool:
    return not is_cli_app(manifest)


CLI_APPS = SeamGroup(
    "cli apps",
    "every cli app's story tests import only the root module or their cli entry module",
    is_cli_app,
)
LIBRARIES = SeamGroup(
    "libraries",
    "every library's story tests import only their root module",
    _is_library,
)


def run_seam_check(repo: Repo, ctx: Context, res: CheckResult, group: SeamGroup) -> None:
    paths = ctx.paths(repo)
    packages = story_docs.PY.package_dirs(repo, ctx, paths)
    if not packages:
        res.skip("no Python packages")
        return

    seam = Seam.from_paths(repo, ctx, paths)
    members = [package for package in packages if group.includes(seam.load_manifest(package))]
    if not members:
        res.skip(f"no {group.label}")
        return

    for package in sorted(members):
        seam.check_package(res, package)

    if not res.problems:
        res.ok(group.ok_message)
