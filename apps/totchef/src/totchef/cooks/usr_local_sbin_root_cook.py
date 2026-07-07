"""StateCook for [usr_local_sbin.<name>] — install a bundled command into /usr/local/sbin (admin and daemon helpers, outside ordinary users' PATH), named after its source stem; always root."""

from totchef.cooks.bin_cook_base import BinCommandCook


class UsrLocalSbinCook(BinCommandCook):
    needs_root = True
    bin_dir = "/usr/local/sbin"
