import pytest

from autarkia.tools import ToolCatalog, ToolDeclaration, search_tool_metadata
from autarkia.tools.metadata import ToolDiscoveryMetadata, RISK_LEVELS, LOAD_POLICIES
from tests.conftest import EchoTool


def test_declaration_rejects_unknown_risk_level():
    with pytest.raises(ValueError, match="risk_level"):
        ToolDeclaration(domain="utility", risk_level="extremely_dangerous")


def test_declaration_rejects_unknown_load_policy():
    with pytest.raises(ValueError, match="load_policy"):
        ToolDeclaration(domain="utility", load_policy="sometimes")


def test_risk_levels_are_ordered_least_to_most_dangerous():
    assert RISK_LEVELS == (
        "read", "write", "external_write", "device_read", "device_control", "sensitive",
    )
    assert LOAD_POLICIES == ("base", "on_demand", "hidden")


def test_undeclared_tool_builds_no_metadata():
    catalog = ToolCatalog()
    catalog.declare("other", ToolDeclaration(domain="utility"))
    assert catalog.build(EchoTool()) is None


def test_declared_tool_builds_metadata():
    catalog = ToolCatalog()
    catalog.declare("echo", ToolDeclaration(
        domain="utility", risk_level="read", load_policy="base", tags=("demo",),
    ))
    meta = catalog.build(EchoTool())
    assert meta is not None
    assert meta.name == "echo"
    assert meta.domain == "utility"
    assert meta.risk_level == "read"
    assert meta.load_policy == "base"
    assert meta.tags == ("demo",)
    assert meta.short_description  # derived from description


def test_domain_of_and_membership_helpers():
    catalog = ToolCatalog()
    catalog.declare("echo", ToolDeclaration(domain="utility"))
    assert catalog.domain_of("echo") == "utility"
    assert catalog.domain_of("nope") == ""
    assert catalog.has("echo") is True
    assert catalog.names() == ("echo",)


def test_search_exact_name_match_first():
    catalog = ToolCatalog()
    catalog.declare("echo", ToolDeclaration(domain="utility", tags=("repeat",)))
    catalog.declare("echoes_history", ToolDeclaration(domain="utility", tags=("history",)))
    echo_meta = catalog.build(EchoTool())

    results = search_tool_metadata(
        [catalog.build(t) for t in _all_tools(catalog)], "echo", limit=5
    )
    assert results[0].name == "echo"


def test_search_cjk_bigram_matching():
    meta = ToolDiscoveryMetadata(
        name="search_memory", domain="memory", tags=("记忆", "聊天历史"),
        risk_level="read", load_policy="on_demand", short_description="搜索记忆",
    )
    results = search_tool_metadata([meta], "聊天")
    assert results and results[0].name == "search_memory"


def test_search_respects_limit_and_stable_order():
    metas = [
        ToolDiscoveryMetadata(
            name=f"tool_{i}", domain="utility", tags=("demo",),
            risk_level="read", load_policy="on_demand", short_description="demo tool",
        )
        for i in range(10)
    ]
    results = search_tool_metadata(metas, "demo", limit=3)
    assert len(results) == 3
    # Equal scores keep registration order (stable sort, index tiebreak).
    assert [m.name for m in results] == ["tool_0", "tool_1", "tool_2"]


def test_search_empty_query_returns_empty():
    assert search_tool_metadata([], "") == []


def _all_tools(catalog):
    tools = []
    for name in catalog.names():
        tool = EchoTool()
        tool.name = name
        tools.append(tool)
    return tools
