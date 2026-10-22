# T16 semantic-v1.3 冒烟 dry-run（2026-10-19）

本次模型调用为 0；不启动全量。main 基线 `d2801b1c4de5132910732db498aef7c5ed9a89b4`；rebase 后 harness 提交 `40e12ecf91394fde3a4f341629613f7b4addd88d`。

- eval-v1.2：`90e13b385a639a9164ac78430c50c11a7859f976`，从外部只读副本读取，通过 harness tag 内容校验。
- semantic-v1.3：`d2801b1c4de5132910732db498aef7c5ed9a89b4`，semantic/、render/ 及重建的两个上下文通过校验。
- 按用户传达的 PR #136 第一期开跑裁决排除 judge：题库 122 题中 judge 13 题；pilot 原 24 题，跳过 Q40，实际每单元 23 题 × 1。裁决正文目前取自 origin/coord-replan-1019，尚未进入该 main。
- 模型 deepseek-flash；预期指纹 `e72d3c7f663d3e1383b00b3884cb4501`；任何不一致停止。
- 实际运行限北京时间 18:00 后，一个单元完成后再跑另一个，保留全部原始执行行集。

| 修正率情景 | 单元 | 作答 | 调用 | 错峰预计费用（元） | 用量来源 |
|---|---|---:|---:|---:|---|
| 10.0% | SQL-L2 | 23 | 25 | 0.389358 | measured |
| 10.0% | JSON-L2 | 23 | 25 | 0.372535 | estimated |
| 10.0% | 合计 | 46 | 50 | 0.761892 | |
| 45.8% | SQL-L2 | 23 | 34 | 0.529526 | measured |
| 45.8% | JSON-L2 | 23 | 34 | 0.506647 | estimated |
| 45.8% | 合计 | 46 | 68 | 1.036173 | |
| 100.0% | SQL-L2 | 23 | 46 | 0.716418 | measured |
| 100.0% | JSON-L2 | 23 | 46 | 0.685464 | estimated |
| 100.0% | 合计 | 46 | 92 | 1.401882 | |

默认修正率 10%；SQL 使用旧语义说明冒烟的平均 token 与命中率，JSON 使用当前说明长度和默认输出 3000 token、命中率 95%；均非费用保证。45.8% 情景取旧 SQL 冒烟 11/24；100% 为每题均修正一次的调用上界，token 长度仍为估计。

## 冻结文件逐字节核验

- `harness/prompt.py` 与 main 逐字节相同；SHA256 `86fefce2157ff4fc09819fe8c8c5ad4fe7e6e064850f9ce9c8b1b67e97919e5e`。
- `harness/scorer.py` 与 main 逐字节相同；SHA256 `3be6d29f5a11fafa5843c086362b6ddcfd3b2391413e82e3a98c09f09de50efd`。
- `harness/scorer_v2.py` 与 main 逐字节相同；SHA256 `a012aba545e8df760e967828a1df1ca0a1db993fc3d309ece24a70bc4ce207d4`。

`uv run --offline pytest tests/test_harness.py tests/test_cube_executors.py -q` 退出码 0（无外部数据环境，数据依赖测试按现有条件跳过）；`git diff --check` 通过。

## 复现命令

先设置 SEMDEBT_EVAL_DIR 指向已核验的 eval-v1.2 只读副本，SEMDEBT_DATA_DIR 指向外部数据目录。每单元分别执行：

```sh
uv run python -m harness.run_direct --cell SQL-L2 --pilot --questions Q08,Q100,Q102,Q117,Q15,Q17,Q28,Q34,Q49,Q50,Q51,Q66,Q68,Q69,Q70,Q71,Q73,Q74,Q75,Q76,Q80,Q81,Q82 --reps 1 --model deepseek-flash --eval-tag eval-v1.2 --semantic-tag semantic-v1.3 --expected-fingerprint e72d3c7f663d3e1383b00b3884cb4501 --budget 20 --dry-run
```

JSON-L2 将上述命令的 `--cell SQL-L2` 换成 `--cell JSON-L2`。实际运行另设新的 run-id、去掉 --dry-run，记录最终本地提交号。

冒烟通过后才估全量：排除 13 道 judge 后每单元 109 题 × 3 次；SQL-L2 v1.3、SQL-L2 v1.2、JSON-L2 共三组。旧说明必须使用 semantic-v1.2 的隔离内容并经过 tag 校验，不能在 v1.3 上临时替换说明绕过检查。全量费用待冒烟实测后 dry-run，等用户批准，20 元上限。
