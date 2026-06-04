# CLAUDE.md

`totchef` — an idempotent, declarative system configurator: you describe the machine in `recipe.toml`, and `just up` makes it comply.

## Invariants

- **Persisting means codifying.** The trigger is the effect, never the request wording: any action that leaves durable state outside this repo — packages, files under `$HOME` (`~/.local/bin`, `~/.config`, dotfiles), systemd units, crontabs, env vars — happens one way only: add it to `recipe.toml`; the user applies it with `just up`. Never write such state directly (`apt`, `curl | sh`, writing a script into `$HOME`, …) and never offer to. No exceptions for urgency or one-offs — "I just need it right now" gets the artifact in `/tmp` or pasted in chat, plus an offer to codify. If `recipe.toml` can't express the change yet, say so and ask — its current contents never narrow this rule's scope.
- **Wayland-only.** Never install or suggest anything Xorg / X11 / X-display-manager related. It's a relic here — don't reach for it.
