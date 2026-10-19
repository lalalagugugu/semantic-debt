# T02 评分器 v2 验证

语料只读；不执行查询、不调用模型。judge 单列，不进入评分器。

- 输入行数：3645；分类：`{'correct': 1307, 'exec_error': 560, 'wrong': 1275, 'refused': 115, 'judge': 388}`。
- unscored：0；新评分超时：0；输入不合法：0。
- 旧评分超时上限：10 秒；判定差异：47；旧评分未完成：12。
- 完整逐条耗时和原因：`scorer_v2_cases.jsonl`。

## 输入指纹

- t13.jsonl：`d66b2ad19e83652503a9ab6387b3d2a2feda61b47f226d908b9c30aaba2a6b8b`
- pilot288.jsonl：`395839fa4ceca37fa7881fa8515d54e067055e87f2552502853ba5a77ea82b47`
- ext600.jsonl：`da4626ec18ceba0d4379193442ccd3994447e9979ee3648ed0a3f2346a347fb5`

## final 与 /t0 分开统计

| 阶段 | 输入 | 分类 | 翻转 | invalid_input | unscored | 总秒数 | 最慢秒数 |
|---|---:|---|---:|---:|---:|---:|---:|
| final | 3084 | {'correct': 1307, 'wrong': 1275, 'refused': 115, 'judge': 324, 'exec_error': 63} | 47 | 0 | 0 | 16.275017 | 0.378900 |
| t0 | 561 | {'exec_error': 497, 'judge': 64} | 0 | 0 | 0 | 0.014262 | 0.000535 |

## 最慢 10 条

| case_id | 秒 | 状态 / 判定 |
|---|---:|---|
| pilot288/pro/SQL-L1/Q74/r1 | 0.378900 | wrong |
| pilot288/flash/SQL-L1/Q74/r1 | 0.343563 | wrong |
| t13/SQL-L0/Q74/r2 | 0.340560 | wrong |
| pilot288/pro/SQL-L1/Q74/r3 | 0.336880 | wrong |
| t13/SQL-L1/Q34/r1 | 0.295671 | correct |
| pilot288/flash/SQL-L1/Q34/r1 | 0.280605 | correct |
| pilot288/pro/SQL-R/Q74/r2 | 0.275465 | wrong |
| t13/SQL-L1/Q34/r2 | 0.274864 | correct |
| t13/SQL-R/Q74/r3 | 0.267843 | wrong |
| t13/SQL-R/Q34/r1 | 0.267500 | correct |

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
| t13/SQL-L1.5W/Q98/r3 | correct | wrong | 旧评分器把选择身份的 NULL 当作任意标签：候选缺少 NULL 身份且多出非空身份；仅恢复该身份后原规则判对（第五节第 7 条、12.15；空标签例外不适用身份） |
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
| t13/SQL-L0/Q117/r2 | wrong | 0.003416 |
| t13/SQL-L0/Q74/r2 | wrong | 0.340560 |
| t13/SQL-L0/Q111/r1 | wrong | 0.044659 |
| t13/SQL-L0/Q111/r2 | wrong | 0.040295 |
| t13/SQL-L1.5W/Q79/r3 | wrong | 0.000778 |
| t13/SQL-L1/Q79/r2 | wrong | 0.000781 |
| t13/SQL-R/Q74/r2 | correct | 0.158207 |
| t13/SQL-R/Q74/r1 | correct | 0.161123 |
| t13/SQL-R/Q79/r1 | wrong | 0.000708 |
| t13/SQL-R/Q79/r2 | wrong | 0.000739 |
| t13/SQL-R/Q79/r3 | wrong | 0.000772 |
| ext600:codex_gpt_5_4_raw:Q74 | correct | 0.237359 |

## 输入不合法

| case_id | 错误 |
|---|---|

## 第十三节修复与归因更正

此前 c6ed93c 把 Q119 的 6 处名次翻转归为旧版错误，归因错误，现撤回。实际缺陷在 v2：列必要条件筛选按行数限制名次，而同一排名对象可出现在多个输出组的多行中；位置编号的唯一性也应按组内对象核对。

修复后：竞赛 / 稠密排名允许同对象重复输出；位置编号按排名组和对象去重计数，同对象在同组内保持一致，不同对象不能占用同一位置。参考每对象只有一行时，行匹配见证可证明对象互异，覆盖 Q122 对象编码列非必答的情况。新增合成正反例保护这些条件。

Q119 先去掉 selection、保留名次约束，19 次参考域自比探针全部 correct。完整参考域含 4 组额外边界对象，完整域本身不得用 N+k 冒充 N；合法选择后的 306 行在原规则下 correct。此处与 T05b 正式报告的探针上下文相同。

选择约束发现漏组、多组、N+k、错对象时给 selection；身份都正确而数值错误给 values。有序值匹配失败先核验去掉名次后的行序，Q92 两条改为 order。

### 被撤销的 6 条名次翻转

| case_id | 旧版 | 修复后 v2 |
|---|---|---|
| t13/SQL-L1.5W/Q119/r1 | correct | correct |
| t13/SQL-L1/Q119/r1 | correct | correct |
| t13/SQL-L1/Q119/r3 | correct | correct |
| t13/SQL-L1c/Q119/r1 | correct | correct |
| t13/SQL-R/Q119/r1 | correct | correct |
| t13/SQL-R/Q119/r2 | correct | correct |

## 验证状态与限制

- 47 处新旧翻转全部逐条归因：46 处人名拆合 wrong→correct、1 处 NULL 选择身份 correct→wrong；不再有名次翻转。当前正式语料 invalid_input、unscored、v2 timeout 均为 0。
- 本轮旧 / 新评分器先全量运行；发现 Q122 回归后修复，再对全部 3,645 条重跑最终 v2。旧评分器代码与输入未变，保留本轮旧评分结果；两条额外超时重试已完成，最终仍为原来的 12 条旧版超时，未编造其判定，不算翻转。
- 作者合成 180 passed；旧版相关回归 185 passed、109 条兼容 warning；作者压力 8 passed。二百万行正确 / 错误整项耗时 7.24 / 25.53 秒，内部判分断言 ≤30 秒。
- 当前 194 条只读共用用例的判定差异为 0、原因码差异为 1，不能声称全部通过。`t05b/name/selection-identity-wrong` 仍预期 values，按第十三节第 2 条应为 selection，已交用户 / T05b 更新；未覆盖、未修改输入预期。刻意触发 mapping_cap 的 1 条合成用例单列，不影响真实 unscored=0。
- 仓库结构测试另有 2 条 main 基线失败（T21 前置检查点、T19a 卡片登记）；用 origin/main 原文件复现，未做卡外改动。
- 当前结果交 T05b 按第十三节再做独立复验；不把本报告当作跨实现全部验收完成，不打 tag、不启动正式重评。

- 最终评分器 SHA256：`a012aba545e8df760e967828a1df1ca0a1db993fc3d309ece24a70bc4ce207d4`。

## 复现

```sh
UV_CACHE_DIR="$TMPDIR/t02-uv-cache" uv run --no-sync python -m pytest \
  tests/test_scorer_v2.py tests/test_scorer_v2_performance.py \
  tests/test_scorer_v2_shared.py tests/test_scorer.py \
  tests/test_scorer_presentation.py tests/test_selection.py --durations=12

UV_CACHE_DIR="$TMPDIR/t02-uv-cache" uv run --no-sync python scripts/validate_scorer_v2.py \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/t13.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/pilot288.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/ext600.jsonl" --old-timeout 10
```

## 报告脱敏与历史范围

实际和共用预期中的 exec_error 原因只写 execution_failed 与 SHA256；输入错误只保留异常类别与 SHA256。数据库报错原文留在库外语料，未写入本分支报告。旧 scorer 与 prompt 未改。

此前已按授权仅清理 T02-scorer-v2 独有历史并用固定 lease 推送。本轮普通追加提交，审计本分支各独有提交的 reports / JSONL，不只最新工作树；不更改 main 继承的报告和只追加运行日志，也不声称托管端旧对象已物理删除。
