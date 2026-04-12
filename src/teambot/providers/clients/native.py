"""Native (direct SDK) provider client — stub for Chunk 1 (implemented in Chunk 2)."""
from __future__ import annotations

from typing import Any, Callable

from ..base import NormalizedResponse, ProviderEndpoint

# Budget maps — populated in Chunk 2.
_THINKING_BUDGET_MAP: dict[str, int] = {}
_THINKING_MAX_TOKENS_MAP: dict[str, int] = {}


class NativeProviderClient:
    def __init__(self, endpoint: ProviderEndpoint) -> None:
        self.endpoint = endpoint

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any] | str,
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        raise NotImplementedError("NativeProviderClient not yet implemented (Chunk 2)")

    def _invoke_anthropic_chat(self, **kwargs: Any) -> NormalizedResponse:
        raise NotImplementedError("NativeProviderClient not yet implemented (Chunk 2)")

    def _invoke_anthropic(self, **kwargs: Any) -> NormalizedResponse:
        raise NotImplementedError("NativeProviderClient not yet implemented (Chunk 2)")

    def _invoke_openai_chat(self, **kwargs: Any) -> NormalizedResponse:
        raise NotImplementedError("NativeProviderClient not yet implemented (Chunk 2)")
