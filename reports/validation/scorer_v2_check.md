# T02 评分器 v2 验证

语料只读；不执行查询、不调用模型。judge 单列，不进入评分器。

- 输入行数：3645；分类：`{'correct': 1301, 'exec_error': 560, 'wrong': 1281, 'refused': 115, 'judge': 388}`。
- unscored：0；新评分超时：0；输入不合法：0。
- 旧评分超时上限：10 秒；判定差异：53；旧评分未完成：12。
- 完整逐条耗时和原因：`scorer_v2_cases.jsonl`。

## 输入指纹

- t13.jsonl：`d66b2ad19e83652503a9ab6387b3d2a2feda61b47f226d908b9c30aaba2a6b8b`
- pilot288.jsonl：`395839fa4ceca37fa7881fa8515d54e067055e87f2552502853ba5a77ea82b47`
- ext600.jsonl：`da4626ec18ceba0d4379193442ccd3994447e9979ee3648ed0a3f2346a347fb5`

## final 与 /t0 分开统计

| 阶段 | 输入 | 分类 | 翻转 | invalid_input | unscored | 总秒数 | 最慢秒数 |
|---|---:|---|---:|---:|---:|---:|---:|
| final | 3084 | {'correct': 1301, 'wrong': 1281, 'refused': 115, 'judge': 324, 'exec_error': 63} | 53 | 0 | 0 | 18.829042 | 0.517960 |
| t0 | 561 | {'exec_error': 497, 'judge': 64} | 0 | 0 | 0 | 0.018684 | 0.000669 |

## 最慢 10 条

| case_id | 秒 | 状态 / 判定 |
|---|---:|---|
| pilot288/pro/SQL-L1/Q74/r2 | 0.517960 | wrong |
| ext600:claude_claude_opus_4_7_raw:Q74 | 0.453204 | wrong |
| pilot288/pro/SQL-L1/Q74/r3 | 0.402506 | wrong |
| pilot288/pro/SQL-L1/Q74/r1 | 0.372298 | wrong |
| t13/SQL-L1/Q34/r2 | 0.367088 | correct |
| t13/SQL-L1/Q34/r1 | 0.324218 | correct |
| pilot288/flash/SQL-L1/Q34/r1 | 0.321083 | correct |
| ext600:codex_gpt_5_4_raw:Q74 | 0.318772 | correct |
| pilot288/flash/SQL-L1/Q74/r1 | 0.311670 | wrong |
| t13/SQL-R/Q34/r1 | 0.308864 | correct |

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
| t13/SQL-L1.5W/Q119/r1 | correct | wrong | 旧评分器错误接受名次：参考全部为单元素排名块，三种允许写法均应精确相等；仅移除名次要求即匹配成功（第五节第 9 条、12.12） |
| t13/SQL-L1.5W/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q75/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1.5W/Q98/r3 | correct | wrong | 旧评分器把选择身份的 NULL 当作任意标签：候选缺少 NULL 身份且多出非空身份；仅恢复该身份后原规则判对（第五节第 7 条、12.15；空标签例外不适用身份） |
| t13/SQL-L1/Q08/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q08/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q119/r1 | correct | wrong | 旧评分器错误接受名次：参考全部为单元素排名块，三种允许写法均应精确相等；仅移除名次要求即匹配成功（第五节第 9 条、12.12） |
| t13/SQL-L1/Q119/r3 | correct | wrong | 旧评分器错误接受名次：参考全部为单元素排名块，三种允许写法均应精确相等；仅移除名次要求即匹配成功（第五节第 9 条、12.12） |
| t13/SQL-L1/Q35/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q35/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1/Q35/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q08/r1 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q08/r2 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q08/r3 | wrong | correct | 旧评分器未覆盖参考拆列、候选合列方向；v2 依第三节第 7 条合并相邻必答字符串列，整表匹配成功 |
| t13/SQL-L1c/Q119/r1 | correct | wrong | 旧评分器错误接受名次：参考全部为单元素排名块，三种允许写法均应精确相等；仅移除名次要求即匹配成功（第五节第 9 条、12.12） |
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
| t13/SQL-R/Q119/r1 | correct | wrong | 旧评分器错误接受名次：参考全部为单元素排名块，三种允许写法均应精确相等；仅移除名次要求即匹配成功（第五节第 9 条、12.12） |
| t13/SQL-R/Q119/r2 | correct | wrong | 旧评分器错误接受名次：参考全部为单元素排名块，三种允许写法均应精确相等；仅移除名次要求即匹配成功（第五节第 9 条、12.12） |
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
| t13/SQL-L0/Q117/r2 | wrong | 0.003321 |
| t13/SQL-L0/Q74/r2 | wrong | 0.296498 |
| t13/SQL-L0/Q111/r1 | wrong | 0.045765 |
| t13/SQL-L0/Q111/r2 | wrong | 0.050800 |
| t13/SQL-L1.5W/Q79/r3 | wrong | 0.000727 |
| t13/SQL-L1/Q79/r2 | wrong | 0.000818 |
| t13/SQL-R/Q74/r2 | correct | 0.202142 |
| t13/SQL-R/Q74/r1 | correct | 0.196406 |
| t13/SQL-R/Q79/r1 | wrong | 0.000700 |
| t13/SQL-R/Q79/r2 | wrong | 0.000982 |
| t13/SQL-R/Q79/r3 | wrong | 0.000891 |
| ext600:codex_gpt_5_4_raw:Q74 | correct | 0.318772 |

## 输入不合法

| case_id | 错误 |
|---|---|

## 验证与复现

- 当前真实语料共 3,645 条；三份输入 SHA256 均与用户通知一致，bank 全为 `eval-v1.2@90e13b3`。不读取旧版 `*.eval-v1.1.jsonl`。
- 53 处翻转逐条归因完成：46 处人名拆合、6 处单元素块名次错误、1 处 NULL 选择身份被当作标签；均归为旧评分器错误，无待归因条目。逐条记录带输入行 SHA256。
- 6 处名次反事实核验：保留其他约束、仅移除名次要求，均为 correct；所有参考排名块 size=1 且 rank=dense，所以三种允许写法均须精确相等。
- 1 处身份反事实核验：保留原规则，仅将候选多出的非空身份恢复为缺失的 NULL 身份，即为 correct。反事实不改变正式判定。
- 12 条旧评分器超过 10 秒，未获得其判定，不能声称这些条目已完成新旧判定比较；均单列且不计翻转。v2 全部完成。
- 测试：作者测试 173 项、旧评分器相关回归 185 项、共用用例及压力测试 201 项，合计 559 项通过。旧版回归产生 109 条兼容 warning。
- 当前压力复跑：20 万行单值错误 16.28 秒、全值错误 12.65 秒；5 万行单值错误 3.24 秒、全值错误 2.58 秒。二百万行正确 / 错误的整项耗时（含构造）6.25 / 23.36 秒，内部判分均通过 30 秒上限断言。
- 193 条共用用例零分歧，1 条刻意触发 mapping_cap 的合成用例单列；真实语料 unscored 为 0。
- 本轮未改 `harness/scorer_v2.py`，评分器 SHA256：`d2e85ef14d4d5e9c3f153794c08941e32f907cd49ed194c2721297885e25a305`。旧评分器和 prompt 与 main 无差异。
- T05b 在 eval-v1.2 真实语料上的独立实现对账仍由 T05b / 协调会话执行；本报告不替代该跨实现验收，不打 tag、不启动正式重评。

```sh
UV_CACHE_DIR="$TMPDIR/t02-uv-cache" uv run --no-sync python -m pytest \
  tests/test_scorer_v2.py tests/test_scorer_v2_shared.py \
  tests/test_scorer_v2_performance.py tests/test_scorer.py \
  tests/test_scorer_presentation.py tests/test_selection.py --durations=12

UV_CACHE_DIR="$TMPDIR/t02-uv-cache" uv run --no-sync python scripts/validate_scorer_v2.py \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/t13.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/pilot288.jsonl" \
  --corpus "$SEMDEBT_DATA_DIR/scorer-corpus/ext600.jsonl" --old-timeout 10
```

## 历史清理与隐私审计

用户授权仅重写 `T02-scorer-v2`，已用固定旧远端提交的 `--force-with-lease` 清理草稿历史；其他分支、tag 与 stash 未改。审计范围是 `origin/main..HEAD` 的全部独有提交，而非仅最新提交：逐提交检查本分支新增 / 修改的 reports 和 JSONL，保留标识、状态、原因码、耗时、计数和哈希，无查询、题目原文或模型原始作答。执行错误只保留 execution_failed 和 SHA256；输入错误只保留异常类型和 SHA256。

main 继承的报告及运行日志有既存查询内容，本分支保持其字节不变；不能把本次审计表述为整个主仓库历史均无查询。分支清理移除了旧提交的可达路径，不代表托管端已清除旧对象或缓存。
