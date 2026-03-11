from teambot.actions.event_handlers.builtin import build_registry as build_event_handler_registry
from teambot.actions.tools.registry import ToolManifest, ToolRegistry
from teambot.domain.models import AgentState
from teambot.actions.registry import PluginHost


def _state() -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "recent_turns": [],
        "conversation_summary": "",
        "memory_system_prompt_suffix": "",
        "event_type": "message",
        "user_text": "hello",
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "active_skill_names": [],
        "active_skill_docs": [],
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }


def test_plugin_host_unifies_event_handler_and_tool_actions() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="tool_echo", description="echo", risk_level="low"),
        lambda state: {"message": f"echo:{state['user_text']}"},
    )

    host = PluginHost()
    host.bind_event_handler_registry(build_event_handler_registry())
    host.bind_tool_registry(tools)

    names = {action.name for action in host.list_actions()}
    assert {"create_task", "tool_echo"} <= names

    result = host.invoke("tool_echo", _state())
    assert result["message"] == "echo:hello"
    assert result["_action_source"] == "tool"
    assert result["_action_name"] == "tool_echo"


def test_plugin_host_activation_toggle() -> None:
    host = PluginHost()
    host.bind_event_handler_registry(build_event_handler_registry())

    assert host.has_action("create_task") is True
    assert host.deactivate("create_task") is True
    assert host.has_action("create_task") is False
    assert host.activate("create_task") is True
    assert host.has_action("create_task") is True
