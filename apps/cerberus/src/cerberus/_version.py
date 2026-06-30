from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zyplux-cerberus")
except PackageNotFoundError:
    __version__ = "0+unknown"
