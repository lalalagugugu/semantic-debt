# DAX 写法说明补到 2 级（T17-mac）

- 依据：`decisions/2026-10-19-self-built-p-and-cube-notes.md` 第五节第 3 条（DAX 说明开跑前补到 2 级）；`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第三节第 1 条。
- 改了什么：`render/syntax/dax.md` 原有 12 条（1 级）一字未删；关系那条补一句 `model_relationship` 标记的含义（格式定义，1 级）；新增「使用条件与禁忌」18 条（2 级）。没有完整示范查询（3 级以上），只用占位名称，不点名本数据集的任何表、列、指标（`tests/test_render.py::test_syntax_notes_say_nothing_about_this_dataset`）。
- 来源：**全部来自 DAX 的通用行为，没有一条来自本实验的作答**（DAX 线还没跑过，没有 DAX 报错可用；也没有读题库）。ClickHouse 2 级（C13）的禁忌来自调优题报错，这一点两边不同，报告里要写明。
- **以下各条都没有在真实引擎上验证过**（Mac 上没有 Power BI）。Windows 探测 `windows\t17.ps1 probe -Tier L1` 的「写法说明 2 级条目」一段逐条跑一条查询，看引擎是否如说明所说（查询在 `harness/dax_probe.py` 的 `SYNTAX`）。**不符的条目在 DAX 开跑前删掉或改窄**，不改成别的写法（同 T16 对 Cube 说明的处理）。

| # | 2 级条目（摘要） | 探测 | 预期 |
|---|---|---|---|
| 1 | `EVALUATE` 后单个数值要包成 `ROW` | S01 / S01b | 报错 / 通过 |
| 2 | `DEFINE MEASURE` 要写明挂在哪张表上；`DEFINE VAR` 可在 `EVALUATE` 里用 | S02 / S02b / S02c | 报错 / 通过 / 2 行 |
| 3 | 结果列名可用中文；`ADDCOLUMNS` 新列不能与已有列同名 | S03b / S03 | 通过 / 报错 |
| 4 | `ORDER BY` 只能排结果里有的列；新算的列写 `[结果列名]` | S04 / S04b | 报错 / 通过 |
| 5 | `TOPN` 遇并列返回多于 N 行 | S05 | 多于 1 行 |
| 6 | `SUMMARIZECOLUMNS` 去掉结果全为空的组合 | S06 | 0 行 |
| 7 | 分组列所在表没有激活关系连到事实表时，每组同一个合计、不报错；加 `USERELATIONSHIP` 后分开 | S07 / S07b | 各组相同 / 各组不同 |
| 8 | `SUMMARIZECOLUMNS` 不要放进逐行函数内部 | S08 | 报错（新版引擎若已支持，这条是保守写法，记录实际行为，不算错） |
| 9 | 孤儿行在按一端表的列分组时归入空白组 | S09 | 有空白组 |
| 10 | `RELATED` 只能在逐行计算的地方用；自连接用 `LOOKUPVALUE` | S10 / S11 | 报错 / 通过 |
| 11 | `CALCULATE` 的简写条件不能比较两张表的列；用到度量值时改用 `FILTER` | S12 / S12b | 报错 / 报错（若新版允许度量值，说明是保守写法，记录实际行为） |
| 12 | 字符串 `=` 不区分大小写；`BLANK() = 0` 为真、`BLANK() == 0` 为假 | S13 / S13b / S13c | 真 / 真 / 假 |
| 13 | `/` 分母为零不报错、返回无穷大；`QUOTIENT` 整数除法 | S14 / S18 | 无穷大 / 3 |
| 14 | 日期列不能和字符串比较，写成 `DATE(…)` | S15 / S15b | 报错 / 通过 |
| 15 | 时间智能函数要传日期维度表的日期列 | — | 不单独探测；L2 的同比、环比、变体度量值就是这样写的，探测的「度量值」「v1.4 变体」两段间接验证 |
| 16 | `RANKX` 第一个参数写 `VALUES` 时每组都排第 1，写 `ALL` 正常排名；并列默认跳号 | S16 / S16b | 各组相同 / 各组不同 |
| 17 | `DISTINCTCOUNT` 把空值算作一个值 | S17 | a = b + 1 |
| 18 | `FORMAT` 返回文本 | — | 不探测（函数文档事实，没有可观察的失败形态） |

另：关系那条补的「`model_relationship: inactive` / `none`」由 `render/check_pbip.py`（静态，对着 TMDL）和探测「Desktop 实际载入的模型」一段的关系数、非激活数核对。

## 大纲对照表的 DAX 列（`reports/validation/syntax-syllabus.md` 的同一组写法项）

| 写法项 | 改前 | 改后 | 新增的条件或禁忌 |
|---|---|---|---|
| 筛选 | 1 | 2 | 简写条件只比较同一张表的列和固定值；日期不和字符串比较；字符串比较不分大小写 |
| 分组 | 1 | 2 | `SUMMARIZECOLUMNS` 去掉全空组合、要有激活关系、只放最外层 |
| 连表 | 2 | 2 | 补 `model_relationship` 标记的含义；`RELATED` 的使用位置；自连接用 `LOOKUPVALUE` / `PATH` |
| 时间分桶 | 1 | 1 | — |
| 排名与窗口 | 1 | 2 | `RANKX` 的第一个参数、并列与 `DENSE` |
| 比率 | 1 | 1 | — |
| 同比 / 环比 | 2 | 2 | 时间智能函数传日期维度表的列、外面要有期的筛选 |
| 前 N | 1 | 2 | `TOPN` 的并列与排序 |
| 空值 | 1 | 2 | `BLANK` 与 0 的比较、`ISBLANK`、`==`；孤儿行的空白组；`DISTINCTCOUNT` 计入空值 |
| 除法 | 2 | 2 | `/` 不报错返回无穷大；`QUOTIENT` |
| 标识符与别名引号 | 1 | 2 | 结果列名用双引号、可中文；`ADDCOLUMNS` 不能重名；`ORDER BY` 的写法 |
| 去重计数 | 1 | 2 | `DISTINCTCOUNT` / `DISTINCTCOUNTNOBLANK` |
| 在结果上再算一步 | 1 | 2 | `EVALUATE` 后必须是表；`DEFINE MEASURE` 要写表名；`DEFINE VAR` |
| 多个事实表 | 0 | 0 | — |

篇幅（去空白字符）：改前 922，改后 2,509；ClickHouse 1 级 953，C13 的 ClickHouse 2 级 1,831。四份说明不再等长的约束随本次去掉（`tests/test_render.py::test_syntax_note_lengths`，T12-4 已裁决栈之间篇幅可以不同）。
