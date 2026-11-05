# T34：本机 Claude Code 独立复核清单

仅本清单及 JSON 清单入库。题面、参考、作答和实际上下文只在本机私有目录。

- 目录：`$SEMDEBT_DATA_DIR/t34-run-20261104/claude-review/`
- 版本：`non-v2-v2`；按主表做法排除 v2 直接判对项，仅复核 R1–R11 放行和 Codex 人工判对项。
- 条目：**174 = 109 + 65**，匿名编号 `T34V2R0001`–`T34V2R0174`。
- 原 1,013 条全量包归档于 `$SEMDEBT_DATA_DIR/t34-run-20261104/claude-review-all-positive-v1/`，不再使用旧 T34R 编号；旧结果不得套到新版编号上。
- 本机普通模式 Claude Code 先读包内 `REVIEW.md`，核对下面 SHA-256，再全量复核完整结果。不使用 T34 盲模式会话，不经云端协调会话转交；不得读包外的 Codex 理由、身份映射或标签。
- 复核文档、题面、最终查询/响应、完整执行结果与允许参考之间的内容一致性；沿用主表 D1 原则，不改变规则。实际系统消息仅按哈希命名，为原则 C 所需。

## 判对来源及范围

| 单元 | v2 直接判对（不复核） | R1–R11 放行（复核） | Codex 人工判对（复核） | 判对合计 |
|---|---:|---:|---:|---:|
| SQL-L1 | 192 | 25 | 17 | 234 |
| SQL-L1-onto | 193 | 23 | 19 | 235 |
| SQL-L1plus | 226 | 31 | 12 | 269 |
| SQL-L3a-full | 228 | 30 | 17 | 275 |
| 合计 | 839 | 109 | 65 | 1013 |

三类互斥；v2 直接判对的 839 条未进行跨厂商复核，不能计为独立复核通过。

## 写回格式

写入当前包目录 `results.json`，JSON 数组，恰好每个新版匿名编号一条：

```json
[{"anonymous_id": "T34V2R0001", "correct": true, "note": "独立核对证据"}]
```

`correct` 必须为布尔值。每个不通过项或文档/参考冲突在 `note` 中说明；私有说明不入仓库。输入文件不改。Codex 回收后逐条处理分歧并更新报告；未回收不代表无分歧。

## 文件

| 文件 | SHA-256 | 条目数 | 匿名编号范围 |
|---|---|---:|---|
| `REVIEW.md` | `e9fca2ef5c3977569279ebee42e88a124891f7599bdfcb3bcd06c01fa7b45195` | 0 | 说明 |
| `cases-001.json` | `2c22363b9a93e314997278211c3a1b4f8d796a1f19ea357ee3de3830a1109fbf` | 40 | T34V2R0001–T34V2R0040 |
| `cases-002.json` | `299a15b14dfc27f84c3b9c310d61c4e38be5d3235fadb7cfde0f21ec09d5acb0` | 40 | T34V2R0041–T34V2R0080 |
| `cases-003.json` | `8cba973901c1527902ee31a32a1ca6e7235e1227f7fb114e66d766b97d288c35` | 40 | T34V2R0081–T34V2R0120 |
| `cases-004.json` | `e1341dee19f96969ff067c0a19d7c10eabe43ed503f30ff7fe0cfcf040d54155` | 40 | T34V2R0121–T34V2R0160 |
| `cases-005.json` | `2e0cafd43fce724bd36031634c6f296bdb91951a17668b9b8f5e593e147c756e` | 14 | T34V2R0161–T34V2R0174 |
| `context-33f01624084b19c4941dd0a0ece60bb149ecbeaaadc47202e92941879e7a74eb.txt` | `33f01624084b19c4941dd0a0ece60bb149ecbeaaadc47202e92941879e7a74eb` | 1 | 共享上下文 |
| `context-6a5ab637b0f598f2d56de068d25756894caba33fe7d1d973f29b0fa489edfe61.txt` | `6a5ab637b0f598f2d56de068d25756894caba33fe7d1d973f29b0fa489edfe61` | 1 | 共享上下文 |
| `context-8df43ae0552cab461d8bd490ff4e21114995681ff0ccd38cf85115f65e44f6a6.txt` | `8df43ae0552cab461d8bd490ff4e21114995681ff0ccd38cf85115f65e44f6a6` | 1 | 共享上下文 |
| `context-b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3.txt` | `b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3` | 1 | 共享上下文 |
