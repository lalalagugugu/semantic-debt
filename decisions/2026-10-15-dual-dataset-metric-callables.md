# 2026-10-15 两张表都能算的指标：每表一个调用名

- 裁决人：用户，2026-10-15
- 来源：`decisions/open-questions.md` 第 `T10-1` 条（T10 渲染器开工时发现）
- 约束：T10（渲染器）、T16（Cube）、T17/T18（DAX）、`semantic/metrics.yaml`、`semantic/schema/validate.py`

## 问题

`metrics.yaml` 里有 23 个指标带 `alternate_dataset`（销售额、毛利、退货率等），但每个只有一个调用名。
`cube_member` 指向全渠道 cube `sales`（FactSales），即使默认表是 FactOnlineSales。DAX 度量值名在整个模型里必须唯一，所以只能挂在一张表上。
照现状，L2 回答「未说明渠道的销售额」（约定 1）只能调到全渠道口径，结果必错。

## 裁决

1. 这 23 个指标各出**两个调用名**，一张表一个；文字口径不变，不新增口径（设计规矩 3 仍成立）。
2. Cube：`online_sales.<成员>`（FactOnlineSales）与 `sales.<成员>`（FactSales），成员名相同、cube 不同。
3. DAX：默认表用 `metrics.yaml` 的原名。另一张表加前缀：默认表是线上的，全渠道那个加 `All Channel `，如 `[Sales Amount]` 与 `[All Channel Sales Amount]`；默认表是全渠道的，线上那个加 `Online `。
4. 在 `metrics.yaml` 里为这 23 条显式补 `alternate_dax_measure` 和 `alternate_cube_member`，并修正 `cube_member`，让它指向默认表所在的 cube。`validate.py` 增加校验：凡有 `alternate_dataset` 就必须有这两个字段，且所有调用名全局唯一。
5. L2 上下文对这些指标同时列出两个调用名，并写明各自落在哪张表；每个单元仍只出现本栈的那一种写法。
