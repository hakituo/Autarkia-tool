# autarkia

**Tool governance for AI agents** — a registry, risk levels, role-based access, visibility rules, and execution guards for LLM tool calling.

This is the tool layer of [Autarkia](https://qishihao.icu/projects/autarkia), a self-hosted agent runtime that has run on a single machine for months: around 90 tools across 20+ domains, isolated per role, with pre-execution permission checks — not prompt promises.

## Why

Most agent frameworks answer "how do I call a tool". This library answers the question that shows up after your agent has been running for a while: **who is allowed to call what, and what happens before it runs.**

- **Registry** — one place for tool instances, runtime enable/disable, and stable OpenAI function-calling schemas (byte-stable output so API-side prompt caches keep hitting).
- **Declared risk levels** — every tool carries an explicit risk class (`read`, `write`, `external_write`, `device_read`, `device_control`, `sensitive`). If you forgot to declare one, it simply does not appear in discovery. Risk is never inferred.
- **Role policies** — resident / on-demand / disabled per role, plus keyword routing for the first turn. A role that was never granted a tool cannot see it, search for it, or call it.
- **Visibility rules** — persona-level allow/deny by name or category, with mode and sensitive-mode overlays.
- **Execution guard** — authorization against the request's own snapshot, argument validation, and per-call context isolation (no shared mutable tool state across concurrent roles).

Zero runtime dependencies beyond `pydantic`. No framework lock-in: tools are plain classes, the registry is a plain object, and the OpenAI-compatible schema export works with any API that speaks function calling.

## Install

```bash
pip install autarkia
```

## Quick start

```python
from pydantic import BaseModel

from autarkia.tools import BaseTool, ToolCatalog, ToolDeclaration, ToolRegistry


class EchoArgs(BaseModel):
    text: str

class EchoTool(BaseTool):
    name = "echo"
    description = "Echo the given text back."
    args_schema = EchoArgs

    async def _run(self, text: str) -> str:
        return text


# Declare what each tool is allowed to be. Undeclared tools stay invisible.
catalog = ToolCatalog()
catalog.declare(
    "echo",
    ToolDeclaration(
        domain="utility",
        risk_level="read",
        load_policy="base",
        tags=("demo", "echo"),
    ),
)

registry = ToolRegistry(catalog=catalog)
registry.register(EchoTool())

# OpenAI function-calling format, cached and byte-stable.
print(registry.get_openai_tools())
```

### Role-based access

```python
from autarkia.tools import RolePolicyResolver

profiles = {
    "defaults": {"on_demand": ["domain:*"]},
    "roles": {
        "librarian": {"resident": ["echo"], "disabled": ["domain:execution"]},
    },
    "modes": {},
    "routes": [
        {"keywords": ["repeat"], "tools": ["echo"]},
    ],
}

resolver = RolePolicyResolver(profiles, catalog=catalog)
policy = resolver.resolve(scope="librarian")
policy.allows("echo")        # True
policy.allows("run_code")    # False — disabled for this role

picked = resolver.select("please repeat this", scope="librarian")
```

### Execution guard

```python
import asyncio
from autarkia.tools import execute_tool_call

result = asyncio.run(execute_tool_call(
    agent=agent,                 # any object exposing .tool_registry
    tool_name="echo",
    arguments={"text": "hi"},
    user_id="user-1",
    allowed_tool_names=policy.visible_tool_names(),
))
```

The guard never trusts the model: it checks the tool against the allowed list passed by the orchestrator, validates arguments, and copies the tool instance so concurrent roles cannot bleed state into each other.

## Concepts

| Piece | File | What it decides |
| --- | --- | --- |
| `BaseTool` | `autarkia.tools.base` | what a tool is (name, args schema, category) |
| `ToolCatalog` / `ToolDeclaration` | `autarkia.tools.metadata` | domain, tags, risk level, load policy — declared per tool |
| `ToolRegistry` | `autarkia.tools.registry` | registration, enable/disable, schema export, discovery search |
| `RoleToolPolicy` / `RolePolicyResolver` | `autarkia.tools.policy` | resident / on-demand / disabled per role, keyword routing |
| `filter_tool_names` | `autarkia.tools.visibility` | persona allow/deny, mode and sensitive-mode overlays |
| `execute_tool_call` | `autarkia.tools.execution` | the last line of defense before a tool runs |

Risk levels: `read` → `write` → `external_write` → `device_read` → `device_control` → `sensitive`.
Load policies: `base` (always offered), `on_demand` (found through discovery), `hidden` (exists, never advertised).

## The bigger picture

Autarkia itself is not on PyPI — it is a single-machine runtime, not a SaaS. This package ships the governance layer that survived that experiment, because it turned out to be the part other projects kept asking for.

- Project page: <https://qishihao.icu/projects/autarkia>
- Runtime repository: <https://github.com/hakituo/Autarkia>
- This package: <https://github.com/hakituo/autarkia-tools>
- Author: Shihao Qi — <https://qishihao.icu>

## License

MIT
