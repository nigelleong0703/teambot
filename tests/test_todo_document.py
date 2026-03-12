from teambot.todo.codec import TodoDocumentCodec
from teambot.todo.models import TodoItem, TodoList


def test_todo_document_round_trips_canonical_markdown() -> None:
    todo_list = TodoList(
        items=[
            TodoItem(
                content="Design document-backed todo storage",
                active_form="Designing document-backed todo storage",
                status="in_progress",
            ),
            TodoItem(
                content="Add todo repository",
                active_form="Adding todo repository",
                status="pending",
            ),
            TodoItem(
                content="Remove `/todo` deterministic route",
                active_form="Removing `/todo` deterministic route",
                status="completed",
            ),
        ]
    )

    text = TodoDocumentCodec.to_markdown(todo_list)

    assert "# Tasks" in text
    assert "## 1. Design document-backed todo storage" in text
    assert "- **Active Form**: Designing document-backed todo storage" in text
    assert "- **Status**: In Progress" in text

    parsed = TodoDocumentCodec.from_markdown(text)

    assert parsed == todo_list


def test_todo_document_parses_empty_tasks_file() -> None:
    parsed = TodoDocumentCodec.from_markdown("# Tasks\n")

    assert parsed == TodoList(items=[])


def test_todo_document_normalizes_numbering_when_rendering() -> None:
    text = """# Tasks

## 9. First task
- **Active Form**: Doing first task
- **Status**: Pending

## 4. Second task
- **Active Form**: Doing second task
- **Status**: Completed
"""

    parsed = TodoDocumentCodec.from_markdown(text)
    rendered = TodoDocumentCodec.to_markdown(parsed)

    assert "## 1. First task" in rendered
    assert "## 2. Second task" in rendered

