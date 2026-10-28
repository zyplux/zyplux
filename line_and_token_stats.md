# Stats - zyplux

## Line Counts

| Language | Files | Branch | Prose | Code | Total |
|---|---|---|---|---|---|
| Python | 229 | 10.7% | 0.7% | 99.3% | 27,766 |
| .ts | 190 | 9.3% | 0.1% | 99.9% | 11,165 |
| JSON | 40 | 0.0% | 0.0% | 100.0% | 7,039 |
| Markdown | 157 | — | 100.0% | 0.0% | 4,616 |
| TOML | 14 | 0.0% | 4.9% | 95.1% | 889 |
| YAML | 8 | 0.0% | 1.4% | 98.6% | 417 |
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
| **Total** | 653 | 8.5% | 9.4% | 90.6% | 52,487 |

> `Prose` — comment-only lines (no code); or non-blank lines in .md.
>
> `Branch` — `if`, loops, `catch`, `case`, ternaries, short-circuit operators, etc.
>
> `Total` — non-blank lines.

## Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.2% | 2.1% | 19.7% | 28.6% | 49.4% | 99.8% | 234,025 | 243,627 | 359,616 |
| .ts | 0.0% | 1.2% | 6.8% | 21.7% | 70.3% | 100.0% | 96,519 | 74,799 | 143,210 |
| JSON | 0.0% | 2.6% | 26.9% | 0.0% | 70.6% | 100.0% | 48,256 | 31,301 | 65,361 |
| TOML | 2.2% | 1.6% | 21.5% | 24.0% | 50.6% | 97.8% | 2,725 | 2,154 | 3,533 |
| YAML | 0.5% | 1.8% | 52.1% | 0.0% | 45.6% | 99.5% | 1,116 | 2,652 | 3,161 |
| Shell | 0.6% | 8.2% | 8.8% | 40.0% | 42.4% | 99.4% | 170 | 188 | 258 |
| **Total** | 0.1% | 1.9% | 17.5% | 23.1% | 57.3% | 99.9% | 382,811 | 354,721 | 575,139 |

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
| Python | 1.5% | 1.7% | 34.1% | 30.8% | 31.8% | 98.3% | 301,034 |
| .ts | 1.0% | 0.2% | 24.7% | 42.3% | 31.8% | 99.8% | 114,626 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 80,562 |
| JSON | 1.7% | 0.0% | 0.0% | 31.4% | 66.9% | 100.0% | 72,302 |
| TOML | 0.5% | 12.4% | 12.6% | 11.0% | 63.4% | 87.6% | 9,058 |
| YAML | 0.8% | 4.0% | 0.0% | 18.1% | 77.1% | 96.0% | 2,698 |
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
| **Total** | 1.4% | 15.0% | 26.4% | 33.1% | 37.7% | 85.0% | 586,014 |

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
| Python | 138 | 0.8% | 19.7% | 99.2% | 12,372 |
| .ts | 95 | 0.1% | 17.3% | 99.9% | 5,395 |
| JSON | 22 | 0.0% | 0.0% | 100.0% | 1,842 |
| Markdown | 25 | 100.0% | — | 0.0% | 886 |
| TOML | 7 | 1.2% | 0.0% | 98.8% | 346 |
| YAML | 2 | 0.0% | 0.0% | 100.0% | 158 |
| .just | 1 | — | — | — | 59 |
| **Total** | 290 | 4.8% | 16.8% | 95.2% | 21,058 |

## Production Lexical Token and CST Node Counts

| Language | Prose | Literal | String | Identifier | Syntax | Code | Total | CST named | CST |
|---|---|---|---|---|---|---|---|---|---|
| Python | 0.1% | 2.0% | 13.1% | 32.6% | 52.2% | 99.9% | 105,481 | 108,122 | 163,406 |
| .ts | 0.0% | 1.5% | 4.5% | 25.9% | 68.0% | 100.0% | 48,002 | 38,834 | 71,863 |
| JSON | 0.0% | 8.6% | 16.2% | 0.0% | 75.3% | 100.0% | 14,060 | 8,800 | 19,382 |
| TOML | 0.4% | 1.2% | 23.0% | 23.0% | 52.6% | 99.6% | 1,124 | 852 | 1,443 |
| YAML | 0.0% | 0.8% | 57.7% | 0.0% | 41.5% | 100.0% | 395 | 962 | 1,126 |
| **Total** | 0.1% | 2.4% | 11.1% | 27.9% | 58.6% | 99.9% | 169,062 | 157,570 | 257,220 |

## Production BPE Token Counts

| Language | Literal | Prose | String | Identifier | Syntax | Code | Total |
|---|---|---|---|---|---|---|---|
| Python | 1.6% | 1.6% | 25.5% | 33.2% | 38.1% | 98.4% | 121,949 |
| .ts | 1.5% | 0.3% | 15.7% | 32.4% | 50.1% | 99.7% | 51,319 |
| Markdown | — | 100.0% | — | — | — | 0.0% | 18,881 |
| JSON | 6.5% | 0.0% | 54.9% | 0.0% | 38.6% | 100.0% | 18,494 |
| TOML | 0.5% | 3.0% | 65.1% | 16.9% | 14.5% | 97.0% | 2,800 |
| YAML | 0.3% | 0.0% | 85.3% | 0.0% | 14.4% | 100.0% | 1,123 |
| .just | — | — | — | — | — | — | 525 |
| **Total** | 2.0% | 9.8% | 26.6% | 29.4% | 40.8% | 90.2% | 215,091 |

### Left out files

- `docs/assets/og.png` — binary
