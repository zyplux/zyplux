from __future__ import annotations

import ast


def split_code_and_docstrings(source: str) -> tuple[str, str]:
    """Split a Python source string into pure code and its docstrings, via AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, ""

    docstrings: list[str] = []
    spans: list[tuple[int, int, int, int]] = []
    for node in ast.walk(tree):
        docstring_owner = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        if isinstance(node, docstring_owner) and node.body and isinstance(node.body[0], ast.Expr):
            expr = node.body[0]
            if (
                isinstance(expr.value, ast.Constant)
                and isinstance(expr.value.value, str)
                and expr.end_lineno is not None
                and expr.end_col_offset is not None
            ):
                spans.append((expr.lineno, expr.col_offset, expr.end_lineno, expr.end_col_offset))
                docstrings.append(expr.value.value)

    lines = source.splitlines(keepends=True)
    for start_line, start_col, end_line, end_col in sorted(spans, reverse=True):
        if start_line == end_line:
            line_bytes = lines[start_line - 1].encode("utf-8")
            lines[start_line - 1] = (line_bytes[:start_col] + line_bytes[end_col:]).decode("utf-8")
        else:
            lines[start_line - 1] = lines[start_line - 1].encode("utf-8")[:start_col].decode("utf-8") + "\n"
            for idx in range(start_line, end_line - 1):
                lines[idx] = ""
            lines[end_line - 1] = lines[end_line - 1].encode("utf-8")[end_col:].decode("utf-8")

    return "".join(lines), "\n".join(docstrings)
