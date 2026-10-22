# T16 L2 交付审查（无模型调用）

审查对象：`eval-v1.2` + `semantic-v1.3`，Cube Core 1.8.6；源运行 `20261019-T16-pilot-v13-02`。不改冻结材料、不改原作答或分数。本文只写题号、类别、能力证据，不写题面或题目专用查询。按题诊断查询、返回行集和参考核验留在 `$SEMDEBT_DATA_DIR/interface-probes/t16-l2-delivery-audit-20261019/`。

## 后续补充分责

按用户新增口径，原“当前交付接口限制10条”进一步归责为 **①常用指标交付不足9条、②题目特有组合的JSON接口限制1条（Q117）**。这是交付责任层次，不改变当前10条均不能用现有成员完整表达的事实。详见 [逐题补充分责及建议指标](t16_l2_delivery_classification.md)；原下文保留原审查的技术可表达性口径，不可再直接把10条全部算作接口本身限制。

## 结论

- JSON-L2 的10条拒答：现有成员下一条正确JSON可表达 **0条**；按用户给定“不能→接口限制”口径，**10条当前交付接口限制，0条可表达但素材误导**。其中多项缺预定义度量/派生维度，扩充模型可能补齐；这属于当前交付能力不足，不是声称Cube产品永久做不到。
- SQL-L2 的4条执行失败：**4条写法说明缺口，0条已证实接口能力限制，占比0/4=0%**。Q80已定位，不能再列待定。原查询全部复现错误；仅改英文输出别名全部可执行。Q50/Q76/Q80还直接通过v2参考核验。Q82的英文版本虽执行却为空，另用两侧分别聚合的CTE得到正确结果并通过v2核验。
- 上述手写诊断不替换模型作答、不重写冒烟成绩。此前Q50“违反列名规则”虽是事实，但本轮只改别名即可成功且通过参考，故不能继续把它当该执行错误的已证实根因。
- 全量不估算、不启动；模型调用0、模型费用0。

## JSON判定口径

一条JSON查询只能引用现有已定义成员，直接产生所需结果。取回明细后用Python/SQL重算、分多次请求拼接、把参考答案推导的阈值或对象清单硬编码进filters，都不算本单元能够表达。判断同时检查必答列和选择规则，不把只返回部分基础指标的查询算成正确答案。

静态模型与实时/meta的25个cube、338个成员名完全一致（102度量、236维度）；没有已定义segment。92个度量标记可见，另10个隐藏辅助度量也纳入审查；主键的隐藏标记同样不作能力排除依据。`J_hidden_key`、`J_hidden_measure`直接验证不可见成员可显式查询。

| 题号 | 一条正确JSON | 类别 | 缺失能力代码 | 已有相关成员（不足以构成完整答案） |
|---|---|---|---|---|
| Q100 | 不能 | 接口限制（当前冻结交付） | I-RANK, I-INTERSECT | `online_sales.order_count`, `online_sales.average_order_value` |
| Q117 | 不能 | 接口限制（当前冻结交付） | I-NEST, I-RANK, I-SCOPE | `sales.same_store_sales_growth_pct`, `sales.same_store_sales_amount` |
| Q70 | 不能 | 接口限制（当前冻结交付） | I-AGG | `sales.sales_amount`, `store.SellingAreaSize` |
| Q71 | 不能 | 接口限制（当前冻结交付） | I-NEST | `online_sales.sales_amount` |
| Q73 | 不能 | 接口限制（当前冻结交付） | I-EXPR, I-RANK | `inventory.current_on_hand_quantity`, `inventory.current_safety_stock_quantity` |
| Q74 | 不能 | 接口限制（当前冻结交付） | I-NEST, I-RANK, I-SCOPE | `sales.sales_amount`, `sales.sales_amount_share` |
| Q76 | 不能 | 接口限制（当前冻结交付） | I-COHORT, I-EXPR | `online_sales.order_count`, `online_sales.sales_amount` |
| Q80 | 不能 | 接口限制（当前冻结交付） | I-REAGG | `online_sales.customer_recency_months`, `online_sales.DateKey` |
| Q81 | 不能 | 接口限制（当前冻结交付） | I-REAGG, I-DERIVED | `online_sales.sales_per_customer`, `online_sales.customer_count` |
| Q82 | 不能 | 接口限制（当前冻结交付） | I-SELF, I-AGG, I-EXPR | `employee.EmployeeKey`, `employee.ParentEmployeeKey`, `employee.HireDate` |

能力代码是通用操作定义，不是题面复述：

- **I-RANK**：无已定义排名/分位成员；不能动态产生名次、百分位筛选阈值。
- **I-INTERSECT**：不能求两个由聚合结果动态排名产生的集合的交集。
- **I-NEST**：limit作用于整个结果；没有分组内Top-N或父子两阶段选择。
- **I-SCOPE**：没有所需分母作用域/差额占比成员；现有share的group_by为空，不能临时改成按父组归约。
- **I-AGG**：缺少所需预定义聚合度量；维度存在不代表可以临时对它写AVG/COUNT。
- **I-EXPR**：缺少所需预定义计算成员；JSON不能临时写算术或日期差表达式。
- **I-COHORT**：缺少所需聚合后群组判定再重聚合的计算成员；对当前分组的指标做filter不是先按另一粒度选集合。
- **I-REAGG**：缺少所需两级聚合成员；JSON不能先按实体聚合、再对实体结果重新分组/平均。
- **I-DERIVED**：所需派生分组键没有定义为维度；不能把MIN等聚合表达式临时用作维度。
- **I-SELF**：缺少所需预定义自关联关系和度量；不能临时声明第二个cube别名及ON条件。

### 现有说明是否误导

本轮没有“能用既有成员写对、却被说明误导拒答”的实例。因此“素材缺陷（可表达分支）”为0，不据拒答数量直接指控命名/描述不清。下列原句描述了实际边界，通用探针亦支持：

- `render/syntax/cube_json.md:5`：「只能引用数据模型里已定义的成员」；成员字符串不能写表达式。
- `:11`：「连接条件不需要也不能写。」
- `:17`：「limit 作用于整个结果，不能『每组各取前 N』。」
- `:19`：「不能写任意表达式……这些计算只能由模型里已定义的指标完成。」
- `:20`：「数据模型里有对应的指标时直接调用它；没有时，这个接口在一条查询里表达不了。」

“指标缺失”在这里是当前能力短板，不能只靠改名称、说明或一段语法提示补齐；需要新增可调用的计算或改变作答协议。本轮仅报告，不实施扩模。以上不能被解读为所有缺失能力都是JSON协议的固有限制。

## SQL逐条归因

| 题号 | 最终类别 | 定位证据 | 正确实现核验 |
|---|---|---|---|
| Q50 | 写法说明缺口：聚合CTE互连的中文输出别名 | 原样报错；只替换输出别名，其他逻辑和CTE同名输出保持原样，即可执行 | v2正确，1行；通用G_join_aggregate正反例 |
| Q76 | 写法说明缺口：聚合CTE互连后再聚合的中文输出别名 | 原样报错；只替换输出别名即可执行 | v2正确，9行；通用G_join_aggregate正反例 |
| Q80 | 写法说明缺口：多层维度聚合后排序的中文输出别名；已定位 | 原样报空标识符；只替换输出别名即可执行，不改日期逻辑 | v2正确，29行；G_date_chain_unicode/ASCII正反例，取消ORDER BY则中文别名可执行且数值正确 |
| Q82 | 写法说明缺口：中文输出别名，以及同cube直接多别名不能当独立扫描 | 只换英文后错误消失但返回0行；两侧分别聚合CTE、独立列名后得到完整结果 | v2正确，11行；G_dimension_self_direct静默空集，G_dimension_self_aggregated与物理表自连接3行逐值相等 |

v2按原eval-v1.2题级及逐参考rules执行，使用原10秒打分超时闸，四条均为correct、无pending。没有为了报告改评分器或放宽规则；SQL诊断结果不是新的模型实验成绩。Q82区分“报错根因已解”和“查询语义正确”两层，不能仅因英文版不报错就判通过。

### 应增补的条件所针对的原句

- `cube_sql.md:12`允许双引号中文别名，仅把输出窗口结果列为例外；本轮证明复杂投影/再聚合排序还有例外。
- `:46`允许外层再聚合，未覆盖再聚合+排序时的中文别名投影错误。
- `:49`要求两聚合CTE列名彼此不同；这是已验可用规范，但不是修复所有错误的充分条件，也不能把同名就必错当成定理。
- `:15–22`讲cube连接与两个事实cube分开聚合，未说明同一cube重复引用不等价于两个独立表扫描。

本次只提出追加说明，见 `t16_l2_delivery_additions.md`；不删除、不替换或直接修改上述原句。

## 通用探针与独立核验

25条通用探针（不含题面、不是从题目查询复制的样例），11条接受、14条预期报错；另有9条按题故障诊断，全部保存在外部数据目录。通用探针完整查询及原始报错见本报告同名JSON的generic_probes，不包含按题查询。

- 中文别名不是一概不可用：单CTE外层聚合、多层日期聚合在不排序时均可用；加ORDER BY后报错，按原列排序和按中文别名排序都报错；英文版排序可用。
- 两聚合CTE互连再聚合，英文输出正常，中文输出报错。
- 同一小维度两别名直接关联“不报错但空集”；分别聚合为两个CTE后返回3行，与物理表自连接一致。
- JSON既有成员查询成功；临时AVG度量、算术成员、窗口表达式、派生维度、手写join均拒绝。隐藏成员显式查询成功，不误当成成员不存在。
- 额外只读核对了容器实际安装的api-gateway/query.js和gateway.js：schema包含expression数组及PatchMeasure形态，因此不以最初错误格式的拒绝作为唯一证据；正确数组形态、序列化SqlFunction形态、PatchMeasure形态均直接补测，分别报参数匹配失败、REST上下文不允许表达式、反序列化类型错误。当前REST /load未发现可用的临时成员通路。
- 6项独立数值检查全部通过：原始FactSales按键聚合、日期跨度按实体算再平均、原始DimChannel自连接。相对1e-8/绝对1e-6只用于接口控制，不改评分器容差。

## 复现与完整性

先设置SEMDEBT_DATA_DIR指向外部数据目录，SEMDEBT_EVAL_DIR指向eval-v1.2只读副本；所有命令显式移除DEEPSEEK_API_KEY。

```sh
env -u DEEPSEEK_API_KEY uv run python scripts/audit_l2_delivery_t16.py --stage report
```

该命令核验既存探针文件哈希，重新执行4条固定ClickHouse物理基线及4条v2参考比较，重建JSON摘要；不重放模型、不执行原候选。完整重新采集请换新的--audit-id：依次inventory、localize，再用external读取原外部目录phase2/phase3/phase4/phase5-cases.json，最后report。若只重放通用探针，可在新audit-id使用generic；其输入取已提交JSON中的通用查询。按题查询与任何行集均不提交。

脚本拒绝覆盖已存在的单次探针文件；外部summary按行追加。报告保存每条文件sha256，模型原始拒答及两个原运行日志sha256核验不变。脚本要求环境中没有DEEPSEEK_API_KEY；不构建模型客户端、不调用模型API。harness/prompt.py、scorer.py、scorer_v2.py、score_guard.py与main d2801b1逐字节一致；semantic/与render/仍等于semantic-v1.3。

审查结束不自动放行全量。等待用户审定交付结论；本轮不估费用、不跑模型、不改模型、说明、系统提示、评分器或任何tag。
