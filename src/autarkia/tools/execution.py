"""Unified execution boundary: authorization snapshot + per-call isolation.

Ported from the Autarkia runtime unchanged in behavior — it is already
host-free. This is the last line of defense before a tool runs.
"""

from copy import copy
import json
from typing import Any, List, Mapping, Optional


async def execute_tool_call(
    *,
    agent: Any,
    tool_name: str,
    arguments: Mapping[str, Any],
    user_id: str,
    allowed_tool_names: List[str],
    persona_filename: Optional[str] = None,
    is_sensitive_mode: bool = False,
    used_tool_names: Optional[List[str]] = None,
    last_user_text: str = "",
) -> str:
    """Execute one tool call against the request's own authorization snapshot.

    The model never picks roles, paths, or permissions here — everything
    comes from the orchestrator's snapshot for this request.

    ``used_tool_names`` collects what was authorized *and* actually
    dispatched (not what succeeded — ``BaseTool.run()`` turns tool errors
    into strings by design, and a timed-out weather call is exactly the
    thing the next turn should be allowed to retry).

    ``last_user_text`` carries the raw user message for tools that must
    only reference what the user actually said.
    """
    registry = getattr(agent, "tool_registry", None)
    if tool_name not in allowed_tool_names or registry is None or not registry.is_enabled(tool_name):
        return json.dumps(
            {"ok": False, "error": "tool not allowed for the current role", "tool": tool_name},
            ensure_ascii=False,
        )
    if not isinstance(arguments, Mapping):
        return json.dumps(
            {"ok": False, "error": "tool arguments must be an object", "tool": tool_name},
            ensure_ascii=False,
        )
    # The registry stores reusable implementations; every call gets an
    # isolated copy so concurrent roles cannot bleed state into each other.
    tool = copy(registry.get_tool(tool_name))
    tool.set_runtime_context({
        "agent": agent,
        "user_id": user_id,
        "persona_filename": persona_filename,
        "scope": "sensitive" if is_sensitive_mode else "sfw",
        "allowed_tool_names": list(allowed_tool_names),
        "last_user_text": str(last_user_text or ""),
    })
    if used_tool_names is not None and tool_name not in used_tool_names:
        used_tool_names.append(tool_name)
    return await tool.run(**dict(arguments))
