# dual-loop-eval · 面试一页卡

**仓** https://github.com/BeeDogxxx/dual-loop-eval · **命令** `make interview` · **看板** `artifacts/interview_dashboard.html`

---

## 开场（15 秒）

> 这是我开源的 **dual-loop-eval**：可选 DeepTeam 当红队引擎；我做的是 **场景包编排 + 失败归因 Judge + Pairwise 金标过滤**。接下来两分钟：跑通 → 指看板讲。

---

## 现场三步

| 步 | 你做什么 | 指哪里 |
|----|----------|--------|
| 1 | `make interview` | 终端出 HTML 路径 |
| 2 | 打开看板 | Hero → 架构卡片 |
| 3 | 讲 A → B → 边界 | Section A 归因表 / B keep-drop |

---

## 核心叙事（背这四句）

1. **引擎可换，编排是我的**：Heuristic 默认可离线演示；DeepTeam 可选。
2. **左环对抗**：Pack → Engine → Trace → **Attribution**（locus / rule / fix）→ badcase 回流。
3. **右环资产**：gold / error / challenge 驱动下一轮；评测与尺子一起迭代。
4. **Pairwise 三坑**：位置随机 remap；多轮一致只当置信度；**precision > coverage**（例 6/25）。

---

## 和简历怎么接（脱敏）

> 业务侧做过 Agent 评测与失败归因闭环；这个仓是把同类思路 **产品化、可演示化**——场景包、归因字段、双循环资产、Pairwise 金标，笔记本两分钟跑通。

---

## 追问速答

| 问 | 答 |
|----|-----|
| 为啥全红？ | Demo Agent 故意脆弱，展示归因链；看 locus/fix，不刷绿。 |
| DeepTeam？ | 可选；没装走 heuristic，面试只走 mock。 |
| 用了 LLM？ | 默认 mock；可接 OpenAI-compatible，演示不依赖。 |
| 和 Auto Rubrics？ | 吸收三坑教训的迷你可跑子集，不声称复现全文。 |
| 金标怎么进闭环？ | 高精度偏好并入 gold 类资产，Runner 下轮加载。 |

---

## 收尾（5 秒）

> 代码在 BeeDogxxx/dual-loop-eval；README 有 DEMO 与脚本。谢谢。

**别踩坑**：别说「我从零写了红队引擎」；别展开公司内部 ACE 细节；被问数字就指看板 keep/fail，别编线上指标。
