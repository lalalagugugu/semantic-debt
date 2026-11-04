# T34：本机 Claude Code 独立复核清单

仅本清单及 JSON 清单入库。题面、参考、作答和实际上下文只在本机私有目录。

- 目录：`$SEMDEBT_DATA_DIR/t34-run-20261104/claude-review/`
- 条目：1,013（全部主表判对作答，含自动规则项），匿名编号 `T34R0001`–`T34R1013`。
- 使用本机普通模式 Claude Code，不使用 T34 盲模式会话，不经云端协调会话转交。先读包内 `REVIEW.md`，核对下面 SHA-256，再逐条复核完整结果。不得读包外的 Codex 理由、原始身份映射或标签。
- 复核实际交付文档、题面、最终查询/响应、完整执行结果与允许参考之间的内容一致性；沿用主表 D1 原则，不改变规则。
- 上下文采用实际系统消息，按哈希命名；为原则 C 所需，不额外附单元名。

## 写回格式

写入同目录 `results.json`，JSON 数组，恰好每个匿名编号一条：

```json
[{"anonymous_id":"T34R0001","correct":true,"note":"独立核对证据"}]
```

`correct` 必须为布尔值。每个不通过项或文档/参考冲突在 `note` 中说明；这些私有说明也不得进仓库。输入文件不改。Codex 回收后逐条处理分歧并更新报告；结果未回收不代表无分歧。

## 文件

| 文件 | SHA-256 | 条目数 | 匿名编号范围 |
|---|---|---:|---|
| `REVIEW.md` | `b432307b5f93c91d2dbd1f010209b2c9f17096b86f6672405489b3f6c4d7141e` | 0 | 说明 |
| `cases-001.json` | `3fc3a63536b5000016b352f015db99fdb1cb4e35becda287f58c7eb9e1683bdf` | 40 | T34R0001–T34R0040 |
| `cases-002.json` | `d652e21aaa998b0c5524c876b5d33cad433ee19fd7ed87096795d10154bcad73` | 40 | T34R0041–T34R0080 |
| `cases-003.json` | `38ff39931bec8437e3b4b496ea68f30a33092695252abdb9b6242f7a4388cc74` | 40 | T34R0081–T34R0120 |
| `cases-004.json` | `647628275943614474805cf86db4b438bd0f5bbd6af0ba971b62122efecfbf4c` | 40 | T34R0121–T34R0160 |
| `cases-005.json` | `f2202ee95e332910a90ae9ce830d01b8caccee1244509224f9bd5ba8aca34cc9` | 40 | T34R0161–T34R0200 |
| `cases-006.json` | `6044eacfb711e2485c132273018ffbdfb334114b663f4c20f88668dea22f3110` | 40 | T34R0201–T34R0240 |
| `cases-007.json` | `a1c81bb29ea7cb4e35abef447296a69488be13875342779272cf62e31071ab4e` | 40 | T34R0241–T34R0280 |
| `cases-008.json` | `74cf391f87fb1d91a01d4206a8d824d42064cbcfbca2493700a9a466a09a5d23` | 40 | T34R0281–T34R0320 |
| `cases-009.json` | `8c00f328c08673d014ccd6fe9e46f49e0aafa7c1b2a4b1e0fa31fefc10f6b2ac` | 40 | T34R0321–T34R0360 |
| `cases-010.json` | `388da731fcab498d3f82f8565fdc24934b6d56fbdc01fcf75cd9ebfc25a5be5d` | 40 | T34R0361–T34R0400 |
| `cases-011.json` | `481be4e0eaa3b6ef0d14ef4e818487cca4734fa00a1c0bbd53d9c14ced6d5585` | 40 | T34R0401–T34R0440 |
| `cases-012.json` | `7577424fd5cac46f357e2807d0a17b58782bb1877145e38d5e1fa3ccc5de26f3` | 40 | T34R0441–T34R0480 |
| `cases-013.json` | `9e039c46648940798007c933e2fc2c323a72286bf71e5d04aacf5ed86c8efd02` | 40 | T34R0481–T34R0520 |
| `cases-014.json` | `c640e3055e93b84691614728a3d968c8445baa7a873d1f3cf9a782bd635bffb8` | 40 | T34R0521–T34R0560 |
| `cases-015.json` | `40d0f9182043c4200ddfc6132f28de9325b1f72b1ce9b67d5412f9aac821424c` | 40 | T34R0561–T34R0600 |
| `cases-016.json` | `77557dc331b96ada0a90305d5997b1f084102c34735e430671810da50a48be87` | 40 | T34R0601–T34R0640 |
| `cases-017.json` | `0bf7977cc890cbdbec6dd2d6fd6ee4ef1aaccec5fdf925beca068a375e6cd265` | 40 | T34R0641–T34R0680 |
| `cases-018.json` | `084de555a873c1b6321383ff9d2ff8379b007b28330e9105ea20f26dc3d73e10` | 40 | T34R0681–T34R0720 |
| `cases-019.json` | `8f0fce747aeaf2db8591f5b961fc0a268041664a11e7f2917a7c82ccb8eaeee8` | 40 | T34R0721–T34R0760 |
| `cases-020.json` | `9ca6d81aa4bae166e9d97c3acbe8873c79750ace605c33ce25d357fa755d6220` | 40 | T34R0761–T34R0800 |
| `cases-021.json` | `ff7ed555497c5927a05ef85c45d91c6efae6323acc22ad6e0c8b571e958c5482` | 40 | T34R0801–T34R0840 |
| `cases-022.json` | `8b1aaec4780e8bf9a266594816fa52e693b7c419fbdbd9f2db84c4f28aea0f97` | 40 | T34R0841–T34R0880 |
| `cases-023.json` | `aecdef9e2817a881abf191698f7e89bea08ca0f8f2c65b8ca8b4041a6496e9e3` | 40 | T34R0881–T34R0920 |
| `cases-024.json` | `f3f7a4187b116f79420b706fc24db1d0f42f1015cf70d8271df8d07fc49e3545` | 40 | T34R0921–T34R0960 |
| `cases-025.json` | `65ae4d714f3e12005fae8a212fc68f3c00f8e84746eec8bbf499143b4a216351` | 40 | T34R0961–T34R1000 |
| `cases-026.json` | `c13dde35785062e6dddcfba8f4a1035cbe9bfa1af1a8ffda6eeb86b45ca6e2a0` | 13 | T34R1001–T34R1013 |
| `context-33f01624084b19c4941dd0a0ece60bb149ecbeaaadc47202e92941879e7a74eb.txt` | `33f01624084b19c4941dd0a0ece60bb149ecbeaaadc47202e92941879e7a74eb` | 1 | 共享上下文 |
| `context-6a5ab637b0f598f2d56de068d25756894caba33fe7d1d973f29b0fa489edfe61.txt` | `6a5ab637b0f598f2d56de068d25756894caba33fe7d1d973f29b0fa489edfe61` | 1 | 共享上下文 |
| `context-8df43ae0552cab461d8bd490ff4e21114995681ff0ccd38cf85115f65e44f6a6.txt` | `8df43ae0552cab461d8bd490ff4e21114995681ff0ccd38cf85115f65e44f6a6` | 1 | 共享上下文 |
| `context-b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3.txt` | `b80107d469e5600f1c7f3150afef18d11734452a25cc9340f1df46bc470073a3` | 1 | 共享上下文 |
