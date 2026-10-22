# 调度器（Autarkia-Scheduler）评估与决策

**日期**：2026-10-22
**对象**：运行时里的 `cpp_modules/cpp_scheduler/`（路线图队列第 10 项）
**结论**：**值得作为 GitHub 仓库存在，不做成 PyPI 包**；且当前状态满足不了"别人能构建"，仓库化前必须先过干净环境构建验证。

---

## 1. 现状实测

| 项 | 数值 |
| --- | --- |
| 规模 | 约 50 个源文件 / 约 1.4 万行 C++（含头文件与测试） |
| 可移植核心 | `queue/task_queue`(222) + `core/resource_isolation_scheduler`(918) + `core/native_executor`(182) + `core/async_scheduler`(354) + `core/phase_strategy`(665) ≈ **2.3k 行** |
| 宿主耦合 | `core/biological_system` + `core/bio_state_store`（生物节律：神经递质、昼夜节律、认知延迟）；`workers/llama_*` ≈1.3k 行（绑 llama.cpp）；`config/system_config` 1127 行（本机配置）；`optimization/performance_optimizer` 1184 行（本机硬件调参）；`monitoring/resource_monitor` 689 行 |
| 后端现状 | 自述：LLM/TTS/图像后端以 Mock 为主；`api/*` 是 Mock（只注册路由，不做真实 HTTP 监听） |
| 构建 | CMake + `FetchContent` **在 configure 阶段下载 libuv 与 llama.cpp 源码**；CUDA 默认关（需 `-DLLAMA_CUDA=ON -DGGML_CUDA=ON`）；要求 cmake ≥ 3.15 + pybind11 3.x |
| 构建残留 | `CMakeLists.txt` 里写死一条 WSL2 绝对路径作为 llama.cpp 候选源；Windows 下 nvcc 对含空格/中文路径敏感（构建脚本注释里有记录） |
| 已有产物 | 本机 `build/cuda/Release/scheduler_py.cp310-win_amd64.pyd`（588 KB）、`build/Release/...pyd`（583 KB）、`legacy/` 下有 Linux `.so` |
| 可展示资产 | `bench/native_executor_bench.cpp`——可以量化"跑图像任务时 LLM 延迟变化" |

**判断**：在作者机器上是真能跑的真工程；对外则是一个"后端为 Mock、构建要联网拉十几 GB 依赖、路径写死"的原型。

---

## 2. 为什么不做成 PyPI 包

1. **轮子矩阵不可承受**：C 扩展要按 `{Windows, Linux} × Python 3.10–3.13 × {CPU, CUDA}` 出 wheel；CUDA 变体涉及驱动/cudart 版本，基本无法可靠分发。结果只能是源码分发，而源码分发要求用户自备 MSVC/GCC、Python 头文件、网络与 llama.cpp 源码——`pip install` 的失败率会高于使用率。
2. **它不是"装完即可用"的产品**：后端是 Mock，API 层是 Mock。作为架构样本很好，作为库装完什么都跑不出来。
3. **最值钱的逻辑与机器绑定**：1127 行系统配置 + 1184 行性能调优 + 生物节律模块都是宿主专属；剥掉之后剩"带优先级的资源隔离队列"，用 Python 讲清楚比发 C++ 轮子更有说服力。
4. **受众极小**：真正需要"本地多模态 GPU/CPU 隔离调度"的人是单机自托管玩家，而他们更倾向用现成的 llama.cpp server / vLLM / 系统级 MPS，不会装一个陌生的小众扩展。

---

## 3. 如果做仓库：保留 / 丢弃

保留（约 2.3k 行核心 + 绑定 + bench）：

| 保留 | 作用 |
| --- | --- |
| `queue/task_queue.*` | 任务生命周期与队列 |
| `core/resource_isolation_scheduler.*` | 执行域隔离、优先级、取消语义 |
| `core/native_executor.*` | 原生定时驱动 |
| `core/async_scheduler.*` | 异步调度线程 |
| `core/phase_strategy.*` | 阶段/负载策略 |
| `bindings/python_bindings.cpp`（精简） | 证明 Python 侧可用 |
| `bench/native_executor_bench.cpp` | 量化隔离效果，仓库的卖点 |

丢弃：

| 丢弃 | 理由 |
| --- | --- |
| `core/biological_system.*`、`core/bio_state_store.*` | 宿主特有语义，外人不需要 |
| `workers/llama_*`、`workers/gpu_llm_worker.*` | llama.cpp 改为可选后端，默认 `-DLLAMA_CPP=OFF` |
| `optimization/performance_optimizer.*` | 本机硬件调参 |
| `config/system_config.*` | 本机配置系统 |
| `api/*` | Mock server，留着会让人误以为可用 |

仓库化前置条件（缺一不可）：

1. 删除写死的 WSL2 绝对路径；llama.cpp 只作为可选 `FetchContent`，默认关闭。
2. 在干净 Linux 容器里验证一次 `cmake -B build && cmake --build build` 通过（**当前未验证**）。
3. README 首段给出架构图 + 一张隔离效果对比表（有/无图像任务时 LLM 的 p50/p95/首 token 延迟）。
4. 明确声明这是"架构样本，非稳定 API"，不打 PyPI 主包名。

---

## 4. 若要变成"真正的库"

正确形态不是移植 C++，而是**把策略层用纯 Python 重写**：准入控制、优先级老化、资源预留、取消语义、执行域隔离、退避与公平性。C++ 留在运行时当加速器。

这样做的理由与前 9 个库一致：可测试、可移植、可解释，且不背轮子矩阵。前提是先把策略从 C++ 实现里整理成可枚举的规则（当前分散在 `resource_isolation_scheduler` 与 `phase_strategy` 中）。

---

## 5. 决策

| 选项 | 结论 |
| --- | --- |
| PyPI 发布（作为组件库第 10 个） | **不做** |
| GitHub-only 仓库（源码 + 架构 + benchmark） | **可做**，需先过构建验证 |
| 策略层纯 Python 重写为新库 | **以后再说**，先确认策略已稳定 |

下一步动作（按顺序）：

1. 干净 Linux 环境构建验证（一次性，判定仓库化是否可行）。
2. 通过则按第 3 节剥离，产出 benchmark 数字。
3. 不通过则维持现状：留在运行时内，不对外。
