from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .adapters.providers import (
    ROLE_AGENT,
    ProviderInvocationError,
    build_default_provider_manager,
)
from .agents.prompts import build_system_prompt_from_working_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test agent_model provider call."
    )
    parser.add_argument(
        "--roles",
        default="agent",
        help="Deprecated. Kept for compatibility; only agent role is tested.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output JSON.",
    )
    return parser.parse_args()


def _agent_prompt() -> str:
    return build_system_prompt_from_working_dir()


def _agent_payload() -> dict[str, Any]:
    return {"message": "hello from provider smoke test"}


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _test_agent_role() -> dict[str, Any]:
    manager = build_default_provider_manager()
    if manager is None:
        return {
            "role": ROLE_AGENT,
            "ok": False,
            "error": "ProviderManager unavailable (missing role bindings in env).",
        }
    if not manager.has_role(ROLE_AGENT):
        return {
            "role": ROLE_AGENT,
            "ok": False,
            "error": f"Role not configured: {ROLE_AGENT}",
        }

    binding = manager.settings.get_role_binding(ROLE_AGENT)
    endpoint = binding.endpoints[0]
    summary: dict[str, Any] = {
        "role": ROLE_AGENT,
        "configured": {
            "provider": endpoint.provider,
            "model": endpoint.model,
            "base_url": endpoint.base_url,
            "timeout_seconds": endpoint.timeout_seconds,
            "api_key_preview": _mask(endpoint.api_key),
            "max_attempts": binding.max_attempts,
        },
    }

    try:
        result = manager.invoke_role_text(
            role=ROLE_AGENT,
            system_prompt=_agent_prompt(),
            user_message=_agent_payload()["message"],
        )
        summary.update(
            {
                "ok": True,
                "invoked_provider": result.provider,
                "invoked_model": result.model,
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "response_text": result.text,
            }
        )
        return summary
    except ProviderInvocationError as exc:
        summary.update(
            {
                "ok": False,
                "error": str(exc),
                "attempts": [
                    {
                        "provider": item.provider,
                        "model": item.model,
                        "endpoint": item.endpoint,
                        "error": item.error,
                    }
                    for item in exc.attempts
                ],
            }
        )
        return summary
    except Exception as exc:  # pragma: no cover
        summary.update({"ok": False, "error": str(exc)})
        return summary


def main() -> None:
    args = parse_args()
    results = [_test_agent_role()]
    report = {
        "ok": all(item.get("ok") for item in results),
        "results": results,
    }
    if args.pretty:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(report, ensure_ascii=False, default=str))

    if not report["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
