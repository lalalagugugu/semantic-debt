# T22b L1+ 与 L3a：渲染、运行、报告、残余歧义归因

- 状态：未开始
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
