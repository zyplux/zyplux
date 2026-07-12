from __future__ import annotations

from functools import cache

import tiktoken

TIKTOKEN_ENCODINGS = {
    "cl100k": "cl100k_base",
    "o200k": "o200k_base",
    "gpt2": "gpt2",
}


@cache
def load_tiktoken_encoding(encoding_key: str) -> tiktoken.Encoding:
    return tiktoken.get_encoding(TIKTOKEN_ENCODINGS[encoding_key])


def count_tiktoken_tokens(encoding_key: str, text: str) -> int:
    return len(load_tiktoken_encoding(encoding_key).encode(text, disallowed_special=()))
