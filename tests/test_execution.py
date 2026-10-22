import asyncio
import json

from tests.conftest import Agent, EchoTool, MutatingTool
from autarkia.tools import ToolRegistry, execute_tool_call


def _agent(*tools):
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return Agent(registry)


def execute(agent, *, tool_name="echo", arguments=None, allowed_tool_names=None, user_id="user-1", **kwargs):
    if allowed_tool_names is None:
        allowed_tool_names = ["echo", "mutate"]
    return execute_tool_call(
        agent=agent,
        tool_name=tool_name,
        arguments=arguments if arguments is not None else {},
        user_id=user_id,
        allowed_tool_names=allowed_tool_names,
        **kwargs,
    )


def test_unauthorized_tool_is_rejected():
    agent = _agent(EchoTool())
    result = json.loads(asyncio.run(execute(agent, tool_name="echo", allowed_tool_names=[])))
    assert result["ok"] is False
    assert "not allowed" in result["error"]
    assert result["tool"] == "echo"


def test_runtime_disabled_tool_is_rejected_even_if_allowed():
    agent = _agent(EchoTool())
    agent.tool_registry.disable_tool("echo")
    result = json.loads(asyncio.run(execute(agent, tool_name="echo", allowed_tool_names=["echo"])))
    assert result["ok"] is False


def test_non_mapping_arguments_rejected():
    agent = _agent(EchoTool())
    result = json.loads(asyncio.run(execute(agent, arguments=["not", "a", "dict"])))
    assert result["ok"] is False
    assert "arguments" in result["error"]


def test_authorized_call_runs_with_injected_context():
    agent = _agent(EchoTool())
    result = asyncio.run(execute(
        agent, tool_name="echo",
        arguments={"text": "hi"},
        persona_filename="ling.json",
        last_user_text="please repeat hi",
    ))
    assert result == "hi"
    ctx = EchoTool.context_log[-1]
    assert ctx["user_id"] == "user-1"
    assert ctx["persona_filename"] == "ling.json"
    assert ctx["scope"] == "sfw"
    assert ctx["last_user_text"] == "please repeat hi"


def test_sensitive_mode_sets_scope():
    agent = _agent(EchoTool())
    asyncio.run(execute(agent, tool_name="echo", arguments={"text": "x"}, is_sensitive_mode=True))
    assert EchoTool.context_log[-1]["scope"] == "sensitive"


def test_used_tool_names_records_dispatch():
    agent = _agent(EchoTool())
    used: list = []
    asyncio.run(execute(agent, tool_name="echo", arguments={"text": "x"}, used_tool_names=used))
    assert used == ["echo"]

    # No duplicates across retries within the same request.
    asyncio.run(execute(agent, tool_name="echo", arguments={"text": "x"}, used_tool_names=used))
    assert used == ["echo"]


def test_per_call_context_isolation():
    """Two sequential calls must not share runtime context."""
    tool = MutatingTool()
    MutatingTool.context_log.clear()
    EchoTool.context_log.clear()
    agent = _agent(tool)
    asyncio.run(execute(agent, tool_name="mutate", arguments={"marker": "a"},
                        user_id="u1", persona_filename="ling.json"))
    asyncio.run(execute(agent, tool_name="mutate", arguments={"marker": "b"},
                        user_id="u2", persona_filename="ye.json"))
    assert EchoTool.context_log == []
    assert [ctx["user_id"] for ctx in MutatingTool.context_log] == ["u1", "u2"]
    assert [ctx["persona_filename"] for ctx in MutatingTool.context_log] == ["ling.json", "ye.json"]
    # ran_for is shared through the shallow copy, so both markers are visible.
    assert tool.ran_for == ["a", "b"]


def test_agent_without_registry_rejected():
    class BareAgent:
        pass

    result = json.loads(asyncio.run(execute(BareAgent(), tool_name="echo")))
    assert result["ok"] is False
