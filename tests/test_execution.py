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


# -- registry-first contract (no host object required) ----------------------


def _registry(*tools):
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def test_registry_only_call_needs_no_host_object():
    EchoTool.context_log.clear()
    result = asyncio.run(execute_tool_call(
        registry=_registry(EchoTool()),
        tool_name="echo",
        arguments={"text": "hi"},
        allowed_tool_names=["echo"],
        user_id="u1",
    ))
    assert result == "hi"
    ctx = EchoTool.context_log[-1]
    assert ctx["user_id"] == "u1"
    assert ctx["scope"] == "sfw"
    # No host object was passed, so nothing pretending to be one is injected.
    assert "agent" not in ctx


def test_missing_registry_is_rejected():
    result = json.loads(asyncio.run(execute_tool_call(
        tool_name="echo", arguments={}, allowed_tool_names=["echo"],
    )))
    assert result["ok"] is False
    assert "registry" in result["error"]


def test_registry_authorization_still_applies():
    result = json.loads(asyncio.run(execute_tool_call(
        registry=_registry(EchoTool()),
        tool_name="echo",
        arguments={"text": "x"},
        allowed_tool_names=[],
    )))
    assert result["ok"] is False
    assert "not allowed" in result["error"]


def test_explicit_context_is_merged():
    EchoTool.context_log.clear()
    asyncio.run(execute_tool_call(
        registry=_registry(EchoTool()),
        tool_name="echo",
        arguments={"text": "x"},
        allowed_tool_names=["echo"],
        context={"is_master": True, "tenant": "t1"},
    ))
    ctx = EchoTool.context_log[-1]
    assert ctx["is_master"] is True
    assert ctx["tenant"] == "t1"
    assert ctx["scope"] == "sfw"


def test_explicit_context_overrides_derived_values():
    EchoTool.context_log.clear()
    asyncio.run(execute_tool_call(
        registry=_registry(EchoTool()),
        tool_name="echo",
        arguments={"text": "x"},
        allowed_tool_names=["echo"],
        user_id="derived",
        context={"user_id": "override", "scope": "trusted"},
    ))
    ctx = EchoTool.context_log[-1]
    assert ctx["user_id"] == "override"
    assert ctx["scope"] == "trusted"


def test_allowed_names_accept_any_iterable():
    EchoTool.context_log.clear()
    asyncio.run(execute_tool_call(
        registry=_registry(EchoTool()),
        tool_name="echo",
        arguments={"text": "y"},
        allowed_tool_names=(name for name in ("echo",)),
    ))
    assert EchoTool.context_log[-1]["allowed_tool_names"] == ["echo"]


def test_context_does_not_leak_between_calls():
    EchoTool.context_log.clear()
    registry = _registry(EchoTool())
    asyncio.run(execute_tool_call(
        registry=registry, tool_name="echo", arguments={"text": "a"},
        allowed_tool_names=["echo"], context={"is_master": True},
    ))
    asyncio.run(execute_tool_call(
        registry=registry, tool_name="echo", arguments={"text": "b"},
        allowed_tool_names=["echo"],
    ))
    assert EchoTool.context_log[0]["is_master"] is True
    assert "is_master" not in EchoTool.context_log[1]


def test_legacy_agent_path_keeps_agent_in_context():
    EchoTool.context_log.clear()
    asyncio.run(execute(_agent(EchoTool()), arguments={"text": "x"}))
    assert isinstance(EchoTool.context_log[-1]["agent"], Agent)
