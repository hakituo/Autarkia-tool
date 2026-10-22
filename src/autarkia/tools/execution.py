"""Execution boundary: authorization snapshot + per-call isolation.

Ported from the Autarkia runtime unchanged in behavior — it is already
host-free. This is the last line of defense before a tool runs.

Integration contract: the caller passes the registry it authorized against
(``registry=``) plus an optional ``context`` mapping. Nothing here reaches
for global state, a singleton, or a framework object. The older ``agent=``
parameter still works for backwards compatibility — it is only used to read
``agent.tool_registry`` and is copied into the tool context as before.
"""

from __future__ import annotations

from copy import copy
import json
from typing import Any, Iterable, List, Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class ToolHost(Protocol):
    """Minimal host contract for the legacy ``agent=`` path.

    Any object exposing ``tool_registry`` satisfies it. New code should pass
    ``registry=`` directly instead of shaping an object for the library.
    """

    tool_registry: Any


def _error(message: str, tool_name: str) -> str:
    return json.dumps({"ok": False, "error": message, "tool": tool_name}, ensure_ascii=False)


async def execute_tool_call(
    *,
    tool_name: str,
    arguments: Mapping[str, Any],
    registry: Any = None,
    allowed_tool_names: Iterable[str] = (),
    context: Optional[Mapping[str, Any]] = None,
    agent: Any = None,
    user_id: str = "",
    persona_filename: Optional[str] = None,
    is_sensitive_mode: bool = False,
    used_tool_names: Optional[List[str]] = None,
    last_user_text: str = "",
) -> str:
    """Execute one tool call against the request's own authorization snapshot.

    The model never picks roles, paths, or permissions here — everything
    comes from the orchestrator's snapshot for this request.

    Args:
        tool_name: Tool to dispatch.
        arguments: Decoded function-call arguments (must be a mapping).
        registry: The :class:`ToolRegistry` this request was authorized
            against. Required unless ``agent`` is passed.
        allowed_tool_names: The visible/authorized names for this request.
            Empty means "nothing authorized" — a safe default, not "all".
        context: Extra runtime-context keys for the tool. Merged last, so it
            can override the derived ``user_id`` / ``scope`` values.
        agent: Deprecated. Only used to reach ``agent.tool_registry``; it is
            still injected into the tool context so existing tools keep
            working.
        user_id / persona_filename / is_sensitive_mode / last_user_text:
            Convenience keys for the most common context fields.
        used_tool_names: Collects what was authorized *and* actually
            dispatched (not what succeeded — ``BaseTool.run()`` turns tool
            errors into strings by design, and a timed-out weather call is
            exactly the thing the next turn should be allowed to retry).
    """
    allowed = [str(name) for name in (allowed_tool_names or ())]
    resolved_registry = registry if registry is not None else getattr(agent, "tool_registry", None)
    if resolved_registry is None:
        return _error("no tool registry available for this call", tool_name)
    if tool_name not in allowed or not resolved_registry.is_enabled(tool_name):
        return _error("tool not allowed for the current role", tool_name)
    if not isinstance(arguments, Mapping):
        return _error("tool arguments must be an object", tool_name)

    # The registry stores reusable implementations; every call gets an
    # isolated copy so concurrent roles cannot bleed state into each other.
    tool = copy(resolved_registry.get_tool(tool_name))
    runtime_context: dict[str, Any] = {
        "user_id": user_id,
        "persona_filename": persona_filename,
        "scope": "sensitive" if is_sensitive_mode else "sfw",
        "allowed_tool_names": allowed,
        "last_user_text": str(last_user_text or ""),
    }
    if agent is not None:
        runtime_context["agent"] = agent
    if context:
        runtime_context.update(dict(context))
    tool.set_runtime_context(runtime_context)

    if used_tool_names is not None and tool_name not in used_tool_names:
        used_tool_names.append(tool_name)
    return await tool.run(**dict(arguments))


__all__ = ["execute_tool_call", "ToolHost"]
