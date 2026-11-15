# Stats - zyplux

TLDR: prod 21,075/203,512 · infra 557/4,176 · tests 21,659/246,113

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 249 | 11.0% | 0.9% | 99.1% | 29,982 |
| .ts | 189 | 9.2% | 0.6% | 99.4% | 11,208 |
| JSON | 42 | 0.0% | 0.0% | 100.0% | 7,019 |
| Markdown | 161 | — | 100.0% | 0.0% | 4,822 |
| TOML | 15 | 0.0% | 4.9% | 95.1% | 900 |
| YAML | 11 | 0.0% | 1.0% | 99.0% | 622 |
| justfile | 1 | — | — | — | 99 |
| .just | 1 | — | — | — | 60 |
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
| **Total** | 681 | 8.7% | 9.5% | 90.5% | 54,884 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 20.2% | 28.3% | 49.3% | 99.8% | 254,016 | 264,087 | 389,628 |
| .ts | 0.1% | 1.2% | 6.8% | 21.7% | 70.2% | 99.9% | 96,511 | 74,817 | 143,169 |
| JSON | 0.0% | 2.7% | 21.4% | 0.0% | 75.9% | 100.0% | 44,834 | 27,905 | 61,914 |
| TOML | 2.3% | 1.7% | 21.9% | 23.8% | 50.3% | 97.7% | 2,661 | 2,097 | 3,436 |
| YAML | 0.4% | 1.8% | 52.4% | 0.0% | 45.4% | 99.6% | 1,600 | 3,850 | 4,576 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.2% | 1.9% | 17.2% | 23.4% | 57.3% | 99.8% | 399,792 | 372,944 | 602,981 |

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
| Python | 1.5% | 1.7% | 34.0% | 30.9% | 31.9% | 98.3% | 323,584 |
| .ts | 1.0% | 0.3% | 24.6% | 42.0% | 32.0% | 99.7% | 115,173 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 84,962 |
| JSON | 1.9% | 0.0% | 0.0% | 35.8% | 62.2% | 100.0% | 63,307 |
| TOML | 0.5% | 12.4% | 12.5% | 10.6% | 64.0% | 87.6% | 9,065 |
| YAML | 0.8% | 2.7% | 0.0% | 17.3% | 79.2% | 97.3% | 4,022 |
| justfile | — | — | — | — | — | — | 856 |
| Containerfile | — | — | — | — | — | — | 782 |
| .just | — | — | — | — | — | — | 532 |
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
| **Total** | 1.5% | 15.3% | 27.1% | 33.5% | 36.6% | 84.7% | 603,458 |

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
| Python | 0.8% | 155 | 20.3% | 99.2% | 13,369 |
| .ts | 0.1% | 95 | 17.2% | 99.9% | 5,391 |
| JSON | 0.0% | 23 | 0.0% | 100.0% | 1,847 |
| TOML | 1.1% | 8 | 0.0% | 98.9% | 364 |
| YAML | 0.0% | 4 | 0.0% | 100.0% | 222 |
| .just | — | 1 | — | — | 60 |
| Markdown | 100.0% | 2 | — | 0.0% | 22 |
| **Total** | 0.7% | 288 | 17.2% | 99.3% | 21,275 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.3% | 32.5% | 52.1% | 99.9% | 114,647 | 117,264 | 177,249 |
| .ts | 0.0% | 1.5% | 4.5% | 26.0% | 68.0% | 100.0% | 47,984 | 38,838 | 71,846 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,083 | 8,816 | 19,415 |
| TOML | 0.3% | 1.2% | 22.8% | 23.3% | 52.4% | 99.7% | 1,191 | 910 | 1,534 |
| YAML | 0.0% | 1.6% | 57.7% | 0.0% | 40.7% | 100.0% | 560 | 1,380 | 1,608 |
| **Total** | 0.1% | 2.4% | 11.4% | 28.0% | 58.2% | 99.9% | 178,465 | 167,208 | 271,652 |

## Production BPE Token Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.5% | 1.6% | 24.8% | 33.8% | 38.3% | 98.5% | 131,283 |
| .ts | 0.3% | 1.5% | 15.7% | 32.4% | 50.1% | 99.7% | 51,314 |
| JSON | 0.0% | 6.5% | 54.9% | 0.0% | 38.6% | 100.0% | 18,522 |
| TOML | 2.8% | 0.5% | 64.9% | 17.0% | 14.7% | 97.2% | 2,959 |
| YAML | 0.0% | 0.6% | 85.5% | 0.0% | 14.0% | 100.0% | 1,619 |
| Markdown | 100.0% | — | — | — | — | 0.0% | 808 |
| .just | — | — | — | — | — | — | 532 |
| **Total** | 1.4% | 2.0% | 26.3% | 29.9% | 40.7% | 98.6% | 207,037 |

### Left out files

- `docs/assets/og.png` — binary
