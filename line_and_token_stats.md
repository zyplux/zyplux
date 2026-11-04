# Stats - zyplux

TLDR: prod 20,402/197,125 · infra 758/5,427 · tests 21,184/240,640

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 232 | 10.8% | 0.7% | 99.3% | 28,834 |
| .ts | 190 | 9.2% | 0.1% | 99.9% | 11,181 |
| JSON | 41 | 0.0% | 0.0% | 100.0% | 7,040 |
| Markdown | 158 | — | 100.0% | 0.0% | 4,722 |
| TOML | 14 | 0.0% | 5.1% | 94.9% | 867 |
| YAML | 8 | 0.0% | 1.2% | 98.8% | 483 |
| just | 1 | — | — | — | 278 |
| justfile | 1 | — | — | — | 95 |
| .just | 1 | — | — | — | 59 |
| Containerfile | 1 | — | — | — | 43 |
| .gitignore | 1 | — | — | — | 34 |
| .service | 2 | — | — | — | 27 |
| Shell | 1 | 12.5% | 4.2% | 95.8% | 24 |
| LICENSE | 1 | — | — | — | 17 |
| .containerignore | 1 | — | — | — | 9 |
| CODEOWNERS | 1 | — | — | — | 7 |
| .prettierignore | 1 | — | — | — | 3 |
| .svg | 1 | — | — | — | 3 |
| .nvmrc | 1 | — | — | — | 1 |
| .python-version | 1 | — | — | — | 1 |
| **Total** | 658 | 8.6% | 9.4% | 90.6% | 53,728 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 20.0% | 28.4% | 49.4% | 99.8% | 244,260 | 254,054 | 374,953 |
| .ts | 0.0% | 1.2% | 6.8% | 21.7% | 70.3% | 100.0% | 96,660 | 74,913 | 143,420 |
| JSON | 0.0% | 2.7% | 21.5% | 0.0% | 75.8% | 100.0% | 44,919 | 27,974 | 62,025 |
| TOML | 2.3% | 1.7% | 21.8% | 23.8% | 50.4% | 97.7% | 2,567 | 2,021 | 3,314 |
| YAML | 0.5% | 1.5% | 52.1% | 0.0% | 45.9% | 99.5% | 1,257 | 2,996 | 3,573 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.0% | 23.3% | 57.6% | 99.9% | 389,833 | 362,146 | 587,543 |

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
| Python | 1.5% | 1.7% | 34.0% | 30.8% | 31.9% | 98.3% | 312,520 |
| .ts | 1.0% | 0.2% | 24.7% | 42.3% | 31.8% | 99.8% | 114,765 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 82,511 |
| JSON | 1.9% | 0.0% | 0.0% | 35.8% | 62.3% | 100.0% | 63,518 |
| TOML | 0.5% | 12.8% | 12.4% | 10.5% | 63.7% | 87.2% | 8,780 |
| YAML | 0.7% | 3.5% | 0.0% | 17.9% | 77.9% | 96.5% | 3,079 |
| just | — | — | — | — | — | — | 2,541 |
| justfile | — | — | — | — | — | — | 834 |
| Containerfile | — | — | — | — | — | — | 724 |
| .just | — | — | — | — | — | — | 525 |
| Shell | 5.4% | 1.7% | 49.0% | 19.4% | 24.5% | 98.3% | 294 |
| LICENSE | — | — | — | — | — | — | 210 |
| .service | — | — | — | — | — | — | 179 |
| .svg | — | — | — | — | — | — | 160 |
| .gitignore | — | — | — | — | — | — | 149 |
| CODEOWNERS | — | — | — | — | — | — | 92 |
| .containerignore | — | — | — | — | — | — | 66 |
| .prettierignore | — | — | — | — | — | — | 9 |
| .python-version | — | — | — | — | — | — | 3 |
| .nvmrc | — | — | — | — | — | — | 1 |
| **Total** | 1.5% | 15.2% | 27.0% | 33.6% | 36.6% | 84.8% | 590,960 |

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
| Python | 140 | 0.8% | 19.9% | 99.2% | 12,760 |
| .ts | 95 | 0.1% | 17.2% | 99.9% | 5,411 |
| JSON | 22 | 0.0% | 0.0% | 100.0% | 1,842 |
| Markdown | 25 | 100.0% | — | 0.0% | 945 |
| TOML | 7 | 1.2% | 0.0% | 98.8% | 347 |
| YAML | 2 | 0.0% | 0.0% | 100.0% | 158 |
| .just | 1 | — | — | — | 59 |
| **Total** | 292 | 4.9% | 16.9% | 95.1% | 21,522 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.1% | 32.5% | 52.2% | 99.9% | 108,813 | 111,260 | 168,352 |
| .ts | 0.0% | 1.5% | 4.5% | 26.0% | 68.0% | 100.0% | 48,143 | 38,948 | 72,073 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,060 | 8,800 | 19,382 |
| TOML | 0.4% | 1.2% | 23.0% | 22.9% | 52.6% | 99.6% | 1,126 | 853 | 1,445 |
| YAML | 0.0% | 0.5% | 58.0% | 0.0% | 41.5% | 100.0% | 393 | 958 | 1,121 |
| **Total** | 0.1% | 2.4% | 11.1% | 27.9% | 58.5% | 99.9% | 172,535 | 160,819 | 262,373 |

## Production BPE Token Counts

| Language | Literal | Prose | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.5% | 25.2% | 33.5% | 38.2% | 98.5% | 125,426 |
| .ts | 1.5% | 0.3% | 15.7% | 32.4% | 50.1% | 99.7% | 51,458 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 20,179 |
| JSON | 6.5% | 0.0% | 54.9% | 0.0% | 38.6% | 100.0% | 18,494 |
| TOML | 0.5% | 3.0% | 65.3% | 16.8% | 14.5% | 97.0% | 2,813 |
| YAML | 0.2% | 0.0% | 85.5% | 0.0% | 14.3% | 100.0% | 1,124 |
| .just | — | — | — | — | — | — | 525 |
| **Total** | 2.0% | 10.2% | 26.4% | 29.7% | 40.8% | 89.8% | 220,019 |

### Left out files

- `docs/assets/og.png` — binary
