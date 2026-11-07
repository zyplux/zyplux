# Stats - zyplux

TLDR: prod 20,623/199,054 · infra 544/4,082 · tests 21,315/242,413

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 235 | 10.8% | 0.7% | 99.3% | 29,163 |
| .ts | 189 | 9.2% | 0.1% | 99.9% | 11,151 |
| JSON | 42 | 0.0% | 0.0% | 100.0% | 7,120 |
| Markdown | 159 | — | 100.0% | 0.0% | 4,751 |
| TOML | 15 | 0.0% | 4.9% | 95.1% | 892 |
| YAML | 10 | 0.0% | 1.1% | 98.9% | 550 |
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
| **Total** | 664 | 8.6% | 9.3% | 90.7% | 53,953 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 20.1% | 28.3% | 49.3% | 99.8% | 247,623 | 257,531 | 379,997 |
| .ts | 0.0% | 1.2% | 6.8% | 21.7% | 70.2% | 100.0% | 96,426 | 74,744 | 143,072 |
| JSON | 0.0% | 2.7% | 21.6% | 0.0% | 75.7% | 100.0% | 45,314 | 28,250 | 62,556 |
| TOML | 2.2% | 1.7% | 22.0% | 23.7% | 50.3% | 97.8% | 2,667 | 2,100 | 3,441 |
| YAML | 0.4% | 1.7% | 52.2% | 0.0% | 45.7% | 99.6% | 1,417 | 3,399 | 4,047 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.1% | 23.3% | 57.5% | 99.9% | 393,617 | 366,212 | 593,371 |

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
| Python | 1.6% | 1.7% | 34.0% | 30.8% | 32.0% | 98.3% | 316,069 |
| .ts | 1.0% | 0.2% | 24.7% | 42.3% | 31.8% | 99.8% | 114,521 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 82,500 |
| JSON | 1.9% | 0.0% | 0.0% | 35.7% | 62.3% | 100.0% | 64,110 |
| TOML | 0.5% | 12.4% | 12.5% | 10.5% | 64.0% | 87.6% | 9,059 |
| YAML | 0.7% | 3.1% | 0.0% | 17.8% | 78.4% | 96.9% | 3,483 |
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
| **Total** | 1.5% | 15.1% | 27.0% | 33.6% | 36.7% | 84.9% | 593,056 |

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
| Python | 142 | 0.8% | 20.0% | 99.2% | 12,950 |
| .ts | 95 | 0.1% | 17.2% | 99.9% | 5,389 |
| JSON | 23 | 0.0% | 0.0% | 100.0% | 1,847 |
| Markdown | 15 | 100.0% | — | 0.0% | 739 |
| TOML | 8 | 1.1% | 0.0% | 98.9% | 362 |
| YAML | 3 | 0.0% | 0.0% | 100.0% | 191 |
| .just | 1 | — | — | — | 59 |
| **Total** | 287 | 4.0% | 16.9% | 96.0% | 21,537 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.2% | 32.5% | 52.2% | 99.9% | 110,517 | 113,012 | 170,943 |
| .ts | 0.0% | 1.5% | 4.5% | 26.0% | 68.0% | 100.0% | 47,974 | 38,830 | 71,833 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,083 | 8,816 | 19,415 |
| TOML | 0.3% | 1.2% | 23.1% | 23.0% | 52.3% | 99.7% | 1,202 | 915 | 1,544 |
| YAML | 0.0% | 1.3% | 57.4% | 0.0% | 41.4% | 100.0% | 474 | 1,164 | 1,360 |
| **Total** | 0.1% | 2.4% | 11.2% | 27.9% | 58.4% | 99.9% | 174,250 | 162,737 | 265,095 |

## Production BPE Token Counts

| Language | Literal | Prose | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.5% | 25.2% | 33.4% | 38.2% | 98.5% | 127,118 |
| .ts | 1.5% | 0.3% | 15.7% | 32.4% | 50.1% | 99.7% | 51,298 |
| JSON | 6.5% | 0.0% | 54.9% | 0.0% | 38.6% | 100.0% | 18,522 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 17,623 |
| TOML | 0.5% | 2.8% | 65.3% | 16.8% | 14.6% | 97.2% | 2,974 |
| YAML | 0.5% | 0.0% | 85.0% | 0.0% | 14.6% | 100.0% | 1,332 |
| .just | — | — | — | — | — | — | 525 |
| **Total** | 2.0% | 9.1% | 26.5% | 29.6% | 40.8% | 90.9% | 219,392 |

### Left out files

- `docs/assets/og.png` — binary
