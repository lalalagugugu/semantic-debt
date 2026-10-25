# T23 scorer v3：82 条新增判对的跨厂商逐条复核（Claude Code）

- 复核方：Claude Code（T14 A 角会话，跨厂商；不是 T23 的同厂商子 agent）。日期 2026-10-25。
- 对象：`runs/20261025-T23-v3-02` 中 v2 判错、v3 判对的全部 82 条（都是 P1 期间等价）。复核包 `$SEMDEBT_DATA_DIR/t23-v3-review/20261025-T23-v3-02/cases.jsonl`（含题面与结果行，不入库）。
- 依据：`decisions/2026-10-25-t23-presentation-rules-proposal.md`（P1 及其防误判条件）、`decisions/2026-10-25-t23-presentation-rules-approved.md`（保守范围：只用原始结果与参考 MANIFEST 已有的列名和类型；缺年份来源、需要翻译或业务同义词映射的维持原判；涉及 selection / rankings / Top-N / unordered_pairs 的期间转换维持原判）。
- 本文件只含题号、来源运行、单元、次序、期间粒度与结论；不含题面、不含结果行。

## 结论

**82 条全部 pass；fail 0 条，unsure 0 条。** 另有三点解读请用户知悉，见「需要用户知悉的解读」，它们不改变结论。

## 方法

1. **输入来源核对**（全部通过）：
   - 复核包的 82 条与 `runs/20261025-T23-v3-02` 中 `final` v2 非 correct、v3 correct 的条目一一对应，`exec_raw_sha256` 与规则（P1）一致。该运行里没有 v2 correct → v3 非 correct 的条目。
   - 每条的候选结果行与 `$SEMDEBT_DATA_DIR/runs-raw/<源运行>/<单元>/` 中哈希等于 `exec_raw_sha256` 的原始执行文件逐行相同（82/82）。
   - 12 道题的参考结果与 `rules` 与 eval-v1.2（只读 worktree）逐行相同。
2. **独立判定**：自写检查脚本，不导入 T23 的评分器，也不采用 v3 记录的转换，只用 v2 的数值容差（相对 0.5%，按值类型的绝对下限，比率 / 百分比允许 ×100、÷100）：
   - 两边的期间列各自解析成（年份或无，粒度，序号）。候选侧接受英文月名、`YYYY-MM`、恰为月首的日期、`YYYY Qn`、`Qn` 配年份列、`Year YYYY`、四位年份文本，以及与独立年份列的拆合。参考侧按列名识别 `month` / `*_month`、`quarter`、`year` / `*_year`。
   - 粒度必须相同；年份「两边都有」或「两边都无」，不推断年份。
   - 参考的每个必答非期间列都要映射到一个候选列，按「期间键相同 + 全部必答列在容差内」做行的一对一匹配，行数必须相等（保留重复次数）。规则为 ordered 时还要逐行对齐（这 82 条都没有 ordered / top_n / selection / rankings / unordered_pairs / order_by）。
3. **其他核对**：
   - 用作期间的日期列全部恰为月首（14 条）。
   - 唯一一条带多余日期列的作答，多余列与月份逐行一致、年份与参考范围一致（P4，不矛盾）。

## 分组小结

| 候选期间表示 ↔ 参考 | 条数 | 年份 |
|---|---:|---|
| 英文月名 ↔ 月序号 | 53 | 两边都无年份（题面限定单一年份，参考亦不带年份） |
| 月首日期 ↔ 月序号 + 年份列 | 13 | 两边都有，逐行一致 |
| `YYYY-MM` 文本 ↔ 月序号 + 年份列 | 5 | 两边都有 |
| 英文月名 + 独立年份列 ↔ 月序号 + 年份列 | 3 | 两边都有 |
| `Year YYYY` 标签 ↔ 年份 | 5 | — |
| 四位年份文本 ↔ 年份 | 1 | — |
| `YYYY Qn` 标签 ↔ 季度标签 + 年份列 | 1 | 两边都有 |
| `Qn` 标签 + 年份列 ↔ 季度标签 + 年份列 | 1 | 两边都有 |

## 需要用户知悉的解读（不改变结论）

1. **英文月名、两边都没有年份（53 条，Q12、Q23、Q64、Q77、Q113）**：我把英文月名视为「无歧义的标准日历表示」，不算「翻译或业务同义词映射」。参考本身不带年份，所以不需要补年份，也没有推断年份。若用户认为月名属于需要映射的情形，这 53 条应退回 v2 原判。
2. **`Year YYYY` 标签（5 条，Q16、Q81、Q90、Q96）**：视为标准日历年份标签，不算批准文件里「不同业务前缀不合并」的业务前缀。数值逐行在容差内，排除了按其他年制分组的情况。
3. **Q90（1 条）**：除年份标签外，参考中品类为 NULL 的一组，候选给了文字标签。这一点由 v2 已有的 NULL 名称规则判等（参考为 NULL / 空、候选文字不与其他成员重名），不是 P3；v2 判错只因年份标签。批准文件说「Unknown / 未知 是真实成员」，那是对参考侧文字名称的 P3 限定，与本条无关。

## 逐条结论

| # | 题号 | 源运行 | 单元 | 次 | 粒度 | 结论 | 理由 |
|---|---|---|---|---|---|---|---|
| 1 | Q116 | 20261019-T15-explorer-01 | SQL-L1-E | r3 | month | pass | YYYY-MM text ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 2 | Q116 | 20261019-T15-explorer-01 | SQL-L1-E | r1 | month | pass | YYYY-MM text ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 3 | Q12 | 20261019-T15-explorer-01 | SQL-L1-E | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 4 | Q16 | 20261019-T15-explorer-01 | SQL-L1-E | r1 | year | pass | 'Year YYYY' label ↔ year number; year kept on both sides; 2/2 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 5 | Q23 | 20261019-T15-explorer-01 | SQL-L1-E | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 6 | Q64 | 20261019-T15-explorer-01 | SQL-L1-E | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 7 | Q64 | 20261019-T15-explorer-01 | SQL-L1-E | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 8 | Q90 | 20261019-T15-explorer-01 | SQL-L1-E | r3 | year | pass | 'Year YYYY' label ↔ year number; year kept on both sides; 27/27 rows matched one-to-one; 4 required non-period columns within v2 tolerance; the NULL-category reference row matches a text label via v2's existing NULL-name rule, not via P3 |
| 9 | Q113 | 20261025-T14-tuned-01 | SQL-L1-tuned | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 33/33 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 10 | Q12 | 20261025-T14-tuned-01 | SQL-L1-tuned | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 11 | Q12 | 20261025-T14-tuned-01 | SQL-L1-tuned | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 12 | Q12 | 20261025-T14-tuned-01 | SQL-L1-tuned | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 13 | Q23 | 20261025-T14-tuned-01 | SQL-L1-tuned | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 14 | Q116 | 20261019-T15-explorer-01 | SQL-L0-E | r1 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 15 | Q116 | 20261019-T15-explorer-01 | SQL-L0-E | r2 | month | pass | YYYY-MM text ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 16 | Q12 | 20261019-T15-explorer-01 | SQL-L0-E | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 17 | Q12 | 20261019-T15-explorer-01 | SQL-L0-E | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 18 | Q116 | 20261019-T15-explorer-01 | SQL-L0-E | r3 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 19 | Q77 | 20261019-T15-explorer-01 | SQL-L0-E | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 2 required non-period columns within v2 tolerance; extra first-of-month date column agrees with the month on every row (P4) |
| 20 | Q96 | 20261019-T15-explorer-01 | SQL-L0-E | r2 | year | pass | 'Year YYYY' label ↔ year number; year kept on both sides; 2/2 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 21 | Q113 | 20261018-T13-sql-direct-01 | SQL-R | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 33/33 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 22 | Q12 | 20261018-T13-sql-direct-01 | SQL-R | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 23 | Q12 | 20261018-T13-sql-direct-01 | SQL-R | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 24 | Q12 | 20261018-T13-sql-direct-01 | SQL-R | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 25 | Q64 | 20261018-T13-sql-direct-01 | SQL-R | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 26 | Q64 | 20261018-T13-sql-direct-01 | SQL-R | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 27 | Q12 | 20261019-T16-full-v14-sql-new-01 | SQL-L2 | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 28 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1c | r1 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 29 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1c | r3 | month | pass | YYYY-MM text ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 30 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1c | r2 | month | pass | English month name + separate year column ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 31 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1c | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 32 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1c | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 33 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1c | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 34 | Q23 | 20261018-T13-sql-direct-01 | SQL-L1c | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 35 | Q23 | 20261018-T13-sql-direct-01 | SQL-L1c | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 36 | Q23 | 20261018-T13-sql-direct-01 | SQL-L1c | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 37 | Q116 | 20261019-C13-ladder-02 | SQL-L1-T2 | r3 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 38 | Q116 | 20261019-C13-ladder-02 | SQL-L1-T2 | r2 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 39 | Q116 | 20261019-C13-ladder-02 | SQL-L1-T2 | r1 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 40 | Q12 | 20261019-C13-ladder-02 | SQL-L1-T2 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 41 | Q23 | 20261019-C13-ladder-02 | SQL-L1-T2 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 42 | Q23 | 20261019-C13-ladder-02 | SQL-L1-T2 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 43 | Q64 | 20261019-C13-ladder-02 | SQL-L1-T2 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 44 | Q64 | 20261019-C13-ladder-02 | SQL-L1-T2 | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 45 | Q64 | 20261019-C13-ladder-02 | SQL-L1-T2 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 46 | Q72 | 20261019-C13-ladder-02 | SQL-L1-T2 | r1 | quarter | pass | 'YYYY Qn' label ↔ quarter label + year column; year kept on both sides; 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 47 | Q23 | 20261019-C13-ladder-02 | SQL-L1-T4 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 48 | Q23 | 20261019-C13-ladder-02 | SQL-L1-T4 | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 49 | Q113 | 20261019-C13-ladder-02 | SQL-L1-T4 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 33/33 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 50 | Q64 | 20261019-C13-ladder-02 | SQL-L1-T4 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 51 | Q77 | 20261019-C13-ladder-02 | SQL-L1-T4 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 52 | Q12 | 20261018-T13-sql-direct-01 | SQL-L0 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 53 | Q12 | 20261018-T13-sql-direct-01 | SQL-L0 | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 54 | Q12 | 20261018-T13-sql-direct-01 | SQL-L0 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 55 | Q16 | 20261018-T13-sql-direct-01 | SQL-L0 | r2 | year | pass | 'Year YYYY' label ↔ year number; year kept on both sides; 2/2 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 56 | Q64 | 20261018-T13-sql-direct-01 | SQL-L0 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 57 | Q116 | 20261020-T15-explorer-l2e-02 | SQL-L2-E | r3 | month | pass | YYYY-MM text ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 58 | Q72 | 20261020-T15-explorer-l2e-02 | SQL-L2-E | r1 | quarter | pass | 'Qn' label + separate year column ↔ quarter label + year column; year kept on both sides; 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 59 | Q116 | 20261019-C13-ladder-02 | SQL-L1-T3 | r1 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 60 | Q116 | 20261019-C13-ladder-02 | SQL-L1-T3 | r3 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 61 | Q116 | 20261019-C13-ladder-02 | SQL-L1-T3 | r2 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 62 | Q12 | 20261019-C13-ladder-02 | SQL-L1-T3 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 63 | Q12 | 20261019-C13-ladder-02 | SQL-L1-T3 | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 64 | Q23 | 20261019-C13-ladder-02 | SQL-L1-T3 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 65 | Q64 | 20261019-C13-ladder-02 | SQL-L1-T3 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 66 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r2 | month | pass | English month name + separate year column ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 67 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r3 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 68 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r1 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 69 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 70 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 71 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 72 | Q64 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r2 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 73 | Q64 | 20261018-T13-sql-direct-01 | SQL-L1.5W | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 74 | Q110 | 20261018-T13-sql-direct-01 | SQL-L1 | r2 | year | pass | YYYY text ↔ year number; year kept on both sides; 2/2 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 75 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1 | r1 | month | pass | English month name + separate year column ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 76 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1 | r2 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 77 | Q116 | 20261018-T13-sql-direct-01 | SQL-L1 | r3 | month | pass | first-of-month date ↔ month number + year column; year kept on both sides; 4/4 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
| 78 | Q12 | 20261018-T13-sql-direct-01 | SQL-L1 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 79 | Q23 | 20261018-T13-sql-direct-01 | SQL-L1 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 80 | Q23 | 20261018-T13-sql-direct-01 | SQL-L1 | r1 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 1 required non-period columns within v2 tolerance |
| 81 | Q64 | 20261018-T13-sql-direct-01 | SQL-L1 | r3 | month | pass | English month name ↔ month number; no year on either side (none inferred); 12/12 rows matched one-to-one; 3 required non-period columns within v2 tolerance |
| 82 | Q81 | 20261018-T13-sql-direct-01 | SQL-L1 | r2 | year | pass | 'Year YYYY' label ↔ year number; year kept on both sides; 2/2 rows matched one-to-one; 2 required non-period columns within v2 tolerance |
