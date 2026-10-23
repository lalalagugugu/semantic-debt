# 调优包 sql-l1：清单与题集划分逐题核对

- 生成：`uv run python -m harness.tuning_packet --packet sql-l1 --eval-tag eval-v1.2`（harness `69356c5`）
- 题库：`eval-v1.2` = `90e13b3`（只读 worktree，`verify_eval_tag` 校验通过）
- 第一次运行：`runs/20261018-T13-sql-direct-01-rescore-01/SQL-L1.jsonl`（harness-v1.1 最终判定），作答结果取自 `$SEMDEBT_DATA_DIR/runs-raw/20261018-T13-sql-direct-01/`（逐个核对 sha256）
- 题库 122 题：调优题 54、留出题 55（均不含 judge），judge 13
- 进包：23 题、51 次答错的作答；规则：调优题、非 judge、第一次运行 3 次中至少 1 次不是 correct，只放不是 correct 的那几次
- 包的位置：`build/tuning-packet/sql-l1/`（不入库，含题面）；B 角写 `semantic/tuning/SQL-L1.yaml`

## 自动核对

- ✅ 清单题号与 `cases/` 文件一一对应
- ✅ 进包的题全部是 `split: tuning`
- ✅ 没有 judge 题
- ✅ 没有 correct 的作答
- ✅ 调优题里所有非 correct 的作答都在包里（不漏）
- ✅ 包里只有 README、MANIFEST 与清单里的题文件
- ✅ 任何文件都不出现包外的题号（与题库题号比对；Q1–Q4 是季度）
- ✅ 任何文件都不含留出题的题面
- ✅ 不提及其他单元

结果：全部通过。

## 逐题对照（题号、划分、第一次运行的判定）

| 题号 | 划分 | 评分 | 第一次运行 r1/r2/r3 | 进包 | 理由 |
|---|---|---|---|---|---|
| Q01 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q02 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q03 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q04 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q05 | heldout | deterministic | correct/wrong/correct | 否 | 留出题 |
| Q06 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q07 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q08 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q09 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q10 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q11 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q12 | tuning | deterministic | wrong/correct/wrong | 是 | 答错 r1,3 |
| Q13 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q14 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q15 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q16 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q17 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q18 | heldout | deterministic | wrong/correct/wrong | 否 | 留出题 |
| Q19 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q20 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q21 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q22 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q23 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q24 | tuning | deterministic | correct/exec_error/correct | 是 | 答错 r2 |
| Q25 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q26 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q27 | tuning | deterministic | correct/correct/wrong | 是 | 答错 r3 |
| Q28 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q29 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q30 | heldout | deterministic | wrong/correct/wrong | 否 | 留出题 |
| Q31 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q32 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q33 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q34 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q35 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q36 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q37 | heldout | deterministic | correct/wrong/correct | 否 | 留出题 |
| Q38 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q39 | heldout | judge | pending/pending/pending | 否 | 留出题 |
| Q40 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q41 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q42 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q43 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q44 | heldout | judge | pending/pending/pending | 否 | 留出题 |
| Q45 | heldout | judge | pending/pending/pending | 否 | 留出题 |
| Q46 | heldout | judge | pending/pending/pending | 否 | 留出题 |
| Q47 | tuning | deterministic | correct/wrong/correct | 是 | 答错 r2 |
| Q48 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q49 | tuning | deterministic | wrong/correct/wrong | 是 | 答错 r1,3 |
| Q50 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q51 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q52 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q53 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q54 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q55 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q56 | tuning | deterministic | correct/wrong/correct | 是 | 答错 r2 |
| Q57 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q58 | tuning | deterministic | wrong/correct/wrong | 是 | 答错 r1,3 |
| Q59 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q60 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q61 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q62 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q63 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q64 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q65 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q66 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q67 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q68 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q69 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q70 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q71 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q72 | tuning | deterministic | correct/wrong/correct | 是 | 答错 r2 |
| Q73 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q74 | tuning | deterministic | wrong/correct/correct | 是 | 答错 r1 |
| Q75 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q76 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q77 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q78 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q79 | heldout | deterministic | correct/wrong/correct | 否 | 留出题 |
| Q80 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q81 | tuning | deterministic | correct/wrong/correct | 是 | 答错 r2 |
| Q82 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q83 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q84 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q85 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q86 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q87 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q88 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q89 | heldout | deterministic | wrong/wrong/correct | 否 | 留出题 |
| Q90 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q91 | heldout | judge | pending/pending/pending | 否 | 留出题 |
| Q92 | heldout | deterministic | wrong/correct/correct | 否 | 留出题 |
| Q93 | heldout | judge | pending/pending/pending | 否 | 留出题 |
| Q94 | heldout | deterministic | wrong/wrong/wrong | 否 | 留出题 |
| Q95 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q96 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q97 | tuning | judge | pending/pending/pending | 否 | judge 题 |
| Q98 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q99 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q100 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q101 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q102 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q103 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q104 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q105 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q106 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q107 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q108 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q109 | tuning | deterministic | wrong/correct/wrong | 是 | 答错 r1,3 |
| Q110 | heldout | deterministic | correct/wrong/correct | 否 | 留出题 |
| Q111 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q112 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q113 | heldout | deterministic | wrong/exec_error/wrong | 否 | 留出题 |
| Q114 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q115 | tuning | deterministic | correct/correct/correct | 否 | 3 次全对 |
| Q116 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q117 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q118 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q119 | heldout | deterministic | correct/wrong/correct | 否 | 留出题 |
| Q120 | heldout | deterministic | correct/correct/correct | 否 | 留出题 |
| Q121 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
| Q122 | tuning | deterministic | wrong/wrong/wrong | 是 | 答错 r1,2,3 |
