# 执行完整性：从错误到可复核结果

本页记录可在本地复现的程序行为，不把离线演示作为模型准确率证明。

## 修复前的实际问题

基线提交：`b0d01eed46f90a93741e53383ebfafed5232c12c`。原有 27 项测试通过，但未覆盖以下问题：

1. `--judge llm` 未配置 API Key 或请求超时，会改用 mock 评分；一个普通回复因此得到 `pass=true, score=1.0`。
2. 被测 Agent 每次调用都抛出异常时，异常文字被当成普通回复。五个场景中四个被判为满分通过，一个被判为业务失败。
3. 评分响应中的字符串 `"false"` 被 Python `bool()` 转成 `True`。
4. Pairwise 接受 `--mode llm`，实际执行的仍是 mock；DeepTeam 无法解析的结果会被新生成的演示对话替代。
5. 报告只保留评分结论，无法从 Bad Case 直接复核完整对话。

## 修复后的判定口径

| 情况 | status | pass / score | 是否计入业务通过率 |
| --- | --- | --- | --- |
| 已明确选择 mock，正常完成评分 | complete | 启发式布尔结果 / 分数 | 是，但仅属演示 |
| LLM 返回有效结构 | complete | 真实响应布尔值 / 有限的 0–1 分数 | 是 |
| 缺少 Key、请求失败、响应不合格 | error | null / null | 否 |
| 被测 Agent 异常或回复为空 | error | null / null | 否 |
| Pairwise LLM 未实现、DeepTeam 结果无法映射 | 终止，退出码 2 | 不生成替代评分 | 否 |

`summary.json` 的 `total = evaluated + errors`，`evaluated = passed + failed`。通过率的分母是有效评测数；没有有效评测时，通过率和均分均为 `null`。

`judge_model` 记录配置的评分模型名称；不宣称已核验提供商实际部署模型。原始对话在 `traces.jsonl`，业务失败在 `badcases.jsonl`，执行错误在 `execution_errors.jsonl`。错误记录不保存异常正文，避免把认证信息或服务响应正文带入导出。

## 本地验收

安装 `pip install -e '.[dev]'` 后运行：

```sh
python -m pytest -q
python -m dual_loop_eval.cli interview --no-sample --artifact-dir artifacts/interview
python -m dual_loop_eval.cli pairwise-select --mode mock --artifact-dir artifacts/pairwise
```

缺少密钥的验收（不调用外部模型）：

```sh
env -u OPENAI_API_KEY python -m dual_loop_eval.cli demo \
  --engine heuristic --judge llm --artifact-dir artifacts/missing-key
```

预期退出码为 `2`，摘要中 `errors=5`、`evaluated=0`、`passed=0`、`failed=0`；每条 `error_type=missing_api_key`。这表示该轮评测未完成，不能称为模型不合格。

完整故障覆盖见 `tests/test_execution_integrity.py`：网络异常、无效布尔值、缺字段、NaN、越界分数、空回复、全失败、混合结果、证据导出、CLI 退出码和禁止隐式降级。

## 仍需完成的工作

- gold/error/challenge 当前仅加载并统计，尚未驱动下一轮回归。
- 真实模型调用、DeepTeam 真实服务兼容性和业务评分准确率未包含在离线验证中。
- Mock 采用关键词规则，不能识别所有否定、引用和复杂业务语境。
- 同一输出目录会被后续运行覆盖；比较不同批次时使用不同目录。
