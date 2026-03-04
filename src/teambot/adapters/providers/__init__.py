"""Provider adapters exposed behind stable adapter imports."""

from ...agents.providers.contracts import (
    ProviderAttempt,
    ProviderConfigError,
    ProviderEndpoint,
    ProviderInvocationError,
    ProviderRoleBinding,
    ProviderSettings,
)
from ...agents.providers.settings import ROLE_AGENT
from ...agents.providers.manager import (
    ProviderInvocationResult,
    ProviderManager,
    ProviderTextResult,
    build_default_provider_manager,
)

__all__ = [
    "ROLE_AGENT",
    "ProviderAttempt",
    "ProviderConfigError",
    "ProviderEndpoint",
    "ProviderInvocationError",
    "ProviderInvocationResult",
    "ProviderTextResult",
    "ProviderManager",
    "ProviderRoleBinding",
    "ProviderSettings",
    "build_default_provider_manager",
]
