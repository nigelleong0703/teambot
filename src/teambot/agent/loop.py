from __future__ import annotations

import json
from typing import Any, Callable

from ..contracts.contracts import ModelToolSpec
from ..actions.tools.registry import ToolRegistry
from ..providers.manager import PROFILE_AGENT
from ..domain.models import RuntimeEvent

_FALLBACK_TEXT = "I was unable to produce a response."
_MAX_STEPS = 10


class AgentLoop:
    """Stateless tool-calling loop.

    Calls ``provider_manager.invoke_profile_chat`` in a loop, executing tool
    calls via ``tool_registry`` and accumulating token usage across all steps.
    Returns a 3-tuple ``(final_text, messages, usage)`` where ``usage`` is a
    ``dict`` with ``input_tokens`` and ``output_tokens`` keys.
    """

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        provider_manager: Any,
        max_steps: int = _MAX_STEPS,
    ) -> None:
        self.tool_registry = tool_registry
        self.provider_manager = provider_manager
        self.max_steps = max_steps

    def _tool_specs(self) -> list[ModelToolSpec]:
        specs: list[ModelToolSpec] = []
        for manifest in self.tool_registry.list_manifests():
            schema = manifest.input_schema if isinstance(manifest.input_schema, dict) else {}
            specs.append(
                ModelToolSpec(
                    name=manifest.name,
                    description=manifest.description,
                    input_schema=schema or {"type": "object", "properties": {}},
                )
            )
        return specs

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        system_prompt: str,
        conversation_key: str = "",
        working_dir: str = "",
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[RuntimeEvent], None] | None = None,
    ) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
        """Run the tool-calling loop and return (final_text, messages, usage)."""
        messages = list(messages)
        tools = self._tool_specs()
        total_input = 0
        total_output = 0

        for _step in range(self.max_steps):
            result = self.provider_manager.invoke_profile_chat(
                profile=PROFILE_AGENT,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools if tools else None,
                on_token=on_token,
            )
            total_input += result.usage.get("input_tokens", 0)
            total_output += result.usage.get("output_tokens", 0)

            if not result.tool_calls:
                final_text = result.text or _FALLBACK_TEXT
                messages.append({"role": "assistant", "content": final_text})
                return final_text, messages, {"input_tokens": total_input, "output_tokens": total_output}

            # Append the assistant turn with tool calls
            messages.append({"role": "assistant", "content": result.text or "", "tool_calls": [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in result.tool_calls
            ]})

            # Execute each tool call and append results
            for call in result.tool_calls:
                if self.tool_registry.has(call.name):
                    tool_output = self.tool_registry.invoke(call.name, call.arguments)
                else:
                    tool_output = {"message": f"Unknown tool: {call.name}"}
                output_text = (
                    tool_output.get("message", "")
                    if isinstance(tool_output, dict)
                    else str(tool_output)
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": output_text,
                })

        return _FALLBACK_TEXT, messages, {"input_tokens": total_input, "output_tokens": total_output}
