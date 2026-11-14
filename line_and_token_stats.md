# Stats - zyplux

TLDR: prod 20,809/200,837 · infra 544/4,069 · tests 21,446/244,178

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 240 | 10.9% | 0.6% | 99.4% | 29,447 |
| .ts | 189 | 9.2% | 0.1% | 99.9% | 11,147 |
| JSON | 42 | 0.0% | 0.0% | 100.0% | 7,146 |
| Markdown | 161 | — | 100.0% | 0.0% | 4,799 |
| TOML | 15 | 0.0% | 4.9% | 95.1% | 893 |
| YAML | 11 | 0.0% | 1.0% | 99.0% | 607 |
| justfile | 1 | — | — | — | 95 |
| .just | 1 | — | — | — | 59 |
| Containerfile | 1 | — | — | — | 45 |
| .gitignore | 1 | — | — | — | 34 |
| .service | 2 | — | — | — | 27 |
| Shell | 1 | 12.5% | 4.2% | 95.8% | 24 |
| LICENSE | 1 | — | — | — | 17 |
| .containerignore | 1 | — | — | — | 10 |
| CODEOWNERS | 1 | — | — | — | 7 |
| .prettierignore | 1 | — | — | — | 3 |
| .svg | 1 | — | — | — | 3 |
| .nvmrc | 1 | — | — | — | 1 |
| .python-version | 1 | — | — | — | 1 |
| **Total** | 672 | 8.6% | 9.3% | 90.7% | 54,365 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 20.1% | 28.3% | 49.3% | 99.8% | 250,328 | 260,247 | 384,088 |
| .ts | 0.0% | 1.2% | 6.8% | 21.7% | 70.2% | 100.0% | 96,458 | 74,767 | 143,116 |
| JSON | 0.0% | 2.7% | 21.5% | 0.0% | 75.8% | 100.0% | 45,491 | 28,353 | 62,813 |
| TOML | 2.3% | 1.7% | 21.9% | 23.9% | 50.3% | 97.7% | 2,654 | 2,094 | 3,429 |
| YAML | 0.4% | 1.7% | 52.6% | 0.0% | 45.3% | 99.6% | 1,562 | 3,760 | 4,468 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.2% | 23.3% | 57.4% | 99.9% | 396,663 | 369,409 | 598,172 |

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
| Python | 1.6% | 1.6% | 34.0% | 30.9% | 32.0% | 98.4% | 319,216 |
| .ts | 1.0% | 0.2% | 24.7% | 42.3% | 31.8% | 99.8% | 114,582 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 83,527 |
| JSON | 1.9% | 0.0% | 0.0% | 35.8% | 62.3% | 100.0% | 64,232 |
| TOML | 0.5% | 12.5% | 12.5% | 10.6% | 63.8% | 87.5% | 9,022 |
| YAML | 0.7% | 2.8% | 0.0% | 17.3% | 79.2% | 97.2% | 3,924 |
| justfile | — | — | — | — | — | — | 832 |
| Containerfile | — | — | — | — | — | — | 782 |
| .just | — | — | — | — | — | — | 525 |
| Shell | 5.4% | 1.7% | 49.0% | 19.4% | 24.5% | 98.3% | 294 |
| LICENSE | — | — | — | — | — | — | 210 |
| .service | — | — | — | — | — | — | 179 |
| .svg | — | — | — | — | — | — | 160 |
| .gitignore | — | — | — | — | — | — | 149 |
| CODEOWNERS | — | — | — | — | — | — | 92 |
| .containerignore | — | — | — | — | — | — | 78 |
| .prettierignore | — | — | — | — | — | — | 9 |
| .python-version | — | — | — | — | — | — | 3 |
| .nvmrc | — | — | — | — | — | — | 1 |
| **Total** | 1.5% | 15.2% | 27.0% | 33.6% | 36.7% | 84.8% | 597,817 |

> `BPE` — Byte Pair Encoding, tiktoken `o200k_base`.
>
> `Prose` — comments; or everything non-whitespace in .md.
>
> `Code` — everything but prose and whitespace.
>
> `Total` — tokens that aren't whitespace.

Production scope: Cerberus source defaults, overlaid by `[source_oracle]` in the repository's `cerberus.toml`. Includes assets and configuration under production roots; excludes test files. Metrics use the legends above.

## Production Line Counts

| Language | Prose | Files | Branch | Code | Total |
|---|---|---|---|---|---|
| Python | 0.8% | 146 | 20.1% | 99.2% | 13,102 |
| .ts | 0.1% | 95 | 17.2% | 99.9% | 5,391 |
| JSON | 0.0% | 23 | 0.0% | 100.0% | 1,847 |
| TOML | 1.1% | 8 | 0.0% | 98.9% | 363 |
| YAML | 0.0% | 4 | 0.0% | 100.0% | 222 |
| .just | — | 1 | — | — | 59 |
| Markdown | 100.0% | 2 | — | 0.0% | 21 |
| **Total** | 0.7% | 279 | 17.0% | 99.3% | 21,005 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.2% | 32.5% | 52.2% | 99.9% | 111,953 | 114,480 | 173,172 |
| .ts | 0.0% | 1.5% | 4.5% | 26.0% | 68.0% | 100.0% | 47,984 | 38,838 | 71,846 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,083 | 8,816 | 19,415 |
| TOML | 0.3% | 1.2% | 22.7% | 23.4% | 52.4% | 99.7% | 1,189 | 909 | 1,532 |
| YAML | 0.0% | 1.6% | 57.7% | 0.0% | 40.7% | 100.0% | 560 | 1,380 | 1,608 |
| **Total** | 0.1% | 2.4% | 11.2% | 28.0% | 58.3% | 99.9% | 175,769 | 164,423 | 267,573 |

## Production BPE Token Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.5% | 1.6% | 25.1% | 33.5% | 38.3% | 98.5% | 128,607 |
| .ts | 0.3% | 1.5% | 15.7% | 32.4% | 50.1% | 99.7% | 51,314 |
| JSON | 0.0% | 6.5% | 54.9% | 0.0% | 38.6% | 100.0% | 18,522 |
| TOML | 2.8% | 0.5% | 64.8% | 17.1% | 14.7% | 97.2% | 2,950 |
| YAML | 0.0% | 0.6% | 85.5% | 0.0% | 14.0% | 100.0% | 1,619 |
| Markdown | 100.0% | — | — | — | — | 0.0% | 792 |
| .just | — | — | — | — | — | — | 525 |
| **Total** | 1.5% | 2.0% | 26.5% | 29.6% | 40.8% | 98.5% | 204,329 |

### Left out files

- `docs/assets/og.png` — binary
