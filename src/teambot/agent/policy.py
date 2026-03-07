from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class ExecutionPolicyGate:
    def __init__(
        self,
        *,
        allow_high_risk: bool = False,
        allowlisted_actions: set[str] | None = None,
    ) -> None:
        self.allow_high_risk = allow_high_risk
        self.allowlisted_actions = allowlisted_actions or set()

    @classmethod
    def from_env(cls) -> "ExecutionPolicyGate":
        allow_high_risk = os.getenv("ALLOW_HIGH_RISK_ACTIONS", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        raw = os.getenv("HIGH_RISK_ALLOWED_ACTIONS", "").strip()
        allowlisted_actions = {
            part.strip() for part in raw.split(",") if part.strip()
        }
        return cls(
            allow_high_risk=allow_high_risk,
            allowlisted_actions=allowlisted_actions,
        )

    def check(self, action_name: str, risk_level: str) -> PolicyDecision:
        if action_name in self.allowlisted_actions:
            return PolicyDecision(allowed=True)
        if risk_level.lower() == "high" and not self.allow_high_risk:
            return PolicyDecision(
                allowed=False,
                reason=f"High-risk action blocked by policy: {action_name}",
            )
        return PolicyDecision(allowed=True)
