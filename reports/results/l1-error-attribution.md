# SQL-L1 失败归类（T19b）

- 依据：`decisions/2026-10-20-l1-error-attribution.md`，`tasks/T19b-l1-error-attribution.md`，编码手册 `reports/attribution/codebook.md`。
- 条目：`20261018-T13-sql-direct-01-rescore-01` 中 SQL-L1 的全部非正确作答，judge 题除外，含低区分度，共 117 条（错答 115、执行失败 2、拒答 0）。每次作答单独归类。
- Flash：`runs/20261020-T19b-attrib-01/attribution.jsonl`（deepseek-flash 初判）。Codex：`reports/attribution/codex.csv`（独立复核，不看 Flash 的结果）。题目标签取自 eval-v1.2 = 90e13b3。
- 复现：`SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/l1_attribution_report.py`
- 本文只含题号、次数、标签和 L1 位置，不含题面、参考 SQL、作答 SQL 和自由文本说明。

## 偏离与已知局限

1. **Flash 自评偏差（已知局限）**：初判用的是被测模型 `deepseek-flash` 本身，不是设计里的 V4 Pro。它可能倾向于把自己的错归给文档或题面。缓解办法：不给原作答的思考内容；文档证据必须给出位置；Codex 全量独立复核。本文的结论以两家一致的部分为准，并给出根因 3 的下限和上限。
2. **高峰时段运行**：Flash 初判在 2026-10-22 16:29–16:36 运行，经用户明确批准，预算上限由 3 元提到 5 元，实际 4.42 元。
3. **在 T13 的 clone 里开分支**：卡片负责方是 T13 会话，T19b 当时未列入 cards.yaml。Codex 在自己的 clone（分支 `T19b-codex`）里标注，那个 clone 里也有 Flash 的日志；交接时已要求它不得读，Codex 自述未读取。
4. **用户抽检尚未做**：第 7 节列出待抽检的分歧条目，抽检结果由用户填写。

## 要点

1. **类别较一致，根因一致性一般。** 类别 κ = 0.70，根因 κ = 0.37。根因的数字要按区间读，不宜取单点。
2. **「模型没理解或没用上」（根因 3）占 11%–46%**（下限：两家都判；上限：至少一家判）。
3. **最大的分歧是 Flash 判 3、Codex 判 2（文档有歧义）**，共 22 条，Codex 的类别主要是 路径错（17）、选错表或字段（4）。Flash 判根因 3 的条目（42）多于 Codex（25）。也就是说，裁决担心的偏向（被测模型把自己的错推给文档或题面）在总量上没有出现，Flash 反而更多地归咎于自己。
4. **参考答案或评分可疑（根因 5）两家都判的有 26 条、15 题。** 比例不低，第 5 节的清单交题库负责方核对。核对之前，根因的占比有这一块不确定性。

## 1. 类别 × 根因

根因：1 = 文档没写；2 = 文档有歧义；3 = 文档清楚、模型没理解或没用上；4 = 题面有歧义；5 = 参考答案或评分可疑。

### Flash

| 类别 \ 根因 | 1 | 2 | 3 | 4 | 5 | 合计 |
|---|---:|---:|---:|---:|---:|---:|
| 语法错 | 0 | 0 | 2 | 0 | 0 | 2 |
| 读错问题 | 0 | 0 | 0 | 1 | 0 | 1 |
| 选错表或字段 | 0 | 5 | 5 | 0 | 0 | 10 |
| 路径错 | 0 | 0 | 18 | 0 | 1 | 19 |
| 口径错 | 0 | 7 | 3 | 6 | 25 | 41 |
| 筛选错 | 0 | 8 | 1 | 0 | 2 | 11 |
| 粒度错 | 0 | 0 | 13 | 7 | 13 | 33 |
| **合计** | **0** | **20** | **42** | **14** | **41** | **117** |

### Codex

| 类别 \ 根因 | 1 | 2 | 3 | 4 | 5 | 合计 |
|---|---:|---:|---:|---:|---:|---:|
| 语法错 | 2 | 0 | 0 | 0 | 0 | 2 |
| 读错问题 | 0 | 0 | 6 | 0 | 0 | 6 |
| 选错表或字段 | 0 | 9 | 4 | 0 | 1 | 14 |
| 路径错 | 0 | 18 | 1 | 0 | 0 | 19 |
| 口径错 | 0 | 0 | 8 | 4 | 25 | 37 |
| 筛选错 | 0 | 15 | 0 | 2 | 0 | 17 |
| 粒度错 | 0 | 0 | 6 | 10 | 6 | 22 |
| **合计** | **2** | **42** | **25** | **16** | **32** | **117** |

已声明假设：Flash 判「是」54.7%（64/117），Codex 判「是」55.6%（65/117）。

## 2. 两家一致率

| 标签 | 原始一致率 | Cohen's κ |
|---|---:|---:|
| 类别 | 76.1%（89/117） | 0.70 |
| 根因 | 53.0%（62/117） | 0.37 |
| 已声明假设 | 92.3%（108/117） | 0.84 |

根因的混淆矩阵（行 = Flash，列 = Codex）：

| Flash \ Codex | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 | 0 |
| 2 | 0 | 16 | 1 | 1 | 2 |
| 3 | 2 | 22 | 13 | 5 | 0 |
| 4 | 0 | 0 | 3 | 7 | 4 |
| 5 | 0 | 4 | 8 | 3 | 26 |

## 3. 根因 3（模型没理解或没用上）的占比

| 口径 | 根因 3 | 对照：根因 1 或 2（文档问题） | 对照：根因 5（参考或评分可疑） |
|---|---:|---:|---:|
| 下限：两家都判为该根因 | 11.1%（13/117） | 13.7%（16/117） | 22.2%（26/117） |
| 上限：至少一家判为该根因 | 46.2%（54/117） | 41.0%（48/117） | 40.2%（47/117） |

## 4. 按题目标签拆根因

### 按语义依赖

| 语义依赖 | 条目 | 根因 1/2/3/4/5（Flash） | 根因 1/2/3/4/5（Codex） | 根因 3 下限–上限 |
|---|---:|---|---|---|
| 只能由业务告知 | 98 | 0/20/35/11/32 | 2/38/21/11/26 | 9–47 |
| 可从数据发现 | 19 | 0/0/7/3/9 | 0/4/4/5/6 | 4–7 |

### 按Q 级

| Q 级 | 条目 | 根因 1/2/3/4/5（Flash） | 根因 1/2/3/4/5（Codex） | 根因 3 下限–上限 |
|---|---:|---|---|---|
| Q1 | 18 | 0/0/10/5/3 | 0/4/6/6/2 | 6–10 |
| Q2 | 60 | 0/14/13/6/27 | 1/21/12/7/19 | 3–22 |
| Q3 | 39 | 0/6/19/3/11 | 1/17/7/3/11 | 4–22 |

### 按用户类型

| 用户类型 | 条目 | 根因 1/2/3/4/5（Flash） | 根因 1/2/3/4/5（Codex） | 根因 3 下限–上限 |
|---|---:|---|---|---|
| 分析师 | 73 | 0/11/29/6/27 | 2/24/18/6/23 | 12–35 |
| 管理层 | 44 | 0/9/13/8/14 | 0/18/7/10/9 | 1–19 |

低区分度题的条目：22 条，已含在上面各表里。

## 5. 根因 5（参考答案或评分可疑）的题号清单

交题库负责方核对，本卡不改分。「两家」= Flash 与 Codex 都判为 5。

| 题 | 两家 | 仅 Flash | 仅 Codex |
|---|---|---|---|
| Q12 | r1、r3 | — | — |
| Q17 | — | r1、r2 | — |
| Q20 | r1 | r2 | — |
| Q22 | r1、r2、r3 | — | — |
| Q23 | r1、r2、r3 | — | — |
| Q30 | — | r1、r3 | — |
| Q31 | — | r3 | — |
| Q56 | — | r2 | — |
| Q64 | r2 | — | r1、r3 |
| Q67 | — | r2 | — |
| Q72 | r2 | — | — |
| Q75 | r1、r2、r3 | — | — |
| Q77 | r1、r2、r3 | — | — |
| Q81 | r2 | — | — |
| Q83 | r1、r2、r3 | — | — |
| Q85 | — | r1、r2 | — |
| Q94 | — | — | r1 |
| Q109 | — | r1、r3 | — |
| Q110 | r2 | — | — |
| Q112 | r2 | — | — |
| Q113 | r1 | — | r3 |
| Q116 | r3 | — | r1、r2 |
| Q117 | r3 | r1、r2 | — |
| Q122 | — | r1 | — |

共 24 题；两家都判 5 的题：15 题。

## 6. 两家都判为文档问题（根因 1 或 2）的条目与 L1 位置

| 题 | 次 | Flash 根因 / 位置 | Codex 根因 / 位置 |
|---|---:|---|---|
| Q29 | 2 | 2 / conventions#1；metrics.日均销售额 | 2 / conventions#1；metrics.日均销售额 |
| Q29 | 3 | 2 / conventions#1；metrics.日均销售额 | 2 / conventions#1；metrics.日均销售额 |
| Q37 | 2 | 2 / datasets.retail.FactSales.columns.StoreKey | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q38 | 1 | 2 / conventions#12；datasets.retail.FactSalesQuota.when_to_use | 2 / conventions#12；datasets.retail.FactSalesQuota.columns.ScenarioKey |
| Q38 | 2 | 2 / conventions#12 | 2 / conventions#12；datasets.retail.FactSalesQuota.columns.ScenarioKey |
| Q38 | 3 | 2 / conventions#12；datasets.retail.FactSalesQuota.when_to_use | 2 / conventions#12；datasets.retail.FactSalesQuota.columns.ScenarioKey |
| Q74 | 1 | 2 / datasets.retail.FactSales.columns.StoreKey | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q85 | 3 | 2 / datasets.retail.FactSales.columns.StoreKey；datasets.retail.DimStore.description | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q89 | 2 | 2 / conventions#13；datasets.retail.FactOnlineSales.columns.SalesQuantity | 2 / conventions#13；datasets.retail.FactOnlineSales.columns.SalesQuantity |
| Q94 | 2 | 2 / datasets.retail.FactSales.columns.StoreKey；datasets.retail.DimStore.columns.StoreType | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q94 | 3 | 2 / datasets.retail.DimStore.columns.StoreKey | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q112 | 1 | 2 / datasets.retail.FactSales.columns.StoreKey；datasets.retail.DimStore.columns.StoreType | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q112 | 3 | 2 / datasets.retail.FactSales.columns.StoreKey；datasets.retail.DimStore.columns.StoreType | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q119 | 2 | 2 / datasets.retail.FactSales.columns.StoreKey；datasets.retail.DimStore.description | 2 / datasets.retail.FactSales.columns.StoreKey |
| Q122 | 2 | 2 / conventions#13；metrics.订单数 | 2 / conventions#13；datasets.retail.FactOnlineSales.columns.SalesQuantity |
| Q122 | 3 | 2 / conventions#13；datasets.retail.FactOnlineSales.description | 2 / conventions#13；datasets.retail.FactOnlineSales.columns.SalesQuantity |

## 7. 用户抽检（待填）

根因不一致的条目共 55 条。按清单顺序等距抽 10 条，由用户判定哪家对，或给出第三种判定。

| 题 | 次 | Flash 类别 / 根因 | Codex 类别 / 根因 | 用户判定 | 说明 |
|---|---:|---|---|---|---|
| Q17 | 1 | 口径错 / 5 | 口径错 / 3 |  |  |
| Q24 | 2 | 语法错 / 3 | 语法错 / 1 |  |  |
| Q31 | 1 | 粒度错 / 4 | 粒度错 / 3 |  |  |
| Q61 | 1 | 路径错 / 3 | 路径错 / 2 |  |  |
| Q65 | 1 | 粒度错 / 3 | 粒度错 / 4 |  |  |
| Q76 | 2 | 路径错 / 3 | 路径错 / 2 |  |  |
| Q87 | 2 | 选错表或字段 / 3 | 选错表或字段 / 2 |  |  |
| Q89 | 1 | 口径错 / 3 | 筛选错 / 2 |  |  |
| Q99 | 1 | 路径错 / 3 | 路径错 / 2 |  |  |
| Q113 | 2 | 语法错 / 3 | 语法错 / 1 |  |  |
