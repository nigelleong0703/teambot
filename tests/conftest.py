from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_runtime_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    workdir = tmp_path / ".teambot"
    monkeypatch.setenv("WORKING_DIR", str(workdir))
    monkeypatch.delenv("ACTIVE_SKILLS_DIR", raising=False)
    monkeypatch.delenv("CUSTOMIZED_SKILLS_DIR", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("AGENT_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("AGENT_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("AGENT_FALLBACKS_JSON", raising=False)
    monkeypatch.delenv("ROUTER_MODEL", raising=False)
    monkeypatch.delenv("ROUTER_PROVIDER", raising=False)
    monkeypatch.delenv("ROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("ROUTER_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("ROUTER_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("ROUTER_FALLBACKS_JSON", raising=False)
    monkeypatch.delenv("ALLOW_HIGH_RISK_ACTIONS", raising=False)
    monkeypatch.delenv("HIGH_RISK_ALLOWED_ACTIONS", raising=False)
    monkeypatch.delenv("ENABLE_ECHO_TOOL", raising=False)
    monkeypatch.delenv("ENABLE_EXEC_TOOL", raising=False)
