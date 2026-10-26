# T29 B2：按声明假设认可（免费敏感性分析）

SQL-L1plus原109题×3次，按冻结B1人工逐条核对最终假设与SQL，再用原v2规则核对对应结果；主评分不改。私有标注、原包与B1哈希均已校验。无新API调用。

|类别|次数|
|---|---:|
|总作答|327|
|原主评分正确|245|
|B2正确|235|
|新认可|5|
|声明与命中参考明确矛盾而撤销|11|
|符合可疑旧参考、违反明确约定，另列排除|4|
|单一理解题只写无|17|
|多解题只写无|0|
|多解题未声明所选理解|7|
|笼统声明结合SQL映射的额外认可上限（不计主口径）|2|

|题号|类别|次数|
|---|---|---:|
|Q58|newly_recognized|3|
|Q65|newly_recognized|1|
|Q82|newly_recognized|1|
|Q100|revoked_declared_contradiction|2|
|Q115|revoked_declared_contradiction|1|
|Q118|revoked_declared_contradiction|2|
|Q120|revoked_declared_contradiction|3|
|Q30|revoked_declared_contradiction|3|
|Q35|excluded_reference_l1plus|3|
|Q82|excluded_reference_l1plus|1|

未声明或笼统声明不用于撤销。只有单一理解的无声明按唯一理解处理；多解无声明不给新认可。约定排除与假设矛盾撤销分开，数量关系为：原正确＋新认可−矛盾撤销−约定排除＝B2正确。结合SQL映射笼统声明的上限只作参考，不进入B2主口径。

这是敏感性分析，不替换v2主评分，也不改变冻结B1。新B1参考仅沿用v2比较，不增加期间转换或其他v3呈现宽容。结果中的不认可不能直接归因于模型选择能力；本表不是正式运行的效果结论。

逐次题号/单元/类别、私有标注及来源哈希见`t29-assumptions-audit.json`；假设、SQL与参考结果原文仅保留于SEMDEBT_DATA_DIR。
