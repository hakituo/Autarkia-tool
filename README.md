<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/hakituo/Autarkia-tool/main/autarkia-dark.svg">
    <img src="https://raw.githubusercontent.com/hakituo/Autarkia-tool/main/autarkia.svg" alt="Autarkia" width="360">
  </picture>
</p>

<p align="center">
  <b>Tool governance for AI agents</b><br>
  <sub>面向 AI Agent 的工具治理层：注册表 · 显式风险分级 · 角色策略 · 可见性过滤 · 执行前拦截</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/Autarkia/"><img alt="PyPI" src="https://img.shields.io/pypi/v/autarkia.svg"></a>
  <a href="https://pypi.org/project/Autarkia/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/autarkia.svg"></a>
  <a href="https://github.com/hakituo/Autarkia-tool/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/hakituo/Autarkia-tool/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
</p>

<p align="center">
  <a href="#中文">简体中文</a> · <a href="#english">English</a>
</p>

---

## 中文

大多数 agent 框架回答的是**怎么调工具**。这个库回答跑久了才会冒出来的那个问题：**谁能调、拦在哪、失败了算谁的。**

它来自一个单机长期运行的 agent 运行时：20+ 领域、约 90 个工具，按角色隔离，权限校验发生在代码里而不是提示词里。

- **注册表**：工具实例、运行时启用/禁用、稳定的 OpenAI function-calling schema（输出字节稳定，避免每次请求都让 prompt cache 失效）。
- **显式风险分级**：每个工具必须声明风险等级（`read` / `write` / `external_write` / `device_read` / `device_control` / `sensitive`）。**没声明就等于不存在**——不会出现在检索里，也不会被模型看到。风险从不推断。
- **角色策略**：按角色（scope）配置 resident / on_demand / disabled，外加首轮关键词路由。没被授予的工具，看不见、搜不到、也调不动。
- **可见性过滤**：按人设的 allow/deny（按名字或 category），叠加 mode 与 sensitive-mode 覆盖。
- **执行边界**：用本次请求自己的授权快照校验、校验参数、每次调用复制一份工具实例（并发角色之间不串状态）。

除 `pydantic` 外零运行时依赖，不绑定框架：工具是普通类，注册表是普通对象，导出的 schema 任何支持 function calling 的 API 都能用。

### 安装

```bash
pip install autarkia
```

### 快速开始

完整可运行版本：[`examples/minimal.py`](examples/minimal.py)（无网络、无 API key）。

```python
from pydantic import BaseModel
from autarkia import BaseTool, ToolCatalog, ToolDeclaration, ToolRegistry

class EchoArgs(BaseModel):
    text: str

class EchoTool(BaseTool):
    name = "echo"
    description = "Echo the given text back."
    args_schema = EchoArgs

    async def _run(self, text: str) -> str:
        return text

# 声明它是什么：未声明 = 不可见
catalog = ToolCatalog()
catalog.declare("echo", ToolDeclaration(
    domain="utility", risk_level="read", load_policy="on_demand",
))

registry = ToolRegistry(catalog=catalog)
registry.register(EchoTool())
print(registry.get_openai_tools())        # 稳定、可缓存
```

角色策略与可见性过滤：

```python
from autarkia import RolePolicyResolver, filter_tool_names

profiles = {
    "defaults": {"on_demand": ["domain:*"]},
    "roles": {"librarian": {"resident": ["echo"], "disabled": ["domain:execution"]}},
    "modes": {},
    "routes": [{"keywords": ["repeat"], "tools": ["echo"]}],
}

resolver = RolePolicyResolver(profiles, catalog=catalog)
policy = resolver.resolve(scope="librarian")

visible = filter_tool_names(
    registry.get_active_tools(), policy=policy, tool_registry=registry,
)
picked = resolver.select("please repeat this", scope="librarian")
```

执行拦截（不需要把整个 runtime 对象塞进来）：

```python
import asyncio
from autarkia import execute_tool_call

result = asyncio.run(execute_tool_call(
    registry=registry,                 # 本次请求授权时用的那个注册表
    tool_name="echo",
    arguments={"text": "hi"},
    allowed_tool_names=visible,        # 空列表 = 什么都不许，安全默认
    user_id="user-1",
    context={"is_master": False},      # 额外上下文，最后合并、可覆盖派生值
))
```

### 三层分工（为什么不是一层）

| 层 | 回答的问题 | 数据来源 |
| --- | --- | --- |
| 声明 `ToolDeclaration` | 这个工具**是什么**（领域、标签、风险、加载策略） | 每个工具的显式声明 |
| 角色策略 `RoleToolPolicy` | 这个角色**能不能调**（粗粒度闸门：resident / on_demand / disabled） | 注入的 profiles 映射 |
| 可见性 `filter_tool_names` | 此刻**要不要给模型看**（人设 allow/deny、mode / sensitive 覆盖） | 人设的 `tool_access` |

一句话：**角色策略决定“能不能调”，可见性决定“要不要露出来”，执行边界负责“真的调的时候再查一遍”。**

### 风险分级与加载策略

```text
风险：read → write → external_write → device_read → device_control → sensitive
加载：base（常驻） / on_demand（检索发现） / hidden（存在但不广播）
```

### 和主运行时的关系

Autarkia 本身不在 PyPI 上——它是一个单机运行时，不是 SaaS。这个包把那次实验里活下来的治理层单独发出来。

- 项目页：<https://qishihao.icu/projects/autarkia>
- 运行时仓库：<https://github.com/hakituo/Autarkia>
- 组件库路线图：<https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md>
- 作者：Shihao Qi — <https://qishihao.icu>

### 许可

MIT

---

## English

Most agent frameworks answer **how to call a tool**. This library answers the question that shows up after your agent has been running for a while: **who is allowed to call what, and what happens before it runs.**

It comes from a self-hosted agent runtime that has run on a single machine for months: 20+ domains, around 90 tools, isolated per role, with permission checks in code — not prompt promises.

- **Registry** — tool instances, runtime enable/disable, and byte-stable OpenAI function-calling schemas (so API-side prompt caches keep hitting).
- **Declared risk levels** — every tool carries an explicit risk class (`read`, `write`, `external_write`, `device_read`, `device_control`, `sensitive`). If you forgot to declare one, it simply does not exist for discovery: risk is never inferred.
- **Role policies** — resident / on-demand / disabled per role, plus keyword routing for the first turn. A role that was never granted a tool cannot see it, search it, or call it.
- **Visibility rules** — persona-level allow/deny by name or category, with mode and sensitive-mode overlays.
- **Execution guard** — authorization against the request's own snapshot, argument validation, and per-call context isolation (no shared mutable tool state across concurrent roles).

Zero runtime dependencies beyond `pydantic`. No framework lock-in: tools are plain classes, the registry is a plain object, and the exported schema works with any API that speaks function calling.

### Install

```bash
pip install autarkia
```

### Quick start

Runnable end to end: [`examples/minimal.py`](examples/minimal.py) — no network, no API key.

```python
from pydantic import BaseModel
from autarkia import BaseTool, ToolCatalog, ToolDeclaration, ToolRegistry

class EchoArgs(BaseModel):
    text: str

class EchoTool(BaseTool):
    name = "echo"
    description = "Echo the given text back."
    args_schema = EchoArgs

    async def _run(self, text: str) -> str:
        return text

catalog = ToolCatalog()
catalog.declare("echo", ToolDeclaration(
    domain="utility", risk_level="read", load_policy="on_demand",
))

registry = ToolRegistry(catalog=catalog)
registry.register(EchoTool())
print(registry.get_openai_tools())        # stable, cacheable
```

Role policy and visibility:

```python
from autarkia import RolePolicyResolver, filter_tool_names

profiles = {
    "defaults": {"on_demand": ["domain:*"]},
    "roles": {"librarian": {"resident": ["echo"], "disabled": ["domain:execution"]}},
    "modes": {},
    "routes": [{"keywords": ["repeat"], "tools": ["echo"]}],
}

resolver = RolePolicyResolver(profiles, catalog=catalog)
policy = resolver.resolve(scope="librarian")

visible = filter_tool_names(
    registry.get_active_tools(), policy=policy, tool_registry=registry,
)
picked = resolver.select("please repeat this", scope="librarian")
```

The guard takes the registry directly — no runtime object required:

```python
import asyncio
from autarkia import execute_tool_call

result = asyncio.run(execute_tool_call(
    registry=registry,                 # the registry this request was authorized against
    tool_name="echo",
    arguments={"text": "hi"},
    allowed_tool_names=visible,        # empty means nothing is allowed — a safe default
    user_id="user-1",
    context={"is_master": False},      # merged last; may override derived values
))
```

### Three layers, not one

| Layer | Question it answers | Where the data comes from |
| --- | --- | --- |
| `ToolDeclaration` | **What is** this tool (domain, tags, risk, load policy) | explicit declaration per tool |
| `RoleToolPolicy` | **May this role call** it (coarse gate: resident / on_demand / disabled) | injected `profiles` mapping |
| `filter_tool_names` | **Should the model see** it right now (persona allow/deny, mode / sensitive overlays) | the persona's `tool_access` block |

In one line: **role policy decides whether a tool may run, visibility decides whether it is shown, and the execution guard re-checks at call time.**

### Risk levels and load policies

```text
risk: read → write → external_write → device_read → device_control → sensitive
load: base (always offered) / on_demand (found via search) / hidden (exists, never advertised)
```

### The bigger picture

Autarkia itself is not on PyPI — it is a single-machine runtime, not a SaaS. This package ships the governance layer that survived that experiment, because it turned out to be the part other projects kept asking for.

- Project page: <https://qishihao.icu/projects/autarkia>
- Runtime repository: <https://github.com/hakituo/Autarkia>
- Component roadmap: <https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md>
- Author: Shihao Qi — <https://qishihao.icu>

### License

MIT
