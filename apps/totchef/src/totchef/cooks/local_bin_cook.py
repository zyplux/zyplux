"""StateCook for [local_bin.<name>] — install a bundled command into ~/.local/bin (per-user, no privilege), named after its source stem."""

from totchef.cooks.bin_cook_base import BinCommandCook


class LocalBinCook(BinCommandCook):
    bin_dir = "~/.local/bin"
