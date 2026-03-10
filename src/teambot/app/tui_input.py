from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class TuiInputReader(Protocol):
    def read(self, prompt_text: str) -> str:
        ...


@dataclass
class PlainInputReader:
    input_func: Callable[[str], str] = input

    def read(self, prompt_text: str) -> str:
        return self.input_func(prompt_text)


@dataclass
class PromptToolkitInputReader:
    session: Any
    ansi_factory: Callable[[str], Any] | None = None

    def read(self, prompt_text: str) -> str:
        prompt_arg = self.ansi_factory(prompt_text) if self.ansi_factory is not None else prompt_text
        return self.session.prompt(prompt_arg)


def build_tui_input_reader(*, use_color: bool) -> TuiInputReader:
    modules = _load_prompt_toolkit_modules()
    if modules is None:
        return PlainInputReader()

    PromptSession, ANSI, InMemoryHistory, KeyBindings = modules
    bindings = KeyBindings()

    @bindings.add("enter")
    def _submit(event) -> None:
        event.current_buffer.validate_and_handle()

    @bindings.add("escape", "enter")
    @bindings.add("c-j")
    def _newline(event) -> None:
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        multiline=True,
        key_bindings=bindings,
        prompt_continuation=_prompt_continuation,
        history=InMemoryHistory(),
        reserve_space_for_menu=0,
    )
    ansi_factory = ANSI if use_color else None
    return PromptToolkitInputReader(session=session, ansi_factory=ansi_factory)


def _load_prompt_toolkit_modules():
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.key_binding import KeyBindings
    except ImportError:
        return None
    return PromptSession, ANSI, InMemoryHistory, KeyBindings


def _prompt_continuation(width: int, line_number: int, is_soft_wrap: bool) -> str:
    _ = (line_number, is_soft_wrap)
    if width <= 2:
        return "· "
    return " " * (width - 2) + "· "
