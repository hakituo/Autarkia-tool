"""Tool visibility: persona allow/deny with mode and sensitive-mode overlays.

Ported from the Autarkia runtime. The host's persona-manager singleton
lookups were removed — callers pass ``persona_data`` explicitly, which
keeps the filter pure and concurrency-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from autarkia.tools.policy import RoleToolPolicy


@dataclass(frozen=True)
class ToolVisibilityContext:
    """Who is asking, in which mode."""

    persona_filename: str = ""
    mode: str = "chat"
    is_sensitive_mode: bool = False


@dataclass
class ToolVisibilityRules:
    """Merged allow/deny sets by tool name and category."""

    allow_names: Set[str] = field(default_factory=set)
    deny_names: Set[str] = field(default_factory=set)
    allow_categories: Set[str] = field(default_factory=set)
    deny_categories: Set[str] = field(default_factory=set)

    def merge(self, other: "ToolVisibilityRules") -> "ToolVisibilityRules":
        self.allow_names.update(other.allow_names)
        self.deny_names.update(other.deny_names)
        self.allow_categories.update(other.allow_categories)
        self.deny_categories.update(other.deny_categories)
        return self


def _normalize_string_set(values: Any) -> Set[str]:
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {
        str(item).strip()
        for item in values
        if isinstance(item, (str, int, float)) and str(item).strip()
    }


def _rules_from_dict(raw_rules: Any) -> ToolVisibilityRules:
    if not isinstance(raw_rules, dict):
        return ToolVisibilityRules()
    return ToolVisibilityRules(
        allow_names=_normalize_string_set(raw_rules.get("allow_names")),
        deny_names=_normalize_string_set(raw_rules.get("deny_names")),
        allow_categories=_normalize_string_set(raw_rules.get("allow_categories")),
        deny_categories=_normalize_string_set(raw_rules.get("deny_categories")),
    )


def get_tool_access_config(persona_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Read the ``tool_access`` block from a persona dict.

    Also accepts the nested ``interaction_logic.tool_access`` shape.
    """
    if not isinstance(persona_data, dict):
        return {}

    tool_access = persona_data.get("tool_access")
    if isinstance(tool_access, dict):
        return tool_access

    interaction_logic = persona_data.get("interaction_logic")
    if isinstance(interaction_logic, dict):
        nested_access = interaction_logic.get("tool_access")
        if isinstance(nested_access, dict):
            return nested_access
    return {}


def get_effective_visibility_rules(
    context: ToolVisibilityContext,
    persona_data: Optional[Dict[str, Any]] = None,
) -> ToolVisibilityRules:
    """Merge base rules with mode and sensitive-mode overlays."""
    config = get_tool_access_config(persona_data)

    rules = ToolVisibilityRules()
    rules.merge(_rules_from_dict(config))

    mode_rules = config.get("mode_rules")
    if isinstance(mode_rules, dict):
        rules.merge(_rules_from_dict(mode_rules.get(context.mode)))

    if context.is_sensitive_mode:
        rules.merge(_rules_from_dict(config.get("sensitive_mode")))

    return rules


def filter_tool_names(
    tool_names: Iterable[str],
    *,
    policy: Optional[RoleToolPolicy] = None,
    persona_data: Optional[Dict[str, Any]] = None,
    persona_filename: str = "",
    mode: str = "chat",
    is_sensitive_mode: bool = False,
    tool_registry: Any = None,
    default_hidden_categories: Iterable[str] = (),
    default_hidden_names: Iterable[str] = (),
) -> List[str]:
    """Filter tool names by role policy, persona rules, and mode context.

    Args:
        policy: resolved :class:`RoleToolPolicy`; ``None`` skips the
            role-policy pass.
        persona_data: the persona dict; its ``tool_access`` (optionally
            nested under ``interaction_logic``) provides allow/deny rules.
        default_hidden_*: deployment-level hidden lists. Explicit
            ``allow_*`` rules re-admit tools hidden by default.

    Design principles kept from the original:
    - persona can open or close tools/categories explicitly
    - ``mode_rules`` / ``sensitive_mode`` overlay on top
    - tools may expose ``is_available_for_persona(filename)`` for
      per-persona availability; not callable means available
    """
    context = ToolVisibilityContext(
        persona_filename=str(persona_filename or "").strip(),
        mode=str(mode or "chat").strip() or "chat",
        is_sensitive_mode=bool(is_sensitive_mode),
    )
    rules = get_effective_visibility_rules(context, persona_data=persona_data)

    default_hidden_categories = set(default_hidden_categories)
    default_hidden_names = set(default_hidden_names)
    default_hidden_categories.difference_update(rules.allow_categories)
    default_hidden_names.difference_update(rules.allow_names)

    filtered_names: List[str] = []
    seen_names: Set[str] = set()
    for raw_name in tool_names:
        tool_name = str(raw_name).strip()
        if not tool_name or tool_name in seen_names:
            continue
        seen_names.add(tool_name)

        if policy is not None and not policy.allows(tool_name):
            continue

        tool = tool_registry.get_tool(tool_name) if hasattr(tool_registry, "get_tool") else None
        tool_category = (
            str(getattr(tool, "category", "") or "").strip() if tool is not None else ""
        )

        if tool_name in rules.deny_names:
            continue
        if tool_category and tool_category in rules.deny_categories:
            continue
        if not tool_category and tool_name in default_hidden_names:
            continue
        if tool_category and tool_category in default_hidden_categories:
            continue

        availability = getattr(tool, "is_available_for_persona", None)
        if callable(availability) and not availability(context.persona_filename):
            continue

        filtered_names.append(tool_name)

    return filtered_names
