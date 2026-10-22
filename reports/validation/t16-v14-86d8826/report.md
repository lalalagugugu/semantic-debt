# T16：v1.4 候选 86d8826 实测

结论：**未通过，不能固定 v1.4 覆盖表**。PR #144 分支头 `86d8826b7bdcbbae740f77706cb7e2f1e23b4da2` 的完整模型不能编译；新客 rolling_window 实现也未通过。全程零模型调用、零评分调用，不估全量。T12 源文件、冻结材料、模型作答、原分数与原覆盖表均未修改。

## 1. 整体加载与诊断边界

从该提交导出独立快照，重新运行 `render.cube`，生成 25 个 Cube、102 个公开指标。容器挂载该快照的完整模型：

| 检查 | 结果 |
|---|---|
| `/readyz` | 200，仅证明服务就绪 |
| `/cubejs-api/v1/meta` | **500，整模型编译失败** |
| 首个原文错误 | `product.ClassID cannot be resolved. There's no such member or cube.` |

`reduce_by` 生成器枚举了源表所有列，但模型已省略部分技术列，造成 11 处无效引用，涉及 6 个不同成员：

| 所属辅助成员 | 不存在的 reduce_by 成员 |
|---|---|
| sales.sales_amount_in_category | product.ClassID、StyleID、ColorID、UnitOfMeasureID、StockTypeID |
| online_sales.sales_amount_in_category | 同上 5 个 product 成员 |
| sales.sales_amount_in_channel | store.LastRemodelDate |

为继续定位，只在另一个**临时诊断模型副本**中删除上述 11 行，未改任何公式、公开调用名或其他成员。该副本 `/meta` 200、25 个 Cube 可加载。附件 `unresolved-delete-only.patch` 精确记录删项；它针对重渲产物，不是已经应用到 T12 源码的修复。

以下成功均为**删项诊断副本上的有条件证据**，不得写成原 `86d8826` 已通过。有效的跨 Cube 维度引用本身在诊断中可用；不能把这次失败泛化为 reduce_by 一概不接受连接 Cube 的维度。

验证结束已恢复 T16 原有模型挂载，恢复后 `/meta` 200。

## 2. 逐调用名与独立物理聚合

通用参数使用 2007-02、2008 前三个季度、2007/2008 作基年等；不取自题目，不按题修查询。每个数值探针在 JSON、SQL 两接口分别执行，基线直接聚合原始事实表，不使用 Cube 指标表达式。按成员名归一化 JSON 列序，逐组比较完整行集；数值容差 rel=1e-8、abs=1e-6，不静默删行。

| 调用名 | 诊断副本结果 | 证据 / 成立条件 |
|---|---|---|
| sales.sales_amount_share_in_channel | 成立 | 按渠道与门店分组，门店销售额 ÷ 同渠道合计，两接口均一致 |
| sales.sales_amount_share_in_category | 成立 | 分别按品类+子类、品类+产品分组；排除无有效品类键的组，均一致 |
| online_sales.sales_amount_share_in_category | 成立 | 同上，两种子层级均一致 |
| sales.sales_amount_qoq_pct | 成立 | 2008 前三个季度，对照上一完整季度；期初基期在范围外仍正确取到 |
| online_sales.sales_amount_qoq_pct | 成立 | 同上 |
| sales_quota.sales_amount_quota_by_scenario | **有条件成立** | 显式筛 Actual/Forecast，或场景 set，完整行集一致；不筛场景多一个 NULL 空组 |
| sales_quota.sales_quantity_quota_by_scenario | **有条件成立** | 同上 |
| sales_quota.gross_margin_quota_by_scenario | **有条件成立** | 同上 |
| strategy_plan.plan_revenue_by_scenario | 成立 | 全部场景、显式 Actual、显式 Forecast 都一致；收入账户仍受约束 |
| sales.same_store_sales_as_base_year | 成立 | 分别以 2007、2008 作基年，独立筛两年均有销售的门店后汇总基年金额，两接口一致 |
| online_sales.new_customer_count | **不成立：引擎限制** | 5 个单日截止日和一条连续月份滑动查询，两接口共 12 次全部执行失败，见下节 |

前三个目标变体的“不筛场景”对照，非空场景的数值没有错，但实际多出 `[NULL, NULL]`。原因是所属 Cube 同时容纳无场景的实绩行；度量过滤不会移除该分组。显式场景筛选、或 `scenario.ScenarioName set` / SQL `IS NOT NULL` 后与物理参考相同。原先 6 条整行集差异全部保存，没有过滤结果后冒称原探针通过。这里是调用条件，不能把三个变体一概判成不可调用。

另补 6 条子项筛选对照：产品键范围筛选下的两种品类内占比、门店键范围筛选下的渠道内占比，均保持筛选范围，分母没有错误扩大到全部子项，两接口与物理基线一致。

总计 80 次本地接口执行：54 条变体/同店/新客，16 条说明及空组条件，4 条预期连接失败，6 条子项筛选。58 条正向结果与物理聚合一致、4 条负向错误符合预期、12 条新客执行失败、6 条未筛场景的空组差异。完整逐项查询、错误原文、行数、原始证据哈希见 `results.json`；完整行集留数据目录。

## 3. 新客窗口确实验证了滑动

独立基线先在完整事实表求每个客户首次购买日，再对每个截止日筛 `[截止日−89天, 截止日]`，不是只数当前查询窗口内发生的交易。

| 截止日 | 独立物理计数 | JSON / SQL |
|---|---:|---|
| 2007-02-10 | 14,463 | 均执行失败 |
| 2007-03-11 | 16,638 | 均执行失败 |
| 2007-04-13 | 10,011 | 均执行失败 |
| 2007-05-17 | 3,892 | 均执行失败 |
| 2007-07-21 | 0 | 均执行失败 |

另外一次 2007-02 至 2007-05 的按月输出，4 个截止日的期望计数依次为 15,910、18,015、5,894、2,868，两接口也都失败。未把整段时间的一个累计数当作滑动窗口通过证据。

错误原文起始：`Cannot determine join keys in JOIN ON expression [Predcates: () Residual filter: ...]`。Cube 生成连接窗口序列与事实日期的范围 JOIN，当前 ClickHouse 执行栈不能为它确定连接键。完整原文均在 `results.json`，没有脱敏，也没有尝试改 ClickHouse 设置绕过。

## 4. 两份说明逐字核对

核对的是该提交实际文件，逐句原文与行号保存在 `results.json.notes_verbatim_review`。**四条新增说明不是先前 T16 交接建议的逐字复制**；原文相等检查均为 false，不能声称“文字逐字相同”。逐字读过后的技术条件，已有以下实测支撑：

| 说明中的条件 | 本轮证据 |
|---|---|
| 使用复合指标所属 Cube 的日期 | inventory、sales_quota 均按自己日期分两个月输出，两接口与独立物理聚合一致 |
| 已有公共日历连接时可用日历日期 | 两个 Cube 均按 calendar.DateKey 分月，两接口一致；不泛化到任意连接图 |
| 不要为公式内部的另一事实来源另加日期筛选 | 两个 Cube × 两接口均复现 join-path 错误 |
| CROSS JOIN / JSON 添加成员不会创建新路径 | 同上，负探针符合禁止条件 |
| 月目标和日实绩按同一完整月份比较 | 分月正向探针一致 |
| 月目标不会按天摊分 | 2007-02 前半月的目标仍等于完整二月目标，两接口与完整月物理目标一致；不意味着任意半月区间都有目标行 |

未发现新增时间筛选条款中有本轮证据不支持的技术说法；没有改写说明。该结论仍受“原候选整模型加载失败”的总闸约束。

## 5. 只删除建议与未执行项

1. **删除 11 处不存在成员的 reduce_by 引用**，见附件。T12 应在生成端使重渲产物得到同样删项，再交新的分支头；本次没有修改生成器、语义源或扩展指标范围。
2. **将未通过的新客 rolling_window 实现从“可用且已对齐”的交付项中删除，标为接口限制**，本轮不提供改写公式或替代实现。不能仅删 rolling_window 选项后把查询窗内首购人数当作等价 90 日新客数；旧实现的窗口漏计也不能被重新宣布合格。
3. 三个场景变体是有条件成立，不建议删除。保留未筛场景空组的边界记录。

第 4 项“全部通过后固定覆盖表”的前提未满足，所以**没有生成或提交新的标准成员集与 (a)–(d) 固定表**；`t16_l2_scope_coverage.{md,json}` 仍为 `9a3a4a6` 的原版本。季度变体在诊断模型中可用，不足以提前把 Q94 从 b 改成能答；Q114 的新客实现未通过，也不能转为能答。

隐藏成员另存 `results.json.hidden_members`：15 个辅助度量、8 个技术主键维度全部标为 **不公开、不计交付**，并核对未作为指标调用名出现在重渲 JSON-L2 上下文中。没有建议公开这些实现细节。

## 复现

源码快照和全部行集位于 `$SEMDEBT_DATA_DIR/interface-probes/t16-v14-86d8826/`。该目录的 `source` 为 `git archive 86d8826` 导出，完整与删项模型分别在 `source/build/cube/model`、`deletion-model`。`results.json` 保存候选源与生成模型哈希，确认源未改。

重新导出到新的证据目录、用现有虚拟环境重渲 `render.cube` 和 `render.context JSON-L2`，先按该快照模型挂载启动 Cube 并请求 `/meta`。不能用 `/readyz` 替代编译验证。若原样失败，保存原证据；删项诊断只能另存副本、另行挂载。

在已经明确加载记录中诊断模型的前提下，本轮四个只读检查命令为：

```sh
env -u DEEPSEEK_API_KEY uv run --offline python -m scripts.verify_cube_v14_t16 --mode deletion-diagnostic
env -u DEEPSEEK_API_KEY uv run --offline python -m scripts.verify_cube_v14_t16 --mode deletion-diagnostic --suite time-notes
env -u DEEPSEEK_API_KEY uv run --offline python -m scripts.verify_cube_v14_t16 --mode deletion-diagnostic --suite negative
env -u DEEPSEEK_API_KEY uv run --offline python -m scripts.verify_cube_v14_t16 --mode deletion-diagnostic --suite scopes
```

脚本拒绝覆盖既有证据。原始日志和评分器未触碰，模型调用次数为 0。
