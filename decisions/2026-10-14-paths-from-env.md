# 2026-10-14 路径以环境变量为准

## 背景

设计文档和 `START-HERE.md` 写的目录布局是 `~/semdebt/{semantic-debt,semantic-debt-eval,cards,data}`，但本机实际装在 `~/dev/semdebt/` 下。T00 发现后记入 `decisions/open-questions.md` 第 1 条并停下问用户。

## 裁决

用户 2026-10-14 裁决：**改成以环境变量为准。**

## 改了什么

- `AGENTS.md`「环境」：删掉「目录布局固定」那句，改成一张环境变量表（含含义与本机值），并写明「文档里出现的 `~/semdebt/...` 只是默认示例，不是约定」。开工自检第 4、5 条里的硬路径换成 `$SEMDEBT_MAIN_DIR`、`$SEMDEBT_EVAL_DIR`、`$SEMDEBT_CARDS_DIR`。
- `START-HERE.md`：开头加「关于路径」一段；第 1–4 节的命令改用 `$SEMDEBT_BASE`（搬家只改这一行），并标注第 1–4 节已于 2026-10-14 做完；第 5–7 节的命令改用环境变量。
- `tasks/BOARD.md`：T01a 的「模式」列由「两个仓库的上一级 `~/semdebt`」改为「两个仓库的上一级」。
- `tasks/T14-tuning.md`：调优包示例路径改为 `$SEMDEBT_CARDS_DIR/...`。

## 新增的两个可选变量

`scripts/start-card.sh` 需要两个在原设计里没有名字的目录，都给了默认值，**不设也能用**：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `SEMDEBT_CARDS_DIR` | `$SEMDEBT_MAIN_DIR` 的同级 `cards/` | 每张卡的独立 clone 放在哪 |
| `SEMDEBT_VENDOR_DIR` | `$SEMDEBT_MAIN_DIR` 的同级 `_vendor/` | 外部基准克隆到哪（只有 T01a 用） |

## 没改什么，以及为什么

- `docs/design-v5-public.md`：按 `AGENTS.md`「工作方式」——设计改动不改 `docs/`，只记在 `decisions/`。该文件里的 `~/semdebt/` 目录树和启动命令保留 v5 原文，读的时候以本文件和 `AGENTS.md` 为准。
- `decisions/2026-10-14-revisions.md`：历史记录，不回改。
- `tasks/T00-bootstrap.md` 的「交付物」原文：那是下发给 T00 的规格，保留原样；实际落地与偏离写在同一张卡的「记录」里。

## 约束没有放松

两个仓库仍必须是**同级目录**——T01a 要在它们的上一级同时往两个仓库提交。`scripts/start-card.sh` 的 `codex-root` 模式会检查这一点，不同级时改用绝对路径并提示。
