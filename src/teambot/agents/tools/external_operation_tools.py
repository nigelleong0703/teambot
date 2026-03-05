from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ...models import AgentState

_DEFAULT_EXEC_TIMEOUT_SECONDS = 20
_DEFAULT_BROWSER_TIMEOUT_SECONDS = 10
_DEFAULT_OUTPUT_MAX_CHARS = 4000


def _coerce_input(state: AgentState) -> dict[str, object]:
    raw = state.get("skill_input", {})
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def _resolve_working_dir() -> Path:
    configured = os.getenv("WORKING_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.cwd().resolve()


def _resolve_file_path(file_path: str) -> Path:
    path = Path(file_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (_resolve_working_dir() / path).resolve()


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _truncate(text: str) -> str:
    max_chars = _to_int(os.getenv("TEAMBOT_TOOL_OUTPUT_MAX_CHARS"), _DEFAULT_OUTPUT_MAX_CHARS)
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<truncated>"


def read_file(state: AgentState) -> dict[str, object]:
    params = _coerce_input(state)
    file_path = str(params.get("file_path") or params.get("path") or "").strip()
    if not file_path:
        return {"message": "Error: `file_path` is required.", "error": True}

    path = _resolve_file_path(file_path)
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

    path = _resolve_file_path(file_path)
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

    path = _resolve_file_path(file_path)
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

    timeout_seconds = _to_int(
        params.get("timeout_seconds") or os.getenv("TEAMBOT_EXEC_TIMEOUT_SECONDS"),
        _DEFAULT_EXEC_TIMEOUT_SECONDS,
    )
    if timeout_seconds <= 0:
        timeout_seconds = _DEFAULT_EXEC_TIMEOUT_SECONDS

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=_resolve_working_dir(),
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
    if not url:
        return {
            "message": "Error: `url` is required for browser_use.",
            "error": True,
        }

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"message": f"Error: Unsupported URL scheme in {url}.", "error": True}

    timeout_seconds = _to_int(
        params.get("timeout_seconds") or os.getenv("TEAMBOT_BROWSER_TIMEOUT_SECONDS"),
        _DEFAULT_BROWSER_TIMEOUT_SECONDS,
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
    path = _resolve_file_path(file_path)
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
