"""Shared fixtures for autarkia tests."""

import pytest
from pydantic import BaseModel

from autarkia.tools import BaseTool


class EchoArgs(BaseModel):
    text: str
    times: int = 1


class Nested(BaseModel):
    unit: str


class NestedArgs(BaseModel):
    target: Nested


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo the given text back."
    args_schema = EchoArgs
    category = "utility"

    # Class-level observation log: execute_tool_call runs a *copy* of the
    # registered instance, so instance attributes set inside _run are not
    # visible on the original. Appending to a class attribute is.
    context_log = []

    def __init__(self):
        super().__init__()
        self.calls = 0

    async def _run(self, text: str, times: int = 1) -> str:
        self.calls += 1
        type(self).context_log.append(dict(getattr(self, "_runtime_context", {})))
        return text * times


class MutatingTool(BaseTool):
    """Tool that mutates instance state — used to prove per-call isolation."""

    name = "mutate"
    description = "Record that it ran."
    category = "utility"

    context_log = []

    def __init__(self):
        super().__init__()
        self.ran_for = []

    async def _run(self, marker: str = "") -> str:
        self.ran_for.append(marker)  # shared via shallow copy — visible on original
        type(self).context_log.append(dict(getattr(self, "_runtime_context", {})))
        return "done"


class Agent:
    def __init__(self, registry):
        self.tool_registry = registry


@pytest.fixture()
def echo_tool():
    EchoTool.context_log.clear()
    return EchoTool()


@pytest.fixture()
def agent(echo_tool):
    from autarkia.tools import ToolRegistry

    registry = ToolRegistry()
    registry.register(echo_tool)
    return Agent(registry)
