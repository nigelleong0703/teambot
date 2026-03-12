from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


TodoStatus = Literal["pending", "in_progress", "completed"]
_VALID_STATUSES = {"pending", "in_progress", "completed"}


@dataclass(frozen=True)
class TodoItem:
    content: str
    active_form: str
    status: TodoStatus

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("todo content cannot be empty")
        if not self.active_form.strip():
            raise ValueError("todo active_form cannot be empty")
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"invalid todo status: {self.status}")


@dataclass(frozen=True)
class TodoList:
    items: list[TodoItem] = field(default_factory=list)

