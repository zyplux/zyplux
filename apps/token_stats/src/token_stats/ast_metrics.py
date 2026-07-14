from __future__ import annotations

import ast
import io
import tokenize


def count_compiler_tokens(pure_code: str) -> int:
    """Count semantic native Python compiler tokens: names, operators, numbers, strings."""
    semantic_types = (tokenize.NAME, tokenize.OP, tokenize.NUMBER, tokenize.STRING)
    count = 0
    try:
        for tok in tokenize.generate_tokens(io.StringIO(pure_code).readline):
            if tok.type in semantic_types:
                count += 1
    except tokenize.TokenError, SyntaxError, IndentationError:
        pass
    return count


def count_ast_nodes(pure_code: str) -> int:
    """Count every node in the parsed Abstract Syntax Tree."""
    try:
        return len(list(ast.walk(ast.parse(pure_code))))
    except SyntaxError:
        return 0
