# AGENTS.md — Autarkia（Autarkia 组件库系列）

给改动本仓库的 agent 看的说明书。读完应该能回答：这是什么、语义以谁为准、怎么验证、怎么发布。

## 这是什么

Autarkia 运行时组件库系列的**第一个库**：工具治理层——注册表、声明式风险分级、角色策略、可见性过滤、执行前校验。

- PyPI：<https://pypi.org/project/Autarkia/>
- 系列路线图：本仓库 `ROADMAP.md`（**先读它**，系列全景/命名规范/SOP 都在那）
- 主运行时（语义权威源）：本地 `D:\AI\xiaoyou-public`，GitHub <https://github.com/hakituo/Autarkia>
- 作者站点：<https://qishihao.icu/projects/autarkia>

## 了解背景：先看主仓库的哪些文件

本库从主运行时抽取而来，**行为语义以主仓库为准**。改任何行为前，按顺序看：

1. `D:\AI\xiaoyou-public\PROJECT_TECHNICAL_REFERENCE.md` —— 运行时架构总览
2. 源头文件对照表（本库每个模块从哪来）：

| 本库模块 | 主仓库源头（D:\AI\xiaoyou-public\） |
| --- | --- |
| `src/autarkia/tools/base.py` | `core\tools\base.py` |
| `src/autarkia/tools/metadata.py` | `core\tools\tool_metadata.py` |
| `src/autarkia/tools/policy.py` | `core\tools\tool_policy.py` |
| `src/autarkia/tools/registry.py` | `core\tools\registry.py` |
| `src/autarkia/tools/execution.py` | `core\tools\execution.py` |
| `src/autarkia/tools/visibility.py` | `core\tools\tool_visibility.py` |

3. `D:\AI\xiaoyou-public\tests\unit\test_tool_carryover.py` —— 宿主侧行为锁（抽取时测试的母本）
4. `D:\AI\xiaoyou-public\core\tools\registry.py` 的 `register_all_tools`（~380 行宿主工具装配）——**有意不抽**，库只含治理层不含具体工具，别"补全"它

抽取时做过的通用化改造（不要再改回去）：宿主硬编码的工具目录表 → 声明式 `ToolCatalog`/`ToolDeclaration`；QQ master 判断与 persona 单例 → 运行时上下文注入；`config.tool_profiles` YAML → 注入式 profiles 映射；宿主 logger → stdlib logging；`execute_tool_call(agent=...)` 对 `.tool_registry` 的隐式依赖 → `registry=` + `context=` 显式参数（`agent=` 仅作兼容路径保留，只用于取 `.tool_registry`，新代码不要再用）。

## 本仓库结构

```text
AGENTS.md                 本文件
ROADMAP.md                系列路线图（10 个库的队列/规范/SOP）
src/autarkia/             包本体（import 名 autarkia；tools/ 是治理层子包）
tests/                    行为测试（72 项，不跑 LLM/网络）
examples/minimal.py       端到端示例（declare → policy → filter → guard），CI 会跑它
.github/workflows/ci.yml  Python 3.10–3.13 矩阵：安装 + pytest + 跑示例
autarkia.svg / -dark.svg  项目 logo（README 头，light/dark 双版本，必须保留）
dist/                     构建产物（gitignore，不入库）
pyproject.toml            hatchling；运行时依赖仅 pydantic>=2；Python >=3.10
```

## 硬规则

1. **运行时依赖只有 `pydantic>=2`**。新增依赖必须先在 ROADMAP 立项说明理由。
2. **宿主 import 一个不许进 src/**：`config.*`、`core.utils.*`、`core.services.*`、`clients.*` 在库内只能以参数注入的形式存在。PR/提交前扫一眼。
3. **风险分级必须显式声明**（`ToolDeclaration`），不做推断；未声明的工具不可见——这是本库的设计哲学，不是遗漏。
4. 行为变更先改/加测试，保持 ≥72 项全绿再提交（含 `test_package.py` 的版本同步断言）。
5. **每次 `twine upload` 前必须递增 `pyproject.toml` 的 version**（PyPI 禁止重传同版本号）。
6. PyPI token 不进 git、不写进仓库任何文件；它只存在于 `%USERPROFILE%\.pypirc`。

## 命令（本机环境）

venv 已建好：`.venv\`（Python 3.10）。

| 用途 | 命令 |
| --- | --- |
| 测试 | `.venv\Scripts\python -m pytest -q` |
| 构建 | `.venv\Scripts\python -m build --no-isolation` |
| 装依赖/装包 | `.venv\Scripts\python -m pip install <pkg> -i https://pypi.org/simple --proxy http://127.0.0.1:7897` |
| 发布检查 | `.venv\Scripts\python -m twine check dist\*` |
| 发布 | `.venv\Scripts\python -m twine upload dist\* --non-interactive` |

**本机 pip 坑**：不加 `-i https://pypi.org/simple --proxy http://127.0.0.1:7897` 会报 `from versions: none`（全局 pip.ini 指向的镜像直连不通）。**twine 坑**：不认 `--proxy` 参数，走环境变量 `$env:HTTP_PROXY/$env:HTTPS_PROXY`（上传前设置）。

## 提交

- commit message 中文一句话，说清做了什么；Windows 下写进临时文件用 `git commit -F` 防中文乱码。
- 改完自己提交并推送 `origin main`，不要停在"改好了"等确认。
- 推送前 `git status --porcelain` 确认只含本次任务涉及的文件。

## 新库开工时

复制本文件为新库仓库的 `AGENTS.md`，只替换三节：「这是什么」「源头对照表」「本仓库结构」——硬规则、命令、提交流程保持一致。SOP 全流程见 `ROADMAP.md`。
