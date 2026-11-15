"""Safety contracts for the machine recipe shipped with TotChef."""

import tomllib

from project_paths import REPO_ROOT


def test_t14_1_pnpm_installs_from_next_12_and_updates_itself() -> None:
    recipe_path = REPO_ROOT / "apps/totchef/examples/totchef_recipe.toml"
    recipe = tomllib.loads(recipe_path.read_text(encoding="utf-8"))

    assert recipe["url"]["pnpm"]["env"] == {"PNPM_VERSION": "next-12"}
    assert recipe["url"]["pnpm"]["update_action"] == ["self-update", "next-12"]
    assert "node" not in recipe["url"]
    assert "node@26" in recipe["pnpm"]["packages"]
    assert recipe["skills"]["depends_on"] == ["pnpm"]
