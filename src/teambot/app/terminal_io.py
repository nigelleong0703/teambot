from __future__ import annotations

import sys
from contextlib import contextmanager

try:
    import termios
except Exception:  # pragma: no cover - non-POSIX fallback
    termios = None  # type: ignore[assignment]


def discard_pending_stdin() -> None:
    """Drop buffered keystrokes typed while the app was still rendering output."""
    if termios is None or not sys.stdin.isatty():
        return
    try:
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (termios.error, OSError, ValueError):
        return


@contextmanager
def suppress_stdin_echo():
    """Hide keystrokes typed while the agent is still rendering output."""
    if termios is None or not sys.stdin.isatty():
        yield
        return

    fd = sys.stdin.fileno()
    try:
        original_attrs = termios.tcgetattr(fd)
    except (termios.error, OSError, ValueError):
        yield
        return

    hidden_attrs = list(original_attrs)
    hidden_attrs[3] &= ~termios.ECHO

    try:
        discard_pending_stdin()
        termios.tcsetattr(fd, termios.TCSADRAIN, hidden_attrs)
        yield
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, original_attrs)
        except (termios.error, OSError, ValueError):
            pass
        discard_pending_stdin()
