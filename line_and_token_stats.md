# Stats - zyplux

TLDR: prod 20,707/199,767 · infra 544/4,074 · tests 21,388/243,384

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 238 | 10.8% | 0.7% | 99.3% | 29,299 |
| .ts | 189 | 9.2% | 0.1% | 99.9% | 11,151 |
| JSON | 42 | 0.0% | 0.0% | 100.0% | 7,105 |
| Markdown | 160 | — | 100.0% | 0.0% | 4,758 |
| TOML | 15 | 0.0% | 4.9% | 95.1% | 892 |
| YAML | 11 | 0.0% | 1.0% | 99.0% | 572 |
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
| **Total** | 669 | 8.6% | 9.3% | 90.7% | 54,103 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 20.1% | 28.3% | 49.3% | 99.8% | 249,009 | 258,915 | 382,084 |
| .ts | 0.0% | 1.2% | 6.8% | 21.7% | 70.2% | 100.0% | 96,426 | 74,744 | 143,072 |
| JSON | 0.0% | 2.7% | 21.6% | 0.0% | 75.7% | 100.0% | 45,340 | 28,271 | 62,586 |
| TOML | 2.3% | 1.7% | 21.9% | 23.9% | 50.3% | 97.7% | 2,651 | 2,092 | 3,425 |
| YAML | 0.4% | 1.8% | 52.3% | 0.0% | 45.5% | 99.6% | 1,476 | 3,550 | 4,221 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 2.0% | 17.2% | 23.3% | 57.4% | 99.9% | 395,072 | 367,760 | 595,646 |

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
| Python | 1.6% | 1.7% | 33.9% | 30.8% | 32.0% | 98.3% | 317,630 |
| .ts | 1.0% | 0.2% | 24.7% | 42.3% | 31.8% | 99.8% | 114,521 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 82,716 |
| JSON | 1.9% | 0.0% | 0.0% | 35.7% | 62.4% | 100.0% | 64,177 |
| TOML | 0.5% | 12.5% | 12.5% | 10.6% | 63.9% | 87.5% | 9,022 |
| YAML | 0.8% | 3.0% | 0.0% | 17.7% | 78.6% | 97.0% | 3,640 |
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
| **Total** | 1.5% | 15.1% | 27.0% | 33.6% | 36.7% | 84.9% | 595,020 |

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
| Python | 0.8% | 144 | 19.9% | 99.2% | 13,013 |
| .ts | 0.1% | 95 | 17.2% | 99.9% | 5,389 |
| JSON | 0.0% | 23 | 0.0% | 100.0% | 1,847 |
| TOML | 1.1% | 8 | 0.0% | 98.9% | 362 |
| YAML | 0.0% | 4 | 0.0% | 100.0% | 212 |
| .just | — | 1 | — | — | 59 |
| Markdown | 100.0% | 1 | — | 0.0% | 8 |
| **Total** | 0.6% | 276 | 16.9% | 99.4% | 20,890 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.2% | 32.5% | 52.2% | 99.9% | 111,087 | 113,619 | 171,845 |
| .ts | 0.0% | 1.5% | 4.5% | 26.0% | 68.0% | 100.0% | 47,974 | 38,830 | 71,833 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,083 | 8,816 | 19,415 |
| TOML | 0.3% | 1.2% | 22.8% | 23.4% | 52.4% | 99.7% | 1,186 | 907 | 1,528 |
| YAML | 0.0% | 1.7% | 57.3% | 0.0% | 41.1% | 100.0% | 531 | 1,311 | 1,529 |
| **Total** | 0.1% | 2.4% | 11.3% | 27.9% | 58.4% | 99.9% | 174,861 | 163,483 | 266,150 |

## Production BPE Token Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.5% | 1.6% | 25.2% | 33.4% | 38.2% | 98.5% | 127,708 |
| .ts | 0.3% | 1.5% | 15.7% | 32.4% | 50.1% | 99.7% | 51,298 |
| JSON | 0.0% | 6.5% | 54.9% | 0.0% | 38.6% | 100.0% | 18,522 |
| TOML | 2.8% | 0.5% | 64.9% | 17.0% | 14.7% | 97.2% | 2,945 |
| YAML | 0.0% | 0.6% | 84.8% | 0.0% | 14.6% | 100.0% | 1,484 |
| .just | — | — | — | — | — | — | 525 |
| Markdown | 100.0% | — | — | — | — | 0.0% | 406 |
| **Total** | 1.3% | 2.0% | 26.5% | 29.6% | 40.7% | 98.7% | 202,888 |

### Left out files

- `docs/assets/og.png` — binary
