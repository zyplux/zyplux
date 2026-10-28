# Stats - zyplux

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 234 | 10.8% | 0.7% | 99.3% | 28,351 |
| .ts | 181 | 9.1% | 0.1% | 99.9% | 10,515 |
| JSON | 40 | 0.0% | 0.0% | 100.0% | 6,976 |
| Markdown | 154 | — | 100.0% | 0.0% | 4,606 |
| TOML | 15 | 0.0% | 5.0% | 95.0% | 872 |
| YAML | 8 | 0.0% | 1.5% | 98.5% | 403 |
| just | 1 | — | — | — | 278 |
| justfile | 1 | — | — | — | 81 |
| .just | 1 | — | — | — | 59 |
| Containerfile | 1 | — | — | — | 45 |
| .gitignore | 1 | — | — | — | 31 |
| .service | 2 | — | — | — | 27 |
| Shell | 1 | 12.5% | 4.2% | 95.8% | 24 |
| LICENSE | 1 | — | — | — | 17 |
| .containerignore | 1 | — | — | — | 10 |
| CODEOWNERS | 1 | — | — | — | 7 |
| .prettierignore | 1 | — | — | — | 3 |
| .svg | 1 | — | — | — | 3 |
| .nvmrc | 1 | — | — | — | 1 |
| .python-version | 1 | — | — | — | 1 |
| .typed | 1 | — | — | — | 0 |
| **Total** | 648 | 8.5% | 9.4% | 90.6% | 52,310 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 19.7% | 28.6% | 49.4% | 99.8% | 239,780 | 249,543 | 368,392 |
| .ts | 0.0% | 1.2% | 6.8% | 21.6% | 70.4% | 100.0% | 89,571 | 69,312 | 132,954 |
| JSON | 0.0% | 2.7% | 23.9% | 0.0% | 73.4% | 100.0% | 46,065 | 29,227 | 63,043 |
| TOML | 2.3% | 1.4% | 21.7% | 24.2% | 50.5% | 97.7% | 2,663 | 2,114 | 3,458 |
| YAML | 0.6% | 1.8% | 52.1% | 0.0% | 45.5% | 99.4% | 1,084 | 2,576 | 3,069 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.3% | 23.3% | 57.3% | 99.9% | 379,333 | 352,960 | 571,174 |

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
| Python | 1.5% | 1.7% | 34.0% | 30.9% | 31.8% | 98.3% | 307,359 |
| .ts | 1.0% | 0.2% | 24.6% | 41.8% | 32.5% | 99.8% | 107,783 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 80,431 |
| JSON | 1.8% | 0.0% | 0.0% | 33.0% | 65.2% | 100.0% | 68,390 |
| TOML | 0.4% | 12.5% | 12.7% | 10.9% | 63.4% | 87.5% | 8,940 |
| YAML | 0.8% | 4.1% | 0.0% | 18.1% | 77.0% | 95.9% | 2,618 |
| just | — | — | — | — | — | — | 2,541 |
| Containerfile | — | — | — | — | — | — | 770 |
| justfile | — | — | — | — | — | — | 732 |
| .just | — | — | — | — | — | — | 525 |
| Shell | 5.4% | 1.7% | 49.0% | 19.4% | 24.5% | 98.3% | 294 |
| LICENSE | — | — | — | — | — | — | 210 |
| .service | — | — | — | — | — | — | 179 |
| .svg | — | — | — | — | — | — | 160 |
| .gitignore | — | — | — | — | — | — | 120 |
| CODEOWNERS | — | — | — | — | — | — | 92 |
| .containerignore | — | — | — | — | — | — | 75 |
| .prettierignore | — | — | — | — | — | — | 9 |
| .python-version | — | — | — | — | — | — | 3 |
| .nvmrc | — | — | — | — | — | — | 1 |
| .typed | — | — | — | — | — | — | 0 |
| **Total** | 1.4% | 15.1% | 26.7% | 33.1% | 37.4% | 84.9% | 581,232 |

> `BPE` — Byte Pair Encoding, tiktoken `o200k_base`.
>
> `Prose` — comments; or everything non-whitespace in .md.
>
> `Code` — everything but prose and whitespace.
>
> `Total` — tokens that aren't whitespace.

Production scope: Cerberus source defaults, overlaid by `[source]` in the repository's `cerberus.toml`. Includes assets and configuration under production roots; excludes test files. Metrics use the legends above.

## Production Line Counts

| Language | Files | Prose | Branch | Code | Total |
|---|---|---|---|---|---|
| Python | 147 | 0.9% | 19.7% | 99.1% | 13,189 |
| .ts | 90 | 0.2% | 17.4% | 99.8% | 4,953 |
| JSON | 22 | 0.0% | 0.0% | 100.0% | 1,839 |
| Markdown | 24 | 100.0% | — | 0.0% | 904 |
| TOML | 9 | 4.8% | 0.0% | 95.2% | 665 |
| YAML | 2 | 0.0% | 0.0% | 100.0% | 158 |
| .just | 1 | — | — | — | 59 |
| .service | 2 | — | — | — | 27 |
| .typed | 1 | — | — | — | 0 |
| **Total** | 298 | 4.9% | 16.6% | 95.1% | 21,794 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 1.9% | 13.3% | 32.5% | 52.1% | 99.9% | 112,734 | 115,602 | 174,626 |
| .ts | 0.0% | 1.5% | 4.4% | 25.9% | 68.1% | 100.0% | 43,660 | 35,350 | 65,432 |
| JSON | 0.0% | 8.6% | 16.1% | 0.0% | 75.3% | 100.0% | 14,034 | 8,784 | 19,346 |
| TOML | 1.7% | 1.4% | 21.5% | 25.1% | 50.4% | 98.3% | 1,934 | 1,545 | 2,520 |
| YAML | 0.0% | 0.8% | 57.7% | 0.0% | 41.5% | 100.0% | 395 | 962 | 1,126 |
| **Total** | 0.1% | 2.4% | 11.5% | 28.0% | 58.0% | 99.9% | 172,757 | 162,243 | 263,050 |

## Production BPE Token Counts

| Language | Literal | Prose | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.7% | 25.7% | 33.1% | 37.9% | 98.3% | 130,534 |
| .ts | 1.5% | 0.4% | 16.0% | 32.4% | 49.7% | 99.6% | 47,176 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 19,177 |
| JSON | 6.5% | 0.0% | 54.8% | 0.0% | 38.6% | 100.0% | 18,462 |
| TOML | 0.5% | 10.7% | 63.9% | 13.8% | 11.1% | 89.3% | 6,526 |
| YAML | 0.3% | 0.0% | 85.3% | 0.0% | 14.4% | 100.0% | 1,123 |
| .just | — | — | — | — | — | — | 525 |
| .service | — | — | — | — | — | — | 179 |
| .typed | — | — | — | — | — | — | 0 |
| **Total** | 2.0% | 10.0% | 27.7% | 29.1% | 39.7% | 90.0% | 223,702 |

### Left out files

- `docs/assets/og.png` — binary
