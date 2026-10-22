"""Autarkia — tool governance for AI agents.

Registry, risk levels, role-based access, visibility rules, and execution
guards for LLM tool calling. The tool layer of the Autarkia agent runtime.
"""

__version__ = "0.1.0"

from autarkia.tools import (
    BaseTool,
    RolePolicyResolver,
    RoleToolPolicy,
    ToolCatalog,
    ToolDeclaration,
    ToolDiscoveryMetadata,
    ToolRegistry,
    ToolVisibilityContext,
    ToolVisibilityRules,
    execute_tool_call,
    filter_tool_names,
)

__all__ = [
    "BaseTool",
    "RolePolicyResolver",
    "RoleToolPolicy",
    "ToolCatalog",
    "ToolDeclaration",
    "ToolDiscoveryMetadata",
    "ToolRegistry",
    "ToolVisibilityContext",
    "ToolVisibilityRules",
    "execute_tool_call",
    "filter_tool_names",
]
