# 2026-10-14 外部基准的许可怎么保留

## 背景

T01a（Codex）开工自检时停下报了两件事：

1. 外部基准 `cubedevinc/semantic-layer-benchmark` 在提交 `4c37310f9fae65255f6d0015475b430ceea3ab1f` **没有 LICENSE 文件**，README 里只注明「MIT」。而卡片要求两个仓库都保留 LICENSE——没有东西可复制。
2. 卡片要求主仓库的 PR 只改三个 vendor 文件，而 `AGENTS.md`「工作方式」要求每张卡更新 `tasks/BOARD.md`。两条打架。

**事实来源**：以上由 Codex 核实。Claude Code 没有也不会去看那个仓库——它含有基准的题目与语义文档，而 Claude Code 之后要盲写 T08–T10（硬规则 1）。本裁决在「Codex 所报事实为真」的前提下作出；事实若有出入，由 Codex 在 T01a 的记录里更正。

## 裁决（用户，2026-10-14）

### 一、不补写 MIT 全文，不代上游署名

MIT 的核心义务是**保留上游的版权声明**。上游没有给出版权声明，也就没有可保留之物。自己造一行 `Copyright (c) ... ` 等于替上游署名：署错是硬伤，署对也是我们编的；G4 之后这套东西要公开，这笔账会留痕。

做法：两个仓库各放一份 `vendor/cube/NOTICE.md`，记录

- 来源 URL、提交号 `4c37310f9fae65255f6d0015475b430ceea3ab1f`、取得日期；
- 本目录保留了哪些上游文件；
- README 中关于许可的**原话逐字照抄**（不改写、不翻译）；
- 一句话说明：上游在该提交没有 LICENSE 文件，故本仓库不附 MIT 全文、不代为署名著作权人；若上游日后补上 LICENSE，按其内容更新本文件并补齐保留义务。

可选、不阻塞：向上游开 issue 请其补 LICENSE。补上之后回来更新 NOTICE。

### 二、BOARD 可以进同一个 PR

「只改三个 vendor 文件」的用意是**别让主仓库的 PR 混进题库内容**，不是禁止记账。BOARD 的状态格不是题库内容，拆成第二个 PR 只会让 BOARD 与实际进度漂移。

主仓库这个 PR 的范围定死为：3 个 vendor 文件 + `vendor/cube/NOTICE.md` + `tasks/BOARD.md` 里 **T01a 那一行的状态格**。BOARD 的其余行不动。

## 影响

- T01a 的交付物多一份 `vendor/cube/NOTICE.md`（两个仓库各一）。
- 卡片原文的「保留 LICENSE」与「只改三个文件」两条以本文件为准。
- T01 不受影响：它只用 `vendor/cube/retail_schema.sql`。
