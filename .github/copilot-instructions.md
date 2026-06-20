# Copilot review instructions

`totchef` is a declarative, idempotent system-configuration tool. Python ≥3.14, `uv`-managed, gated by `just check` (ruff, pyrefly, vulture, pytest).

Project conventions — do not flag these as defects:

- **Unparenthesized multi-type `except A, B:`** is intentional and required. PEP 758 (Python 3.14) makes the parentheses optional, and `ruff format` strips them — so this is the formatter-mandated form, not a `SyntaxError`. Never suggest adding parentheses.
- **Long single-line docstrings** are the house style. Ruff does not enable `E501`, and the formatter never wraps docstrings, so line length is not a lint concern. Don't suggest wrapping docstrings or flag them as too long.
- **`src/totchef/files/*.py` are standalone `uv` scripts**, deployed verbatim and run via their own inline `# /// script` dependencies. Their imports are not library dependencies and belong out of `[project.dependencies]`.
</content>
</invoke>
