# T02 v2 第十三节共用用例验证

仅运行只读的 T05b 数据文件，未导入或读取独立检查器代码。真实语料复验见 `scorer_v2_check.md`；当前按主规格第十三节判定。

- 共 194 条；判定 / 原因差异 1 条。
- 任一侧 unscored 单列 1 条；不计入分歧（第十二节第 7 条）。
- 输入 SHA256：`5954bcac3a4dee62d4f50d89a0d57f16c59723fa914a0d7a1cb9392c91fb285d`；验证前后文件哈希一致。
- 评分器 SHA256：`a012aba545e8df760e967828a1df1ca0a1db993fc3d309ece24a70bc4ce207d4`。
- 逐条耗时及预期 / 实际结果：`scorer_v2_independent.jsonl`。

## 最慢 10 条

| 用例 | 秒 | 上限 | 判定 |
|---|---:|---:|---|
| t05b/stress/rows200000-one-value-wrong | 18.088184 | 30 | wrong |
| t05b/stress/rows200000-all-values-wrong | 14.802282 | 30 | wrong |
| t05b/stress/rows50000-one-value-wrong | 3.272989 | 30 | wrong |
| t05b/stress/rows50000-all-values-wrong | 2.427247 | 30 | wrong |
| t05b/stress/rows200000-correct-shuffled | 1.107259 | 30 | correct |
| t05b/stress/identical-columns-wrong-cap | 0.651356 | 2 | unscored |
| t05b/stress/wide24-shuffled-correct | 0.522394 | 2 | correct |
| t05b/stress/wide24-one-cell-wrong | 0.504859 | 2 | wrong |
| t05b/stress/rows5000-one-value-wrong | 0.275893 | 2 | wrong |
| t05b/stress/rows50000-correct-shuffled | 0.236263 | 30 | correct |

## 判定 / 原因差异

| 用例 | 预期 | 实际 |
|---|---|---|
| t05b/name/selection-identity-wrong | {'outcome': 'wrong', 'reason': 'values'} | selection |

## unscored 单列

| 用例 | 预期 | 实际 |
|---|---|---|
| t05b/stress/identical-columns-wrong-cap | unscored | unscored |

## 当前用例预期冲突（未改只读输入）

当前文件 194 条，SHA256 `5954bcac3a4dee62d4f50d89a0d57f16c59723fa914a0d7a1cb9392c91fb285d`。
判定差异为 0，原因码差异为 1：`t05b/name/selection-identity-wrong` 的预期仍为 values，v2 按第十三节第 2 条返回 selection。未覆盖或修改预期，未将该差异计为通过；已交用户 / T05b 更新只读数据。本轮 1 条刻意触发 mapping_cap 的合成用例照第十二节第 7 条单列。

## 修复覆盖与压力

- 作者合成用例 180 passed，新增第十三节正反例覆盖：同对象跨输出行和跨组、三种名次写法、位置编号冲突、漏组 / 多组 / N+k / 错对象、对象正确但值错误、order 与 rank 的阶段顺序。
- Q119 的 19 次参考域自比探针（去掉 selection，保留排名约束）全部 correct。完整域含额外边界对象，不把完整域的 N+k 当作合法选择；对合法选择后的 306 行，原规则含 selection 判 correct。
- 作者压力 8 passed（33.35 秒）；二百万行正确 / 错误整项耗时 7.24 / 25.53 秒，内部判分均满足 ≤30 秒。
- 旧评分器相关回归 185 passed；109 条旧版兼容 warning。旧评分器和 prompt 未改。
- 仓库结构检查另有 2 条 main 基线失败：T21 的 after=T15 不被旧检查接受、BOARD 的 T19a 未进 cards.yaml；取 origin/main 原文件复现同样失败，未做卡外修改。
- 从未读取或导入 T05b 检查器代码；只读取共用数据和其正式对账报告。

## PR #120 裁决已确认

主仓库第十三节补充已明确：合法选择后的参考应判 correct；完整边界域的 N+k 应判 selection，对完整域仅核验名次按对象计数。当前实现与已完成的全语料复验符合该裁决，无需修改评分逻辑。

共用旧预期冲突以第十三节为准，不再是待裁决问题；只读用例由 T05b 更新，等待新的条数和 SHA256 后复验。当前文件仍为 194 条、SHA256 `5954bcac3a4dee62d4f50d89a0d57f16c59723fa914a0d7a1cb9392c91fb285d`，未修改或覆盖预期，也未计作全部通过。
