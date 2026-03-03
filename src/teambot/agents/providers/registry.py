from __future__ import annotations

from typing import Callable

from .base import ProviderClient, ProviderEndpoint
from .clients import LangChainProviderClient


class ProviderClientRegistry:
    def __init__(
        self,
        *,
        client_factory: Callable[[ProviderEndpoint], ProviderClient] | None = None,
    ) -> None:
        self._client_factory = client_factory or LangChainProviderClient
        self._clients: dict[str, ProviderClient] = {}

    def get_client(self, endpoint: ProviderEndpoint) -> ProviderClient:
        client = self._clients.get(endpoint.key)
        if client is not None:
            return client
        created = self._client_factory(endpoint)
        self._clients[endpoint.key] = created
        return created

