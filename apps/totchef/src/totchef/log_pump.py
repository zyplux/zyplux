"""The log pump's line-processing core: pure functions taking their dependencies explicitly, testable with a plain stream and spies — no real pipe/fd needed."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import threading
    from collections.abc import Callable, Iterable


def emit_terminal(line: str, *, enabled: bool, sink: Callable[[str], None] | None) -> None:
    """Mirror one line to the terminal sink, honoring the echo toggle; a line reaches the log file regardless of this."""
    if enabled and sink is not None:
        sink(line)


def pump_lines(
    lines: Iterable[str],
    *,
    write_log: Callable[[str], None],
    emit_terminal: Callable[[str], None],
    drain_events: dict[str, threading.Event],
) -> None:
    """Drain the stream to exhaustion: a line matching a registered drain marker is swallowed and signals its event, everything else is logged then mirrored."""
    for line in lines:
        if (event := drain_events.pop(line.strip(), None)) is not None:
            event.set()
            continue
        write_log(line)
        emit_terminal(line)
