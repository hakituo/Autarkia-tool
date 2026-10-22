"""BaseTool — what a tool is.

Ported from the Autarkia runtime's tool base class. Host-specific helpers
(QQ master detection, persona scope resolution) were replaced with
runtime-context conventions so the base class stays dependency-free.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel


class BaseTool(ABC):
    """Base class for all tools.

    Class attributes:
        name: unique tool name (used as the registry key).
        description: full description, also used as the function-calling
            description in exported schemas.
        args_schema: optional pydantic model describing the arguments.
        short_description: one-line hint for prompt injection; overrides
            ``description`` when a compact list is rendered.
        category: free-form grouping label (e.g. "memory", "device").
        enabled_by_default: whether the tool is offered before any
            explicit enable/disable call.
    """

    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None
    short_description: Optional[str] = None
    category: str = "utility"
    enabled_by_default: bool = True

    def set_runtime_context(self, context: Dict[str, Any]) -> None:
        """Inject runtime context (agent, user_id, scope, ...) before execution."""
        self._runtime_context = context

    def _get_ctx(self, key: str, default: Any = None) -> Any:
        """Convenience accessor for runtime context keys."""
        return getattr(self, "_runtime_context", {}).get(key, default)

    def is_master(self) -> bool:
        """Whether the current session belongs to a master/admin caller.

        The orchestrator decides what "master" means and injects either
        ``is_master: bool`` or ``master_ids: collection[str]`` alongside
        ``user_id`` into the runtime context.
        """
        if bool(self._get_ctx("is_master", False)):
            return True
        master_ids = self._get_ctx("master_ids")
        if not master_ids:
            return False
        user_id = str(self._get_ctx("user_id") or "").strip()
        return bool(user_id) and user_id in {str(item) for item in master_ids}

    def current_scope(self) -> str:
        """Scope of the current call (role / persona slug / tenant id).

        Resolution order, all injected per request by the orchestrator:
        ``scope`` → ``persona_filename`` → empty string. Never reads
        global singletons, so concurrent roles stay isolated.
        """
        scope = str(self._get_ctx("scope") or "").strip()
        if scope:
            return scope
        return str(self._get_ctx("persona_filename") or "").strip()

    @abstractmethod
    async def _run(self, *args, **kwargs) -> Any:
        """Implementation of the tool."""

    async def run(self, *args, **kwargs) -> str:
        """Execute the tool and return the result as a string.

        Tool-internal exceptions are converted into an error string on
        purpose: the model reads the result either way, and a weather API
        timeout should look like a retryable outcome, not a crash.
        """
        try:
            result = await self._run(*args, **kwargs)
            return str(result)
        except Exception as exc:  # noqa: BLE001 - deliberate boundary
            return f"Error executing tool {self.name}: {exc}"
