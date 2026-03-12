from __future__ import annotations

from pathlib import Path

from .codec import TodoDocumentCodec
from .models import TodoList


class TodoRepository:
    def todo_path(self, working_dir: str | Path) -> Path:
        return Path(working_dir).expanduser().resolve() / "todo.md"

    def load(self, working_dir: str | Path) -> TodoList:
        path = self.todo_path(working_dir)
        if not path.exists():
            return TodoList(items=[])
        return TodoDocumentCodec.from_markdown(path.read_text(encoding="utf-8"))

    def save(self, working_dir: str | Path, todo_list: TodoList) -> Path:
        path = self.todo_path(working_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = TodoDocumentCodec.to_markdown(todo_list)
        tmp_path = path.with_suffix(".md.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
        return path

