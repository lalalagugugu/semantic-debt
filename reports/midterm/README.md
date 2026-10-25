# T24 中期报告补数

本包使用本卡开工时已有的定稿日志，预算0元。主表98题，附表109题；不包含T12选模型或T21小样本。旧L1.5S、旧SQL-L2说明单列，主表分别使用semantic-v1.4和新说明。C13第4级仅留出题，实际为主表子集49题、含低区分度55题。

| 任务 | 产出 |
|---|---|
| 1 稳定性 | [stability.md](stability.md)：三次全对、全错、时对时错；正式14个单元及2个旧版对照 |
| 2 C4逐题比较 | [unstable-l1.md](unstable-l1.md)、review.json、raw-check.csv：20题、60次最终作答；120份原始文件哈希核对 |
| 3 C5自评把握 | [confidence.md](confidence.md)：A档按题型、稳定性、根因及三轴交叉，逐条列错答 |
| 4 C6探查 | [explorer.md](explorer.md)、tool-audit.csv：完整结果流向、互斥SQL形态用途代理；后者须结合分类限制阅读 |
| 5 C7敏感性 | [l1-l2.md](l1-l2.md)：四单元、固定19题集合、按题配对差及区间 |
| 6 token及费用 | [tokens-cost.md](tokens-cost.md)：命中/未命中/输出含思考，历史价格、全冷估算、异常替代作答费用 |
| 7 数据与质量 | [dataset-quality.md](dataset-quality.md)、quality-evidence.json：25表、244字段、34,326,191行及102条查询 |
| 8 名词与来源 | [glossary.md](glossary.md)、[numbers.md](numbers.md)、sources.json、attempts.csv |

已为T14两个调优单元和T22b的SQL-L1plus、SQL-L3a留位。完成后在analyze.py的SPECS追加核定来源，再运行相同脚本；未完成单元不计入现有表的数字。

复现（变量仅在调用环境中设置，使用用户确认的值）：

```sh
uv run python reports/midterm/quality.py
uv run python reports/midterm/analyze.py
```

先生成质量证据，再生成分析及数字索引。两条命令都不调用模型，不改写runs。analyze.py只从题库的eval-v1.2标签读取题型与排除标注；quality.py只读取本地Parquet，不打开共享chDB目录。原始响应、执行结果行及题目原文均未复制入本包。CSV只含题号、状态、汇总分类、来源位置或哈希。

关键读法：SQL-L1在主表有19/98题不稳定，含低区分度时为20/109；20题中7题涉及呈现或评分边界，不能全部当作理解摇摆。SQL-L2相对L1的主表差为−2.4点，排除19题后为−1.3点，区间均跨0。探查的净差不能代替流向分析，例如L2-E把14次最终执行失败中的5次变对、9次变成能执行的错答。

质量查询的首次执行在CloseDate类型比较处失败，修正探针后102条全部成功；过程见dataset-quality.md。层级环分别报告环节点和能进入环的受影响行，自指根另列。

状态：本卡产出已生成；协调会话尚需跨厂商独立重算第1、5、6项，并抽查第2、4项。尚未通过独立验收，不将内部断言通过写成验收通过。
