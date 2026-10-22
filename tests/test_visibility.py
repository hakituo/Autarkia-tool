from autarkia.tools import RoleToolPolicy, ToolRegistry, filter_tool_names
from tests.conftest import EchoTool


def _persona(**tool_access):
    return {"tool_access": tool_access}


def test_no_rules_everything_passes():
    names = ["echo", "time", "run_code"]
    assert filter_tool_names(names) == names


def test_policy_blocks_disabled():
    policy = RoleToolPolicy("r", resident=("echo",), on_demand=(), disabled=("run_code",))
    result = filter_tool_names(["echo", "time", "run_code"], policy=policy)
    assert result == ["echo"]


def test_deny_names():
    result = filter_tool_names(
        ["echo", "time"], persona_data=_persona(deny_names=["echo"]),
    )
    assert result == ["time"]


def test_deny_categories_and_category_resolution():
    registry = ToolRegistry()
    echo = EchoTool()
    echo.category = "device"
    registry.register(echo)
    result = filter_tool_names(
        ["echo", "plain"], tool_registry=registry,
        persona_data=_persona(deny_categories=["device"]),
    )
    # "echo" resolves to category "device" via the registry and is denied;
    # "plain" has no registry entry, hence no category, and passes.
    assert result == ["plain"]


def test_dedupes_and_strips_blanks():
    # None would be stringified to "None" — callers pass real names.
    assert filter_tool_names(["echo", " echo ", ""]) == ["echo"]


def test_mode_rules_overlay():
    persona = {
        "tool_access": {
            "mode_rules": {"study": {"deny_names": ["time"]}},
        },
    }
    assert filter_tool_names(["echo", "time"], persona_data=persona, mode="chat") == ["echo", "time"]
    assert filter_tool_names(["echo", "time"], persona_data=persona, mode="study") == ["echo"]


def test_sensitive_mode_overlay():
    persona = {
        "tool_access": {"sensitive_mode": {"allow_names": ["scene_a"]}},
        # nothing else — sensitive overlay only adds when present
    }
    persona_deny = {"tool_access": {"sensitive_mode": {"deny_names": ["time"]}}}
    assert filter_tool_names(["echo", "time"], persona_data=persona, is_sensitive_mode=True) == ["echo", "time"]
    assert filter_tool_names(["echo", "time"], persona_data=persona_deny, is_sensitive_mode=True) == ["echo"]


def test_allow_reopens_default_hidden():
    hidden_names = ["scene_a"]
    result = filter_tool_names(
        ["echo", "scene_a"],
        default_hidden_names=hidden_names,
    )
    assert result == ["echo"]
    result = filter_tool_names(
        ["echo", "scene_a"],
        persona_data=_persona(allow_names=["scene_a"]),
        default_hidden_names=hidden_names,
    )
    assert result == ["echo", "scene_a"]


def test_default_hidden_category_needs_registry_category():
    # Without a registry, no category can be resolved, so the tool name
    # path of the default-hidden check applies instead.
    result = filter_tool_names(
        ["scene_a"], default_hidden_categories=("scene",),
    )
    assert result == ["scene_a"]


def test_is_available_for_persona_hook():
    registry = ToolRegistry()
    tool = EchoTool()
    tool.is_available_for_persona = lambda filename: filename != "restricted"
    registry.register(tool)

    assert filter_tool_names(["echo"], tool_registry=registry, persona_filename="free") == ["echo"]
    assert filter_tool_names(["echo"], tool_registry=registry, persona_filename="restricted") == []


def test_policy_and_rules_compose():
    policy = RoleToolPolicy("r", resident=("echo", "time"), on_demand=(), disabled=("run_code",))
    result = filter_tool_names(
        ["echo", "time", "run_code"],
        policy=policy,
        persona_data=_persona(deny_names=["time"]),
    )
    assert result == ["echo"]
