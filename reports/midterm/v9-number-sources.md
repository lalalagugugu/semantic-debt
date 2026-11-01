# 中期报告 v9：数字—出处清单（供 Codex 再核）

报告在 Claude Docs 文档 `e6ba0940-5536-4c83-b2fd-296fbdf47b8d` 的「中期报告 v9」tab。本清单只含数字和题号，不含题面。没列的数字沿用 `reports/midterm/v8-number-sources.md`，取值没有变。差值单位从「个点」改成「个百分点」，数值不变。

路径约定：`v8num` = `reports/results/t19a-v8-numbers.md`（`scripts/t19a_v8_numbers.py` 生成）；`cmp` = `reports/results/accuracy-v5-comparisons.csv`；`v7num` = `reports/results/t19a-v7-numbers.md`；`causes` = `reports/results/t19a-v8-error-causes.md`；`u2` = `reports/results/t29-u2-content-analysis.md`。

## 需要 Codex 再核的新数字

- 26%（1,411 / 5,439 = 25.9%）。
- L1 的 44 次里 42 次有查询结果。
- 第 6 节 3 次 = 2 + 1。
- 第二轮新增：第 3 节 44%、13%；第 5 节「同一批题上 L1」一列；第 10 节 9 题不答、拦下的 9 题里 6 题本来是对的。

## 新增或改动

| 节 | 数字或说法 | 出处 |
|---|---|---|
| 标题、TL;DR | 不到 40%（L1.5S 39.8）、93%（L1+ 93.2，全部 98 题）；测试集 92.5 | `accuracy-v5-cells.csv`；用户 2026-11-02 裁决，`tasks/T19a-v9-plan.md` 第一节 |
| 实验描述 | 指标层单元的 Postgres 方言；JSON-L2 不写 SQL | `docs/design-v5-public.md` 第 51 行；`tasks/T16-metric-layer.md` |
| 2 | 78 题 +43.2；20 题 +13.3 | `v7num` D3 移组行 |
| 4 | L1+ = L1 原文 + 109 条；L3a 只改这 109 条；30 条形式化、79 条注解、16 条有现成写法，共 46 | `render/l1plus.py`；`reports/validation/l1plus-l3a-correspondence.md`；`reports/validation/l3a-ontology-validation.md` |
| 4 | 第一轮 token 约 7.5 万、约 22 万（含 L1 原文） | `v8num`：75,258、219,864 |
| 5 | L1.5S −7.9 [−19.0, +3.2]；JSON-L2 −4.5 [−12.6, +2.7] | `v7num` 第 5 节 |
| 5 | 「金额最大的一笔」应按单行销售算，JSON-L2 算成一整单 | Q58 第 1、2 次，`$SEMDEBT_DATA_DIR/t31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/codex-decisions.json` 的 note；参考答案为单行 |
| 6 | 3 次 = 2 次修一次后仍执行失败（Q24、Q113 各第 2 次）+ 1 次能执行但 SQL 机制用错（Q05 第 2 次） | `causes`；`v8num` |
| 6 | 48 次 = 24 题 × 2 单元 × 1 次 | `runs/20261019-T21-pilot-01/` |
| 8 | L1 上的对账没有查出「日均销售额」的矛盾 | `reports/validation/metric-text-vs-impl.md` |
| 9 | 测试集 93.2、92.5、93.2 | `accuracy-v5-cells.csv` |
| 3 | 看数据和查枚举 L0 44%、L1 13% | `v8num` 用途占比：34.5 + 9.4 = 43.9；7.2 + 6.0 = 13.2 |
| 3 | 20 题 −1.7（L0→L0-E） | `v7num` D3 移组行 |
| 5 | 同一批题上 L1：85.0、85.0、92.9、91.9 | `v7num` 第 5 节；`accuracy-v5-cells.csv` |
| 7 | 指标代码和对账由另一个会话做（Claude Code） | `render/measures.py` 的提交记录（3434837 等）；`reports/validation/metric-text-vs-impl.md`（4d03430） |
| 10 | 9 题不答 = 98 − 89；拦下的 9 题 = 3 次错答 + 6 题本来对 | `v7num` D4 |
| 10 | 42/44；12/12 能出结果 | `v8num` |
| 10 | 294 次全答、82.0%；157 次（53.4%）、87.3% | `u2` SQL-L1-u2 |
| 10 | 已答准确率 48.1→65.2、82.0→86.0；拒答率差 +30.3、+5.4 | `u2` |
| 局限 | 26%；判错没有复查；判对只复核一部分（420 次里 194 次跨厂商） | `reports/validation/t31-v7-rescan.md` |
| 附录 | 叠加单元以 L1+ 为准，删 12 个条目（含 9 条示例 SQL），其余不改 | `tasks/T30-combo-cell.md`；`reports/results/combo.md` |
| 附录 | 原始响应 25 个单元，对照页 19 个单元 | `decisions/2026-10-31-publication-choices.md` |
