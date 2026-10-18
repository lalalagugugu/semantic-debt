# T02 评分器 v2 验证（历史检查点）

> 历史检查点：本报告基于 eval-v1.1 和第十二节合并前的规格，不代表当前判定或验收结果。第十二节共用用例的当前结果见 `scorer_v2_shared_check.md`；正式对账等待按 eval-v1.2 重新导出的语料。

语料只读；不执行查询、不调用模型。judge 单列，不进入评分器。

- 输入行数：3645；分类：`{'correct': 1295, 'exec_error': 524, 'wrong': 1191, 'judge': 388, 'invalid_input': 137, 'refused': 110}`。
- unscored：0；新评分超时：0；输入不合法：137。
- 旧评分超时上限：10.0 秒；判定差异：46；旧评分未完成：12。
- 完整逐条耗时和原因：`scorer_v2_cases.jsonl`。

## 输入指纹

- pilot288.jsonl：`ddecb0355656911e2c1a3eb13277fc85946ec460a6aabbcfe25219546395b586`
- t13.jsonl：`600946ea962d241a2c829b9d13e9412686f72ca5c8360beac818b63e000367b2`
- ext600.jsonl：`fc248fe1bfcc92039b27f4514a1602ab4bb9b5fcb337521a376262fa99093f37`

## 最慢 10 条

| case_id | 秒 | 状态 / 判定 |
|---|---:|---|
| t13/SQL-L1/Q34/r1 | 0.348111 | correct |
| t13/SQL-L1.5W/Q34/r3 | 0.312819 | correct |
| t13/SQL-L1/Q34/r2 | 0.301699 | correct |
| t13/SQL-L1/Q34/r3 | 0.282403 | correct |
| t13/SQL-R/Q34/r1 | 0.268689 | correct |
| t13/SQL-L1c/Q34/r3 | 0.243511 | wrong |
| pilot288/flash/SQL-L1/Q34/r1 | 0.241568 | correct |
| t13/SQL-L1.5W/Q34/r2 | 0.230268 | wrong |
| ext600:codex_gpt_5_4_raw:Q36 | 0.213082 | wrong |
| ext600:claude_claude_sonnet_4_6_raw:Q36 | 0.199418 | wrong |

## 逐条新旧判定差异

| case_id | 旧 | 新 | 归因 |
|---|---|---|---|
| t13/SQL-L0/Q22/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q22/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q22/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q75/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q75/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L0/Q75/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q08/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q08/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q08/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q75/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q08/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q08/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q08/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q08/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q08/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q22/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q22/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q22/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q75/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q75/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q75/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q08/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q08/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q22/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q22/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q75/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q75/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-R/Q75/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| ext600:claude_claude_sonnet_4_6_raw:Q35 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| ext600:claude_claude_sonnet_4_6_semantic:Q35 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| ext600:codex_gpt_5_4_raw:Q22 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |

## 旧评分器未完成（不计为判定翻转）

| case_id | v2 状态 / 判定 | 秒 |
|---|---|---:|
| t13/SQL-L0/Q117/r2 | invalid_input | 0.000024 |
| t13/SQL-L0/Q74/r2 | invalid_input | 0.000134 |
| t13/SQL-L0/Q111/r1 | wrong | 0.054256 |
| t13/SQL-L0/Q111/r2 | wrong | 0.047009 |
| t13/SQL-L1.5W/Q79/r3 | wrong | 0.000638 |
| t13/SQL-L1/Q79/r2 | wrong | 0.000609 |
| t13/SQL-R/Q74/r2 | invalid_input | 0.000125 |
| t13/SQL-R/Q74/r1 | invalid_input | 0.000119 |
| t13/SQL-R/Q79/r1 | wrong | 0.000509 |
| t13/SQL-R/Q79/r2 | wrong | 0.000700 |
| t13/SQL-R/Q79/r3 | wrong | 0.000743 |
| ext600:codex_gpt_5_4_raw:Q74 | invalid_input | 0.000128 |

## 输入不合法

| case_id | 错误 |
|---|---|
| pilot288/flash/SQL-L1/Q117/r3 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q117/r3/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q117/r2 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q117/r2/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q117/r1 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q117/r1/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q74/r2 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q74/r3 | selection identity columns must be required_columns |
| pilot288/flash/SQL-L1/Q74/r1 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q117/r2 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q117/r2/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q117/r3 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q117/r3/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q117/r1 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q117/r1/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q74/r3 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q74/r1 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q74/r1/t0 | selection identity columns must be required_columns |
| pilot288/flash/SQL-R/Q74/r2 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q117/r2 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q117/r3 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q117/r3/t0 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q117/r1 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q117/r1/t0 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q74/r1 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q74/r3 | selection identity columns must be required_columns |
| pilot288/pro/SQL-L1/Q74/r2 | selection identity columns must be required_columns |
| pilot288/pro/SQL-R/Q117/r3 | selection identity columns must be required_columns |
| pilot288/pro/SQL-R/Q117/r1 | selection identity columns must be required_columns |
| pilot288/pro/SQL-R/Q117/r2 | selection identity columns must be required_columns |
| pilot288/pro/SQL-R/Q74/r3 | selection identity columns must be required_columns |
| pilot288/pro/SQL-R/Q74/r1 | selection identity columns must be required_columns |
| pilot288/pro/SQL-R/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-L0/Q117/r1 | selection identity columns must be required_columns |
| t13/SQL-L0/Q117/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L0/Q117/r3 | selection identity columns must be required_columns |
| t13/SQL-L0/Q119/r1 | selection identity columns must be required_columns |
| t13/SQL-L0/Q119/r2 | selection identity columns must be required_columns |
| t13/SQL-L0/Q119/r3 | selection identity columns must be required_columns |
| t13/SQL-L0/Q74/r1 | selection identity columns must be required_columns |
| t13/SQL-L0/Q74/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L0/Q74/r3 | selection identity columns must be required_columns |
| t13/SQL-L0/Q117/r2 | selection identity columns must be required_columns |
| t13/SQL-L0/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-L0/Q98/r2 | selection identity columns must be required_columns |
| t13/SQL-L0/Q98/r1 | selection identity columns must be required_columns |
| t13/SQL-L0/Q98/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L0/Q98/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q119/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q119/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q119/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q117/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q117/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q74/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q74/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q98/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q98/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q98/r3/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q98/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q117/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5S/Q117/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q119/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q119/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q117/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q117/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q117/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q117/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q117/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q119/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q74/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q74/r1 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q74/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q74/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q98/r2 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q98/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q98/r3 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q98/r3/t0 | selection identity columns must be required_columns |
| t13/SQL-L1.5W/Q98/r1 | selection identity columns must be required_columns |
| t13/SQL-L1/Q119/r1 | selection identity columns must be required_columns |
| t13/SQL-L1/Q119/r3 | selection identity columns must be required_columns |
| t13/SQL-L1/Q117/r3 | selection identity columns must be required_columns |
| t13/SQL-L1/Q117/r2 | selection identity columns must be required_columns |
| t13/SQL-L1/Q117/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-L1/Q117/r1 | selection identity columns must be required_columns |
| t13/SQL-L1/Q117/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-L1/Q119/r2 | selection identity columns must be required_columns |
| t13/SQL-L1/Q74/r1 | selection identity columns must be required_columns |
| t13/SQL-L1/Q74/r3 | selection identity columns must be required_columns |
| t13/SQL-L1/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-L1/Q74/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-L1/Q98/r3 | selection identity columns must be required_columns |
| t13/SQL-L1/Q98/r1 | selection identity columns must be required_columns |
| t13/SQL-L1/Q98/r2 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q117/r2 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q117/r3 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q117/r3/t0 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q119/r2 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q119/r3 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q119/r1 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q117/r1 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q74/r1 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q74/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q74/r3 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q98/r1 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q98/r3 | selection identity columns must be required_columns |
| t13/SQL-L1c/Q98/r2 | selection identity columns must be required_columns |
| t13/SQL-R/Q119/r1 | selection identity columns must be required_columns |
| t13/SQL-R/Q119/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-R/Q117/r1 | selection identity columns must be required_columns |
| t13/SQL-R/Q117/r1/t0 | selection identity columns must be required_columns |
| t13/SQL-R/Q117/r3 | selection identity columns must be required_columns |
| t13/SQL-R/Q119/r2 | selection identity columns must be required_columns |
| t13/SQL-R/Q117/r2 | selection identity columns must be required_columns |
| t13/SQL-R/Q117/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-R/Q119/r3 | selection identity columns must be required_columns |
| t13/SQL-R/Q74/r3 | selection identity columns must be required_columns |
| t13/SQL-R/Q74/r2 | selection identity columns must be required_columns |
| t13/SQL-R/Q74/r2/t0 | selection identity columns must be required_columns |
| t13/SQL-R/Q74/r1 | selection identity columns must be required_columns |
| t13/SQL-R/Q98/r2 | selection identity columns must be required_columns |
| t13/SQL-R/Q98/r3 | selection identity columns must be required_columns |
| t13/SQL-R/Q98/r1 | selection identity columns must be required_columns |
| ext600:claude_claude_opus_4_7_raw:Q74 | selection identity columns must be required_columns |
| ext600:claude_claude_opus_4_7_raw:Q98 | selection identity columns must be required_columns |
| ext600:claude_claude_opus_4_7_semantic:Q74 | selection identity columns must be required_columns |
| ext600:claude_claude_opus_4_7_semantic:Q98 | selection identity columns must be required_columns |
| ext600:claude_claude_sonnet_4_6_raw:Q74 | selection identity columns must be required_columns |
| ext600:claude_claude_sonnet_4_6_raw:Q98 | selection identity columns must be required_columns |
| ext600:claude_claude_sonnet_4_6_semantic:Q74 | selection identity columns must be required_columns |
| ext600:claude_claude_sonnet_4_6_semantic:Q98 | selection identity columns must be required_columns |
| ext600:codex_gpt_5_4_raw:Q74 | selection identity columns must be required_columns |
| ext600:codex_gpt_5_4_raw:Q98 | selection identity columns must be required_columns |
| ext600:codex_gpt_5_4_semantic:Q74 | selection identity columns must be required_columns |
| ext600:codex_gpt_5_4_semantic:Q98 | selection identity columns must be required_columns |

## 验收限制与测试

- 本报告为实现检查点，**不是最终验收通过报告**。主仓库规格尚无 T05b 数据引用的第十二节，详见 `scorer_v2_blockers.md`；独立压力测试四项超过 30 秒。
- 真实语料和独立数据对照基于实现检查点 `ab994cb`。其后的小数窗口精度补丁已通过作者测试，但尚未重复全语料；下一轮须按统一规格完整复验。
- 最后一次作者及旧评分器回归：328 passed（24.58 秒）。命令：`.venv/bin/python -m pytest tests/test_scorer_v2.py tests/test_scorer_v2_performance.py tests/test_scorer.py tests/test_scorer_presentation.py tests/test_selection.py --durations=10`。109 个 warning 均来自保留的旧评分器兼容行为。
- 作者二百万行测试的 pytest 整项耗时（包括构造数据）为正确 5.00 秒、错误 18.15 秒；测试内部另对 score 调用断言 ≤30 秒。万行和宽表等作者测试同样通过，但不替代独立压力测试。
- 旧评分器与系统提示未修改；提示文件与 `harness-v1` 逐字节一致的测试通过。
- 46 条真实判定翻转均为 wrong → correct，每条均有参考必答相邻字符串列合并的匹配见证，已归为旧评分器缺失的参考拆列 / 候选合列方向。12 条旧评分器 10 秒未完成的记录单列，不计作翻转。
- 不含任何题目原文、SQL 或参考结果行；逐条 JSONL 只含标识、判定、计时、错误及列位置见证。

## 复现

在环境变量指向现有数据目录后运行：

```sh
.venv/bin/python scripts/validate_scorer_v2.py \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/pilot288.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/t13.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/ext600.jsonl" \
  --old-timeout 10
```

发现 invalid_input、unscored、超时或待审核差异时脚本退出码为 1；本轮因 137 条旧身份标注不合法返回 1，不能作为通过。
## 合成测试覆盖

| 规格 | 正例与反例（测试函数） |
|---|---|
| 一：输入、确定性、五种输出 | `test_input_states`、`test_invalid_input_and_determinism`、`test_mapping_cap_and_early_success` |
| 一：原因码、逐参考汇总 | `test_top_n_boundary_members_and_full_group`、`test_multiple_reference_outcome_precedence`、`test_no_ties_rank_exact_and_top_n_position_prefix` |
| 一：诊断分离与限时 | `test_diagnostics_separate_and_bounded`、`test_numeric_projection_diagnosis`、`test_diagnostic_real_deadline` |
| 二：必需元数据、整份替代、旧开关拒绝 | `test_required_metadata`、`test_invalid_metadata`、`test_per_reference_rules_replace_without_merging` |
| 三：字符串、NULL、参考空标签 | `test_strings_and_null_labels`、`test_reference_only_empty_labels`、`test_numeric_rules` |
| 三：容差方向、atol、百分数双向、计数整数守卫、非有限值 | `test_numeric_rules`、`test_count_nullable_noninteger_guard_and_wrapped_strings` |
| 三：编码双向、前导零和格式反例 | `test_identifiers` |
| 三：日期双向、零点、时区和非零点反例 | `test_dates`、`test_zero_fractional_midnight_and_timezone_rejection` |
| 三：候选拆 / 参考拆、两个列序、邻接与必答限制 | `test_adjacent_name_join`、`test_only_one_required_name_column_does_not_join`、`test_join_requires_adjacent_columns_and_full_table_correspondence`、`test_join_cannot_erase_nonempty_column_when_other_column_is_null` |
| 四：列重排、多列、缺列、一对一覆盖 | `test_column_permutation_extra_missing_and_nonrequired` |
| 五：无序多重集、重复行、容差非传递 | `test_multiset_duplicates_and_augmenting_paths`、`test_flow_witness_requires_reassigning_across_two_numeric_dimensions` |
| 五：有序块、隐藏排序键、量化与容差分离 | `test_ordered_tie_blocks_and_hidden_key`、`test_order_blocks_use_quantization_not_result_tolerance` |
| 五：Top-N、必须覆盖前缀、完整边界、重复成员 | `test_top_n_boundary_members_and_full_group`、`test_top_n_duplicate_boundary_cannot_replace_strict_prefix` |
| 五：零计数组双向、非零数值反例、Top-N / selection 不放宽 | `test_optional_zero_rows_both_directions`、`test_zero_rows_need_count_and_do_not_apply_to_top_n`、`test_optional_zero_rows_keep_numerical_and_label_requirements`、`test_selection_ties_missing_groups_duplicates_and_zero_not_optional` |
| 五：成对对象原样 / 对调、整组交换限制 | `test_unordered_pairs_are_whole_groups_per_row` |
| 五：selection 父对象、组覆盖、边界选择、独立根、重复叶子、必答身份 | `test_selection_parent_and_leaf_constraints`、`test_selection_ties_missing_groups_duplicates_and_zero_not_optional`、`test_selection_identity_must_be_required_and_exact`、`test_selection_separate_root_filters_and_invalid_contracts` |
| 五：不放宽期间、单位、符号、格式化数值、自造标签、宽长表 | `test_dates`、`test_numeric_rules`、`test_strings_and_null_labels`、`test_column_permutation_extra_missing_and_nonrequired`、`test_input_states` |
| 五：名次三种模式、整份统一、分组一致、Top-N 位置编号 | `test_whole_answer_ranking_modes`、`test_no_ties_rank_exact_and_top_n_position_prefix`、`test_rank_style_uniform_across_groups_and_columns` |
| 六：无损哈希、失败转匹配、不量化 | `test_fast_path_miss_is_not_rejection_and_never_rounds`、`test_numeric_rules` |
| 六：最大匹配与列筛选 | `test_random_small_tables_against_exhaustive_matching_oracle`（120 组固定种子的小表穷举真值）、`test_flow_witness_requires_reassigning_across_two_numeric_dimensions` |
| 六：1,000 种上限、先成功与 unscored 汇总 | `test_mapping_cap_and_early_success`、`test_multiple_reference_outcome_precedence` |
| 六：万行 / 二百万行耗时上限 | `test_execution_row_limits`（正确 / 错误，两个规模）、`test_tolerance_augmenting_paths_with_distinct_labels`、`test_large_tie_wrong_wide_permuted_and_multiple_refs`、`test_dense_tolerance_matching_has_linear_witness` |
| 七：冻结提示不变、语料报告 | `test_prompt_byte_identical_to_frozen_tag`、`test_corpus_runner_reports_decoded_cases_without_private_values`、`test_corpus_runner_rejects_incomplete_rules_without_a_verdict` |
| 九：身份隐藏的参考不得静默评分 | `test_selection_identity_must_be_required_and_exact` |

第七节要求的跨厂商独立检查与独立压力测试由 T05b 执行，作者测试不替代独立验收。第八节的协作和第九节的题库修正不由评分器修改题库完成；主分支打 tag、T13 离线重评也不在本 PR 自动执行。
