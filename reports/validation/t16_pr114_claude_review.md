# PR #114：Claude Code 复审交接

状态：待 Claude Code 复审；未执行 Claude 或其他模型调用，未自动合并 PR。

PR：https://github.com/lalalagugugu/semantic-debt/pull/114 。最新 main `0e5f9bb` 已以 merge 合入，提交 `4659cf1`（解决冲突）、`f0c7531`（#143 补充裁决）。

请 Claude Code 重点检查：

1. `harness/run_direct.py` 冲突处理是否同时保留 main 的 `per_cell[cell.name]` 选题、judge 跳过、阶梯单元与 v2 重评，以及 T16 逐次请求边界和指纹停止行为。
2. `runs/INDEX.md` 是否保留双方全部记录。原冒烟两份日志 SHA256 不变；完整行集仍在外部数据目录。
3. 按 #142/#143 与用户可见成员裁决复核静态覆盖、10 个隐藏辅助度量、四项参考读法对齐。v1.4 未交付时，不能把占位范围能力当作已绑定成员；开跑前还要固定最终静态表提交。
4. 核对通用时间探针的正负条件，尤其公共日历路径依赖既有连接、整月目标不等于自动摊分、JSON 返回列序按成员名匹配。
5. Q17 为当前不可见基数的 d，Q69 为模型未遵循展示约定；两题的比例数值均正确、正式分数不改。四条最终 SQL 错误依 #143 归引擎生成 SQL 缺陷；不能沿用旧报告的 0/4。

验证证据：

- `t16_l2_merge_integrity.json`：`harness/prompt.py`、`scorer.py`、`scorer_v2.py`、`score_guard.py` 与 main `0e5f9bb` 逐字节相同，保存 SHA256；semantic/、render/ 与 semantic-v1.3 无差异。
- 定向 harness 检查 19 项、既有冻结字节测试 6 项通过。
- 12 个通用 Cube 探针：8 个成功结果与独立物理事实查询一致，4 个预期连接失败。
- 原模型执行文件哈希逐项核对，数值检查不调用评分器；不进行全量估算或模型调用。

本 PR 的 harness 改动目的：

| 文件 | 目的 |
|---|---|
| harness/cells.py | 接入本机 Cube SQL/JSON 单元与各自上下文 |
| harness/client.py | 可选 before_request 回调覆盖实际请求及传输重试的调用边界 |
| harness/run_direct.py | Cube 执行器接线、原始行集存档、指纹/错峰停止规则和显式高峰放行；合并保留 main 新选题逻辑 |
| harness/rescore.py | 从原始执行列类型恢复 Cube number 的 Decimal 字符串，保留真实字符串与 NULL；评分规则不改 |
| tests/test_harness.py | 验证接线、调用闸、指纹、冻结字节和数值还原 |

本轮新增审查脚本仅调用本地 Cube/ClickHouse 或读取冻结材料，要求环境中移除 DEEPSEEK_API_KEY。没有引入依赖、改动提示或评分器。既有不正确的历史分类保留在历史报告；当前结论统一以 `t16_l2_scope_review.md` 为准。
