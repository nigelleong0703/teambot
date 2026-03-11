from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ...domain.models import AgentState
from ...runtime_paths import get_agent_work_dir
from ...skills.manager import SkillDoc, SkillService
from .config import load_runtime_tool_limits

_DEFAULT_EXEC_TIMEOUT_SECONDS = 20
_DEFAULT_BROWSER_TIMEOUT_SECONDS = 10
_DEFAULT_OUTPUT_MAX_CHARS = 4000
_URL_PATTERN = re.compile(r"https?://[^\s]+")


def _coerce_input(state: AgentState) -> dict[str, object]:
    raw = state.get("action_input")
    if not isinstance(raw, dict):
        raw = state.get("skill_input")
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def _resolve_working_dir(state: AgentState) -> Path:
    state_working_dir = str(state.get("runtime_working_dir") or "").strip()
    if state_working_dir:
        return Path(state_working_dir).expanduser().resolve()
    work_dir = get_agent_work_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def _resolve_file_path(file_path: str, state: AgentState) -> Path:
    path = Path(file_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (_resolve_working_dir(state) / path).resolve()


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _truncate(text: str) -> str:
    _, _, max_chars = load_runtime_tool_limits()
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<truncated>"


def _skill_doc_payload(doc: SkillDoc) -> dict[str, str]:
    return {
        "name": doc.name,
        "description": doc.description,
        "when_to_use": doc.when_to_use,
        "source": doc.source,
        "path": doc.path,
        "content": doc.content,
    }


def _existing_active_skill_docs(state: AgentState) -> list[dict[str, str]]:
    raw = state.get("active_skill_docs")
    if not isinstance(raw, list):
        return []
    docs: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            docs.append({str(key): str(value) for key, value in item.items()})
    return docs


def _extract_first_url(text: str) -> str:
    match = _URL_PATTERN.search(text)
    if match is None:
        return ""
    return match.group(0).rstrip(".,!?;:)]}\"'")


def activate_skill(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    skill_name = str(params.get("skill_name") or "").strip()
    if not skill_name:
        return {"message": "Error: `skill_name` is required.", "error": True}

    doc = SkillService.get_skill_doc(skill_name)
    if doc is None:
        return {"message": f"Error: Unknown skill: {skill_name}", "error": True}

    active_docs = _existing_active_skill_docs(state)
    merged_docs = [item for item in active_docs if item.get("name") != doc.name]
    merged_docs.append(_skill_doc_payload(doc))
    active_names = [item["name"] for item in merged_docs if item.get("name")]

    return {
        "message": f"Activated skill: {doc.name}",
        "_state_update": {
            "active_skill_names": active_names,
            "active_skill_docs": merged_docs,
        },
    }


def read_file(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    file_path = str(params.get("file_path") or params.get("path") or "").strip()
    if not file_path:
        return {"message": "Error: `file_path` is required.", "error": True}

    path = _resolve_file_path(file_path, state)
    if not path.exists():
        return {"message": f"Error: File does not exist: {path}", "error": True}
    if not path.is_file():
        return {"message": f"Error: Path is not a file: {path}", "error": True}

    start_line_raw = params.get("start_line")
    end_line_raw = params.get("end_line")

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
        return {"message": f"Error: Failed to read file: {exc}", "error": True}

    if start_line_raw is None and end_line_raw is None:
        return {
            "message": _truncate(content),
            "file_path": str(path),
        }

    lines = content.splitlines()
    total = len(lines)
    start_line = max(1, _to_int(start_line_raw, 1))
    end_line = min(total, _to_int(end_line_raw, total))

    if total == 0:
        return {"message": f"{path} is empty.", "file_path": str(path)}
    if start_line > total:
        return {
            "message": f"Error: `start_line` {start_line} exceeds file length {total}.",
            "error": True,
        }
    if start_line > end_line:
        return {
            "message": f"Error: `start_line` ({start_line}) cannot exceed `end_line` ({end_line}).",
            "error": True,
        }

    numbered = [
        f"{line_no}: {line}"
        for line_no, line in enumerate(lines[start_line - 1 : end_line], start=start_line)
    ]
    payload = "\n".join(numbered)
    return {
        "message": _truncate(payload),
        "file_path": str(path),
        "start_line": start_line,
        "end_line": end_line,
        "total_lines": total,
    }


def write_file(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    file_path = str(params.get("file_path") or params.get("path") or "").strip()
    content = str(params.get("content") or "")
    if not file_path:
        return {"message": "Error: `file_path` is required.", "error": True}

    path = _resolve_file_path(file_path, state)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(content, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
        return {"message": f"Error: Failed to write file: {exc}", "error": True}

    return {
        "message": f"Wrote {len(content)} bytes to {path}.",
        "file_path": str(path),
        "bytes_written": len(content),
    }


def edit_file(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    file_path = str(params.get("file_path") or params.get("path") or "").strip()
    old_text = str(params.get("old_text") or "")
    new_text = str(params.get("new_text") or "")

    if not file_path:
        return {"message": "Error: `file_path` is required.", "error": True}
    if not old_text:
        return {"message": "Error: `old_text` is required.", "error": True}

    path = _resolve_file_path(file_path, state)
    if not path.exists() or not path.is_file():
        return {"message": f"Error: File does not exist: {path}", "error": True}

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
        return {"message": f"Error: Failed to read file for edit: {exc}", "error": True}

    count = content.count(old_text)
    if count <= 0:
        return {"message": f"Error: `old_text` not found in {path}.", "error": True}

    new_content = content.replace(old_text, new_text)
    try:
        path.write_text(new_content, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem/runtime dependent
        return {"message": f"Error: Failed to write edited file: {exc}", "error": True}

    return {
        "message": f"Replaced {count} occurrence(s) in {path}.",
        "file_path": str(path),
        "replacements": count,
    }


def execute_shell_command(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    command = str(params.get("command") or "").strip()
    if not command:
        command = str(state.get("user_text", "")).strip()
    if not command:
        return {"message": "Error: `command` is required.", "error": True}

    default_exec_timeout, _, _ = load_runtime_tool_limits()
    timeout_seconds = _to_int(
        params.get("timeout_seconds"),
        default_exec_timeout or _DEFAULT_EXEC_TIMEOUT_SECONDS,
    )
    if timeout_seconds <= 0:
        timeout_seconds = _DEFAULT_EXEC_TIMEOUT_SECONDS

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=_resolve_working_dir(state),
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "message": f"Command timed out after {timeout_seconds}s.",
            "error": True,
            "timed_out": True,
        }
    except Exception as exc:  # pragma: no cover - subprocess/runtime dependent
        return {"message": f"Error: Failed to execute command: {exc}", "error": True}

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    parts = [f"Command exited with code {completed.returncode}."]
    if stdout:
        parts.append(f"stdout:\n{_truncate(stdout)}")
    if stderr:
        parts.append(f"stderr:\n{_truncate(stderr)}")
    if not stdout and not stderr:
        parts.append("No output.")
    return {
        "message": "\n\n".join(parts),
        "exit_code": completed.returncode,
        "command": command,
    }


def browser_use(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    url = str(params.get("url") or "").strip()
    if not url:
        user_text = str(state.get("user_text", "")).strip()
        if user_text.startswith("http://") or user_text.startswith("https://"):
            url = user_text
        else:
            url = _extract_first_url(user_text)
    if not url:
        return {
            "message": "Error: `url` is required for browser_use.",
            "error": True,
        }

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"message": f"Error: Unsupported URL scheme in {url}.", "error": True}

    _, default_browser_timeout, _ = load_runtime_tool_limits()
    timeout_seconds = _to_int(
        params.get("timeout_seconds"),
        default_browser_timeout or _DEFAULT_BROWSER_TIMEOUT_SECONDS,
    )
    if timeout_seconds <= 0:
        timeout_seconds = _DEFAULT_BROWSER_TIMEOUT_SECONDS

    request = Request(url, headers={"User-Agent": "teambot-external-operation-tools/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200))
            body = response.read(8192).decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
    except HTTPError as exc:
        return {
            "message": f"Error: HTTP {exc.code} while loading {url}.",
            "error": True,
            "status_code": int(exc.code),
        }
    except URLError as exc:
        return {"message": f"Error: Failed to load {url}: {exc.reason}", "error": True}
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return {"message": f"Error: browser_use failed: {exc}", "error": True}

    preview = _truncate(body.strip())
    return {
        "message": f"Fetched {url} (status={status_code}, content_type={content_type}).\n\n{preview}",
        "url": url,
        "status_code": status_code,
        "content_type": content_type,
    }


def get_current_time(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    timezone_name = str(params.get("timezone") or params.get("tz") or "").strip()
    if timezone_name:
        try:
            now = dt.datetime.now(ZoneInfo(timezone_name))
            resolved_timezone = timezone_name
        except Exception:
            return {"message": f"Error: Unknown timezone '{timezone_name}'.", "error": True}
    else:
        now = dt.datetime.now().astimezone()
        resolved_timezone = str(now.tzinfo or "local")

    iso_timestamp = now.isoformat()
    return {
        "message": f"Current time ({resolved_timezone}): {iso_timestamp}",
        "timezone": resolved_timezone,
        "iso_time": iso_timestamp,
        "unix_time": int(now.timestamp()),
    }


def desktop_screenshot(_state: AgentState) -> dict[str, object]:
    return {
        "message": "desktop_screenshot is unavailable in TeamBot MVP runtime.",
        "blocked": True,
    }


def send_file_to_user(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    file_path = str(params.get("file_path") or params.get("path") or "").strip()
    if not file_path:
        return {"message": "Error: `file_path` is required.", "error": True}
    path = _resolve_file_path(file_path, state)
    if not path.exists() or not path.is_file():
        return {"message": f"Error: File does not exist: {path}", "error": True}

    size_bytes = path.stat().st_size
    return {
        "message": f"Prepared file for user delivery: {path} ({size_bytes} bytes).",
        "file_path": str(path),
        "bytes": size_bytes,
    }


def env_enabled(name: str, default: bool = False) -> bool:
    if name not in os.environ:
        return default
    return _coerce_bool(os.getenv(name))
