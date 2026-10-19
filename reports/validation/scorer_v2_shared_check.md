# T02 v2 第十二节共用用例验证

仅运行只读的 T05b 数据文件，未导入或读取独立检查器代码。真实语料复验见 `scorer_v2_check.md`；当前按主规格第十三节判定。

- 共 207 条；判定 / 原因差异 0 条。
- 任一侧 unscored 单列 1 条；不计入分歧（第十二节第 7 条）。
- 输入 SHA256：`bb5fe9fa6881d4340f5c4e92ebcd17c481a2c7733bd5b9fed8b1405bb0ad2673`；验证前后文件哈希一致。
- 评分器 SHA256：`a012aba545e8df760e967828a1df1ca0a1db993fc3d309ece24a70bc4ce207d4`。
- 逐条耗时及预期 / 实际结果：`scorer_v2_independent.jsonl`。

## 最慢 10 条

| 用例 | 秒 | 上限 | 判定 |
|---|---:|---:|---|
| t05b/stress/rows200000-one-value-wrong | 16.994070 | 30 | wrong |
| t05b/stress/rows200000-all-values-wrong | 14.874692 | 30 | wrong |
| t05b/stress/rows50000-one-value-wrong | 3.680234 | 30 | wrong |
| t05b/stress/rows50000-all-values-wrong | 2.651474 | 30 | wrong |
| t05b/stress/rows200000-correct-shuffled | 1.185391 | 30 | correct |
| t05b/stress/identical-columns-wrong-cap | 0.726575 | 2 | unscored |
| t05b/stress/wide24-shuffled-correct | 0.670017 | 2 | correct |
| t05b/stress/wide24-one-cell-wrong | 0.594749 | 2 | wrong |
| t05b/stress/rows5000-one-value-wrong | 0.318971 | 2 | wrong |
| t05b/stress/rows50000-correct-shuffled | 0.305688 | 30 | correct |

## 判定 / 原因差异

| 用例 | 预期 | 实际 |
|---|---|---|

## unscored 单列

| 用例 | 预期 | 实际 |
|---|---|---|
| t05b/stress/identical-columns-wrong-cap | unscored | unscored |

## 第十三节及 PR #120 更新后的验收

本轮使用提交 af9e2d3 的评分代码，207 条预期全部一致：判定 / 原因码差异 0。1 条刻意触发 mapping_cap 的合成用例两侧一致，依第十二节第 7 条单列。输入只读，运行前后 SHA256 均为 `bb5fe9fa6881d4340f5c4e92ebcd17c481a2c7733bd5b9fed8b1405bb0ad2673`。

原 `selection-identity-wrong` 预期已由 T05b 改为 wrong/selection；新增 13 条 selection、Q119 对象重复 / 合法选择 / N+k、Q92 order 用例均符合预期。此前 194 条文件的旧预期冲突已解除，无需评分器迁就旧预期。

本轮未改评分实现；评分器 SHA256 `a012aba545e8df760e967828a1df1ca0a1db993fc3d309ece24a70bc4ce207d4` 与上一轮一致。此前 180 作者测试、185 旧版回归及 8 作者压力测试已通过，本轮仅重跑更新的共用数据和三份真实语料；不将旧运行冒充本轮重复执行。

未读取或导入 T05b 检查器代码。报告中实际和预期的 exec_error 原因仅保留类别 / SHA256。

```sh
UV_CACHE_DIR="$TMPDIR/t02-uv-cache" uv run --no-sync python scripts/validate_scorer_v2.py \
  --shared "$SEMDEBT_DATA_DIR/scorer-corpus/t05b-cases.jsonl" \
  --output reports/validation/scorer_v2_independent.jsonl \
  --report reports/validation/scorer_v2_shared_check.md
```
