# T22b L1+ 与 L3a：渲染、运行、报告、残余歧义归因

- 状态：进行中（渲染阶段完成，运行待检查点与预算裁决）
- 负责：Codex（2026-10-25 用户：不敏感的活交给 Codex，协调会话只做验收）
- 模式：codex-main
- 依据：`decisions/2026-10-23-l1plus-l3a.md`；`decisions/2026-10-25-no-full-rerun-l1plus-last.md`
- 依赖：T22 第 1–3 步（#164 已合并）；`semantic-v1.4`；`harness-v1.1`；`eval-v1.2`
- 预算：两个单元合计 ≤ 10 元（Flash）；归因 ≤ 3 元（Flash）。先 dry-run、用户批准、错峰

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
