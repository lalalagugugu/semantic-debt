# 中期报告 v7：数字—出处清单（供 Codex 复核）

报告在 Claude Docs 文档 `e6ba0940-5536-4c83-b2fd-296fbdf47b8d` 的「中期报告 v7」tab。本清单只含数字和题号，不含题面。

路径约定：`cells` = `reports/results/accuracy-v5-cells.csv`；`cmp` = `reports/results/accuracy-v5-comparisons.csv`；`derived` = `reports/results/t19a-v7-numbers.md`（`scripts/t19a_v7_numbers.py` 生成）；`followups` = `reports/results/t31-v7-followups.md`。

## 需要 Codex 复核的新算数字

`derived` 全文是写作会话新算的：单元 95% 区间、第 5 节覆盖内准确率和覆盖外结果、第 8 节叠加比较、D3 及 7 道题移组、D4 首答计数。按用户裁决，D3 交 Codex 复核。

## 各节数字

| 节 | 数字 | 出处 |
|---|---|---|
| 标题、TL;DR | 48、85、93、97；留出 96 | `cells`：SQL-L0、SQL-L1、SQL-L1plus、SQL-L1plus-tuned-instr（all、heldout） |
| TL;DR、8 | 留出 85.0、92.5、93.2、95.9 | `cells` split=heldout：SQL-L1、SQL-L1-tuned、SQL-L1-tuned-instr / SQL-L1plus、SQL-L1plus-tuned-instr |
| 方法 | 5,439；13、11、98；模型指纹 e72d3c7f | `reports/results/accuracy-v5.md`；`decisions/2026-10-16-low-discrimination-criteria.md`；计划第二节 |
| 方法、附录 | 格式评法低 4–21，多数 8–17 个点 | `cells`：accuracy − delivery，all |
| 方法 | 费用 104.73 元 | 沿用 v6，未重算 |
| 1 | L0→L1 +37.1 | `cmp` |
| 2 | L0→R +3.7；L1→L1.5W −4.1；L1→L1c −16.3 | `cmp` |
| 2、3 | 71 题 +47.4、27 题 +9.9、+4.7、−6.2；36/41/84、79/73/89；移组 78/77/92 | `derived` D3 |
| 2 | token 约 6,000 / 6,800 / 46,500；八行对照；科目键 4、50 | `$SEMDEBT_DATA_DIR/v7-eval-20261030/report.md` D2 |
| 2 | 13、69；11 行、77 字段；56 组；13 条 | 沿用 v6 |
| 2 | R→L1c 约 +17 | `cmp`（+17.0） |
| 2 | Cube 报告语义层加 17–23 个点 | 用户 2026-10-31 提供，出处为 Cube 基准报告 |
| 3 | L0→L0-E +1.7；L1→L1-E +0.7 | `cmp` |
| 3 | 6.7、2.4 次及用途占比；费用倍数 | 沿用 v6（`reports/midterm/tool-audit.csv`、`tokens-cost.md`），未重算 |
| 4 | L1+→L3a −0.3；3.2、4.8 元 | `cmp`；费用沿用 v6 |
| 4 | 16 次 = 11 / 3 / 2；14 个 = 10 / 4 | `followups` D6、D8 |
| 4 | 109、30、17、13、41、37、1、16、46；14% | 沿用 v6（`reports/validation/l1plus-l3a-correspondence.md`、`l3a-ontology-validation.md`） |
| 5 | 37、42；92/93/87、93/90/85；覆盖内 85、87；覆盖外计数；−4.5、−7.9 | `derived` 第 5 节 |
| 5 | L1→SQL-L2 −1.4 | `cmp` |
| 5 | JSON-L2 覆盖内错 14 次、L1.5S 覆盖内错 19 次（13 + 6）的分类 | `$SEMDEBT_DATA_DIR/t31-v7-census-20261030/snapshots/20261031-T31-v5-rulings-01/codex-decisions.json`（只看 category、note） |
| 5 | 第一版汇总层选错表 | `reports/results/l15s-covered-analysis.md`（修复前的分析） |
| 6 | 留出 85、83、86、86；−2.0、+1.4、+0.7 | `cells`、`cmp` split=heldout |
| 6 | 32.4、2.8、2.4；48 次 | 沿用 v6，未重算 |
| 7 | L1→L1+ +8.2 | `cmp` |
| 8 | L1→tuned 留出 +7.5；tuned-instr→combo 留出 +2.7 | `cmp`；`derived` 第 8 节 |
| 8 | 17 处矛盾 | 沿用 v6 |
| 9 | 叠加 8 次错，7 次能执行 | `runs/20261031-T31-v5-rulings-01/SQL-L1plus-tuned-instr.jsonl` |
| 10 | 92/98、89、86、错 6 拦 3、误拦 6 | `derived` D4；`followups` |
| 10 | 59/59、20% | `followups` |
| 局限 | 1,411、420、991、194、33、24 | `reports/validation/t31-v7-rescan.md`；`tasks/COORDINATION-HANDOFF.md`（coord-compact-prep 分支） |
| 附录 | 单元表 | `derived`；`cells` |
| 附录 | 7,379 = 5,439 + 612 + 约 1,330；排除 330、18、183 | `runs/20261028-T31-v4-rescore-02/manifest.json`；`runs/20261031-T31-v5-rulings-01/manifest.json` |
| 附录 | 5 道修正、原则 A/B/C、统一规则 | `decisions/2026-10-28-reference-rulings-five-questions.md`、`2026-10-28-residual-content-principles.md`、`2026-10-31-v7-content-review-rulings.md` |
