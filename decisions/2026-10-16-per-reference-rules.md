# 2026-10-16 多解题逐参考保存 `rules`

- 裁决人：用户，2026-10-16（经协调会话提案、转交 Codex 时批准）
- 发现者：Codex（补齐 122 题 `rules` 时）
- 约束：T05（题库格式）、T02（评分器接口）、T11（harness 透传）、T05b（独立重算）

## 问题

冻结规则第 6 条允许一题有多份可接受的参考。但 `value_kinds`、`value_types` 是**逐列**的，而多解题的各份参考列数不同：Q97 两份参考分别 4 / 5 列，Q98 分别 3 / 4 列。题级的一份 `rules` 描述不了两种列结构。

现有评分器 `harness/scorer.py` 的 `score(candidate_rows, refs, rules)` 对全部参考共用同一份 `rules`。

## 裁决

1. **每份参考可以带自己的 `rules`**。逐参考 `rules` **整份覆盖**题级 `rules`；没有就沿用题级。向后兼容：只有多解题需要写。
2. 评分器对每份参考**用该参考自己的 `rules`** 比较，命中任一份即判对；判错时的原因与敏感度标签同样按各参考自己的 `rules` 计算。
3. 原则不变：`rules` 是参考答案的元数据，harness **原样透传**，评分器不自行推断。

## 分工

| 改什么 | 归谁 |
|---|---|
| 题库格式、122 题的 `rules`、评分器接口与合成测试 | Codex |
| harness 读取逐参考 `rules` 并透传给评分器 | Claude Code（T11 的延续），**在 Codex 的评分器 PR 合并之后** |
| pandas 重算按逐参考 `rules` 比较 | Claude Code（T05b） |

评分器接口变化须在 `scripts/validate_scorer.py` 的 600 条复验里报告：**判定是否有变**；有变则按「契约变化」单独归因（同 `decisions/2026-10-16-reference-inner-join-undercount.md` 第 5 条）。
