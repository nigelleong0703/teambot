from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .adapters.providers import (
    ROLE_AGENT,
    ROLE_ROUTER,
    ProviderInvocationError,
    build_default_provider_manager,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test model role provider calls (default: agent_model)."
    )
    parser.add_argument(
        "--roles",
        default="agent",
        help="Comma-separated roles to test: agent,router",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output JSON.",
    )
    return parser.parse_args()


def _router_prompt() -> str:
    return (
        "You are a low-cost router model. Return JSON only.\n"
        "Schema: {\n"
        '  "use_agent_model": boolean,\n'
        '  "selected_skill": string,\n'
        '  "note": string\n'
        "}\n"
        "Rules:\n"
        "- selected_skill must be one of available_skills names.\n"
        "- For this test, set use_agent_model=false.\n"
    )


def _router_payload() -> dict[str, Any]:
    return {
        "event_type": "message",
        "user_text": "hello",
        "reaction": None,
        "available_skills": [
            {"name": "general_reply", "description": "Default reply"},
            {"name": "create_task", "description": "Create task from /todo"},
            {"name": "handle_reaction", "description": "Handle reaction events"},
        ],
    }


def _agent_prompt() -> str:
    return (
        "You are a planning module in a ReAct workflow. Return JSON only.\n"
        "Schema: {\n"
        '  "selected_skill": string,\n'
        '  "skill_input": object,\n'
        '  "done": boolean,\n'
        '  "final_message": string,\n'
        '  "note": string\n'
        "}\n"
        "Rules:\n"
        "- If done=false, selected_skill must be in available_skills.\n"
        "- For this test, return done=false.\n"
    )


def _agent_payload() -> dict[str, Any]:
    return {
        "event_type": "message",
        "user_text": "please create a task for writing test docs",
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "previous_skill": "",
        "last_observation": {},
        "available_skills": [
            {"name": "general_reply", "description": "Default reply"},
            {"name": "create_task", "description": "Create task from /todo"},
            {"name": "handle_reaction", "description": "Handle reaction events"},
        ],
        "active_skill_docs": [],
    }


def _mask(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _test_role(role: str) -> dict[str, Any]:
    manager = build_default_provider_manager()
    if manager is None:
        return {
            "role": role,
            "ok": False,
            "error": "ProviderManager unavailable (missing role bindings in env).",
        }
    if not manager.has_role(role):
        return {
            "role": role,
            "ok": False,
            "error": f"Role not configured: {role}",
        }

    binding = manager.settings.get_role_binding(role)
    endpoint = binding.endpoints[0]
    summary: dict[str, Any] = {
        "role": role,
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
        if role == ROLE_ROUTER:
            result = manager.invoke_role_json(
                role=ROLE_ROUTER,
                system_prompt=_router_prompt(),
                payload=_router_payload(),
            )
        else:
            result = manager.invoke_role_json(
                role=ROLE_AGENT,
                system_prompt=_agent_prompt(),
                payload=_agent_payload(),
            )
        summary.update(
            {
                "ok": True,
                "invoked_provider": result.provider,
                "invoked_model": result.model,
                "finish_reason": result.finish_reason,
                "usage": result.usage,
                "response": result.data,
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
    mapping = {"router": ROLE_ROUTER, "agent": ROLE_AGENT}
    requested = [item.strip().lower() for item in args.roles.split(",") if item.strip()]
    roles: list[str] = []
    for item in requested:
        role = mapping.get(item)
        if role and role not in roles:
            roles.append(role)

    if not roles:
        print("No valid roles requested. Use --roles agent[,router]", file=sys.stderr)
        sys.exit(2)

    results = [_test_role(role) for role in roles]
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
