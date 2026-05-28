"""StateCook for [bash.<name>] — a generic idempotent shell executor whose current_state/desired_state/apply snippet keys mirror the StateCook lifecycle. Privilege-agnostic; recipe.toml grants root per entry."""

import subprocess

from loguru import logger

from totchef import shell
from totchef.cook_base import StateChangeOutcome, StateCook, EntrySpec


class BashEntry(EntrySpec):
    current_state: str | None = None
    desired_state: str = ""
    apply: str


class BashCook(StateCook[BashEntry]):
    entry_model = BashEntry

    def get_current_state(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for name, entry in self.entries.items():
            if not entry.current_state:
                states[name] = "(no check)"
                continue
            completed = shell.run("bash", "-c", entry.current_state)
            states[name] = completed.stdout.strip() or "(empty)"
        return states

    def get_desired_state(self) -> dict[str, str]:
        return {name: entry.desired_state for name, entry in self.entries.items()}

    def apply_resource(self, name: str) -> StateChangeOutcome:
        entry = self.entries[name]
        try:
            shell.stream(["bash", "-c", entry.apply], note="apply")
        except subprocess.CalledProcessError as exc:
            return StateChangeOutcome(
                changed=False,
                status="hard_fail",
                message=f"apply failed: {exc}",
            )
        logger.info("applied")
        return StateChangeOutcome(changed=True)
