from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from ctypes import PYFUNCTYPE, c_char_p, c_void_p, py_object, pythonapi
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

from airlock.proc import CommandError, find_root, run
from tree_sitter import Language, Parser

from cerberus import load_source_scope
from cerberus.graph.parse import parse_python, parse_typescript

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tiktoken import Encoding
    from tree_sitter import Node, Tree

BPE_ENCODING = "o200k_base"

REPORT_NAME = "line_and_token_stats.md"

# Generated bulk, matched by file name: lock files, and the reports earlier runs left in the tree.
EXCLUDED_FILES = ("*.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", REPORT_NAME)


class GitError(RuntimeError):
    """Raised when git cannot say which files are tracked."""


# Keyed by suffix, or by file name for suffixless files like `Dockerfile`.
GRAMMARS = {
    ".cts": (".ts", "tree_sitter_typescript.language_typescript"),
    ".mts": (".ts", "tree_sitter_typescript.language_typescript"),
    ".ts": (".ts", "tree_sitter_typescript.language_typescript"),
    ".tsx": (".tsx", "tree_sitter_typescript.language_tsx"),
    ".py": ("Python", "tree_sitter_python.language"),
    ".css": ("CSS", "tree_sitter_css.language"),
    ".html": ("HTML", "tree_sitter_html.language"),
    ".json": ("JSON", "tree_sitter_json.language"),
    ".jsonc": ("JSON", "tree_sitter_json.language"),
    ".yaml": ("YAML", "tree_sitter_yaml.language"),
    ".yml": ("YAML", "tree_sitter_yaml.language"),
    ".toml": ("TOML", "tree_sitter_toml.language"),
    ".nix": ("Nix", "tree_sitter_nix.language"),
    ".sh": ("Shell", "tree_sitter_bash.language"),
    ".bash": ("Shell", "tree_sitter_bash.language"),
    ".sql": ("SQL", "tree_sitter_sql.language"),
    "Dockerfile": ("Dockerfile", "tree_sitter_dockerfile.language"),
    ".Dockerfile": ("Dockerfile", "tree_sitter_dockerfile.language"),
}

# Prose throughout — even fenced code counts as prose, so no grammar is needed: only blank lines
# and whitespace tokens split out, and these rows skip the lexical and CST table.
PROSE_LANGUAGES: dict[str, str] = {".md": "Markdown"}

# Containers none of whose leaves own their content bytes — the walk stops at them, so the whole
# span counts as one leaf instead of falling into no bucket. Scoped per language because a type name
# recurs with different shapes: `string` is such a container in TOML but holds interpolation
# children in Python and TypeScript that must keep counting as code.
ATOMIC_TYPES: dict[str, frozenset[str]] = {
    "TOML": frozenset({"quoted_key", "string"}),
    "Dockerfile": frozenset({"image_tag", "json_string", "mount_param_param", "param"}),
}

# Rows restating several others as one language, listed beside the rows they gather rather than replacing them.
ROLLUPS: dict[str, tuple[str, ...]] = {"TypeScript": (".ts", ".tsx")}

# Content written for humans inside code: comments. Markdown never gets here — `measure_prose`
# counts whole files as prose.
PROSE_TYPES = frozenset({"block_comment", "comment", "line_comment"})
STRING_TYPES = frozenset({
    "attribute_value",
    "block_scalar",
    "raw_text",
    "string_value",
    "text",
    "double_quote_scalar",
    "escape_sequence",
    "heredoc_content",
    "path",
    "path_fragment",
    "raw_string",
    "regex_pattern",
    "shell_fragment",
    "string",
    "string_content",
    "string_end",
    "single_quote_scalar",
    "string_fragment",
    "string_scalar",
    "string_start",
    "template_string",
    "json_string",
    "unquoted_string",
})
IDENTIFIER_TYPES = frozenset({
    "attribute_name",
    "bare_key",
    "class_name",
    "feature_name",
    "function_name",
    "id_name",
    "identifier",
    "image_alias",
    "image_name",
    "property_name",
    "quoted_key",
    "tag_name",
    "property_identifier",
    "shorthand_property_identifier",
    "shorthand_property_identifier_pattern",
    "statement_identifier",
    "type_identifier",
    "variable",
    "variable_name",
    "word",
})

# Named leaves that are still punctuation, markers or keywords — without this they would fall
# through to the literal bucket. SQL spells every keyword as its own `keyword_*` type, matched by
# prefix in `classify_leaf`.
SYNTAX_TYPES = frozenset({
    "dollar_escape",
    "ellipses",
    "image_tag",
    "line_continuation",
    "mount_param_param",
    "op_other",
    "param",
    "test_operator",
})

BRANCH_TYPES = frozenset({
    "case_clause",
    "catch_clause",
    "conditional_expression",
    "do_statement",
    "elif_clause",
    "except_clause",
    "for_in_statement",
    "for_statement",
    "if_statement",
    "switch_case",
    "ternary_expression",
    "while_statement",
})
BRANCH_OPERATORS = frozenset({"&&", "??", "and", "or", "||"})
BLANK_BYTES = frozenset(b" \t\r\n\f\v")
BINARY_SNIFF_BYTES = 8192

# A table is a run of column groups; a group is its parts plus the total that closes it, if it has one.
# Parts are laid out lightest-first from the totals actually measured, so a table's column order tracks
# what the reported directory holds rather than a guess made here.
Column = tuple[str, str]
ColumnGroup = tuple[tuple[Column, ...], Column | None]

# Columns standing for several others gathered together, counted once per file alongside their parts.
SUMMED_KEYS: dict[str, tuple[str, ...]] = {
    "lex_code": ("lex_identifiers", "lex_literals", "lex_strings", "lex_syntax"),
    "bpe_code": ("bpe_identifiers", "bpe_literals", "bpe_strings", "bpe_syntax"),
}

# Columns shown as a percentage, each against the base named here: content categories read against
# the spelled total, so blanks and whitespace don't dilute them.
SHARE_BASES: dict[str, str] = {
    "branches": "spelled_lines",
    "code": "spelled_lines",
    "prose": "spelled_lines",
    "lex_code": "lex_total",
    "lex_identifiers": "lex_total",
    "lex_literals": "lex_total",
    "lex_prose": "lex_total",
    "lex_strings": "lex_total",
    "lex_syntax": "lex_total",
    "bpe_code": "bpe_spelled",
    "bpe_identifiers": "bpe_spelled",
    "bpe_literals": "bpe_spelled",
    "bpe_prose": "bpe_spelled",
    "bpe_strings": "bpe_spelled",
    "bpe_syntax": "bpe_spelled",
}

CENSUS_GROUPS: tuple[ColumnGroup, ...] = (
    (
        (
            ("Files", "files"),
            ("Prose", "prose"),
            ("Branch", "branches"),
            ("Code", "code"),
        ),
        ("Total", "spelled_lines"),
    ),
)
TOKEN_GROUPS: tuple[ColumnGroup, ...] = (
    (
        (
            ("Prose", "lex_prose"),
            ("Literal", "lex_literals"),
            ("String", "lex_strings"),
            ("Identifier", "lex_identifiers"),
            ("Syntax", "lex_syntax"),
            ("Code", "lex_code"),
        ),
        ("Total", "lex_total"),
    ),
    ((("CST", "cst_nodes"), ("CST named", "cst_named_nodes")), None),
)
BPE_GROUPS: tuple[ColumnGroup, ...] = (
    (
        (
            ("Literal", "bpe_literals"),
            ("Prose", "bpe_prose"),
            ("String", "bpe_strings"),
            ("Identifier", "bpe_identifiers"),
            ("Syntax", "bpe_syntax"),
            ("Code", "bpe_code"),
        ),
        ("Total", "bpe_spelled"),
    ),
)
PARSED_KEYS = tuple(
    key
    for parts, total in (*CENSUS_GROUPS, *TOKEN_GROUPS, *BPE_GROUPS)
    for _, key in (*parts, *((total,) if total else ()))
)
UNKNOWN_CELL = "—"


@cache
def load_language(grammar_key: str) -> Language:
    module, factory = GRAMMARS[grammar_key][1].rsplit(".", 1)
    grammar: object = getattr(import_module(module), factory)()
    if isinstance(grammar, int):
        # tree-sitter-dockerfile still exposes the pre-0.25 pointer ABI; Language now expects the
        # PyCapsule emitted by current grammar bindings.
        capsule_new = PYFUNCTYPE(py_object, c_void_p, c_char_p, c_void_p)(("PyCapsule_New", pythonapi))
        grammar = capsule_new(c_void_p(grammar), b"tree_sitter.Language", None)
    return Language(grammar)


@cache
def get_parser(grammar_key: str) -> Parser:
    return Parser(load_language(grammar_key))


def parse_source(source: bytes, grammar_key: str) -> Tree:
    if grammar_key in {".cts", ".mts", ".ts", ".tsx"}:
        return parse_typescript(grammar_key, source.decode("utf-8", errors="replace"))
    if grammar_key == ".py":
        return parse_python(source.decode("utf-8", errors="replace"))
    return get_parser(grammar_key).parse(source)


@cache
def load_encoding() -> Encoding:
    return import_module("tiktoken").get_encoding(BPE_ENCODING)


def walk_nodes(node: Node, atomic: frozenset[str]) -> Iterator[Node]:
    yield node
    if node.type in atomic:
        return
    for child in node.children:
        yield from walk_nodes(child, atomic)


def classify_leaf(node: Node) -> str:
    if node.type in PROSE_TYPES:
        return "lex_prose"
    if node.type in STRING_TYPES:
        return "lex_strings"
    if node.type in IDENTIFIER_TYPES:
        return "lex_identifiers"
    if node.type in SYNTAX_TYPES or node.type.startswith("keyword_"):
        return "lex_syntax"
    return "lex_literals" if node.is_named else "lex_syntax"


def is_branch(node: Node) -> bool:
    if node.type in BRANCH_TYPES:
        return True
    operator = node.child_by_field_name("operator")
    return operator is not None and operator.type in BRANCH_OPERATORS


def count_lines(source: bytes, nodes: list[Node]) -> Counter[str]:
    """Sort every line into blank, prose-only or code, so the three always sum to the line count.

    Classifying by the bytes a line holds rather than by the nodes covering it keeps continuation
    lines of a multi-line scalar or template as code, where a node-coverage test loses them.
    """
    in_prose = bytearray(len(source))
    for node in nodes:
        if node.type in PROSE_TYPES:
            in_prose[node.start_byte : node.end_byte] = b"\1" * (node.end_byte - node.start_byte)

    lines = source.split(b"\n")
    if lines and not lines[-1]:
        lines.pop()

    counts: Counter[str] = Counter({"lines": 0})
    offset = 0
    for line in lines:
        spelled = [step for step, byte in enumerate(line) if byte not in BLANK_BYTES]
        counts["lines"] += 1
        if not spelled:
            counts["blank"] += 1
        elif all(in_prose[offset + step] for step in spelled):
            counts["prose"] += 1
        else:
            counts["code"] += 1
        offset += len(line) + 1
    counts["spelled_lines"] = counts["lines"] - counts["blank"]
    return counts


def count_bpe(source: bytes, leaves: list[Node]) -> Counter[str]:
    """Attribute every BPE token to the leaf holding its first non-blank byte.

    A token that is blank throughout is indentation or a newline, which belongs to no leaf, so the
    buckets partition the file exactly. Skipping the blank prefix matters because BPE merges a leading
    space into the word after it — `␣const` starts one byte before the keyword it spells.
    """
    encoding = load_encoding()
    starts = [leaf.start_byte for leaf in leaves]
    counts: Counter[str] = Counter()
    offset = 0
    for token in encoding.encode(source.decode(errors="replace"), disallowed_special=()):
        piece = encoding.decode_single_token_bytes(token)
        spelled = next((offset + step for step, byte in enumerate(piece) if byte not in BLANK_BYTES), None)
        index = bisect_right(starts, spelled) - 1 if spelled is not None else -1
        covering = leaves[index] if index >= 0 and spelled is not None and spelled < leaves[index].end_byte else None
        counts[classify_leaf(covering).replace("lex_", "bpe_") if covering else "bpe_whitespace"] += 1
        counts["bpe"] += 1
        offset += len(piece)
    counts["bpe_spelled"] = counts["bpe"] - counts["bpe_whitespace"]
    return counts


def measure_parsed(source: bytes, grammar_key: str) -> Counter[str]:
    atomic = ATOMIC_TYPES.get(GRAMMARS[grammar_key][0], frozenset())
    nodes = list(walk_nodes(parse_source(source, grammar_key).root_node, atomic))
    leaves = [node for node in nodes if not node.children or node.type in atomic]
    counts = Counter(dict.fromkeys(PARSED_KEYS, 0))
    counts.update({
        "files": 1,
        "lex_total": len(leaves),
        "cst_nodes": len(nodes),
        "cst_named_nodes": sum(1 for node in nodes if node.is_named),
        "branches": sum(1 for node in nodes if is_branch(node)),
    })
    counts.update(Counter(classify_leaf(leaf) for leaf in leaves))
    counts.update(count_lines(source, nodes))
    counts.update(count_bpe(source, leaves))
    counts.update({name: sum(counts[key] for key in keys) for name, keys in SUMMED_KEYS.items()})
    return counts


def measure_prose(source: bytes) -> Counter[str]:
    """Count a file that is prose throughout: every non-blank line and non-whitespace token is prose."""
    encoding = load_encoding()
    text = source.decode(errors="replace")
    lines = text.splitlines()
    blank = sum(1 for line in lines if not line.strip())
    counts = Counter({
        "files": 1,
        "lines": len(lines),
        "blank": blank,
        "prose": len(lines) - blank,
        "spelled_lines": len(lines) - blank,
        "code": 0,
    })
    for token in encoding.encode(text, disallowed_special=()):
        piece = encoding.decode_single_token_bytes(token)
        is_blank = all(byte in BLANK_BYTES for byte in piece)
        counts["bpe_whitespace" if is_blank else "bpe_prose"] += 1
        counts["bpe"] += 1
    counts["bpe_code"] = 0
    counts["bpe_spelled"] = counts["bpe_prose"]
    return counts


def measure_unparsed(source: bytes) -> Counter[str]:
    encoding = load_encoding()
    text = source.decode(errors="replace")
    lines = text.splitlines()
    blank = sum(1 for line in lines if not line.strip())
    tokens = encoding.encode(text, disallowed_special=())
    whitespace = sum(
        1 for token in tokens if all(byte in BLANK_BYTES for byte in encoding.decode_single_token_bytes(token))
    )
    return Counter({
        "files": 1,
        "lines": len(lines),
        "blank": blank,
        "spelled_lines": len(lines) - blank,
        "bpe": len(tokens),
        "bpe_spelled": len(tokens) - whitespace,
    })


def find_work_tree(directory: Path) -> Path:
    try:
        return find_root(directory)
    except CommandError as exc:
        message = f"{directory} is not inside a git repository"
        raise GitError(message) from exc


def list_tracked_files(root: Path, directory: Path) -> list[Path]:
    """Read the index rather than walking the tree, so gitignored and untracked files never arrive."""
    listing = run("git", "ls-files", "--cached", "-z", cwd=root)
    paths = (root / path for path in listing.split("\0") if path)
    return [path for path in paths if path.is_relative_to(directory)]


def is_binary(source: bytes) -> bool:
    """Treat a NUL byte in the leading block as binary, the same heuristic git uses."""
    return b"\0" in source[:BINARY_SNIFF_BYTES]


def measure_files(
    paths: list[Path], production_paths: set[Path] | None
) -> tuple[dict[str, Counter[str]], dict[str, Counter[str]], list[Path]]:
    languages: dict[str, Counter[str]] = {}
    production: dict[str, Counter[str]] = {}
    binaries: list[Path] = []
    for path in paths:
        if not path.is_file():
            continue
        source = path.read_bytes()
        grammar_key = path.suffix or path.name
        if is_binary(source):
            binaries.append(path)
            continue
        if grammar_key in GRAMMARS:
            language, counts = GRAMMARS[grammar_key][0], measure_parsed(source, grammar_key)
        elif grammar_key in PROSE_LANGUAGES:
            language, counts = PROSE_LANGUAGES[grammar_key], measure_prose(source)
        else:
            language, counts = grammar_key, measure_unparsed(source)
        languages.setdefault(language, Counter()).update(counts)
        if production_paths and path in production_paths:
            production.setdefault(language, Counter()).update(counts)
    return languages, production, binaries


def build_rollups(languages: dict[str, Counter[str]]) -> dict[str, Counter[str]]:
    """Gather each rollup's parts, skipping any that only one part is present for — it would just repeat that row."""
    rollups: dict[str, Counter[str]] = {}
    for name, parts in ROLLUPS.items():
        present = [languages[part] for part in parts if part in languages]
        if len(present) > 1:
            gathered: Counter[str] = Counter()
            for counts in present:
                gathered.update(counts)
            rollups[name] = gathered
    return rollups


def format_cell(counts: Counter[str], key: str, denominator: int | None) -> str:
    """Distinguish a measured zero from a column this language has no grammar to fill.

    A share column reads against the base `SHARE_BASES` names for it, and every row divides by its
    own base rather than by the table's — which is what makes one language's mix comparable to
    another's.
    """
    if key not in counts:
        return UNKNOWN_CELL
    if denominator is None:
        return f"{counts[key]:,}"
    return f"{100 * counts[key] / denominator:.1f}%" if denominator else UNKNOWN_CELL


def arrange_columns(groups: tuple[ColumnGroup, ...], total: Counter[str]) -> list[Column]:
    def get_column_total(column: Column) -> int:
        return total[column[1]]

    return [
        column
        for parts, group_total in groups
        for column in (*sorted(parts, key=get_column_total), *((group_total,) if group_total else ()))
    ]


def format_table(
    rows: dict[str, Counter[str]], groups: tuple[ColumnGroup, ...], label: str, rollups: dict[str, Counter[str]]
) -> list[str]:
    keys = {key for parts, group_total in groups for _, key in (*parts, *((group_total,) if group_total else ()))}
    measured = {name: counts for name, counts in rows.items() if keys & counts.keys()}
    total: Counter[str] = Counter()
    for counts in measured.values():
        total.update(counts)
    shares = {key: SHARE_BASES[key] for parts, _ in groups for _, key in parts if key in SHARE_BASES}
    # A share on the total row divides by the totals of the rows that reported it, so a language with
    # no grammar to fill that column stays out of its denominator as well as out of its numerator.
    share_bases = {
        key: sum(counts[base_key] for counts in measured.values() if key in counts) for key, base_key in shares.items()
    }
    # Rollups restate rows already counted above, so they join the table after the totals are settled.
    measured |= {name: counts for name, counts in rollups.items() if keys & counts.keys()}
    columns = arrange_columns(groups, total)
    headers = [label, *(header for header, _ in columns)]
    # The heaviest row leads, ranked by the total closing the table's first group — the same number
    # that group's last column reports, so the row order and that column agree.
    first_group_width = len(groups[0][0]) + (1 if groups[0][1] else 0)
    rank_key = columns[first_group_width - 1][1]

    def get_rank_count(row: tuple[str, Counter[str]]) -> int:
        return row[1][rank_key]

    heaviest_first = sorted(measured.items(), key=get_rank_count, reverse=True)

    def format_row(name: str, counts: Counter[str], bases: dict[str, int]) -> str:
        cells = (format_cell(counts, key, bases.get(key) if key in shares else None) for _, key in columns)
        return "| " + " | ".join([name, *cells]) + " |"

    body = [
        *(
            format_row(name, counts, {key: counts[base_key] for key, base_key in shares.items()})
            for name, counts in heaviest_first
        ),
        format_row("**Total**", total, share_bases),
    ]
    return ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|", *body]


def name_scope(directory: Path, root: Path) -> str:
    """Name the measured scope by its path under the repo, falling back to the repo's own name at the root.

    A bare "." would end the report's heading in punctuation, which markdown lint rejects (MD026).
    """
    relative = directory.relative_to(root)
    return root.name if relative == Path() else str(relative)


def is_measurable(path: Path, report_path: Path) -> bool:
    """Drop what `EXCLUDED_FILES` names, plus this run's own report when `-o` renames it."""
    return path != report_path and not any(path.match(pattern) for pattern in EXCLUDED_FILES)


def write_report(directory: Path, *, title: str | None = None, out: Path | None = None) -> Path:
    directory = directory.resolve()
    report_path = (out or directory / REPORT_NAME).resolve()
    root = find_work_tree(directory)
    tracked = list_tracked_files(root, directory)
    paths = [path for path in tracked if is_measurable(path, report_path)]
    if not paths:
        message = f"no tracked files under {directory}"
        raise ValueError(message)

    source_scope = load_source_scope(root)
    production_paths = {path for path in paths if source_scope.is_production_file(path.relative_to(root).as_posix())}
    report = build_report(paths, title or name_scope(directory, root), root, production_paths)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    return report_path


LINES_LEGEND = (
    ("> `Prose` — comment-only lines (no code); or non-blank lines in .md."),
    ">",
    ("> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc."),
    ">",
    ("> `Total` — non-blank lines."),
)

TOKEN_LEGEND = (
    ("> `Lexical tokens` — the smallest pieces the language sees."),
    ">",
    ("> `Prose` — comments; a comment counts as one token however many lines it spans."),
    ">",
    ("> `Literal` — a value: `42`, `true`, `null`."),
    ">",
    ("> `String` — anything inside quotes, plus template strings, regexes, YAML scalars and HTML text."),
    ">",
    ("> `Identifier` — names for variables, functions, properties, types, CSS selectors, HTML tags."),
    ">",
    ("> `Syntax` — language punctuation and keywords: `{`, `,`, `=>` and `const`, `let` etc."),
    ">",
    ("> `Code` — everything but prose."),
    ">",
    ("> `CST` — Concrete Syntax Tree - the language syntax"),
    ">",
    ("> `CST named` — named nodes, excludes punctuation."),
)

BPE_LEGEND = (
    ("> `BPE` — Byte Pair Encoding, tiktoken `o200k_base`."),
    ">",
    ("> `Prose` — comments; or everything non-whitespace in .md."),
    ">",
    ("> `Code` — everything but prose and whitespace."),
    ">",
    ("> `Total` — tokens that aren't whitespace."),
)


def build_report(paths: list[Path], title: str, root: Path, production_paths: set[Path] | None = None) -> str:
    languages, production, binaries = measure_files(paths, production_paths)
    sections = [f"# Stats - {title}"]
    scopes = {"": languages}
    if production_paths is not None:
        scopes["Production "] = production
    for prefix, counts in scopes.items():
        if prefix:
            sections += [
                "",
                (
                    "Production scope: Cerberus source defaults, overlaid by `[source]` in the repository's "
                    "`cerberus.toml`. Includes assets and configuration under production roots; excludes test files. "
                    "Metrics use the legends above."
                ),
            ]
            if not counts:
                sections += ["", "No production source files in this scope."]
        rollups = build_rollups(counts)
        for heading, groups, legend in (
            ("Line Counts", CENSUS_GROUPS, LINES_LEGEND),
            ("Lexical Token and CST Node Counts", TOKEN_GROUPS, TOKEN_LEGEND),
            ("BPE Token Counts", BPE_GROUPS, BPE_LEGEND),
        ):
            sections += ["", f"## {prefix}{heading}", "", *format_table(counts, groups, "Language", rollups)]
            if not prefix:
                sections += ["", *legend]
    if binaries:
        sections += [
            "",
            "### Left out files",
            "",
            *(f"- `{path.relative_to(root)}` — binary" for path in sorted(binaries)),
        ]
    return "\n".join([*sections, ""])
