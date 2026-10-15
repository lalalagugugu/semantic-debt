# 2026-10-15 量纲容差与固定并列精度的实现约定

- 授权：用户2026-10-15对open question #7选A，明确量纲判定与固定量化精度由Codex确定；#8仍只估算，不改变正式规则。
- 依据：`2026-10-14-scorer-contract-and-acceptance.md` 第三、四节。
- 规则版本：2026-10-15；实现唯一来源：`harness/value_units.py`。

## 量纲输入与判定

纯评分器接收参考列顺序的 `rules.value_kinds`（percentage/ratio/amount/count/other）；列顺序映射时跟随参考列，不跟随候选列。旧调用未提供时按other，不从数值大小猜金额、比率或计数。验证适配器从参考查询的JSONCompact元数据获取列名与返回类型；不读候选列名，不按题号配置。

名称按CamelCase和非字母边界拆词、转小写。固定优先级为：

1. pct/percent/percentage/percentile/pp → percentage。
2. ratio/rate/correlation/corr → ratio。
3. count/countDistinct/num/n/customers/orders/stores/brands/employees/observations/reports/units/returns、cohort size、returned → count。
4. 整数返回类型且名称含sales、但不含amount/price/revenue → count（数量聚合）。
5. amount/amt/revenue/sales/spend/spent/cost/cogs/price/profit/income/budget/quota/ltv/dollars/discount/margin、lifetime value → amount。
6. 其余 → other。

适配器另用一套全局表达式规则识别参考SQL中COUNT/countDistinct/countIf/uniqExact的显式输出别名，优先标为count。此规则扫描表达式，不列举题号；带嵌套表达式或不表达量纲的别名可能无法识别，保守回退到名称规则/other。未来harness应透传同样自动生成的元数据。量纲识别是明确的命名契约，不是从列值证明业务含义；报告逐题披露量纲向量，便于检查覆盖。不得针对某题追加例外或调容差。

## 结果比较

`abs(candidate-reference) <= max(0.005*abs(reference), atol)`：amount=0.01；ratio=1e-4；percentage先除100转换到小数形式后=1e-4（原单位0.01）；count/other=0。

保留原第5条的小数/百分比等价匹配，保证原来匹配的单元格仍匹配。只有比率类的新绝对下限用于额外单位换算；参考为零时只在声明的参考单位下用绝对下限，不猜100倍单位。现有浮点边界舍入保护保留。NULL、NaN/Inf、列/行映射规则保持原契约。

同一批候选执行结果同时运行旧提交评分器、新评分器、固定新并列参考下的relative-only诊断，检查没有correct→非correct。只将count列改为精确相等的反事实独立输出，正式准确率不使用该反事实。

## 与结果容差完全独立的并列键

- 数值以其十进制字符串构造Decimal；ROUND_HALF_EVEN，不用引擎默认round。
- amount保留2位小数。
- ratio保留6位；percentage先除100，再保留6位。
- count和other数值保留6位；非数值键维持原值。
- 精度全局一次固定，不逐题、逐列临时选择，不引入atol或0.5%容差。

适配器用量化键排序并收全第N名边界成员；量化键相同的参考行以统一行编码固定行序。三次原始参考哈希检查用于同引擎稳定性；T05b跨引擎应核对量化键与成员集合，不要求原始浮点哈希相同。恰在量化边界两侧的跨引擎差异仍须逐题报告，不允许为了消掉差异临时改精度。T06检查未解决的边界成员差异，不得带入eval-v1。
