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
| final | 3084 | {'correct': 1307, 'wrong': 1275, 'refused': 115, 'judge': 324, 'exec_error': 63} | 47 | 0 | 0 | 19.288286 | 0.485621 |
| t0 | 561 | {'exec_error': 497, 'judge': 64} | 0 | 0 | 0 | 0.018997 | 0.001507 |

## 最慢 10 条

| case_id | 秒 | 状态 / 判定 |
|---|---:|---|
| pilot288/flash/SQL-L1/Q34/r1 | 0.485621 | correct |
| pilot288/pro/SQL-L1/Q74/r1 | 0.450722 | wrong |
| pilot288/flash/SQL-L1/Q74/r1 | 0.446997 | wrong |
| pilot288/flash/SQL-L1/Q74/r2 | 0.423595 | wrong |
| pilot288/pro/SQL-L1/Q74/r3 | 0.406795 | wrong |
| t13/SQL-L0/Q74/r2 | 0.357539 | wrong |
| t13/SQL-L1/Q34/r2 | 0.329286 | correct |
| t13/SQL-R/Q34/r1 | 0.314081 | correct |
| pilot288/flash/SQL-R/Q74/r1 | 0.307601 | wrong |
| pilot288/pro/SQL-R/Q74/r2 | 0.307580 | wrong |

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
| t13/SQL-L0/Q117/r2 | wrong | 0.003864 |
| t13/SQL-L0/Q74/r2 | wrong | 0.357539 |
| t13/SQL-L0/Q111/r1 | wrong | 0.048526 |
| t13/SQL-L0/Q111/r2 | wrong | 0.044768 |
| t13/SQL-L1.5W/Q79/r3 | wrong | 0.000794 |
| t13/SQL-L1/Q79/r2 | wrong | 0.000951 |
| t13/SQL-R/Q74/r2 | correct | 0.175340 |
| t13/SQL-R/Q74/r1 | correct | 0.175879 |
| t13/SQL-R/Q79/r1 | wrong | 0.000727 |
| t13/SQL-R/Q79/r2 | wrong | 0.000830 |
| t13/SQL-R/Q79/r3 | wrong | 0.000797 |
| ext600:codex_gpt_5_4_raw:Q74 | correct | 0.265635 |

## 输入不合法

| case_id | 错误 |
|---|---|

## 分语料判定统计（本轮全部重跑 v2）

| 语料 / 阶段 | 输入 | correct | wrong | exec_error | refused | judge | invalid_input | unscored |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t13 / final | 2196 | 959 | 860 | 28 | 115 | 234 | 0 | 0 |
| t13 / t0 | 533 | 0 | 0 | 469 | 0 | 64 | 0 | 0 |
| pilot288 / final | 288 | 133 | 138 | 5 | 0 | 12 | 0 | 0 |
| pilot288 / t0 | 28 | 0 | 0 | 28 | 0 | 0 | 0 | 0 |
| ext600 / final | 600 | 215 | 277 | 30 | 0 | 78 | 0 | 0 |
| ext600 / t0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## wrong 原因码统计

| 语料 | row_count | missing_columns | values | order | selection | rank | top_n_full_group |
|---|---:|---:|---:|---:|---:|---:|---:|
| t13 | 325 | 33 | 419 | 18 | 48 | 17 | 0 |
| pilot288 | 56 | 19 | 51 | 0 | 4 | 8 | 0 |
| ext600 | 121 | 12 | 113 | 2 | 8 | 21 | 0 |
| 全部 | 502 | 64 | 583 | 20 | 60 | 46 | 0 |

所有 wrong 都在 final；/t0 只有 exec_error / judge。数据库执行错误的原文不参与原因码统计，仅保留 execution_failed 与 SHA256。

## 比较基线与第十三节变化

- 相对上一提交 af9e2d3 / 5617caa 的已提交逐条结果，本轮 3,645 条判定和原因码均无变化。评分实现未改。
- 相对旧评分器仍为 47 处翻转：46 人名拆合 wrong→correct、1 NULL 选择身份 correct→wrong；没有 Q119 名次翻转。旧评分器本轮未重复运行，沿用同一输入、同一旧代码的已完成结果；12 条旧版超时照旧单列。
- 相对 c6ed93c（第十三节修复前），6 条 Q119 wrong/rank→correct 已修正，Q92 的 1 条 rank→order 和 1 条 values→order 已修正。
- values→selection 实测 **52 条**，与用户给出的预期 48 条相差 4 条：t13 41、pilot288 3、ext600 8。多出的 4 条均为 Q71，候选有参考全部 8 个组再多 1 组；第十三节明确多组报 selection，未为凑数改回 values。交 T05b 复核统计基线 / 这 4 条，尚不声称真实语料独立对账全部完成。

### 与 48 条预期相差的 Q71 四条（标识和计数，不含原文）

| case_id | 参考组数 | 候选组数 | 共同组数 | 多出组数 | 本轮原因 |
|---|---:|---:|---:|---:|---|
| t13/SQL-L1.5S/Q71/r1 | 8 | 9 | 8 | 1 | selection |
| t13/SQL-L1.5S/Q71/r2 | 8 | 9 | 8 | 1 | selection |
| t13/SQL-L1.5S/Q71/r3 | 8 | 9 | 8 | 1 | selection |
| pilot288/pro/SQL-L1/Q71/r3 | 8 | 9 | 8 | 1 | selection |

### values→selection 全部逐条变化（相对 c6ed93c）

| case_id | 修复前 | 当前 |
|---|---|---|
| t13/SQL-L0/Q119/r1 | values | selection |
| t13/SQL-L0/Q119/r2 | values | selection |
| t13/SQL-L0/Q119/r3 | values | selection |
| t13/SQL-L0/Q74/r1 | values | selection |
| t13/SQL-L0/Q85/r2 | values | selection |
| t13/SQL-L0/Q85/r1 | values | selection |
| t13/SQL-L0/Q85/r3 | values | selection |
| t13/SQL-L0/Q98/r2 | values | selection |
| t13/SQL-L0/Q98/r1 | values | selection |
| t13/SQL-L0/Q98/r3 | values | selection |
| t13/SQL-L1.5S/Q119/r1 | values | selection |
| t13/SQL-L1.5S/Q71/r1 | values | selection |
| t13/SQL-L1.5S/Q71/r3 | values | selection |
| t13/SQL-L1.5S/Q71/r2 | values | selection |
| t13/SQL-L1.5S/Q85/r2 | values | selection |
| t13/SQL-L1.5S/Q98/r1 | values | selection |
| t13/SQL-L1.5S/Q98/r3 | values | selection |
| t13/SQL-L1.5S/Q98/r2 | values | selection |
| t13/SQL-L1.5W/Q119/r2 | values | selection |
| t13/SQL-L1.5W/Q119/r3 | values | selection |
| t13/SQL-L1.5W/Q74/r3 | values | selection |
| t13/SQL-L1.5W/Q74/r1 | values | selection |
| t13/SQL-L1.5W/Q98/r2 | values | selection |
| t13/SQL-L1.5W/Q98/r3 | values | selection |
| t13/SQL-L1/Q74/r1 | values | selection |
| t13/SQL-L1/Q85/r1 | values | selection |
| t13/SQL-L1/Q85/r3 | values | selection |
| t13/SQL-L1/Q98/r3 | values | selection |
| t13/SQL-L1c/Q74/r1 | values | selection |
| t13/SQL-L1c/Q74/r2 | values | selection |
| t13/SQL-L1c/Q74/r3 | values | selection |
| t13/SQL-L1c/Q85/r2 | values | selection |
| t13/SQL-L1c/Q98/r3 | values | selection |
| t13/SQL-L1c/Q98/r2 | values | selection |
| t13/SQL-R/Q119/r3 | values | selection |
| t13/SQL-R/Q22/r3 | values | selection |
| t13/SQL-R/Q85/r1 | values | selection |
| t13/SQL-R/Q85/r2 | values | selection |
| t13/SQL-R/Q98/r2 | values | selection |
| t13/SQL-R/Q98/r3 | values | selection |
| t13/SQL-R/Q98/r1 | values | selection |
| pilot288/pro/SQL-L1/Q71/r3 | values | selection |
| pilot288/pro/SQL-L1/Q74/r2 | values | selection |
| pilot288/pro/SQL-R/Q74/r3 | values | selection |
| ext600:claude_claude_opus_4_7_raw:Q74 | values | selection |
| ext600:claude_claude_opus_4_7_raw:Q98 | values | selection |
| ext600:claude_claude_opus_4_7_semantic:Q74 | values | selection |
| ext600:claude_claude_opus_4_7_semantic:Q98 | values | selection |
| ext600:claude_claude_sonnet_4_6_raw:Q74 | values | selection |
| ext600:claude_claude_sonnet_4_6_raw:Q98 | values | selection |
| ext600:codex_gpt_5_4_raw:Q98 | values | selection |
| ext600:codex_gpt_5_4_semantic:Q98 | values | selection |

## 共用验收、版本与隐私

更新后的 207 条共用用例判定 / 原因码零分歧；1 条有意 mapping_cap 单列。输入 SHA256 为 `bb5fe9fa6881d4340f5c4e92ebcd17c481a2c7733bd5b9fed8b1405bb0ad2673`，运行前后未变。详情见 `scorer_v2_shared_check.md`。

评分器 SHA256 `a012aba545e8df760e967828a1df1ca0a1db993fc3d309ece24a70bc4ce207d4`，与前次真实语料复验相同。三份语料 SHA256 与原验收通知相同，每行输入哈希均核验通过，未读取旧 eval-v1.1 数据。

当前共用用例阻塞已解除；交用户通知 T05b 进行第十三节最终独立对账，不代替独立检查器宣布零分歧、不打 tag、不启动正式重评。

实际和预期中的 exec_error 原因均脱敏，仅保留错误类别与哈希。所有新增 / 修改 reports 和 JSONL 均只含标识、状态、计数、耗时、原因码和哈希；main 继承的只追加日志未改，旧 scorer 与 prompt 未改。

```sh
UV_CACHE_DIR="$TMPDIR/t02-uv-cache" uv run --no-sync python scripts/validate_scorer_v2.py \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/t13.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/pilot288.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/ext600.jsonl" --old-timeout 10
```
