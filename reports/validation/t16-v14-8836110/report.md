# T16：v1.4 第二轮 8836110 验证与覆盖固定

结论：**本轮要求验证通过**。精确候选为 `883611029a65c12d8cc507bc363dda84a4db10b1`（PR #144 / T12-v14）。本次加载完整重渲模型，没有删项或改写源码；新客数按用户要求确认恢复 main 原成员，完整 90 日集合的参考读法仍列接口限制。

全程零模型调用、零评分调用，不重评、不估全量。提示、评分器、语义源、渲染器与历史运行日志均未修改。

## 完整模型

- 从候选提交独立导出并重渲 Cube 模型，25 个 Cube、102 个公开指标。
- 以完整模型挂载启动 Cube 1.8.6，`/readyz` 200、`/cubejs-api/v1/meta` **200，25 个 Cube 全部可编译**。没有沿用上一轮删项副本。
- 三个父组分母辅助成员的完整定义，与 `86d8826 + 上轮11处只删除补丁` 的相应成员逐项一致。
- 候选的渲染期检查及多阶段变体测试通过 2 项；检查会拒绝注入的不存在维度 `product.ClassID`。
- 验证结束恢复 T16 原模型挂载，恢复后 `/meta` 200。后续正式运行应重新加载最终 tag 的模型，不把此次临时挂载当作已经开跑。

## 通用探针与物理基线

72 次本地接口执行全部符合预期：68 次正向结果与独立原始事实聚合一致，4 次负向探针复现禁止条件。没有静默丢行、重试失败作答或调用模型。完整行集在外部数据目录；`results.json` 保留查询、错误原文、行数、行集哈希、源码/模型/上下文版本证据。

| 调用名 / 项目 | 覆盖条件 | JSON / SQL |
|---|---|---|
| sales.sales_amount_share_in_channel | 渠道内门店分母；另验子项门店范围筛选不会被去掉 | 均与物理基线一致 |
| sales.sales_amount_share_in_category | 品类下分别按子类、产品分组；另验产品范围筛选 | 均一致 |
| online_sales.sales_amount_share_in_category | 同上 | 均一致 |
| sales.sales_amount_qoq_pct | 多个相邻季度；另验门店维度、单季时间筛选和指标负值筛选 | 均一致 |
| online_sales.sales_amount_qoq_pct | 同上 | 均一致 |
| sales_quota.sales_amount_quota_by_scenario | 分别显式筛 Budget、Actual、Forecast；另验场景非空 | 均一致 |
| sales_quota.sales_quantity_quota_by_scenario | 同上 | 均一致 |
| sales_quota.gross_margin_quota_by_scenario | 同上 | 均一致 |
| strategy_plan.plan_revenue_by_scenario | 全场景分组、显式 Actual / Forecast，仍限制收入账户 | 均一致 |
| sales.same_store_sales_as_base_year | 分别以2007、2008作基年，同一对比较年份的共同门店集合 | 均一致 |
| 跨事实日期条件 | 所属 Cube / 公共日历按月分组；整月目标不按半月比例缩放 | 均一致 |
| 禁止额外事实日期 | inventory、sales_quota 额外引入 sales 日期 | 4 次均按预期报 join-path 错误 |

三个目标场景变体的候选说明已写明“查询必须显式筛场景，筛具体场景或场景非空”。本轮按该条件测试，不将上轮不筛场景出现的 NULL 空组当作本轮未解决的数值错误；边界事实仍在第一轮报告留档。

季度负值筛选的全渠道门店通用探针，物理参考与两接口均为6行；不是仅在空结果上判断这一组合成立。线上对应负值集合为空，亦如实记录；另有非空的线上连续季度数值对照。

## 新客数与 main 逐字一致

对照 main `0e5f9bb061516d58f83dd6e69868371a7fd20412` 独立导出、重渲的模型：

1. `render/measures.py` 的“新客数”定义行逐字节相同。
2. `online_sales.yml` 中 `new_customer_count` 的完整 YAML 成员块（含展开的 SQL）逐字节相同，SHA256 见 `results.json.static_byte_checks`。
3. 本轮不再把该成员宣称成完整截止日前90日客户集合的修复；上轮 rolling_window 的12次引擎失败作为限制证据保留，未重复失败调用，也没有恢复其候选实现。

“恢复 main 原成员”的本轮要求通过，**不代表参考读法缺口消失**。

## 固定 JSON-L2 分类与标准成员集

固定表为本目录 `coverage.json`、`coverage.md`，由 `scripts/freeze_l2_v14_coverage_t16.py` 在完整加载和72条验证通过后生成。登记版本以**包含这两份文件的 Git 提交号**引用；候选语义内容固定为上述 `8836110`，未假设 semantic-v1.4 tag 已存在。最终 tag 的交付内容若有变化，须先复核本表，不能静默沿用。

| 范围 | 能答 | a | b | c | d | 合计 |
|---|---:|---:|---:|---:|---:|---:|
| 非 judge 全部（含低区分度） | 39 | 34 | 0 | 27 | 9 | 109 |

主表98题、低区分度11题分别标记；judge13题不进入标注或分母。相对 `9a3a4a6` 的登记，仅两题发生分类变化：

| 题号 | 原类别 | 本轮类别 | 固定依据 |
|---|---|---|---|
| Q94 | b | 能答 | 可见 sales.sales_amount_qoq_pct；标准集为 sales.DateKey、sales.sales_amount_qoq_pct、store.StoreName；时间粒度 quarter |
| Q114 | b | c | 完整90日集合的实现被证实受引擎限制，恢复 main 原成员仍不满足该读法 |

其余已有正确标准集保留；不因新增加等价调用名就事后改选唯一“标准”。所有39个标准集均验证存在于候选模型及 L2 上下文。后续机械拆分沿用预先登记规则：执行报错优先；执行成功后区分成员集不同、成员集相同但结果不同。该描述性分组不替代正式评分。

隐藏成员：15个辅助度量、8个技术键维度，全部 **不公开、不计覆盖**，逐名列于固定表。没有公开分母或比较期辅助成员来把展示缺口偷偷转成能答。原覆盖登记不覆盖、原分数不改。

本轮没有需要追加的只删除建议；第一轮未通过结论保留为历史，不再作为第二轮模型加载结论。

## 复现入口

候选导出与完整行集：`$SEMDEBT_DATA_DIR/interface-probes/t16-v14-8836110/`。源文件与模型哈希写进固定表，全部探针证据哈希写进 `results.json`。三个目标变体的显式场景条件包含在重渲上下文中。

已加载记录中的完整模型后执行（脚本会核对挂载路径，拒绝覆盖旧证据）：

```sh
env -u DEEPSEEK_API_KEY uv run --offline python -m scripts.verify_cube_v14_t16 \
  --mode full --suite round2 \
  --audit-dir "$SEMDEBT_DATA_DIR/interface-probes/t16-v14-8836110"
```

覆盖登记使用 `eval-v1.2` 只读副本，校验其完整 tag 内容，再验证候选上下文、所有标准集、隐藏状态及加载/探针前置条件。脚本拒绝覆盖已生成的固定表。
