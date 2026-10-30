# 中期报告 v7：数字—出处清单（供 Codex 复核）

报告在 Claude Docs 文档 `e6ba0940-5536-4c83-b2fd-296fbdf47b8d` 的「中期报告 v7」tab。本清单只含数字和题号，不含题面。

路径约定：`cells` = `reports/results/accuracy-v5-cells.csv`；`cmp` = `reports/results/accuracy-v5-comparisons.csv`；`derived` = `reports/results/t19a-v7-numbers.md`（`scripts/t19a_v7_numbers.py` 生成）；`followups` = `reports/results/t31-v7-followups.md`。

## 需要 Codex 复核的新算数字

`derived` 全文是写作会话新算的：单元 95% 区间、第 5 节覆盖内准确率和覆盖外结果、第 8 节叠加比较、D3 及 7 道题移组、D4 首答计数。按用户裁决，D3 交 Codex 复核。T20 已复核（`reports/final/recheck.md`，PR #229）。

## T20 之后新增或改动、需要 Codex 再核的数字

T20 只对照了本清单的旧版。下面这些是它之后改的或新补出处的：

- 费用约 105 元的纳入范围（第 1 项）。
- 46 = 30 + 16 的定义；14% = 1,715,380 ÷ 12,627,608 的定义（第 3 项）。
- 第 3 节输入量 3 倍、5 倍，缓存没命中 2–2.8 倍；局限一节的 19 道题。这三处是写作会话核正文时发现的 v6 遗留错误。
- 第 3 节移组后 L0→L1 的写法（新写进正文，数字 T20 已核）。
- 清单新补的方法、1、5、6 节各行。

## 各节数字

| 节 | 数字 | 出处 |
|---|---|---|
| 标题、TL;DR | 48、85、93、97；留出 96 | `cells`：SQL-L0、SQL-L1、SQL-L1plus、SQL-L1plus-tuned-instr（all、heldout） |
| TL;DR、8 | 留出 85.0、92.5、93.2、95.9 | `cells` split=heldout：SQL-L1、SQL-L1-tuned、SQL-L1-tuned-instr / SQL-L1plus、SQL-L1plus-tuned-instr |
| 方法 | 5,439；13、11、98；模型指纹 e72d3c7f | `reports/results/accuracy-v5.md`；`decisions/2026-10-16-low-discrimination-criteria.md`；计划第二节 |
| 方法、附录 | 格式评法低 4–21，多数 8–17 个点 | `cells`：accuracy − delivery，all |
| 方法 | 费用约 105 元 | T20 从日志核得 104.61022284 元（`reports/recheck/supplement.json` 的 cost_ledger，PR #229）：旧账本 run 清单 99.64646158 + T29 试跑 0.30458160 + T29 扩展 1.76856564 + T30 2.89061402。截止到 T30，不含 U2。账本取整口径 104.59669244。未返回用量的请求未计入，不是最终实付。v6 的 104.73 无法复现，已弃用 |
| 方法 | 25 张表、244 个字段、约 3,400 万行（34,326,191） | `reports/midterm/dataset-quality.md` 第 6 行 |
| 方法 | 122、100、22 | 题库 `questions/cube_100.yaml`、`questions/new.yaml` 的题数 |
| 方法、局限 | 一、二、三级 38、33、27；调优、留出各 49；管理层 45、分析师 53 | `runs/20261031-T31-v5-rulings-01/SQL-L1.jsonl` 主表 98 题的 q_level、split、persona |
| 方法 | 每次作答约 1–2 分钱 | `reports/midterm/tokens-cost.md` 主表 98 行的「元/作答」0.00758–0.01753；L1+、L3a 按 3.21、4.85 元 ÷ 294 |
| 方法、3 | 最多 8 步 | `docs/design-v5-public.md` 第 52 行 |
| 1 | 约三分之二的表关系 | `docs/design-v5-public.md` 第 66 行 |
| 1 | 7 家虚拟门店 | `semantic/l1plus-audit.md` A01 |
| 1 | L0→L1 +37.1 | `cmp` |
| 2 | L0→R +3.7；L1→L1.5W −4.1；L1→L1c −16.3 | `cmp` |
| 2、3 | 71 题 +47.4、27 题 +9.9、+4.7、−6.2；36/41/84、79/73/89；移组 78/77/92 | `derived` D3 |
| 3 | 移组后 20 题 L0→L1 +13.3 [+0.0, +30.0]，下端恰为 0，按闭区间含 0，写「还不能说有差别」 | `derived` D3；`reports/final/recheck.md`（PR #229） |
| 2 | token 约 6,000 / 6,800 / 46,500；八行对照；科目键 4、50 | `$SEMDEBT_DATA_DIR/v7-eval-20261030/report.md` D2 |
| 2 | 13、69；11 行、77 字段；56 组；13 条 | 沿用 v6 |
| 2 | R→L1c 约 +17 | `cmp`（+17.0） |
| 2 | Cube 报告语义层加 17–23 个点 | https://github.com/cubedevinc/semantic-layer-benchmark 的 README |
| 3 | L0→L0-E +1.7；L1→L1-E +0.7 | `cmp` |
| 3 | 6.7、2.4 次及用途占比；费用 0.9–1.3 倍 | `reports/midterm/tool-audit.csv`、`tokens-cost.md`；T20 已复现（0.863、1.345、1.107） |
| 3 | 输入量 L1、SQL-L2 约 3 倍，L0 约 5 倍 | `reports/midterm/tokens-cost.md` 主表 98 行「平均输入」之比：L1-E/L1 2.70、L2-E/L2 3.23、L0-E/L0 5.18。v6 写的「约 3 倍」不含 L0，已改 |
| 3 | 缓存没命中约 2–2.8 倍 | 同上「全冷元/作答」之比：L0 2.03、L1 2.51、L2 2.76。v6 写的 2–2.5 不含 L2，已改 |
| 4 | L1+→L3a −0.3；3.2、4.8 元 | `cmp`；费用沿用 v6 |
| 4 | 16 次 = 11 / 3 / 2；14 个 = 10 / 4 | `followups` D6、D8 |
| 4 | 109、30、17、13、41、37、1、16 | `reports/validation/l1plus-l3a-correspondence.md`、`l3a-ontology-validation.md`；T20 已复现 |
| 4 | 46 条（不到一半） | 派生，文件里没有这个数：已形式化 30 条 + 注解里有现成写法的 16 条（`l3a-ontology-validation.md` 第 6.2 节，`l3a-ontology/missed.json` 的 formalized_entries、formalizable_annotation_entries）。分母 109，占 42.2% |
| 4、9 | 线上销售表 14% 的行关联不上产品 | 派生，文件里没有这个数：FactOnlineSales 孤儿行 1,715,380（`l3a-ontology-validation.md` 第 5 节）÷ 总行数 12,627,608（同文第 5 节、`dataset-quality.md`）= 13.58% |
| 4 | 费用高约一半 | 4.85 ÷ 3.21 = 1.51 |
| 4 | 文字版 2 行、本体版几十行 | 取数：`$SEMDEBT_DATA_DIR/t31-v7-census-20261030/frozen-inputs/semantic-v1.6-l1plus/SQL-L3a-system.txt` 的 Turtle 部分每个三元组占一行，按行匹配。含 `H10` 的 46 行；匹配 `H10\|Actual\|Budget\|Forecast\|ScenarioKey` 的 81 行（含别名等相关行）。实测范围 46–81 行，条目边界没有唯一定义，所以不写具体行数。v6 的「约 75 行」已弃用 |
| 5 | 37、42；92/93/87、93/90/85；覆盖内 85、87；−4.5、−7.9 | `derived` 第 5 节 |
| 5 | 覆盖外：作答 183、168；拒答 121、97；给出结果 61、67（has_result=true）；答对 26、10；答错 35、57；执行失败 1、4 | `derived` 第 5 节。之前的 62、71 是「未拒答」，混入了执行失败，已改 |
| 5 | 列出全部品牌后数出 11 个 | Q57 三次作答的执行结果都是 11 行（`$SEMDEBT_DATA_DIR/runs-raw/20261019-T16-full-v14-json-01/`） |
| 5 | L1→SQL-L2 −1.4 | `cmp` |
| 5 | JSON-L2 覆盖内错 14 次、L1.5S 覆盖内错 19 次（13 + 6）的分类 | `$SEMDEBT_DATA_DIR/t31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/codex-decisions.json`（只看 category、note） |
| 5 | 第一版汇总层选错表 | `reports/results/l15s-covered-analysis.md`（修复前的分析） |
| 5 | 覆盖外答对的原因：JSON-L2 26 次、L1.5S 10 次 | 下一节逐题分组 |
| 6 | 留出 85、83、86、86；−2.0、+1.4、+0.7 | `cells`、`cmp` split=heldout |
| 6 | 32.4、2.8、2.4；48 次 | T20 已复现（109 题首轮 106、9、8 / 327；T21 两单元各 24 次） |
| 6 | 24 题，一、二、三级各 8 道 | `runs/20261019-T21-pilot-01/`，按题库 q_level 计 |
| 6 | 4 级示例取自 6 道调优题 | `decisions/2026-10-23-blind-data-dir.md`（Q60、Q12、Q78、Q82、Q50、Q49） |
| 7 | L1→L1+ +8.2 | `cmp` |
| 8 | L1→tuned 留出 +7.5；tuned-instr→combo 留出 +2.7 | `cmp`；`derived` 第 8 节 |
| 8 | 17 处矛盾 | `reports/validation/combo-conflicts.md`；T20 已复现（条目对） |
| 8 | 147 次、6 次错答、一次 0.7 个点 | `cells` 叠加留出 141/147；1 ÷ 147 |
| 9 | 叠加 8 次错，7 次能执行 | `runs/20261031-T31-v5-rulings-01/SQL-L1plus-tuned-instr.jsonl` |
| 8 | L1+→叠加 留出 +2.7（−2.0 到 +8.8） | `cmp`；`derived` 第 8 节 |
| 10 | 不筛 94%、筛后 97% | `derived` D4（92/98、86/89） |
| 10 | 92/98、89、86、错 6 拦 3、误拦 6；答 89 题占 91% | `derived` D4；`followups`；89 ÷ 98 |
| 10 | 59/59、20% | `followups` |
| 局限 | 1,411、420、991、194、33、24 | `reports/validation/t31-v7-rescan.md`；`tasks/COORDINATION-HANDOFF.md` |
| 局限 | Pro 贵约 7.5 倍 | `decisions/model.md` 第 76 行 |
| 局限 | 19 道题 | `reports/T12-pilot.md` 选模型表：SQL-L1 主表 57 次 ÷ 3（24 题去掉 judge Q40 和 4 道低区分度题）。v6 写的 20 道不对，已改 |
| 附录 | L1.5W 留出 −8.8（−15.0 到 −3.4）；全部 −4.1（−8.5 到 +0.3） | `cmp` |
| 附录 | 11 条确定性规则 | `reports/results/accuracy-v5.md`（R1–R11） |
| 附录 | 单元表 | `derived`；`cells` |
| 附录 | 7,379 = 5,439 + 612 + 约 1,330；排除 330、18、183 | `runs/20261028-T31-v4-rescore-02/manifest.json`；`runs/20261031-T31-v5-rulings-01/manifest.json` |
| 附录 | 5 道修正、原则 A/B/C、统一规则 | `decisions/2026-10-28-reference-rulings-five-questions.md`、`2026-10-28-residual-content-principles.md`、`2026-10-31-v7-content-review-rulings.md` |

## 第 5 节覆盖外答对的作答

逐次读 `$SEMDEBT_DATA_DIR/runs-raw/` 的原始回包和执行结果，对照 `reports/validation/t16-v14-8836110/coverage.json`（JSON-L2）和题库 `audit/T06-summary-coverage.json`（L1.5S）的标注理由分组。

| 单元 | 原因 | 题号（次数） | 合计 |
|---|---|---|---:|
| JSON-L2 | 标注只因缺格式要求的列（名次、增长金额），内容不受影响 | Q27（3）、Q77（3）、Q50、Q67、Q106 | 9 |
| JSON-L2 | 结果里没有现成答案，但一步能读出或算出 | Q57（3）、Q36（3）、Q47、Q71 | 8 |
| JSON-L2 | 门店数、客户数在维度上没定义，用销售表的去重计数代替，这份数据里恰好相等 | Q10（3）、Q51（3）、Q55（3） | 9 |
| L1.5S | 把汇总表的订单数按行相加：Q108 三次与参考完全一致；Q19 一次差 0.12%，在判分容差内 | Q108（3）、Q19 | 4 |
| L1.5S | 标注认为缺产品粒度，但题目只要标价和成本，产品维度表就够 | Q27（3） | 3 |
| L1.5S | 客户维度表的人数和线上购买过的客户数恰好相等 | Q03 | 1 |
| L1.5S | 用全渠道的 Online 切片，金额和参考不同，但题目只要求子品类名单，名单对 | Q61 | 1 |
| L1.5S | 标注认为缺经理员工键，作答按经理姓名分组 | Q112 | 1 |
