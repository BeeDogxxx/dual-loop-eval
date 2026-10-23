# dual-loop-eval

> **中文主说明 · English summary below**

薄编排层：在 **DeepTeam**（可选引擎）或内置 **BuiltinHeuristicEngine** 之上，叠加 **场景包 × 归因 Judge × 双循环资产 × 报告**。

仓库地址：https://github.com/BeeDogxxx/dual-loop-eval

---

## 面试 DEMO（推荐）

> 笔记本上 **一条命令 → 离线 HTML dashboard → 查看场景、归因与 Pairwise 流程**。无需 API Key；默认使用自建示例、演示 Agent 与关键词评分，不代表真实模型效果。

```bash
make interview
# 或
dual-loop-eval interview
```

成功后打开终端打印的绝对路径：`artifacts/interview_dashboard.html`（自包含 CSS，无 CDN）。

**口述脚本：** [演示脚本](docs/INTERVIEW_SCRIPT.md) · [一页卡](docs/INTERVIEW_CARD.md) / [HTML](docs/INTERVIEW_CARD.html)
**预生成样例（GitHub 可预览）：** [`examples/demo_output/interview_dashboard.html`](examples/demo_output/interview_dashboard.html)

---

## 红蓝对抗竞技场 · Red vs Blue Arena

回合制对抗：**Red** 用 `customer_service_v1` 场景出招，命中后升级变异策略（direct → paraphrase → role_play → pressure → multi_turn_setup）连击；**Blue** 是 demo 客服 Agent；**Referee** 是现有 AttributionJudge，每回合给出 `error_locus / attributed_rule / fix_suggestion`。第一场打完后，Blue 把裁判的修复建议写进 playbook 规则（patch），再打一场复赛，直接演示「双循环」。

```bash
make arena        # → artifacts/arena_replay.html + artifacts/arena_result.json
python -m dual_loop_eval.cli arena --seed 7 --rounds 12 [--no-patch]
```

离线单文件 HTML（无 CDN）：血条、播放/暂停/单步（←/→/空格）、攻击卡、裁判气泡、归因标签、补丁说明、前后对比和记分板。样例：`examples/demo_output/arena_replay.html`。默认 seed=42 时，Blue 拦截率从 0% 升到 100%，胜者从 RED 变为 BLUE。

**诚实边界：** 这是 mock/启发式演示。Red 是模板变异，Blue 是故意留漏洞的 demo agent，patch 是按意图套用的规则回复，不是真实 LLM 对战，也不是自动改 prompt。在固定 seed 下结果可复现。English: offline, deterministic Red-vs-Blue match refereed by the attribution judge, followed by a patch and a rematch; heuristic demo only, not a real LLM battle unless you wire one in.

## 诚实边界（Honest scope）

| 组件 | 角色 |
|------|------|
| **DeepTeam** | 红队 / 攻击生成引擎（可选依赖） |
| **BuiltinHeuristicEngine** | 本仓库默认、始终可用的启发式多轮对抗引擎 |
| **本仓库** | 场景包（scenario packs）× 归因 Judge × 双循环资产（gold/error/challenge）× Markdown/JSON/HTML 报告 |

本项目**不是** DeepTeam 的 fork，也不替代其核心能力；它解决的是「评测编排、失败归因、双循环资产回流」这一层。

---

## 架构

```mermaid
flowchart LR
  Pack[Scenario Packs] --> Runner[DualLoopRunner]
  Assets[Gold / Error / Challenge] --> Runner
  Runner --> Engine{AttackEngine}
  Engine -->|default| Heuristic[BuiltinHeuristicEngine]
  Engine -->|optional| DeepTeam[DeepTeam wrapper]
  Target[DemoCustomerAgent] --> Engine
  Engine --> Traces[Trace list]
  Traces --> Judge[AttributionJudge]
  Judge --> Report[report.md + badcases.jsonl]
  Report --> Dash[interview_dashboard.html]
  Pairwise[Pairwise Rubric Judge] --> Dash
```

---

## 快速开始

> 本仓库 `Makefile` 会自动创建/使用 `.venv`（适配 PEP 668 环境）。


```bash
# 安装（含 pytest）
make install
# 或
pip install -e ".[dev]"

# 一键 demo：启发式引擎跑客服场景包 → 归因 → 写 artifacts/
make demo
```

成功后会生成：

- `artifacts/report.md` — Markdown 评测报告
- `artifacts/badcases.jsonl` — 失败 case 回流银行
- `artifacts/summary.json` — 结构化摘要
- `artifacts/traces.jsonl` — 所有场景的原始对话轨迹，与结果按 `scenario_id` 对齐
- `artifacts/execution_errors.jsonl` — 被测 Agent 或评分器执行失败，单独存档

### 结果可信度与异常处理

- `status=complete` 才有 `pass` 和 `score`；`status=error` 的两项值均为 `null`。执行错误不计入通过／失败、通过率或均分，也不进入业务 Bad Case。
- `summary.json` 使用 `schema_version=2`，记录 `judge`、配置的 `judge_model`、`evaluated` 和 `errors`。当没有有效评测时，`pass_rate`、`average_score` 为 `null`。
- Markdown 和 HTML 都显示评分来源与执行错误；`badcases.jsonl` 中的业务失败保留原始 `trace`，便于复核。再次运行会覆盖同一输出目录，需留存时请指定不同的 `--artifact-dir`。
- `--judge llm` 缺少密钥、请求失败或响应格式不合格时，记录错误并以退出码 **2** 结束；不会静默改用 mock。字符串 `"false"`、越界概率、NaN 和缺失字段均不作为有效评分。
- Pairwise 的 LLM 模式尚未实现：`--mode llm` 会明确报错，退出码为 **2**。当前 Pairwise 结果全部来自离线启发式演示。
- 自动验证覆盖流程与故障处理，不等于评分准确率验证；真实 LLM 服务和中文业务校准需另行验证。

可选 DeepTeam 引擎（需自行安装并配置模型回调）：

```bash
pip install -e ".[deepteam]"
dual-loop-eval demo --engine deepteam
```

DeepTeam 适配层仍为实验性。缺少依赖、无法解释的返回结构或无法映射到场景时会报错，不自动替换引擎或补造对话。当前支持显式 `scenario_id` 与 `turns` / `conversation` 的完整场景结果；真实 DeepTeam 版本兼容性尚未在本仓库 CI 中验证。离线演示请显式使用 `--engine heuristic`。

---

## CLI

```bash
dual-loop-eval demo          # 默认 heuristic 引擎
dual-loop-eval test-pack     # 校验场景包结构
dual-loop-eval pairwise-demo # Pairwise Rubric Judge demo
dual-loop-eval interview     # 面试一键：demo + pairwise + HTML dashboard
python -m dual_loop_eval.cli demo
```

环境变量（仅从环境读取，不写死密钥）：

| 变量 | 用途 |
|------|------|
| `DLE_ENGINE` | `heuristic` \| `deepteam` |
| `DLE_JUDGE` | `mock` \| `llm` |
| `DLE_ARTIFACT_DIR` | 默认 `artifacts` |
| `OPENAI_API_KEY` | Judge llm 模式（OpenAI-compatible） |
| `OPENAI_BASE_URL` | 可选兼容端点 |

---

## 双循环资产

`assets/data/`：

- `gold.jsonl` — 应通过的金标
- `error.jsonl` — 已知失败模式
- `challenge.jsonl` — 加压 / 边界 case

当前 `DualLoopRunner` 读取并展示这三类资产的数量，实际执行的是 `customer_service_v1` 场景包。资产尚未自动转成回归场景，`badcases.jsonl` 也不会自动写回 gold/error/challenge；完整的审核、回流和回归执行是后续工作。

---



## Pairwise Rubric Judge

> 迷你 demo，**不是**完整 Auto Rubrics 流水线。吸收淘天 Auto Rubrics 类文章的教训：

| 陷阱 / 手法 | 我们的做法 |
|------|------------|
| **位置偏差 (position bias)** | 每轮随机交换 A/B 展示顺序，再把 winner **映射回**原始 `a`/`b` |
| **一致性 ≠ 正确性** | 多轮同意只作 **confidence filter**；有人工 `label_chosen` 时还必须对得上 |
| **宁缺毋滥 (precision > coverage)** | Golden Set 只保留「一致 ∧ 标签匹配」的 (pair, rubric, judgment) |
| **Bootstrap Stability Selection**（新增） | 对 preference pairs **有放回重采样**；统计每条 rubric 进入 Golden 的频率，保留频率 ≥ 阈值（默认 0.6） |
| **交叉验证贪心筛 Rubric**（新增） | 在稳定候选上，贪心加入最能提升 hold-out 标签一致率的 rubric；无增益或达上限则停 |

```bash
make pairwise          # 位置随机 + 一致过滤 → Golden Set
make pairwise-select   # 上式 + Bootstrap 稳定选择 + CV 贪心筛 Rubric
# 或
dual-loop-eval pairwise-demo
dual-loop-eval pairwise-select
```

产出：

- `artifacts/pairwise_report.md` — 随机化 / 一致性 /（select 时）稳定性与贪心筛选说明
- `artifacts/golden_preferences.jsonl` — 高精度偏好子集
- `artifacts/rubric_stability.json` — Bootstrap 频率 + 贪心 CV 结果（`make pairwise-select`）
- `artifacts/selected_rubrics.jsonl` — 筛后的 rubric 子集
- `artifacts/golden_preferences_selected.jsonl` — 仅用筛后 rubric 再过滤的金标

数据：`dual_loop_eval/assets/data/preference_pairs.jsonl`、`rubrics.jsonl`。默认 **mock** 启发式，无网络。

## 开发

```bash
make test             # pytest，无网络
make demo             # 端到端本地 demo
make pairwise         # Pairwise Rubric Judge demo
make pairwise-select  # Bootstrap + greedy CV rubric screening
make interview        # 面试 dashboard（推荐）
```

GitHub Actions 会在 Python 3.10 与 3.14 上运行离线测试和演示流程，不配置或调用付费模型服务。异常行为的复现与验收步骤见 [执行完整性验证](docs/EXECUTION_INTEGRITY.md)。

---

## English summary

**dual-loop-eval** is a thin orchestration layer on top of optional [DeepTeam](https://github.com/confident-ai/deepteam) plus an always-available `BuiltinHeuristicEngine`. This repo owns **scenario packs**, an **attribution Judge**, **dual-loop JSONL assets**, a **Pairwise Rubric Judge** (position randomization, consistency filter, Bootstrap Stability Selection, greedy CV rubric screening — mini demo, not full Auto Rubrics), and **report / badcase / interview dashboard** outputs — not the red-team engine itself.

```bash
make install && make interview && make test
```

Interview script (Chinese, ~2 min): [`docs/INTERVIEW_SCRIPT.md`](docs/INTERVIEW_SCRIPT.md).

License: Apache-2.0. DeepTeam credit: see `NOTICE`.
