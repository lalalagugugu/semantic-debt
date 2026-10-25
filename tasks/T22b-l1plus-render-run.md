# T22b L1+ 与 L3a：渲染、运行、报告、残余歧义归因

- 状态：进行中（首跑因监督脚本多进程入口异常停止，待用户确认新 run-id 重跑）
- 负责：Codex（2026-10-25 用户：不敏感的活交给 Codex，协调会话只做验收）
- 模式：codex-main
- 依据：`decisions/2026-10-23-l1plus-l3a.md`；`decisions/2026-10-25-no-full-rerun-l1plus-last.md`
- 依赖：T22 第 1–3 步（#164 已合并）；`semantic-v1.4`；`harness-v1.1`；`eval-v1.2`
- 预算：两个单元合计 ≤ 15 元（Flash，2026-10-25 用户批准上调）；归因 ≤ 3 元（Flash）。先 dry-run、用户批准、错峰

## 要做的事

1. **渲染**：`SQL-L1plus` = L1 上下文 + `semantic/l1plus.yaml`（去掉 `rev` 字段；`clarifications`、`concepts`、`aliases`、`hierarchies`、`general_rules` 全部进上下文）；`SQL-L3a` = 同一份内容生成的 Turtle（OWL 类、对象属性、数据属性、实例别名；SHACL 约束与规则）放在 L1 上下文之后。系统提示与写法说明与 SQL-L1 逐字节相同，只差语义上下文。
2. **核对**：脚本逐条核对 L1+ 与 L3a 一一对应（每个条目编号在两边都出现、数量相同），结果写进 `reports/validation/l1plus-l3a-correspondence.md`；已有单元的上下文逐文件不变（测试）。
3. **不改内容**：`l1plus.yaml` 与 `l1plus-audit.md` 一个字都不改。发现内容问题，写进 `decisions/open-questions.md`，停下来问用户。
4. **tag**：渲染与核对完成、PR 合并后，由用户打 `semantic-v1.6-l1plus`（不是 v1.5，v1.5 留给 DAX）。
5. **运行**：dry-run 报调用次数与费用 → 用户批准 → 错峰，各 109 题（跳过 judge）× 3 次，`--semantic-tag semantic-v1.6-l1plus`。日志、`runs/INDEX.md` 照硬规则 7。
6. **报告** `reports/results/l1plus-l3a.md`：主表 98 题，另列 109 题；L1+ vs L1、L3a vs L1+ 的同题配对差与区间（方法同 `reports/results/sql_direct.md`）；另报「含 / 不含 14 个歧义口径涉及的 19 题」两种算法；三次全对 / 全错 / 时对时错的题数。
7. **残余歧义归因**：对 SQL-L1plus 的错答，用 T19b 的方法（`tasks/T19b-l1-error-attribution.md`，Flash 初判 + Codex 复核）归因，单独报「文字仍有两种以上读法」一类占多少，并列出这些条目（只写题号与类别）。
8. **披露**写进报告开头：L1+ 的默认读法对照参考答案定，代表「一轮系统性歧义审查、业务方逐条拍板」的乐观估计，不是上限。

## 验收（协调会话）

协调会话从原始日志独立重算第 6 步的主表数字，并抽查第 2 步的核对脚本。

## 2026-10-25 渲染阶段产出

- 状态：第 1–2 步完成，第 3 步源文件保持原样；第 4 步等待 PR 合并与用户打 tag；第 5–8 步尚未执行，未调用付费模型。
- 产出：`render/l1plus.py` 从同一份 YAML 生成叠加内容、OWL / SHACL Turtle，并解析实际上下文逐字段核对；`reports/validation/l1plus-l3a-correspondence.md` 共 109 条，形式化 30 条、注解保留 79 条。形式化条目的复杂部分仍完整保留为注解。
- 用户裁决：`decisions/2026-10-25-t22b-l3a-presentation.md`。L3a 只测形式化写法对模型写 SQL 的帮助，不含可执行规则；可执行形式化留第二期 L3b。
- 接线：`harness/cells.py` 注册显式指定的两个单元，`harness/run_direct.py` 识别它们；不扩大既有 `--cell all` 集合。系统提示与 SQL 写法说明沿用 SQL-L1。
- 验证：已有各单元逐字节对比开工基线 `d236e13b719db6fe0c29e5a88af6c127929ac12f`；两个受保护源文件与该基线无差异。核对器测试覆盖缺条目、改 SQL、改类别、丢子类关系、丢 shape 与多余条目。
- 测试：上述三个文件最终合计 **157 passed, 1 skipped**；跳过的是题库当前检出不是 `eval-v1.2` 时的全题库规则校验（tag 本身存在）；未切换共享题库。渲染、核对命令成功，`git diff --check` 通过。
- 偏离与理由：仅完成合并前阶段，遵守第 4–5 步的检查点；未提前生成结果或归因结论。
- 工时：约 0.4 小时（本会话渲染、接线、核对与测试；不含等待审定和后续运行）。

复现渲染与核对：

```sh
uv run python render/context.py
uv run python -m render.l1plus
uv run pytest tests/test_l1plus_render.py tests/test_render.py tests/test_harness.py
```

### 预算预估（未冻结，不是正式 tag 校验 dry-run）

复用 harness 的 `dry_run`，采用卡上每单元 109 题、3 次，默认修正率 10%、输出 3000 token、缓存命中 95%、题面 60 token、不读既有实测。估计：SQL-L1plus 5.98 元，SQL-L3a 8.21 元，合计 **14.19 元**；654 次作答，预计含修正 720 次调用。此估算未验证待打的 tag，不可作为已批准运行的证据。归因预算仍为 3 元。

tag 就绪后的正式 dry-run（仍不调用模型）：

```sh
uv run python -m harness.run_direct --cell SQL-L1plus --cell SQL-L3a --skip-judge --reps 3 --model deepseek-flash --semantic-tag semantic-v1.6-l1plus --eval-tag eval-v1.2 --budget 10 --dry-run
```

### 用户确认

- [ ] 审查并合并渲染 PR，由用户打 `semantic-v1.6-l1plus`。
- [ ] 正式 dry-run 后裁决运行预算（当前初估 14.19 元 > 10 元），明确批准后才开始付费运行。

## 2026-10-25 正式运行中止记录

- 用户已批准：运行预算上调至 15 元，归因另限 3 元；正式 dry-run 通过后明确批准开跑，超预算或异常即停。
- 前置完成：#167、#166 已合并；`semantic-v1.6-l1plus` 指向 `866004b`；本分支快进合入最新 main `34a75dd`。题库使用 `$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2`，未切换共享题库。
- 正式 dry-run：两单元各 109 × 3，合计 654 次作答，预计含修正 720 次调用，5.98 + 8.21 = 14.19 元；`--semantic-tag semantic-v1.6-l1plus --budget 15` 通过预算与版本校验。
- 首跑：`20261025-T22b-l1plus-l3a-01`，周日错峰，并发 4；预期指纹 `e72d3c7f663d3e1383b00b3884cb4501`。原始响应、执行结果、监督费用记录均保存在该 run-id 的外部原始目录。
- 异常：临时监督脚本缺少 `if __name__ == '__main__'` 入口保护，Mac 的 spawn 评分子进程重新执行启动断言，触发 run-id 已使用；Q01 r1 记录为 `harness_error`，随即停止，没有进入后续题目或 SQL-L3a。此错误由 Codex 新增的监督脚本造成，不是模型或冻结评分器问题。
- 实花：**0.03272164 元，2 次 API 调用**（首答 + 冻结规则允许的一次 SQL 修正）；指纹与预期一致。完成判分的作答为 0，不能据此报告主表或 109 题准确率、三次稳定性。日志的 harness_error 行没有 cost 字段，实际费用从原始响应 usage 与 `supervision.jsonl` 两份证据核算，不用摘要里的 0 元替代实花。
- 修复准备：已补入口保护，离线验证实际 spawn 评分与预算停止成功；保存为原始目录内新的 `supervisor-fixed.py`，保留出错版本 `supervisor.py`，不覆盖。未再次付费调用。
- 用户确认：是否允许用新 run-id 重跑；累计运行预算仍限 15 元，已用费用需计入（余额 14.96727836 元）。归因预算 3 元未使用。
