"""Repo hygiene: every docstring — module, class, function, method — stays one line."""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNED_DIRS = (REPO_ROOT / "src", REPO_ROOT / "tests")

type Documentable = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def is_multiline_docstring(node: Documentable) -> bool:
    docstring = ast.get_docstring(node, clean=False)
    return bool(docstring and "\n" in docstring.strip())


def find_offenders(node_types: tuple[type[Documentable], ...]) -> list[str]:
    offenders: list[str] = []
    for directory in SCANNED_DIRS:
        for path in sorted(directory.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, node_types) and is_multiline_docstring(node):
                    name = getattr(node, "name", path.stem)
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{getattr(node, 'lineno', 1)} {name}")
    return offenders


def test_function_docstrings_are_single_line():
    offenders = find_offenders(FUNCTION_NODES)
    assert not offenders, "condense these to one line:\n" + "\n".join(offenders)


def test_class_docstrings_are_single_line():
    offenders = find_offenders((ast.ClassDef,))
    assert not offenders, "condense these to one line:\n" + "\n".join(offenders)


def test_module_docstrings_are_single_line():
    offenders = find_offenders((ast.Module,))
    assert not offenders, "condense these to one line:\n" + "\n".join(offenders)
