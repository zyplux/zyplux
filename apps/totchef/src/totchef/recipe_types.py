"""The shape of a parsed recipe.toml: arbitrarily nested TOML data, before any cook's own schema narrows it."""

type RecipeValue = str | int | float | bool | list[RecipeValue] | dict[str, RecipeValue]
type RecipeConfig = dict[str, RecipeValue]
