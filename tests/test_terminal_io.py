from __future__ import annotations

from teambot.app import terminal_io


def test_discard_pending_stdin_flushes_tty_buffer(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    class _StdinStub:
        @staticmethod
        def isatty() -> bool:
            return True

        @staticmethod
        def fileno() -> int:
            return 7

    class _TermiosStub:
        TCIFLUSH = 2
        error = OSError

        @staticmethod
        def tcflush(fd: int, queue: int) -> None:
            calls.append((fd, queue))

    monkeypatch.setattr(terminal_io, "termios", _TermiosStub)
    monkeypatch.setattr(terminal_io.sys, "stdin", _StdinStub())

    terminal_io.discard_pending_stdin()

    assert calls == [(7, 2)]


def test_discard_pending_stdin_skips_non_tty(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    class _StdinStub:
        @staticmethod
        def isatty() -> bool:
            return False

        @staticmethod
        def fileno() -> int:
            return 7

    class _TermiosStub:
        TCIFLUSH = 2
        error = OSError

        @staticmethod
        def tcflush(fd: int, queue: int) -> None:
            calls.append((fd, queue))

    monkeypatch.setattr(terminal_io, "termios", _TermiosStub)
    monkeypatch.setattr(terminal_io.sys, "stdin", _StdinStub())

    terminal_io.discard_pending_stdin()

    assert calls == []


def test_suppress_stdin_echo_hides_and_restores_terminal_echo(monkeypatch) -> None:
    calls: list[tuple[str, int, object]] = []

    class _StdinStub:
        @staticmethod
        def isatty() -> bool:
            return True

        @staticmethod
        def fileno() -> int:
            return 7

    class _TermiosStub:
        TCIFLUSH = 2
        TCSADRAIN = 3
        ECHO = 0x0008
        error = OSError

        @staticmethod
        def tcflush(fd: int, queue: int) -> None:
            calls.append(("flush", fd, queue))

        @staticmethod
        def tcgetattr(fd: int) -> list[object]:
            calls.append(("get", fd, None))
            return [0, 0, 0, 0x0018, 0, 0]

        @staticmethod
        def tcsetattr(fd: int, when: int, attrs: object) -> None:
            calls.append(("set", fd, (when, attrs)))

    monkeypatch.setattr(terminal_io, "termios", _TermiosStub)
    monkeypatch.setattr(terminal_io.sys, "stdin", _StdinStub())

    with terminal_io.suppress_stdin_echo():
        calls.append(("inside", 0, None))

    assert calls[0] == ("get", 7, None)
    assert calls[1] == ("flush", 7, 2)
    assert calls[2][0] == "set"
    hidden_attrs = calls[2][2][1]
    assert hidden_attrs[3] & _TermiosStub.ECHO == 0
    assert calls[3] == ("inside", 0, None)
    assert calls[4][0] == "set"
    restored_attrs = calls[4][2][1]
    assert restored_attrs[3] & _TermiosStub.ECHO == _TermiosStub.ECHO
    assert calls[5] == ("flush", 7, 2)
