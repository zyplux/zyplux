# Stats - zyplux

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 222 | 10.7% | 0.6% | 99.4% | 26,821 |
| .ts | 181 | 9.1% | 0.1% | 99.9% | 10,568 |
| JSON | 39 | 0.0% | 0.0% | 100.0% | 7,009 |
| Markdown | 151 | — | 100.0% | 0.0% | 4,562 |
| TOML | 14 | 0.0% | 5.0% | 95.0% | 886 |
| YAML | 8 | 0.0% | 1.5% | 98.5% | 411 |
| just | 1 | — | — | — | 278 |
| justfile | 1 | — | — | — | 81 |
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
| **Total** | 630 | 8.4% | 9.5% | 90.5% | 50,841 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 19.6% | 28.7% | 49.5% | 99.8% | 225,906 | 235,375 | 347,428 |
| .ts | 0.0% | 1.2% | 6.8% | 21.6% | 70.4% | 100.0% | 89,861 | 69,544 | 133,387 |
| JSON | 0.0% | 2.6% | 26.4% | 0.0% | 71.0% | 100.0% | 47,812 | 30,911 | 64,855 |
| TOML | 2.2% | 1.6% | 21.5% | 24.1% | 50.6% | 97.8% | 2,713 | 2,145 | 3,518 |
| YAML | 0.5% | 1.8% | 52.0% | 0.0% | 45.6% | 99.5% | 1,103 | 2,621 | 3,124 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.4% | 23.1% | 57.4% | 99.9% | 367,565 | 340,784 | 552,570 |

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
| Python | 1.5% | 1.6% | 34.2% | 30.8% | 31.8% | 98.4% | 291,811 |
| .ts | 1.0% | 0.2% | 24.6% | 41.8% | 32.4% | 99.8% | 108,050 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 80,129 |
| JSON | 1.7% | 0.0% | 0.0% | 31.8% | 66.5% | 100.0% | 71,321 |
| TOML | 0.5% | 12.5% | 12.7% | 11.1% | 63.2% | 87.5% | 8,985 |
| YAML | 0.8% | 4.1% | 0.0% | 18.1% | 77.0% | 95.9% | 2,661 |
| just | — | — | — | — | — | — | 2,541 |
| justfile | — | — | — | — | — | — | 735 |
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
| **Total** | 1.4% | 15.3% | 26.5% | 32.9% | 37.9% | 84.7% | 568,616 |

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
| Python | 134 | 0.7% | 20.2% | 99.3% | 11,707 |
| .ts | 90 | 0.2% | 17.3% | 99.8% | 5,006 |
| JSON | 21 | 0.0% | 0.0% | 100.0% | 1,837 |
| Markdown | 24 | 100.0% | — | 0.0% | 879 |
| TOML | 7 | 1.2% | 0.0% | 98.8% | 345 |
| YAML | 2 | 0.0% | 0.0% | 100.0% | 158 |
| .just | 1 | — | — | — | 59 |
| **Total** | 279 | 4.9% | 17.0% | 95.1% | 19,991 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 12.7% | 33.0% | 52.3% | 99.9% | 100,102 | 102,738 | 155,331 |
| .ts | 0.0% | 1.5% | 4.4% | 25.9% | 68.1% | 100.0% | 43,950 | 35,582 | 65,865 |
| JSON | 0.0% | 8.6% | 16.1% | 0.0% | 75.3% | 100.0% | 14,037 | 8,784 | 19,349 |
| TOML | 0.4% | 1.2% | 22.9% | 23.0% | 52.6% | 99.6% | 1,122 | 851 | 1,441 |
| YAML | 0.0% | 0.8% | 57.7% | 0.0% | 41.5% | 100.0% | 395 | 962 | 1,126 |
| **Total** | 0.1% | 2.4% | 10.9% | 28.0% | 58.7% | 99.9% | 159,606 | 148,917 | 243,112 |

## Production BPE Token Counts

| Language | Literal | Prose | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.3% | 25.1% | 33.6% | 38.5% | 98.7% | 115,598 |
| .ts | 1.5% | 0.4% | 16.0% | 32.4% | 49.8% | 99.6% | 47,443 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 19,021 |
| JSON | 6.5% | 0.0% | 54.9% | 0.0% | 38.6% | 100.0% | 18,467 |
| TOML | 0.5% | 3.0% | 65.0% | 16.9% | 14.6% | 97.0% | 2,789 |
| YAML | 0.3% | 0.0% | 85.3% | 0.0% | 14.4% | 100.0% | 1,123 |
| .just | — | — | — | — | — | — | 525 |
| **Total** | 2.0% | 10.1% | 26.7% | 29.5% | 40.9% | 89.9% | 204,966 |

### Left out files

- `docs/assets/og.png` — binary
