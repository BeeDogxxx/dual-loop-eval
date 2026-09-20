# 面试 DEMO 脚本（≈2 分钟）

> 仓库：https://github.com/BeeDogxxx/dual-loop-eval · 作者：苏笔辉 / BeeDogxxx  
> 前置：本机已 `git clone`，有 Python 3.10+；**无需 API Key**（全程 offline mock）。

---

## 0:00 开场一句话

> 「这是我做的 **dual-loop-eval**：在可选的 DeepTeam 红队引擎之上，自己实现了 **场景包编排 + 失败归因 Judge + Pairwise 偏好金标**；接下来一分钟跑通，打开一个离线 HTML dashboard 讲清楚。」

---

## 0:20 跑 `make interview`

```bash
cd dual-loop-eval
make interview
```

终端会：

1. 跑对抗 demo（heuristic 引擎 + 归因）→ `artifacts/report.md` / `badcases.jsonl`
2. 跑 pairwise demo（位置随机化 + 一致过滤）→ `golden_preferences.jsonl`
3. 生成 **`artifacts/interview_dashboard.html`**，并打印绝对路径

用浏览器打开该 HTML（或 `open` / 双击均可；**无 CDN、可离线**）。

---

## 0:40 指 dashboard 讲双环 + 归因

指着 **Architecture** 卡片与 **Section A**：

1. **左环（对抗评测）**：Scenario Pack → AttackEngine（默认 Heuristic / 可选 DeepTeam）→ Trace → **Attribution Judge**  
2. Judge 不只打分，还给出 **error_locus / attributed_rule / fix_suggestion**，失败写入 `badcases.jsonl`  
3. **右环（资产回流）**：gold / error / challenge JSONL 被 Runner 加载，驱动下一轮评测  

一句话收束：

> 「引擎可以换；**编排、归因、资产回流**是我这边的贡献。」

---

## 1:10 指 pairwise：位置偏差 / 一致过滤

指 **Section B**：

| 陷阱 | 我们的做法 |
|------|------------|
| 位置偏差 | 每轮 **随机交换 A/B**，winner **映射回**原始 `a`/`b` |
| 一致性 ≠ 正确性 | 多轮同意只作 **confidence filter**；有人工 label 还必须匹配 |
| 宁缺毋滥 | Golden Set 只保留「一致 ∧ 标签匹配」—— precision > coverage |

点一下 keep rate（例如 6/25）：

> 「宁可金标小而干净，也不要大而噪声。」

---

## 1:40 诚实边界 + 和简历 ACE 的映射（脱敏）

**诚实边界：**

- DeepTeam = **可选**攻击/红队引擎，不是本仓库 fork  
- 默认路径 = BuiltinHeuristicEngine，**零密钥、可演示**  
- Pairwise 是 **迷你 demo**，不是完整 Auto Rubrics 流水线  

**简历映射（脱敏表述，按需选用）：**

> 「线上/实习相关工作里做过 Agent 评测与失败归因闭环（可称 ACE / eval loop）；这个开源仓库是把同类思路 **产品化、可演示化**：场景包、归因字段、双循环资产、Pairwise 金标过滤 —— 全部可在笔记本上两分钟跑通。」

---

## 可能追问与短答

**Q: 为什么失败率这么高？是不是评测坏了？**  
A: Demo agent **故意脆弱**，用来展示归因链路；真实系统会先修规则再看 pass rate。关注点是 locus/rule/fix，不是刷绿。

**Q: DeepTeam 没装怎么办？**  
A: 默认 heuristic；`DLE_ENGINE=deepteam` 时若不可用会提示并回退。面试只走 mock。

**Q: Judge 用了 LLM 吗？**  
A: 默认 `mock` 启发式归因；`DLE_JUDGE=llm` 可接 OpenAI-compatible，面试不依赖。

**Q: Golden Set 怎么进双循环？**  
A: 高精度偏好可并入 `assets/data/gold.jsonl` 风格资产，下一轮 Runner 加载 —— 闭环叙事。

**Q: 和 Auto Rubrics / 淘天文章的关系？**  
A: 吸收三点教训（位置偏差、一致性≠正确性、precision>coverage），实现迷你可运行子集，不声称复现全文流水线。

---

## 收尾（可选 5 秒）

> 「代码在 GitHub BeeDogxxx/dual-loop-eval；文档里有这份脚本。感谢。」

---

一页速查卡：[`docs/INTERVIEW_CARD.md`](INTERVIEW_CARD.md) / [`docs/INTERVIEW_CARD.html`](INTERVIEW_CARD.html)（可打印）。
