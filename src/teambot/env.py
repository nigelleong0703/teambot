from __future__ import annotations

from pathlib import Path

_ENV_LOADED = False


def load_environment() -> None:
    """Load .env files into process environment once."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    try:
        from dotenv import load_dotenv
    except Exception:
        return

    cwd_env = Path.cwd() / ".env"
    pkg_root_env = Path(__file__).resolve().parents[2] / ".env"

    if cwd_env.exists():
        load_dotenv(dotenv_path=cwd_env, override=False)
    if pkg_root_env.exists() and pkg_root_env != cwd_env:
        load_dotenv(dotenv_path=pkg_root_env, override=False)
