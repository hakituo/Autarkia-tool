from autarkia.tools import ToolCatalog, ToolDeclaration, ToolRegistry
from tests.conftest import EchoTool, Nested, NestedArgs


class NestedTool(EchoTool):
    name = "nested"
    description = "Takes a nested pydantic model."
    args_schema = NestedArgs


def _registry(*tools, catalog=None):
    registry = ToolRegistry(catalog=catalog)
    for tool in tools:
        registry.register(tool)
    return registry


def test_register_and_defaults():
    registry = _registry(EchoTool())
    assert registry.get_tool("echo") is not None
    assert registry.is_enabled("echo") is True
    assert registry.get_active_tools() == ["echo"]
    assert registry.get_tool("ghost") is None


def test_enable_disable_roundtrip():
    registry = _registry(EchoTool())
    assert registry.disable_tool("echo") is True
    assert registry.is_enabled("echo") is False
    assert registry.get_active_tools() == []
    assert registry.enable_tool("echo") is True
    assert registry.is_enabled("echo") is True


def test_disable_unknown_tool_returns_false():
    registry = _registry(EchoTool())
    assert registry.disable_tool("ghost") is False
    assert registry.enable_tool("ghost") is False


def test_enabled_by_default_false_is_never_active():
    registry = ToolRegistry()
    tool = EchoTool()
    tool.enabled_by_default = False
    registry.register(tool)
    assert registry.is_enabled("echo") is False
    assert registry.get_active_tools() == []


def test_openai_schema_shape_and_cache():
    registry = _registry(EchoTool(), NestedTool())
    schema = registry.get_openai_tools()
    names = [t["function"]["name"] for t in schema]
    assert names == ["echo", "nested"]

    echo_def = schema[0]["function"]
    assert schema[0]["type"] == "function"
    params = echo_def["parameters"]
    assert params["additionalProperties"] is False
    assert params["required"] == ["text"]

    nested_params = schema[1]["function"]["parameters"]
    assert "$defs" in nested_params  # nested pydantic models emit $defs

    # Byte-stable across calls (prompt-cache friendly).
    assert registry.get_openai_tools() == schema


def test_disable_invalidates_schema_cache():
    registry = _registry(EchoTool(), NestedTool())
    before = registry.get_openai_tools()
    registry.disable_tool("nested")
    after = registry.get_openai_tools()
    assert [t["function"]["name"] for t in after] == ["echo"]
    assert before != after


def test_schema_respects_include_names():
    registry = _registry(EchoTool(), NestedTool())
    picked = registry.get_openai_tools(include_names=["nested"])
    assert [t["function"]["name"] for t in picked] == ["nested"]
    # Different include sets must not share cache entries.
    assert [t["function"]["name"] for t in registry.get_openai_tools(include_names=["echo"])] == ["echo"]


def test_metadata_requires_catalog():
    registry = _registry(EchoTool())
    assert registry.get_tool_metadata("echo") is None
    assert registry.search_tools("echo") == []


def test_metadata_and_search_with_catalog():
    catalog = ToolCatalog()
    catalog.declare("echo", ToolDeclaration(
        domain="utility", risk_level="read", load_policy="base", tags=("demo",),
    ))
    catalog.declare("nested", ToolDeclaration(
        domain="utility", risk_level="write", load_policy="on_demand",
    ))
    registry = _registry(EchoTool(), NestedTool(), catalog=catalog)

    meta = registry.get_tool_metadata("echo")
    assert meta is not None and meta.risk_level == "read"

    hits = registry.search_tools("echo")
    assert hits and hits[0].name == "echo"

    registry.disable_tool("echo")
    # Registry-level lookup still resolves (registration ≠ visibility),
    # but discovery only lists enabled tools.
    assert registry.get_tool_metadata("echo") is not None
    assert [m.name for m in registry.search_tools("echo")] == []  # "echo" matches nothing now
    assert [m.name for m in registry.search_tools("nested")] == ["nested"]


def test_tools_description_compact_args():
    registry = _registry(EchoTool())
    text = registry.get_tools_description()
    assert "- echo: Echo the given text back." in text
    assert "text* (string)" in text or "text*: string" in text or "text*" in text


def test_concise_prompt_customizable_template():
    registry = _registry(EchoTool())
    catalog = ToolCatalog()
    catalog.declare("echo", ToolDeclaration(domain="utility", short_description="回显文本"))
    registry2 = ToolRegistry(catalog=catalog)
    registry2.register(EchoTool())

    prompt = registry.get_concise_tool_prompt()
    assert prompt.startswith("Available tools:")
    assert "- echo: Echo the given text back" in prompt  # trailing period trimmed by compaction

    custom = registry2.get_concise_tool_prompt(
        header="【可用工具】\n", rules="\n【规则】不要提工具。"
    )
    assert custom.startswith("【可用工具】")
    assert "回显文本" in custom


def test_get_tools_by_category():
    registry = _registry(EchoTool())
    assert registry.get_tools_by_category("utility")
    assert registry.get_tools_by_category("device") == []
