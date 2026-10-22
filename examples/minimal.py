"""Minimal end-to-end example: declare, filter, dispatch, deny.

Run it from a checkout (no install needed):

    python examples/minimal.py

It prints what the model would see, one authorized call, and one refused
call — no network, no API key.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

try:  # installed package
    import autarkia  # noqa: F401
except ModuleNotFoundError:  # running from a source checkout
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pydantic import BaseModel

from autarkia import (
    BaseTool,
    RolePolicyResolver,
    ToolCatalog,
    ToolDeclaration,
    ToolRegistry,
    execute_tool_call,
    filter_tool_names,
)


class SearchArgs(BaseModel):
    query: str


class SearchNotes(BaseTool):
    name = "search_notes"
    description = "Search the user's notes and return matching titles."
    short_description = "Search notes"
    args_schema = SearchArgs
    category = "memory"

    async def _run(self, query: str) -> str:
        return f"3 notes match {query!r} (caller={self._get_ctx('user_id')})"


class DeleteArgs(BaseModel):
    note_id: str


class DeleteNote(BaseTool):
    name = "delete_note"
    description = "Delete a note permanently. This cannot be undone."
    args_schema = DeleteArgs
    category = "write"

    async def _run(self, note_id: str) -> str:
        return f"deleted {note_id}"


def build() -> tuple[ToolRegistry, ToolCatalog]:
    catalog = ToolCatalog()
    catalog.declare("search_notes", ToolDeclaration(
        domain="notes", risk_level="read", load_policy="on_demand", tags=("search", "notes"),
    ))
    catalog.declare("delete_note", ToolDeclaration(
        domain="notes", risk_level="write", load_policy="hidden",
    ))

    registry = ToolRegistry(catalog=catalog)
    registry.register(SearchNotes())
    registry.register(DeleteNote())
    return registry, catalog


PROFILES = {
    "defaults": {"on_demand": ["domain:notes"]},
    "roles": {"visitor": {"resident": ["search_notes"], "disabled": ["delete_note"]}},
    "modes": {},
    "routes": [{"keywords": ["search", "找"], "tools": ["search_notes"]}],
}


async def main() -> None:
    registry, catalog = build()
    resolver = RolePolicyResolver(PROFILES, catalog=catalog)
    policy = resolver.resolve(scope="visitor")

    visible = filter_tool_names(
        registry.get_active_tools(), policy=policy, tool_registry=registry
    )

    print("catalog declared:", catalog.names())
    print("openai schema count:", len(registry.get_openai_tools(include_names=visible)))
    print("visible for 'visitor':", visible)
    print("delete_note allowed by policy:", policy.allows("delete_note"))

    authorized = await execute_tool_call(
        registry=registry,
        tool_name="search_notes",
        arguments={"query": "groceries"},
        allowed_tool_names=visible,
        user_id="user-1",
        context={"is_master": False},
    )
    print("authorized call ->", authorized)

    refused = await execute_tool_call(
        registry=registry,
        tool_name="delete_note",
        arguments={"note_id": "n-42"},
        allowed_tool_names=visible,
        user_id="user-1",
    )
    print("refused call ->", json.loads(refused))

    # Undeclared tools are invisible by design: risk is never inferred.
    class Ghost(BaseTool):
        name = "ghost"
        description = "Never declared, never advertised."

        async def _run(self) -> str:
            return "boo"

    registry.register(Ghost())
    print("undeclared tool metadata:", registry.get_tool_metadata("ghost"))


if __name__ == "__main__":
    asyncio.run(main())
