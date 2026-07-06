from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import networkx as nx

_TOKEN = re.compile(r"[a-z0-9]+")

_EXACT_SCORE = 100.0
_PREFIX_SCORE = 20.0
_SUBSTRING_SCORE = 5.0
_TERM_EXACT_SCORE = 10.0
_TERM_SUBSTRING_SCORE = 1.0

_DEFAULT_SEED_LIMIT = 3


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _haystack(data: dict[str, Any]) -> tuple[str, str]:
    label_tokens = " ".join(_tokens(str(data.get("label", ""))))
    is_file = data.get("kind") == "file"
    path_tokens = " ".join(_tokens(str(data.get("path", "")))) if is_file else ""
    return label_tokens, path_tokens


def score_nodes(graph: nx.Graph[str], text: str) -> list[tuple[float, str]]:
    """Score every node against free text: substring/token match, no IDF or trigram indexing.

    Deliberately simpler than graphify's scorer — this runs once per CLI
    invocation rather than behind a query server, so a plain O(n) scan is fine
    regardless of graph size.
    """
    terms = _tokens(text)
    if not terms:
        return []
    joined = " ".join(terms)
    scored: list[tuple[float, str]] = []
    for node_id in graph.nodes:
        label_tokens, path_tokens = _haystack(graph.nodes[node_id])
        combined = f"{label_tokens} {path_tokens}"
        score = 0.0
        if joined in {label_tokens, path_tokens, node_id.lower()}:
            score += _EXACT_SCORE
        elif label_tokens.startswith(joined) or path_tokens.startswith(joined):
            score += _PREFIX_SCORE
        elif joined in combined:
            score += _SUBSTRING_SCORE
        for term in terms:
            if term in {label_tokens, path_tokens}:
                score += _TERM_EXACT_SCORE
            elif term in combined:
                score += _TERM_SUBSTRING_SCORE
        if score > 0:
            scored.append((score, node_id))
    scored.sort(key=lambda item: (-item[0], len(str(graph.nodes[item[1]].get("label", item[1]))), item[1]))
    return scored


def best_match(graph: nx.Graph[str], text: str) -> str | None:
    if text in graph:
        return text
    scored = score_nodes(graph, text)
    return scored[0][1] if scored else None


def pick_seeds(graph: nx.Graph[str], text: str, limit: int = _DEFAULT_SEED_LIMIT) -> list[str]:
    if text in graph:
        return [text]
    return [node_id for _, node_id in score_nodes(graph, text)[:limit]]
