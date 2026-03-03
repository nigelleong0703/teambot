from __future__ import annotations

from ...models import AgentState
from ..planner import Planner, PlannerError, RulePlanner
from .actions import ActionRegistry


def build_reason_node(action_registry: ActionRegistry, planner: Planner):
    fallback = RulePlanner()
    manifests = action_registry.list_manifests()
    skill_names = {manifest.name for manifest in manifests}
    default_skill = "general_reply" if "general_reply" in skill_names else ""
    if not default_skill and manifests:
        default_skill = manifests[0].name

    def _reason(state: AgentState) -> dict:
        step = state.get("react_step", 0)
        max_steps = state.get("react_max_steps", 3)
        if step >= max_steps:
            return {
                "react_done": True,
                "reasoning_note": f"Reached max ReAct steps: {max_steps}",
                "skill_output": {"message": "Processed."},
            }

        follow_up_skill = state.get("skill_output", {}).get("next_skill")
        if follow_up_skill:
            follow_up = str(follow_up_skill)
            if follow_up in skill_names:
                return {
                    "selected_skill": follow_up,
                    "skill_input": {},
                    "reasoning_note": (
                        f"Continue with follow-up action from observation: {follow_up}"
                    ),
                }
            if not default_skill:
                return {
                    "react_done": True,
                    "reasoning_note": (
                        f"next_skill not found and no fallback action: {follow_up}"
                    ),
                    "skill_output": {"message": "Processed."},
                }
            return {
                "selected_skill": default_skill,
                "skill_input": {},
                "reasoning_note": (
                    f"next_skill not found, fallback to {default_skill}: {follow_up}"
                ),
            }

        try:
            plan = planner.plan(state=state, available_skills=manifests)
        except PlannerError as exc:
            plan = fallback.plan(state=state, available_skills=manifests)
            if not (plan.selected_skill or default_skill):
                return {
                    "react_done": True,
                    "reasoning_note": (
                        f"Model planning failed and no fallback action: {exc}"
                    ),
                    "skill_output": {"message": "Processed."},
                }
            return {
                "selected_skill": plan.selected_skill or default_skill,
                "skill_input": plan.skill_input,
                "reasoning_note": f"Model planning failed, fallback to rule planner: {exc}",
            }

        if plan.done:
            return {
                "react_done": True,
                "reasoning_note": plan.note or "Model planner: finish directly",
                "skill_output": {"message": plan.final_message or "Processed."},
            }
        if plan.selected_skill not in skill_names:
            if not default_skill:
                return {
                    "react_done": True,
                    "reasoning_note": (
                        "Model returned invalid action and no fallback action: "
                        f"{plan.selected_skill}"
                    ),
                    "skill_output": {"message": "Processed."},
                }
            return {
                "selected_skill": default_skill,
                "skill_input": {},
                "reasoning_note": (
                    f"Model returned invalid action {plan.selected_skill}, "
                    f"fallback to {default_skill}"
                ),
            }
        return {
            "selected_skill": plan.selected_skill,
            "skill_input": plan.skill_input,
            "reasoning_note": plan.note or f"Model planner: execute {plan.selected_skill}",
        }

    return _reason


def route_after_reason(state: AgentState) -> str:
    return "compose_reply" if state.get("react_done", False) else "act"
