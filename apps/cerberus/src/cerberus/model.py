"""Define the repositories, findings and results shared by Cerberus checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto


class Status(IntEnum):
    """A check's outcome, ordered least to most severe so statuses compare directly."""

    PASS = auto()
    SKIP = auto()
    FAIL = auto()
    ERROR = auto()


class Scope(Enum):
    """Where a check's facts live."""

    CONTENT = auto()
    GIT_HISTORY = auto()


@dataclass(frozen=True)
class Repo:
    name: str


@dataclass(frozen=True)
class Finding:
    status: Status
    message: str


@dataclass
class CheckResult:
    check: str
    repo: str
    findings: list[Finding] = field(default_factory=list)
    detail: str | None = None
    verbose_lines: list[str] = field(default_factory=list)

    def record(self, status: Status, message: str) -> None:
        self.findings.append(Finding(status, message))

    def ok(self, message: str) -> None:
        self.record(Status.PASS, message)

    def fail(self, message: str) -> None:
        self.record(Status.FAIL, message)

    def skip(self, message: str) -> None:
        self.record(Status.SKIP, message)

    def error(self, message: str) -> None:
        self.record(Status.ERROR, message)

    @property
    def status(self) -> Status:
        if not self.findings:
            return Status.PASS
        return max(f.status for f in self.findings)

    @property
    def problems(self) -> list[Finding]:
        return [f for f in self.findings if f.status >= Status.FAIL]
