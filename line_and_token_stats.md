# Stats - zyplux

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 232 | 10.6% | 0.7% | 99.3% | 28,184 |
| .ts | 190 | 9.2% | 0.1% | 99.9% | 11,181 |
| JSON | 40 | 0.0% | 0.0% | 100.0% | 7,038 |
| Markdown | 158 | — | 100.0% | 0.0% | 4,639 |
| TOML | 14 | 0.0% | 5.1% | 94.9% | 868 |
| YAML | 8 | 0.0% | 1.4% | 98.6% | 419 |
| just | 1 | — | — | — | 278 |
| justfile | 1 | — | — | — | 92 |
| .just | 1 | — | — | — | 59 |
| Containerfile | 1 | — | — | — | 43 |
| .gitignore | 1 | — | — | — | 31 |
| .service | 2 | — | — | — | 27 |
| Shell | 1 | 12.5% | 4.2% | 95.8% | 24 |
| LICENSE | 1 | — | — | — | 17 |
| .containerignore | 1 | — | — | — | 9 |
| CODEOWNERS | 1 | — | — | — | 7 |
| .prettierignore | 1 | — | — | — | 3 |
| .svg | 1 | — | — | — | 3 |
| .nvmrc | 1 | — | — | — | 1 |
| .python-version | 1 | — | — | — | 1 |
| **Total** | 657 | 8.4% | 9.3% | 90.7% | 52,924 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 19.8% | 28.5% | 49.4% | 99.8% | 237,936 | 247,399 | 365,346 |
| .ts | 0.0% | 1.2% | 6.8% | 21.7% | 70.3% | 100.0% | 96,660 | 74,913 | 143,420 |
| JSON | 0.0% | 2.5% | 28.4% | 0.0% | 69.1% | 100.0% | 49,284 | 32,333 | 66,385 |
| TOML | 2.3% | 1.7% | 21.8% | 23.8% | 50.3% | 97.7% | 2,569 | 2,025 | 3,318 |
| YAML | 0.5% | 1.8% | 51.9% | 0.0% | 45.8% | 99.5% | 1,121 | 2,659 | 3,172 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.7% | 23.1% | 57.1% | 99.9% | 387,740 | 359,517 | 581,899 |

> `Lexical tokens` — the smallest pieces the language sees.
>
> `Prose` — comments; a comment counts as one token however many lines it spans.
>
> `Literal` — a value: `42`, `true`, `null`.
>
> `String` — anything inside quotes, plus template strings, regexes, YAML scalars and HTML text.
>
> `Identifier` — names for variables, functions, properties, types, CSS selectors, HTML tags.
>
> `Syntax` — language punctuation and keywords: `{`, `,`, `=>` and `const`, `let` etc.
>
> `Code` — everything but prose.
>
> `CST` — Concrete Syntax Tree - the language syntax
>
> `CST named` — named nodes, excludes punctuation.

## BPE Token Counts

| Language | Literal | Prose | Identifier | Syntax | String | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.7% | 34.1% | 30.8% | 31.8% | 98.3% | 305,421 |
| .ts | 1.0% | 0.2% | 24.7% | 42.3% | 31.8% | 99.8% | 114,765 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 81,132 |
| JSON | 1.7% | 0.0% | 0.0% | 30.9% | 67.4% | 100.0% | 73,491 |
| TOML | 0.5% | 12.9% | 12.5% | 10.6% | 63.6% | 87.1% | 8,760 |
| YAML | 0.8% | 4.0% | 0.0% | 18.2% | 77.0% | 96.0% | 2,695 |
| just | — | — | — | — | — | — | 2,541 |
| justfile | — | — | — | — | — | — | 810 |
| Containerfile | — | — | — | — | — | — | 724 |
| .just | — | — | — | — | — | — | 525 |
| Shell | 5.4% | 1.7% | 49.0% | 19.4% | 24.5% | 98.3% | 294 |
| LICENSE | — | — | — | — | — | — | 210 |
| .service | — | — | — | — | — | — | 179 |
| .svg | — | — | — | — | — | — | 160 |
| .gitignore | — | — | — | — | — | — | 120 |
| CODEOWNERS | — | — | — | — | — | — | 92 |
| .containerignore | — | — | — | — | — | — | 66 |
| .prettierignore | — | — | — | — | — | — | 9 |
| .python-version | — | — | — | — | — | — | 3 |
| .nvmrc | — | — | — | — | — | — | 1 |
| **Total** | 1.4% | 15.0% | 26.5% | 33.0% | 37.8% | 85.0% | 591,998 |

> `BPE` — Byte Pair Encoding, tiktoken `o200k_base`.
>
> `Prose` — comments; or everything non-whitespace in .md.
>
> `Code` — everything but prose and whitespace.
>
> `Total` — tokens that aren't whitespace.

Production scope: Cerberus source defaults, overlaid by `[source_oracle]` in the repository's `cerberus.toml`. Includes assets and configuration under production roots; excludes test files. Metrics use the legends above.

## Production Line Counts

| Language | Files | Prose | Branch | Code | Total |
|---|---|---|---|---|---|
| Python | 140 | 0.8% | 19.5% | 99.2% | 12,579 |
| .ts | 95 | 0.1% | 17.2% | 99.9% | 5,411 |
| JSON | 22 | 0.0% | 0.0% | 100.0% | 1,842 |
| Markdown | 25 | 100.0% | — | 0.0% | 889 |
| TOML | 7 | 1.2% | 0.0% | 98.8% | 346 |
| YAML | 2 | 0.0% | 0.0% | 100.0% | 158 |
| .just | 1 | — | — | — | 59 |
| **Total** | 292 | 4.7% | 16.7% | 95.3% | 21,284 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.1% | 32.6% | 52.2% | 99.9% | 106,976 | 109,398 | 165,506 |
| .ts | 0.0% | 1.5% | 4.5% | 26.0% | 68.0% | 100.0% | 48,143 | 38,948 | 72,073 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,060 | 8,800 | 19,382 |
| TOML | 0.4% | 1.2% | 23.0% | 23.0% | 52.6% | 99.6% | 1,124 | 852 | 1,443 |
| YAML | 0.0% | 0.8% | 57.7% | 0.0% | 41.5% | 100.0% | 395 | 962 | 1,126 |
| **Total** | 0.1% | 2.4% | 11.1% | 27.9% | 58.6% | 99.9% | 170,698 | 158,960 | 259,530 |

## Production BPE Token Counts

| Language | Literal | Prose | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.6% | 25.3% | 33.4% | 38.1% | 98.4% | 123,699 |
| .ts | 1.5% | 0.3% | 15.7% | 32.4% | 50.1% | 99.7% | 51,458 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 19,212 |
| JSON | 6.5% | 0.0% | 54.9% | 0.0% | 38.6% | 100.0% | 18,494 |
| TOML | 0.5% | 3.0% | 65.1% | 16.9% | 14.5% | 97.0% | 2,800 |
| YAML | 0.3% | 0.0% | 85.3% | 0.0% | 14.4% | 100.0% | 1,123 |
| .just | — | — | — | — | — | — | 525 |
| **Total** | 2.0% | 9.9% | 26.5% | 29.6% | 40.8% | 90.1% | 217,311 |

### Left out files

- `docs/assets/og.png` — binary
