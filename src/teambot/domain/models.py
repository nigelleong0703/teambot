from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator


class ReplyTarget(BaseModel):
    team_id: str
    channel_id: str
    thread_ts: str


class InboundEvent(BaseModel):
    event_id: str
    event_type: Literal["message", "reaction_added"] = "message"
    team_id: str
    channel_id: str
    thread_ts: str
    user_id: str
    text: str = ""
    reaction: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "InboundEvent":
        if self.event_type == "message" and not self.text.strip():
            raise ValueError("text is required for message events")
        if self.event_type == "reaction_added" and not self.reaction:
            raise ValueError("reaction is required for reaction events")
        return self


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ConversationRecord(BaseModel):
    conversation_key: str
    reply_target: ReplyTarget
    history: list[ConversationTurn] = Field(default_factory=list)


class OutboundReply(BaseModel):
    event_id: str
    conversation_key: str
    reply_target: ReplyTarget
    text: str
    skill_name: str
    reasoning_note: str = ""
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeEvent(BaseModel):
    run_id: str
    step: int = 0
    event_type: Literal[
        "task_started",
        "thinking",
        "thinking_delta",
        "tool_call",
        "tool_result",
        "final_delta",
        "final_text",
        "run_completed",
    ]
    text: str = ""
    action_name: str = ""
    action_input: dict[str, Any] = Field(default_factory=dict)
    observation: str = ""
    blocked: bool = False


class AgentState(TypedDict):
    conversation_key: str
    event_type: str
    user_text: str
    reaction: str | None
    react_step: int
    react_max_steps: int
    react_done: bool
    react_notes: list[str]
    reasoning_note: str
    selected_action: str
    selected_skill: str
    action_input: dict[str, Any]
    skill_input: dict[str, Any]
    action_output: dict[str, Any]
    skill_output: dict[str, Any]
    execution_trace: list[dict[str, Any]]
    reply_text: str
