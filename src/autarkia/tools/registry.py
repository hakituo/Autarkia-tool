"""ToolRegistry — registration, enable/disable, schema export, discovery.

Ported from the Autarkia runtime. Host config/debug hooks became plain
stdlib logging, and the host's tool assembly function was dropped (the
library only ships the governance layer, not concrete tools).

The OpenAI schema cache is byte-stable on purpose: the ``tools`` payload
participates in API-side prompt-cache keys, so rebuilding it per request
with unstable content would cache-miss every call.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from autarkia.tools.base import BaseTool
from autarkia.tools.metadata import (
    ToolCatalog,
    ToolDiscoveryMetadata,
    search_tool_metadata,
)

logger = logging.getLogger("autarkia.tools")

DEFAULT_PROMPT_HEADER = "Available tools:\n"
DEFAULT_PROMPT_RULES = (
    "\nTool rules:\n"
    "- Tools are invoked through the native function-calling mechanism when needed.\n"
    "- Replies to the user must contain natural language only; never mention tool mechanics.\n"
    "- After a tool result comes back, answer in natural language."
)


class ToolRegistry:
    """Holds tool instances and their runtime enable/disable state."""

    def __init__(self, catalog: Optional[ToolCatalog] = None) -> None:
        self._tools: Dict[str, BaseTool] = {}
        # Per-tool runtime enable/disable (overrides enabled_by_default).
        self._disabled: Set[str] = set()
        self._catalog = catalog
        self._openai_tools_all_cache: Optional[List[Dict[str, Any]]] = None
        self._openai_tools_by_names_cache: Dict[Tuple[frozenset, frozenset], List[Dict[str, Any]]] = {}

    # -- registration -------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        self._invalidate_openai_tools_cache()

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    # -- enable / disable ----------------------------------------------

    def enable_tool(self, name: str) -> bool:
        """Re-enable a previously disabled tool."""
        if name in self._tools:
            self._disabled.discard(name)
            self._invalidate_openai_tools_cache()
            return True
        return False

    def disable_tool(self, name: str) -> bool:
        """Disable a tool at runtime (won't appear in prompts or be callable)."""
        if name in self._tools:
            self._disabled.add(name)
            self._invalidate_openai_tools_cache()
            return True
        return False

    def is_enabled(self, name: str) -> bool:
        """Check if a tool is currently enabled."""
        if name not in self._tools:
            return False
        return name not in self._disabled and self._tools[name].enabled_by_default

    def get_active_tools(self) -> List[str]:
        """Return currently enabled tool names."""
        return [name for name in self._tools if self.is_enabled(name)]

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """Return enabled tools belonging to a category."""
        return [
            tool for name, tool in self._tools.items()
            if self.is_enabled(name) and tool.category == category
        ]

    def _invalidate_openai_tools_cache(self) -> None:
        self._openai_tools_all_cache = None
        self._openai_tools_by_names_cache = {}

    # -- discovery ------------------------------------------------------

    def get_tool_metadata(self, name: str) -> Optional[ToolDiscoveryMetadata]:
        """Discovery metadata, or None when the tool is undeclared.

        Without a catalog the registry cannot know any tool's risk
        profile, so it reports none — risk is never guessed.
        """
        tool = self.get_tool(name)
        if tool is None or self._catalog is None:
            return None
        return self._catalog.build(tool)

    def list_tool_metadata(
        self, include_names: Optional[Sequence[str]] = None
    ) -> List[ToolDiscoveryMetadata]:
        """Metadata for enabled tools, in registration order."""
        allowed = set(include_names) if include_names is not None else None
        items: List[ToolDiscoveryMetadata] = []
        for name, tool in self._tools.items():
            if not self.is_enabled(name):
                continue
            if allowed is not None and name not in allowed:
                continue
            metadata = self.get_tool_metadata(name)
            if metadata is not None:
                items.append(metadata)
        return items

    def search_tools(
        self,
        query: str,
        *,
        include_names: Optional[Sequence[str]] = None,
        limit: int = 5,
    ) -> List[ToolDiscoveryMetadata]:
        """Search only within the given visible tool set."""
        return search_tool_metadata(
            self.list_tool_metadata(include_names=include_names),
            query,
            limit=limit,
        )

    # -- prompt rendering -----------------------------------------------

    def get_tools_description(self, include_names: Optional[Sequence[str]] = None) -> str:
        """Formatted description of available tools (compact args summary)."""
        descriptions = []
        allowed = set(include_names) if include_names is not None else None
        for name, tool in self._tools.items():
            if not self.is_enabled(name):
                continue
            if allowed is not None and name not in allowed:
                continue
            desc_text = tool.short_description or tool.description
            args_simple: Dict[str, str] = {}
            if tool.args_schema:
                schema = _model_schema(tool.args_schema)
                for prop_name, prop_info in schema.get("properties", {}).items():
                    typ = prop_info.get("type", "any")
                    mark = "*" if prop_name in schema.get("required", []) else ""
                    args_simple[f"{prop_name}{mark}"] = f"{typ} - {prop_info.get('description', '')}"
            args_desc = json.dumps(args_simple, ensure_ascii=False)
            descriptions.append(f"- {name}: {desc_text} | Args: {args_desc}")
        return "\n".join(descriptions)

    def get_concise_tool_prompt(
        self,
        include_categories: Optional[Sequence[str]] = None,
        exclude_categories: Optional[Sequence[str]] = None,
        include_names: Optional[Sequence[str]] = None,
        *,
        header: str = DEFAULT_PROMPT_HEADER,
        rules: str = DEFAULT_PROMPT_RULES,
    ) -> str:
        """Minimal name + hint list for prompt injection; template overridable."""
        lines = []
        include_cat = set(include_categories) if include_categories else None
        exclude_cat = set(exclude_categories) if exclude_categories else None
        allowed = set(include_names) if include_names is not None else None
        for name, tool in self._tools.items():
            if not self.is_enabled(name):
                continue
            if allowed is not None and name not in allowed:
                continue
            if include_cat is not None and tool.category not in include_cat:
                continue
            if exclude_cat is not None and tool.category in exclude_cat:
                continue
            metadata = self.get_tool_metadata(name)
            hint = (
                metadata.short_description
                if metadata is not None
                else tool.short_description or tool.description.split("。")[0].split(".")[0]
            )
            if len(hint) > 60:
                hint = hint[:57] + "..."
            lines.append(f"- {name}: {hint}")
        if not lines:
            return ""
        return header + "\n".join(lines) + rules

    # -- function calling -------------------------------------------------

    def get_openai_tools(
        self,
        include_names: Optional[Sequence[str]] = None,
        exclude_categories: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """OpenAI function-calling schema list for the ``tools`` parameter.

        Cached per tool set; cache keys include ``include_names`` and
        ``exclude_categories`` so different views never share entries.
        """
        if include_names is not None:
            key = (frozenset(include_names), frozenset(exclude_categories or ()))
            cached = self._openai_tools_by_names_cache.get(key)
            if cached is not None:
                return list(cached)
            tools = self._build_openai_tools_schema(
                include_names=list(include_names), exclude_categories=exclude_categories
            )
            self._openai_tools_by_names_cache[key] = tools
            return list(tools)

        if exclude_categories is not None:
            return self._build_openai_tools_schema(exclude_categories=exclude_categories)

        if self._openai_tools_all_cache is not None:
            return list(self._openai_tools_all_cache)
        tools = self._build_openai_tools_schema()
        self._openai_tools_all_cache = tools
        return list(tools)

    def _build_openai_tools_schema(
        self,
        include_names: Optional[List[str]] = None,
        exclude_categories: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        tools = []
        for name, tool in self._tools.items():
            if not self.is_enabled(name):
                continue
            if include_names is not None and name not in include_names:
                continue
            if exclude_categories and tool.category in exclude_categories:
                continue

            parameters: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
            if tool.args_schema:
                schema = _model_schema(tool.args_schema)
                parameters["properties"] = schema.get("properties", {})
                parameters["required"] = schema.get("required", [])
                # Nested pydantic models emit $defs/$ref; omitting them breaks
                # strict parsers with "Pointer '/$defs/XXX' does not exist".
                defs = schema.get("$defs")
                if defs:
                    parameters["$defs"] = defs
                parameters["additionalProperties"] = False

            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                },
            })
        return tools


def _model_schema(model: Any) -> Dict[str, Any]:
    """Schema for pydantic v2 models; v1 fallback kept for convenience."""
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()
    return model.schema()
