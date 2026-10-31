# 中期报告 v8：数字—出处清单（供 Codex 再核）

报告在 Claude Docs 文档 `e6ba0940-5536-4c83-b2fd-296fbdf47b8d` 的「中期报告 v8」tab。本清单只含数字和题号，不含题面。

路径约定：`cells` = `reports/results/accuracy-v5-cells.csv`；`cmp` = `reports/results/accuracy-v5-comparisons.csv`；`v7num` = `reports/results/t19a-v7-numbers.md`；`v8num` = `reports/results/t19a-v8-numbers.md`（`scripts/t19a_v8_numbers.py` 生成）；`causes` = `reports/results/t19a-v8-error-causes.md`；`u2` = `reports/results/t29-u2-content-analysis.md`、`.json`；`v7src` = `reports/midterm/v7-number-sources.md`。

## 需要 Codex 再核的新数字

- `v8num` 全文：首轮报错 93、8、5 / 294；第一轮输入 token；覆盖外未得分 157/171、158/177；复盘补语义 12 次错答全部有结果；题目构成 76、22、24。
- 第 3 节「约 2–2.5 倍」：v7 的 2–2.8 含 SQL-L2，v8 只讲 L0、L1。
- 附录 25 单元、7,203 次。
- `causes`、`u2` 已合并到 main，v8 用到的数字和 main 上的文件逐项对过，没有变化。

## 各节数字

| 节 | 数字 | 出处 |
|---|---|---|
| 标题 | 不到 40%（L1.5S 39.8）、96%（复盘补语义 95.9）；18 种 | `cells` SQL-L1.5S、SQL-L1-tuned；19 单元去掉 SQL-L1plus-tuned-instr；标题裁决见 `decisions/2026-11-01-v8-brief-corrections.md` |
| TL;DR | 48.0、85.0、93.2、95.9；测试集 85.0→92.5 | `cells` SQL-L0、SQL-L1、SQL-L1plus、SQL-L1-tuned（all、heldout） |
| TL;DR、10 | 三次一致 96.6（86/89）、不筛 93.9（92/98）；错 6 拦 3；误拦 6 | `v7num` D4 |
| TL;DR、10 | 把握 ≥90：占 53.4，对 87.3 | `u2` SQL-L1-u2 |
| 方法 | 25 张表、244 个字段、约 3,400 万行 | `v7src` |
| 方法 | 98；76、22；一二三级 38、33、27；调优、测试各 49 | `v8num` 题目构成 |
| 方法、附录 | 格式一致口径多数低 8–17，范围 4–21 | `cells`：accuracy − delivery，all |
| 方法、3 | 最多 8 步 | `v7src` |
| 方法 | AI 工具和模型分工 | `tasks/T19a-v8-brief.md`「AI 工具披露」 |
| 1 | L0→L1 +37.1 | `cmp` |
| 1 | 约三分之二的表关系；7 家虚拟门店 | `v7src` |
| 2 | 78 题 40.2、83.3、+43.2；20 题 78.3、91.7、+13.3（区间下端恰为 0，按闭区间含 0，写差异不显著） | `v7num` D3 移组行 |
| 2 | R 51.7；L0→R +3.7；L1→L1c −16.3；R→L1c +17.0 | `cells`、`cmp` |
| 2 | 13、69；11 行、77 字段；56 组；13 条；科目键 4、50 | `v7src` |
| 2 | 约 6,800、约 46,500 token | `v8num`（6,844、46,496） |
| 2 | Cube：46–51、约 68、+17 到 +23；analytical、strict | https://github.com/cubedevinc/semantic-layer-benchmark 的 README，2026-11-01 核对 |
| 3 | 48.0、49.7、85.0、85.7；+1.7、+0.7 | `cells`、`cmp` |
| 3 | 78 题 +2.6、20 题 −1.7（L0→L0-E） | `v7num` D3 移组行 |
| 3 | 6.7、2.4 次；34.5、9.4、51.5、4.6；7.2、6.0、83.2、3.6 | `v8num`（其他 = 行数存在性 + 结构计划） |
| 3 | 输入量约 3、约 5 倍；0.9–1.3 倍；约 2–2.5 倍 | `reports/midterm/tokens-cost.md` 主表 98 行：2.70、5.18；`reports/final/recheck.md`：0.863、1.345；全冷 2.03、2.51 |
| 4 | 93.2、92.9、−0.3 | `cells`、`cmp` |
| 4 | 约 7.5 万、约 22 万 token；标题「约 3 倍」 | `v8num`（75,258、219,864，比值 2.92） |
| 4 | 109、46、14% | `v7src` |
| 4 | 文字版 2 行、本体版几十行 | `v7src` |
| 4 | 21 次 = 15、4、2 | `causes` |
| 5 | 37、42；85.0、83.7、84.9、87.4；92.9、89.7；91.9、92.8 | `cells`；`v7num` 第 5 节 |
| 5 | 39.8、41.8；91.8%（157/171）、89.3%（158/177） | `cells`；`v8num` |
| 5 | JSON-L2 覆盖内错 14 次 | `v7src`；111 − 97 |
| 6 | 44 = 19、22、3 | `causes` |
| 6 | 24 题、48 次，L0 和 L1 | `runs/20261019-T21-pilot-01/SQL-L0-P.jsonl`、`SQL-L1-P.jsonl`；`v7src` |
| 6 | 首轮报错 31.6、2.7、1.7（98 题） | `v8num`。v7 的 32.4、2.8、2.4 是 109 题口径 |
| 6 | 测试集 85.0、83.0、86.4、85.7；−2.0、+1.4、+0.7；6 道调优题 | `cells`、`cmp`；`v7src` |
| 7 | 69、14；41、37、17、13；L1→L1+ +8.2 [2.0, 14.6] | `v7src`；`cmp` |
| 8 | 85.0、92.5、93.2；+7.5 [1.4, 14.3]；+0.7 | `cells`、`cmp` split=heldout |
| 8 | 17 处矛盾 | `reports/validation/combo-conflicts.md` |
| 9 | 单元表；L1+→L3a 测试集 +0.7；L1→L1+ 测试集 +8.2 [−1.4, 17.7] | `cells`、`cmp` split=heldout |
| 9 | 12 次全部有结果；11 次测试集、1 次调优集 | `v8num`；`cells` 136/147、146/147 |
| 9 | 12 = 9、3 | `causes` |
| 10 | 六单元准确率、拒答率、已答准确率 | `u2`；基线行由总计表算出：L0 拒答 9/294 = 3.1%，已答 136/285 = 47.7%；L1 拒答 0，已答 235/294 = 79.9% |
| 10 | 拒答率差 +30.3、+5.4（区间不含 0）；基线错误率 85.1、38.6、66.7、17.4 | `u2`。第 10 节的区间用 `harness/u2_analysis.py`：10,000 次、种子 20261019；主表比较是 5,000 次、seed=0。差别不进正文 |
| 局限 | 1,411、194、420、33、24、991 | `v7src` |
| 局限 | U2：101 次复核；1,019 = 929 + 90 | `u2`；`tasks/COORDINATION-HANDOFF.md` |
| 局限 | Pro 约 7 倍；19 道题；5 道修正 | `v7src` |
| 附录 | 单元表 | `v7num`、`cells` |
| 附录 | 19 单元 5,439 次；U2 六单元 1,764 次，其中 2 个是基线重跑；合计 25 单元 7,203 次 | `reports/results/accuracy-v5.md`；`u2` |
| 附录 | 24 道未计分，都来自公开基准 | `v8num` |
| 附录 | 71 题 +47.4、27 题 +9.9；L1.5W −4.1、−8.8 | `v7num` D3；`cmp` |
| 附录 | 11 条规则、原则 A/B/C、统一规则、5 道修正 | `v7src` |
| 附录 | 所问的格为空值判错；列名单位与数值差 100 倍判错 | `decisions/2026-11-01-u2-null-one-step.md`、`decisions/2026-11-01-u2-independent-review-rulings.md` |
| 公开计划 | 发布范围含题目和参考答案；原始响应只含附录表的 19 个单元 | `decisions/2026-10-31-publication-choices.md` 第 3 条；`reports/validation/t33-publication-artifacts.md` |
