"""Meta-test: story tests assert behavior through fixtures only, zero imports; §8.2/§8.3.2-3 white-box and §7.3.2/§8.3.1 container are pinned exceptions. The act/assert fixtures, in turn, reach totchef only through its public CLI — never its internals."""

import ast

from project_paths import STORIES_DIR

CONTAINER_BOUND = {"test_8_observing_a_run.py"}  # §8.2/§8.3.2-3: rendering/timing white-box (the ownership stories are fixture-driven, zero-import)

# The arrange layer owns the sanctioned system-boundary doubles (bash, network, host),
# so it imports those production modules to patch them; the act and assert layers must
# drive totchef the way an operator does — through nothing but its public CLI.
PUBLIC_ONLY_FIXTURES = ("act_fixtures.py", "assert_fixtures.py")
PUBLIC_CLI_IMPORT = "totchef.cli"  # the one production handle: `from totchef.cli import app`


def _import_bearing_story_tests() -> set[str]:
    bearing = set()
    for path in STORIES_DIR.glob("test_*.py"):
        tree = ast.parse(path.read_text())
        if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)):
            bearing.add(path.name)
    return bearing


def _totchef_imports(source: str) -> list[str]:
    """Every module path a source file pulls from totchef — `from totchef.x import y` and `import totchef.x` alike."""
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "totchef":
            modules.append(node.module or "")
        elif isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names if alias.name.split(".")[0] == "totchef"]
    return modules


def test_story_tests_use_fixtures_only():
    bearing = _import_bearing_story_tests()
    unexpected = bearing - CONTAINER_BOUND
    resolved = CONTAINER_BOUND - bearing
    assert bearing == CONTAINER_BOUND, (
        f"story tests must reach production code only through fixtures (zero imports).\n"
        f"  unexpected import-bearing files: {sorted(unexpected)}\n"
        f"  exceptions now import-free (drop from CONTAINER_BOUND): {sorted(resolved)}"
    )


def test_act_and_assert_fixtures_touch_only_the_public_cli():
    for name in PUBLIC_ONLY_FIXTURES:
        modules = _totchef_imports((STORIES_DIR / name).read_text())
        leaked = sorted(module for module in modules if module != PUBLIC_CLI_IMPORT)
        assert not leaked, (
            f"{name} reaches totchef internals {leaked}; the act/assert layers must operate totchef "
            f"only through its public CLI (`from {PUBLIC_CLI_IMPORT} import app`)."
        )
