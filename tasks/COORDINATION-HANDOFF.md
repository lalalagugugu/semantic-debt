# 协调会话交接（2026-10-19 16:45，北京时间）

协调会话（Claude Code，`sem-debt`）因订阅额度暂停。接手者先读 AGENTS.md、tasks/BOARD.md、本文件，以及 decisions/ 下 2026-10-19 的全部裁决。

## 协调会话的职责与规矩

- 评估各会话的回报，起草裁决（`decisions/`），推分支、开 PR；**用户合并 PR，只有用户说「打 tag」才打 tag**（用 GitHub API 在合并提交上建 annotated tag）。
- 给用户的回复用中文，每次结尾附任务状态表（序 / 事项 / 负责 / 依赖 / 状态 / 需要你做什么）；状态写明在等谁；时间戳先 `TZ=Asia/Shanghai date` 再写。
- 付费调用：先 dry-run、用户批准预算、错峰（工作日 9–12、14–18 是高峰；12–14、18 点后、周末是错峰）；用户可以单次放行高峰。
- 跨厂商：评分器、复核、数字复核归 Codex；会话间只传题号、类别、结论，不传题面。
- 本地 Claude Code 会话（T12、T13、T15、T21、t05b）只能由本地协调会话发消息；**云端会话发不了消息给本地会话**，只能经 PR 与用户转达。Codex 会话（T02、T05、T16）一律由用户转发。

## 已打的 tag（今天）

eval-v1.2（题库 90e13b3）、harness-agent-v1 / v1.1、harness-v1.1（评分器 v2，6a23d3c）、harness-plan-v1（b10ca1a，第二期再用）、semantic-v1.3（d2801b1，Cube 写法说明 2 级）。

## 进行中（截至 16:45）

| 事项 | 谁 | 下一步 |
|---|---|---|
| 通用交付检查（引用检查脚本、约定 × 档位覆盖表、汇总层度量 vs 指标、DAX vs Cube 指标对照）+ T16 两条 Cube 说明增补 + 汇总层约定 1、2 的缺口 → `semantic-v1.4` | T12，分支 `T12-v14`（小步推送） | 完成后交 Codex 复核覆盖表与修复，再由用户合并、打 tag |
| JSON-L2 10 条拒答再分类（常用指标没建 vs 题目特有组合） | Codex T16（用户转发） | 并入 PR #114 |
| C13 写法说明阶梯（ClickHouse 2/3/4 级） | T12，PR #141 待合并 | 用户合并后打 `harness-ladder-v1`；**v1.4 定稿后再跑**（若 L1 上下文也改，1 级要重跑） |
| L1.5S 覆盖内分析 | T13，PR #138 **暂缓合并** | v1.4 后重跑 L1.5S，补「修复后」数字 |

## 已定的裁决（今天，都在 decisions/）

- `2026-10-19-phase1-replan.md`：规划 agent 与 judge 题移到第二期；第一期新跑一律跳过 judge 13 题；C13 阶梯；不为指标文字歧义出 v1.4（报告按含 / 不含 19 题拆）。
- `2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md`：L1.5S 跨档位只比覆盖内、覆盖外单报拒答；加 JSON-L2 · 3 级；DAX 开跑前检查清单；读法以参考答案为准。
- `2026-10-19-self-built-p-and-cube-notes.md`：写法说明归「栈」；教学深度 0–5 级，第一期目标 2 级；SQL-L2 新旧说明各跑一遍全量。

## 之后的顺序

1. Codex 复核 v1.4 → 合并 → `semantic-v1.4`。
2. 重跑 L1.5S；SQL-L2、JSON-L2 冒烟复核 → 全量（SQL-L2 新旧说明各一遍）→ JSON-L2 · 3 级；L2-E（T15）。
3. C13 2/3/4 级（约 10 元）；T14 调优（A、B 两个会话，用户开）。
4. 中期报告 T19a（云端可做，`tasks/T19a-midterm-report.md`，`reports/hypotheses.md` 是底稿）。
5. DAX 线（Windows，先过检查清单）→ 最终报告 → G4。

## 已知结论（暂定口径见 reports/hypotheses.md）

治理：L0 39.1% → R 42.9% → L1 67.7%；探查 agent +0.7（L0、L1）；宽表无增益；汇总层覆盖内低 12.7 点，主因是汇总文档漏了约定 1、2（交付缺陷，待修）；ClickHouse 首轮报错 77% 来自中文别名未加反引号（说明只到 1 级）；JSON-L2 冒烟 26.3%，10/23 拒答。

## T12 进度更新（16:50，分支 `T12-v14`，头 6f5be3e）

- 已完成：T16 两条 Cube SQL 说明增补（1231bc9，只有 SQL-L2、SQL-L2-E 变）；引用检查脚本 `render/check_references.py` + 测试（6f5be3e），全部 10 个上下文只有 L1.5S 有 2 处缺口（坪效、门店人均销售额引用 DimStore 列），已在 summary.yaml 映射到可见列，现在 0 缺口。
- 未完成：约定 × 档位覆盖表（L1、L1.5W、L1.5S、L2）；汇总层度量 vs 指标层、DAX vs Cube 两张覆盖表；按覆盖表修 L1.5S 约定 1、2（ads_online_* vs ads_sales_* 的 Online 渠道）；汇总报告；JSON-L2 · 3 级说明。
- 注意：引用检查只查「名字是否可见」，查不出约定 1、2 这种「约定没对应到可见表」的缺口，所以覆盖表（人工 + Codex 复核）必须做。
