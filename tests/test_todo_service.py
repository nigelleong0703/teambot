from pathlib import Path

from teambot.todo.models import TodoItem
from teambot.todo.service import TodoService


def test_todo_service_reads_missing_file_as_empty(tmp_path: Path) -> None:
    service = TodoService()

    result = service.read(tmp_path)

    assert result.items == []


def test_todo_service_writes_markdown_and_returns_old_and_new_todos(tmp_path: Path) -> None:
    service = TodoService()

    old_and_new = service.write(
        tmp_path,
        items=[
            TodoItem(
                content="Design document-backed todo storage",
                active_form="Designing document-backed todo storage",
                status="in_progress",
            )
        ],
    )

    todo_path = tmp_path / "todo.md"

    assert old_and_new["old_todos"] == []
    assert old_and_new["new_todos"][0].content == "Design document-backed todo storage"
    assert todo_path.exists()
    assert "## 1. Design document-backed todo storage" in todo_path.read_text(encoding="utf-8")


def test_todo_service_clears_items_when_everything_is_completed(tmp_path: Path) -> None:
    service = TodoService()
    service.write(
        tmp_path,
        items=[
            TodoItem(
                content="Initial task",
                active_form="Doing initial task",
                status="in_progress",
            )
        ],
    )

    result = service.write(
        tmp_path,
        items=[
            TodoItem(
                content="Initial task",
                active_form="Doing initial task",
                status="completed",
            )
        ],
    )

    assert result["old_todos"][0].status == "in_progress"
    assert result["new_todos"][0].status == "completed"
    assert service.read(tmp_path).items == []


def test_todo_service_rejects_non_empty_list_without_in_progress_item(tmp_path: Path) -> None:
    service = TodoService()

    try:
        service.write(
            tmp_path,
            items=[
                TodoItem(
                    content="Design document-backed todo storage",
                    active_form="Designing document-backed todo storage",
                    status="pending",
                )
            ],
        )
    except ValueError as exc:
        assert "exactly one in_progress" in str(exc)
    else:  # pragma: no cover - red/green guard
        raise AssertionError("Expected TodoService.write() to reject missing in_progress item.")


def test_todo_service_rejects_multiple_in_progress_items(tmp_path: Path) -> None:
    service = TodoService()

    try:
        service.write(
            tmp_path,
            items=[
                TodoItem(
                    content="Design document-backed todo storage",
                    active_form="Designing document-backed todo storage",
                    status="in_progress",
                ),
                TodoItem(
                    content="Add todo repository",
                    active_form="Adding todo repository",
                    status="in_progress",
                ),
            ],
        )
    except ValueError as exc:
        assert "exactly one in_progress" in str(exc)
    else:  # pragma: no cover - red/green guard
        raise AssertionError("Expected TodoService.write() to reject multiple in_progress items.")
