# 探查带来的结果流向与调用用途

复现：`uv run python reports/midterm/analyze.py`。题库标签 eval-v1.2 = `90e13b385a639a9164ac78430c50c11a7859f976`；仅通过 git show 读取冻结对象，不使用题库当前工作树。

流向按 (题号, rep) 配对，四类互斥；下表列出全部16种流向（含0）。wrong→correct、correct→wrong、exec_error→correct、exec_error→wrong 可直接读取。
报错指直答最终执行失败，不是首轮报错；拒答另列。该配对是描述性比较，不能证明具体一次探查修复了对应直答。

| 对照 | 范围 | 直答结果 | 探查结果 | 作答数 |
|---|---|---|---|---|
| SQL-L0-E vs SQL-L0 | 主表98 | correct | correct | 91 |
| SQL-L0-E vs SQL-L0 | 主表98 | correct | wrong | 21 |
| SQL-L0-E vs SQL-L0 | 主表98 | correct | exec_error | 1 |
| SQL-L0-E vs SQL-L0 | 主表98 | correct | refused | 2 |
| SQL-L0-E vs SQL-L0 | 主表98 | wrong | correct | 26 |
| SQL-L0-E vs SQL-L0 | 主表98 | wrong | wrong | 134 |
| SQL-L0-E vs SQL-L0 | 主表98 | wrong | exec_error | 9 |
| SQL-L0-E vs SQL-L0 | 主表98 | wrong | refused | 2 |
| SQL-L0-E vs SQL-L0 | 主表98 | exec_error | correct | 0 |
| SQL-L0-E vs SQL-L0 | 主表98 | exec_error | wrong | 0 |
| SQL-L0-E vs SQL-L0 | 主表98 | exec_error | exec_error | 0 |
| SQL-L0-E vs SQL-L0 | 主表98 | exec_error | refused | 0 |
| SQL-L0-E vs SQL-L0 | 主表98 | refused | correct | 0 |
| SQL-L0-E vs SQL-L0 | 主表98 | refused | wrong | 7 |
| SQL-L0-E vs SQL-L0 | 主表98 | refused | exec_error | 0 |
| SQL-L0-E vs SQL-L0 | 主表98 | refused | refused | 1 |
| SQL-L0-E vs SQL-L0 | 附表109 | correct | correct | 98 |
| SQL-L0-E vs SQL-L0 | 附表109 | correct | wrong | 24 |
| SQL-L0-E vs SQL-L0 | 附表109 | correct | exec_error | 1 |
| SQL-L0-E vs SQL-L0 | 附表109 | correct | refused | 2 |
| SQL-L0-E vs SQL-L0 | 附表109 | wrong | correct | 31 |
| SQL-L0-E vs SQL-L0 | 附表109 | wrong | wrong | 152 |
| SQL-L0-E vs SQL-L0 | 附表109 | wrong | exec_error | 9 |
| SQL-L0-E vs SQL-L0 | 附表109 | wrong | refused | 2 |
| SQL-L0-E vs SQL-L0 | 附表109 | exec_error | correct | 0 |
| SQL-L0-E vs SQL-L0 | 附表109 | exec_error | wrong | 0 |
| SQL-L0-E vs SQL-L0 | 附表109 | exec_error | exec_error | 0 |
| SQL-L0-E vs SQL-L0 | 附表109 | exec_error | refused | 0 |
| SQL-L0-E vs SQL-L0 | 附表109 | refused | correct | 0 |
| SQL-L0-E vs SQL-L0 | 附表109 | refused | wrong | 7 |
| SQL-L0-E vs SQL-L0 | 附表109 | refused | exec_error | 0 |
| SQL-L0-E vs SQL-L0 | 附表109 | refused | refused | 1 |
| SQL-L1-E vs SQL-L1 | 主表98 | correct | correct | 177 |
| SQL-L1-E vs SQL-L1 | 主表98 | correct | wrong | 20 |
| SQL-L1-E vs SQL-L1 | 主表98 | correct | exec_error | 2 |
| SQL-L1-E vs SQL-L1 | 主表98 | correct | refused | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | wrong | correct | 23 |
| SQL-L1-E vs SQL-L1 | 主表98 | wrong | wrong | 70 |
| SQL-L1-E vs SQL-L1 | 主表98 | wrong | exec_error | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | wrong | refused | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | exec_error | correct | 1 |
| SQL-L1-E vs SQL-L1 | 主表98 | exec_error | wrong | 1 |
| SQL-L1-E vs SQL-L1 | 主表98 | exec_error | exec_error | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | exec_error | refused | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | refused | correct | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | refused | wrong | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | refused | exec_error | 0 |
| SQL-L1-E vs SQL-L1 | 主表98 | refused | refused | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | correct | correct | 188 |
| SQL-L1-E vs SQL-L1 | 附表109 | correct | wrong | 20 |
| SQL-L1-E vs SQL-L1 | 附表109 | correct | exec_error | 2 |
| SQL-L1-E vs SQL-L1 | 附表109 | correct | refused | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | wrong | correct | 28 |
| SQL-L1-E vs SQL-L1 | 附表109 | wrong | wrong | 87 |
| SQL-L1-E vs SQL-L1 | 附表109 | wrong | exec_error | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | wrong | refused | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | exec_error | correct | 1 |
| SQL-L1-E vs SQL-L1 | 附表109 | exec_error | wrong | 1 |
| SQL-L1-E vs SQL-L1 | 附表109 | exec_error | exec_error | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | exec_error | refused | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | refused | correct | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | refused | wrong | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | refused | exec_error | 0 |
| SQL-L1-E vs SQL-L1 | 附表109 | refused | refused | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | correct | correct | 168 |
| SQL-L2-E vs SQL-L2 | 主表98 | correct | wrong | 23 |
| SQL-L2-E vs SQL-L2 | 主表98 | correct | exec_error | 1 |
| SQL-L2-E vs SQL-L2 | 主表98 | correct | refused | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | wrong | correct | 21 |
| SQL-L2-E vs SQL-L2 | 主表98 | wrong | wrong | 67 |
| SQL-L2-E vs SQL-L2 | 主表98 | wrong | exec_error | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | wrong | refused | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | exec_error | correct | 5 |
| SQL-L2-E vs SQL-L2 | 主表98 | exec_error | wrong | 9 |
| SQL-L2-E vs SQL-L2 | 主表98 | exec_error | exec_error | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | exec_error | refused | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | refused | correct | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | refused | wrong | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | refused | exec_error | 0 |
| SQL-L2-E vs SQL-L2 | 主表98 | refused | refused | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | correct | correct | 184 |
| SQL-L2-E vs SQL-L2 | 附表109 | correct | wrong | 28 |
| SQL-L2-E vs SQL-L2 | 附表109 | correct | exec_error | 1 |
| SQL-L2-E vs SQL-L2 | 附表109 | correct | refused | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | wrong | correct | 23 |
| SQL-L2-E vs SQL-L2 | 附表109 | wrong | wrong | 77 |
| SQL-L2-E vs SQL-L2 | 附表109 | wrong | exec_error | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | wrong | refused | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | exec_error | correct | 5 |
| SQL-L2-E vs SQL-L2 | 附表109 | exec_error | wrong | 9 |
| SQL-L2-E vs SQL-L2 | 附表109 | exec_error | exec_error | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | exec_error | refused | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | refused | correct | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | refused | wrong | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | refused | exec_error | 0 |
| SQL-L2-E vs SQL-L2 | 附表109 | refused | refused | 0 |

## 调用用途

采用可复算的SQL形态代理分类，不读取思考、不臆测意图。互斥优先级：结构/计划 → 含数值聚合或排名的候选答案核验 → DISTINCT/GROUP BY枚举 → COUNT行数 → 其余明细样例。
例如带 GROUP BY 的 SUM 归聚合核验，枚举值附带 COUNT 归枚举。被拒、超限和执行报错的调用也计入分母，不能把尝试数称为成功查值数。
逐调用分类在 tool-audit.csv，可凭 source、call、k 回查原SQL；这是操作形态分类，不能区分同一SUM究竟用于试答还是验证。

| 单元 | 范围 | 形态代理用途 | 调用数及占比 |
|---|---|---|---|
| SQL-L0-E | 主表98 | 明细或样例查值 | 682/1977（34.5%） |
| SQL-L0-E | 主表98 | 枚举或分组查值 | 186/1977（9.4%） |
| SQL-L0-E | 主表98 | 结构或执行计划 | 2/1977（0.1%） |
| SQL-L0-E | 主表98 | 聚合或候选答案核验 | 1018/1977（51.5%） |
| SQL-L0-E | 主表98 | 行数或存在性检查 | 89/1977（4.5%） |
| SQL-L0-E | 附表109 | 明细或样例查值 | 753/2175（34.6%） |
| SQL-L0-E | 附表109 | 枚举或分组查值 | 208/2175（9.6%） |
| SQL-L0-E | 附表109 | 结构或执行计划 | 2/2175（0.1%） |
| SQL-L0-E | 附表109 | 聚合或候选答案核验 | 1119/2175（51.4%） |
| SQL-L0-E | 附表109 | 行数或存在性检查 | 93/2175（4.3%） |
| SQL-L0-E | 运行全体含judge | 明细或样例查值 | 863/2502（34.5%） |
| SQL-L0-E | 运行全体含judge | 枚举或分组查值 | 241/2502（9.6%） |
| SQL-L0-E | 运行全体含judge | 结构或执行计划 | 2/2502（0.1%） |
| SQL-L0-E | 运行全体含judge | 聚合或候选答案核验 | 1291/2502（51.6%） |
| SQL-L0-E | 运行全体含judge | 行数或存在性检查 | 105/2502（4.2%） |
| SQL-L1-E | 主表98 | 明细或样例查值 | 52/720（7.2%） |
| SQL-L1-E | 主表98 | 枚举或分组查值 | 43/720（6.0%） |
| SQL-L1-E | 主表98 | 聚合或候选答案核验 | 599/720（83.2%） |
| SQL-L1-E | 主表98 | 行数或存在性检查 | 26/720（3.6%） |
| SQL-L1-E | 附表109 | 明细或样例查值 | 55/810（6.8%） |
| SQL-L1-E | 附表109 | 枚举或分组查值 | 45/810（5.6%） |
| SQL-L1-E | 附表109 | 聚合或候选答案核验 | 680/810（84.0%） |
| SQL-L1-E | 附表109 | 行数或存在性检查 | 30/810（3.7%） |
| SQL-L1-E | 运行全体含judge | 明细或样例查值 | 67/988（6.8%） |
| SQL-L1-E | 运行全体含judge | 枚举或分组查值 | 53/988（5.4%） |
| SQL-L1-E | 运行全体含judge | 结构或执行计划 | 1/988（0.1%） |
| SQL-L1-E | 运行全体含judge | 聚合或候选答案核验 | 836/988（84.6%） |
| SQL-L1-E | 运行全体含judge | 行数或存在性检查 | 31/988（3.1%） |
| SQL-L2-E | 主表98 | 明细或样例查值 | 51/838（6.1%） |
| SQL-L2-E | 主表98 | 枚举或分组查值 | 66/838（7.9%） |
| SQL-L2-E | 主表98 | 聚合或候选答案核验 | 710/838（84.7%） |
| SQL-L2-E | 主表98 | 行数或存在性检查 | 11/838（1.3%） |
| SQL-L2-E | 附表109 | 明细或样例查值 | 52/923（5.6%） |
| SQL-L2-E | 附表109 | 枚举或分组查值 | 69/923（7.5%） |
| SQL-L2-E | 附表109 | 聚合或候选答案核验 | 788/923（85.4%） |
| SQL-L2-E | 附表109 | 行数或存在性检查 | 14/923（1.5%） |
| SQL-L2-E | 运行全体含judge | 明细或样例查值 | 52/923（5.6%） |
| SQL-L2-E | 运行全体含judge | 枚举或分组查值 | 69/923（7.5%） |
| SQL-L2-E | 运行全体含judge | 聚合或候选答案核验 | 788/923（85.4%） |
| SQL-L2-E | 运行全体含judge | 行数或存在性检查 | 14/923（1.5%） |
