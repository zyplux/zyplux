# Copilot code review instructions

Only post medium- and high-severity review comments. Do not post low-severity or nitpick comments.

This project targets Python 3.14 and uses modern syntax. Before flagging any syntax as invalid, verify it against Python 3.14 — recent additions such as PEP 758 unparenthesized `except A, B, C:` clauses and the `type` alias statement are valid here.

Do not flag code based on hedged claims about external API runtime behavior (e.g., a GitHub API field being "often null" for some event type) unless the behavior is documented and definitive. In this repository, workflow runs triggered by the `release` event report `head_branch` as the release tag name.
