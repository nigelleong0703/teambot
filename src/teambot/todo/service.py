from __future__ import annotations

from pathlib import Path

from .models import TodoItem, TodoList
from .repository import TodoRepository


class TodoService:
    def __init__(self, repository: TodoRepository | None = None) -> None:
        self._repository = repository or TodoRepository()

    def read(self, working_dir: str | Path) -> TodoList:
        return self._repository.load(working_dir)

    def write(self, working_dir: str | Path, *, items: list[TodoItem]) -> dict[str, list[TodoItem]]:
        previous = self.read(working_dir)
        new_items = list(items)
        self._validate_progress_shape(new_items)
        persisted = TodoList(items=[] if new_items and all(item.status == "completed" for item in new_items) else new_items)
        self._repository.save(working_dir, persisted)
        return {
            "old_todos": previous.items,
            "new_todos": new_items,
        }

    def _validate_progress_shape(self, items: list[TodoItem]) -> None:
        if not items:
            return
        if all(item.status == "completed" for item in items):
            return
        in_progress = sum(1 for item in items if item.status == "in_progress")
        if in_progress != 1:
            raise ValueError(
                "Non-empty todo lists must contain exactly one in_progress item unless all items are completed."
            )
