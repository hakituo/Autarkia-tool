# Autarkia 组件库路线图

把 Autarkia 运行时里经受过单机长期运行考验的内部机制，抽成一系列独立、可安装的 Python 库。每个库 = 一个 GitHub 仓库 + 一个 PyPI 页面。

- 运行时（大集合，给人看）：https://github.com/hakituo/Autarkia
- 作者站点：https://qishihao.icu/projects/autarkia
- 本路线图所在仓库（系列第一个库）：https://github.com/hakituo/Autarkia-tool

## 命名规范

| 项 | 规则 | 例 |
| --- | --- | --- |
| GitHub 仓库 | `Autarkia-<Component>`，大写开头 | `Autarkia-Cadence` |
| PyPI 发行名 | `Autarkia-<Component>`（PyPI 按 PEP 503 归一化，`autarkia-cadence` 同样可访问） | `Autarkia-Cadence` |
| import 名 | `autarkia_<component>`，小写下划线 | `autarkia_cadence` |
| Python | `>=3.10`，LICENSE MIT，含 `py.typed` | |

import 名不使用 `autarkia.cadence` 命名空间形式：第一个包已占用 `autarkia/__init__.py`，PEP 420 命名空间包会与之冲突。

## 状态

| # | 库 | 状态 |
| --- | --- | --- |
| 0 | [Autarkia](https://pypi.org/project/Autarkia/)（工具治理层） | **已发布 0.2.0** |
| 1 | Autarkia-Cadence | 代码完成，199 项测试全绿，待发布 |
| 2 | Autarkia-Vocab | 代码完成，161 项测试全绿，待发布 |
| 3 | Autarkia-Textkit | 代码完成，86 项测试全绿，待发布 |
| 4 | Autarkia-Io | 代码完成，60 项测试全绿，待发布 |
| 5 | Autarkia-Concurrency | 代码完成，50 项测试全绿，待发布 |
| 6 | Autarkia-Emotion | 代码完成，94 项测试全绿，待发布 |
| 7 | Autarkia-Msgqueue | 代码完成，75 项测试全绿，待发布 |
| 8 | Autarkia-Personas | 代码完成，112 项测试全绿，待发布 |
| 9 | Autarkia-LLM | 未开工 |
| 10 | Autarkia-Scheduler | 未开工 |

## 当前进度与交接（2026-10-22）

前 8 个库已在本地各自建好独立仓库骨架（`pyproject.toml` / LICENSE / `.gitignore` / README / AGENTS.md / `py.typed` / tests），**均已完成本地 `git init -b main` + 首次提交**；版本号均为 `0.1.0`，`build` + `twine check` 全部通过。

**发布卡点**：8 个库都还没有 GitHub remote（`gh` 未登录，无法建仓），因此未 push、未上 PyPI。解卡只需 `gh auth login`（或手动在 GitHub 建好 8 个同名仓库），之后逐个 `git remote add origin` → `git push -u origin main` → 递增版本 → `twine upload`。

| 库 | 本地目录 | 测试 |
| --- | --- | --- |
| Autarkia-Cadence | `D:\AI\Autarkia-Cadence` | 199 |
| Autarkia-Vocab | `D:\AI\Autarkia-Vocab` | 161 |
| Autarkia-Textkit | `D:\AI\Autarkia-Textkit` | 86 |
| Autarkia-Io | `D:\AI\Autarkia-Io` | 60 |
| Autarkia-Concurrency | `D:\AI\Autarkia-Concurrency` | 50 |
| Autarkia-Emotion | `D:\AI\Autarkia-Emotion` | 94 |
| Autarkia-Msgqueue | `D:\AI\Autarkia-Msgqueue` | 75 |
| Autarkia-Personas | `D:\AI\Autarkia-Personas` | 112 |

验证方式（以 Cadence 为例，其余替换目录名即可）：

```powershell
$env:PYTHONPATH="D:\AI\Autarkia-Cadence\src"
D:\AI\autarkia\.venv\Scripts\python -m pytest -q D:\AI\Autarkia-Cadence\tests
```

环境与约定：

- 共用 venv：`D:\AI\autarkia\.venv`（Python 3.10），已安装 `fsrs==6.3.2`（Vocab 需要）。
- 8 个库均无宿主 import（`config.*` / `core.*` / `clients.*`），测试不跑 LLM、不跑网络。
- 每个库的 `AGENTS.md` 记录了源头文件对照、通用化改造与命令；续作前先读对应库的 AGENTS.md。
- 8 个库均已本地提交（`main`，工作区干净，`dist/` 未入库），但**无 remote、未 push、未上 PyPI**；发布按各库 AGENTS.md 的流程逐个执行（建 GitHub 仓库 → 递增版本 → build → twine check → upload）。
- 全部 8 个库共 837 项测试，可在主库 venv 里一次性复跑（见上）。
- Autarkia-Personas 的实现源头在私有仓，public 切片缺该模块；库内**零角色数据**，角色画像与关系由宿主以 JSON/mapping 注入，public 仓库不会出现真实角色名。

剩余工作：

1. **Autarkia-LLM**：先抽 `core/llm/openai_compat/` 19 个文件，再评估 `cloud_router` / `hybrid_module`；测试全部 mock，不发真实请求。
2. **Autarkia-Scheduler**：C++/pybind11 扩展，最后做；剥离 llama workers 与 biological_system 后再评估可移植核心。

## 队列（按发布顺序）

| # | 库 | 一句话定位 | 主要来源（xiaoyou-public / xiaoyou-core） | 难度 |
| --- | --- | --- | --- | --- |
| 1 | **Autarkia-Cadence** | 主动消息节奏治理：频控守卫、静默时段、每日上限、动态间隔、退避抖动、晚安探针 | `core/services/active_care/`：`cadence/cadence_guard.py`(~410 行)、`scheduling/schedule_config_loader.py`(166)、`scheduling/scheduler_logic.py`(148)、`checker/checker_time_gate.py`(63)、`core/sleep_policy.py`、`shared/tuning.py`+`sleep_thresholds.py`+`scheduling_utils.py` | MEDIUM |
| 2 | **Autarkia-Vocab** | FSRS 调度的词汇练习引擎：调度/评分语义版本迁移/每日队列/生词本/统计 | `core/tools/study/english/` 16 文件 ≈4800 行，核心 `fsrs_scheduler.py`(~550) | LOW-MEDIUM |
| 3 | **Autarkia-Textkit** | 中文聊天消息切分（9 件套）+ 集合相似度度量（IoMax/containment/Jaccard/ngram） | `core/utils/text_segmenter*.py` ≈1800 行、`text_similarity.py`(87) | LOW |
| 4 | **Autarkia-Io** | 原子文件 IO：临时文件+指数退避+Windows winerror 5/32 重试+fsync，sync/async 双版本 + JSON 工具 | `core/utils/atomic_io.py`(~440)、`json_utils.py` | LOW |
| 5 | **Autarkia-Concurrency** | 异步并发原语：懒加载锁/单例/资源锁/后台任务/子进程超时 | `core/utils/concurrency/` 7 文件 | LOW |
| 6 | **Autarkia-Emotion** | 情绪状态机：关键词检测→状态→强度衰减→JSONL 持久化，中文词表内置 | `core/emotion/` ≈1300 行 | LOW |
| 7 | **Autarkia-Msgqueue** | 离线消息可靠性队列：双档 TTL/message_id 去重/discard/原子重放/双端时效守卫 | `core/interfaces/websocket/offline_queue.py`(206)、`clients/bots/qq/session/replay_guard.py`(33) | LOW-MEDIUM |
| 8 | **Autarkia-Personas** | 多角色人设注册表 + 互识关系图 + 拒绝猜测的 role 解析（机制入库，角色数据外置） | `core/services/dual_role/personas.py` ≈710 行（**在私有仓 xiaoyou-core**，public 切片缺实现） | LOW |
| 9 | **Autarkia-LLM** | 多 provider OpenAI 兼容网关：路由/降级链/瞬时错误重试/流式/视觉回退路由 | `core/llm/openai_compat/` 19 文件先行，再上 `cloud_router`/`hybrid_module` | MEDIUM-HIGH |
| 10 | **Autarkia-Scheduler** | 端侧 AI 任务 GPU/CPU 资源隔离优先级队列（pybind11 C++ 扩展） | `cpp_modules/cpp_scheduler/`（剥离 llama workers 与 biological_system 后核心 ≈60KB） | HIGH |

不做库：`memory/` 整体（config 硬耦合贯穿 8000 行实现层，收益不成比例）、`memory/nightly/`（应用级流程）、`core/modules/`（硬件绑定）、`core/lifecycle/`（FastAPI 编排）。

## 每个库的标准流程（SOP）

1. **抽取**：从来源复制核心文件，宿主依赖只允许两种下场——换成参数注入，或删除。硬规则：`config.*`、`core.utils.*`、`clients.*` 的 import 一个不留。
2. **通用化**：宿主专有概念（角色名、QQ、数据路径）改成库 API 的参数；宿主硬编码目录表改成声明式 API。风险分级必须显式声明，不做推断。
3. **测试**：行为测试从 xiaoyou-public `tests/unit/` 对应文件改写，不跑 LLM、不跑网络，目标 ≥50 项。
4. **仓库**：`pyproject.toml`（hatchling + py.typed + keywords/classifiers）、README（英文为主，链接回运行时仓库、项目页、本路线图）、LICENSE MIT、`.gitignore`、`AGENTS.md`（从 Autarkia-tool 复制模板，只换「这是什么 / 源头对照表 / 结构」三节）。
5. **发布**：`python -m build --no-isolation` → `twine check` → `twine upload`（token 在 `%USERPROFILE%\.pypirc`）→ GitHub 建仓 `Autarkia-<Component>` 并推送 → 更新本路线图状态。
6. **收尾**：前后两个库的 README 互相链接（实体互链网）；主运行时 README 的相关章节加"组件库化"注记。

## 发布节奏

- 每个库独立发布，完成一个发一个，不攒批次。
- LOW 难度库两个可合并为一个工作日完成。
- 全部发完不设 deadline：优先级高于数量——Cadence 与 Vocab 优先（用户点名 + 价值最高），Textkit/Io 作 quick win 穿插，Scheduler 最后。

## 已完成的版本记录

| 库 | 版本 | 内容 |
| --- | --- | --- |
| Autarkia | 0.1.0 | 首发：注册表/声明式风险分级/角色策略/可见性/执行边界，60 项测试 |
| Autarkia | 0.1.1 | 仓库链接对齐 |
| Autarkia | 0.1.2 | PyPI 显示名改 `Autarkia`，仓库链接对齐 `Autarkia-tool` |
| Autarkia | 0.2.0 | `execute_tool_call` 改为 `registry=` + `context=` 显式入参（`agent=` 保留兼容）；双语 README + logo + CI 矩阵 + 可运行示例；72 项测试 |
