# SQL-L1 20道不稳定题逐题比较

复现：`uv run python reports/midterm/analyze.py`。题库标签 eval-v1.2 = `90e13b385a639a9164ac78430c50c11a7859f976`；仅通过 git show 读取冻结对象，不使用题库当前工作树。

范围为109题（含低区分度Q79）；主表98题中有19道。按三次最终判定取0<正确次数<3。
人工比较三次最终SQL、执行状态和已有T19b复核意见；主类每题唯一，多处变化在说明中保留。这里解释判定变化，不自行改判或修改冻结内容。
已校验60次最终作答的原始响应与执行文件共120份SHA256，均与日志一致；文件路径、哈希和日志行见raw-check.csv。未把原始响应或数据行复制入库。
呈现类只说明表面写法及既有复核指出的可疑点，不宣称重新执行后已证明等价；旧评分器的呈现问题由T23处理。

| 主类 | 题数及占比 |
|---|---|
| 关联路径与空值 | 2/20（10.0%） |
| 呈现与评分边界 | 7/20（35.0%） |
| 执行错误 | 1/20（5.0%） |
| 筛选与纳入范围 | 5/20（25.0%） |
| 表选择与层级路径 | 1/20（5.0%） |
| 读法与分组粒度 | 4/20（20.0%） |

| 题号 | 范围 | 主类 | 三次首轮→最终 | 三次差异与限制 | 日志行 |
|---|---|---|---|---|---|
| Q05 | 主表 | 关联路径与空值 | r1:exec_error→correct(—)；r2:exec_error→wrong(values)；r3:exec_error→correct(—) | r1/r3从产品出发左连接并计行；r2从品类出发左连接再count产品键，未匹配默认键可能被计入。三次都有首轮报错，最终只有r2错。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:21；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:16；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:20 |
| Q12 | 主表 | 呈现与评分边界 | r1:exec_error→wrong(values)；r2:correct→correct(—)；r3:exec_error→wrong(values) | r1输出月初日期；r2同时输出数字月份和月份标签；r3仅输出月份标签。汇总表相同，呈现改变，r2对、r1/r3错；T19b已标呈现可疑。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:88；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:152；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:92 |
| Q18 | 主表 | 读法与分组粒度 | r1:wrong→wrong(row_count)；r2:exec_error→correct(—)；r3:wrong→wrong(row_count) | r1按促销类型及名称分组，r3按活动名称分组；r2仅按促销类型分组并答对。表与过滤基本相同，聚合粒度不同。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:117；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:124；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:120 |
| Q24 | 主表 | 执行错误 | r1:correct→correct(—)；r2:exec_error→exec_error(—)；r3:exec_error→correct(—) | r1/r3使用普通数值转换或直接键关联并执行成功；r2用toInt32OrZero处理数值型子类键，修正后仍engine_error。最终变化由执行失败直接造成。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:138；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:140；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:143 |
| Q27 | 主表 | 呈现与评分边界 | r1:correct→correct(—)；r2:correct→correct(—)；r3:wrong→wrong(values) | 三次都用产品标价和单位成本算利润率并取前列，r1/r2对、r3错；名次次序、并列打破、输出精度及比例单位同时变化。既有复核指向并列边界，不能把它概括成公式不懂。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:144；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:147；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:146 |
| Q30 | 主表 | 读法与分组粒度 | r1:wrong→wrong(values)；r2:correct→correct(—)；r3:wrong→wrong(values) | r1/r3先取展示期之前的历史再算滚动窗口；r2在展示期内起算，只有r2对。两种窗口起点读法造成差异。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:156；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:153；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:159 |
| Q37 | 主表 | 筛选与纳入范围 | r1:exec_error→correct(—)；r2:wrong→wrong(row_count)；r3:correct→correct(—) | r2增加StoreType实体店筛选并错；r1/r3无该限制并对。按门店排名的范围不同。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:177；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:175；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:176 |
| Q47 | 主表 | 读法与分组粒度 | r1:exec_error→correct(—)；r2:wrong→wrong(values)；r3:correct→correct(—) | r1按事件取平均并对；r2按去重设备作分母并错；r3同时输出设备与事件两种平均并对。分母读法与输出覆盖均有变化。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:208；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:206；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:207 |
| Q49 | 主表 | 表选择与层级路径 | r1:wrong→wrong(values)；r2:correct→correct(—)；r3:wrong→wrong(row_count) | r1取计划事实表并按固定多级UNION上卷；r2取销售事实经门店及实际父链上卷；r3同取销售但按名称合并并造空层级组。仅r2对，既有复核还指出跳级重复累计与重名合并。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:221；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:224；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:236 |
| Q56 | 主表 | 筛选与纳入范围 | r1:exec_error→correct(—)；r2:exec_error→wrong(values)；r3:exec_error→correct(—) | r1/r3保留全部客户的均值，并附加稳健统计；r2只给剔除高收入档后的均值，只有r2错。异常值是否剔除的取舍不同。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:238；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:237；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:239 |
| Q58 | 主表 | 读法与分组粒度 | r1:wrong→wrong(values)；r2:exec_error→correct(—)；r3:wrong→wrong(values) | r1/r3按订单号汇总后取最大；r2直接取交易明细极值并对。订单与明细行的粒度读法不同。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:240；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:245；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:242 |
| Q72 | 主表 | 呈现与评分边界 | r1:exec_error→correct(—)；r2:wrong→wrong(values)；r3:correct→correct(—) | r1/r3分列年份和季度并对；r2合成年季period字符串并错。累计计算结构相近，输出期间形态不同；未重新执行证明等价。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:283；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:279；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:287 |
| Q74 | 主表 | 筛选与纳入范围 | r1:wrong→wrong(selection)；r2:exec_error→correct(—)；r3:correct→correct(—) | r1限制实体店并错；r2/r3不限制并对，后两次也保留分母列、设置join_use_nulls。筛选和呈现同时变化，不能只从reason断言单因果。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:289；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:292；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:291 |
| Q79 | 低区分度 | 呈现与评分边界 | r1:correct→correct(—)；r2:exec_error→wrong(rank)；r3:correct→correct(—) | 低区分度题；r1/r3按未舍入比率排序并设名称破并列，r2给窗口编号后按舍入百分比排序。r2的rank错，其他两次对；排序精度与并列顺序不同。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:305；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:309；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:304 |
| Q81 | 主表 | 呈现与评分边界 | r1:correct→correct(—)；r2:wrong→wrong(values)；r3:correct→correct(—) | r1/r3输出数值年份并对；r2将年份加Year前缀并错。首购与消费汇总结构相同，标签形态改变。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:303；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:306；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:308 |
| Q89 | 主表 | 筛选与纳入范围 | r1:wrong→wrong(values)；r2:wrong→wrong(values)；r3:exec_error→correct(—) | r1仅在SalesQuantity>0时计产品，r2限制SalesQuantity=1；r3所有交易行计去重产品并对。购买事件范围不同，另有输出列变化。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:332；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:330；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:333 |
| Q92 | 主表 | 关联路径与空值 | r1:wrong→wrong(row_count)；r2:exec_error→correct(—)；r3:correct→correct(—) | r1内连接产品表丢掉缺产品的事实组并错；r2/r3左连接且显式保留未知品牌组并对。排名函数及比例展示也有变化。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:341；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:339；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:344 |
| Q109 | 主表 | 呈现与评分边界 | r1:wrong→wrong(values)；r2:correct→correct(—)；r3:wrong→wrong(values) | r1/r3把年与季度合成字符串并错；r2给Q季度标签并对。三次都先按日再按季求平均，期间输出形态和辅助列不同。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:54；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:58；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:57 |
| Q110 | 主表 | 呈现与评分边界 | r1:exec_error→correct(—)；r2:exec_error→wrong(values)；r3:correct→correct(—) | r1/r3给数值年份并对；r2用toString年份并错。渠道条件也有键值和名称两种写法，既有复核把主要可疑点标为年份数值/文本不等价。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:63；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:65；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:66 |
| Q119 | 主表 | 筛选与纳入范围 | r1:correct→correct(—)；r2:wrong→wrong(selection)；r3:correct→correct(—) | r2额外限制实体店并selection错；r1/r3无实体店限制并对。三次都计算店内赢家与公司产品排名，范围变化是主要区别。 | runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:87；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:94；runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl:89 |
