from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Status(Enum):
    PASS = auto()
    SKIP = auto()
    FAIL = auto()
    ERROR = auto()

    @property
    def rank(self) -> int:
        order = (Status.PASS, Status.SKIP, Status.FAIL, Status.ERROR)
        return order.index(self)


class Scope(Enum):
    """Where a check's facts live, hence where it can run."""

    CONTENT = auto()  # in the checkout — runnable as a per-repo CI linter
    CONTROL_PLANE = auto()  # GitHub org/admin state — only the central org scan
    GIT_HISTORY = auto()  # the checkout's git history — only the per-repo CI linter


@dataclass(frozen=True)
class Repo:
    name: str
    owner: str
    default_branch: str
    visibility: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def is_private(self) -> bool:
        return self.visibility == "private"


@dataclass(frozen=True)
class Finding:
    status: Status
    message: str


@dataclass
class CheckResult:
    check: str
    repo: str
    findings: list[Finding] = field(default_factory=list)

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
        return max((f.status for f in self.findings), key=lambda s: s.rank)

    @property
    def problems(self) -> list[Finding]:
        return [f for f in self.findings if f.status.rank >= Status.FAIL.rank]
