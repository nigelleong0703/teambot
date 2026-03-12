from __future__ import annotations

import re

from .models import TodoItem, TodoList

_ITEM_PATTERN = re.compile(
    r"^##\s+\d+\.\s+(?P<content>.+?)\n"
    r"-\s+\*\*Active Form\*\*:\s+(?P<active_form>.+?)\n"
    r"-\s+\*\*Status\*\*:\s+(?P<status>.+?)\s*$",
    re.MULTILINE,
)

_STATUS_TO_TITLE = {
    "pending": "Pending",
    "in_progress": "In Progress",
    "completed": "Completed",
}
_TITLE_TO_STATUS = {
    "pending": "pending",
    "in progress": "in_progress",
    "completed": "completed",
}


class TodoDocumentCodec:
    @staticmethod
    def from_markdown(text: str) -> TodoList:
        matches = list(_ITEM_PATTERN.finditer(text.strip()))
        items = [
            TodoItem(
                content=match.group("content").strip(),
                active_form=match.group("active_form").strip(),
                status=TodoDocumentCodec._parse_status(match.group("status")),
            )
            for match in matches
        ]
        return TodoList(items=items)

    @staticmethod
    def to_markdown(todo_list: TodoList) -> str:
        if not todo_list.items:
            return "# Tasks\n"
        lines = ["# Tasks", ""]
        for index, item in enumerate(todo_list.items, start=1):
            lines.extend(
                [
                    f"## {index}. {item.content}",
                    f"- **Active Form**: {item.active_form}",
                    f"- **Status**: {_STATUS_TO_TITLE[item.status]}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _parse_status(raw: str) -> str:
        status = raw.strip().lower()
        if status not in _TITLE_TO_STATUS:
            raise ValueError(f"unsupported todo status label: {raw}")
        return _TITLE_TO_STATUS[status]

