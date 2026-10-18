# 必答列标注比对摘要（T05b vs Codex）

- T05b：`handoff-claude/T05b-required-columns.v4.json`，sha256 `694a21905c49`，题库 `56ade6c`
- Codex：`handoff-codex/required-columns.json`，sha256 `58fbfc02b6a7`
- 两份都基于题库 main `455e96f`（#18 合并后；T05b 记的 `56ade6c` 与之同树）
- 只做机械比对，不评判谁对；只含题号、列号和计数。带题面、表头和前 3 行的版本在 `$SEMDEBT_DATA_DIR/handoff-compare/required-columns-compare.md`（不入库）
- 复现：`uv run python scripts/compare_required_columns.py --t05b … --codex …`

## 计数

| 项 | 数 |
|---|---:|
| 参考 | 136 |
| judge（两边都不标） | 22 |
| 标注（两边集合相同） | 114 |
| required 一致 | 109 |
| required 分歧 | 5 |
| missing_asked 一致 | 114（两边都没有缺列） |

## 分歧类型

| 类型 | 份数 | 参考 |
|---|---:|---|
| 百分比与金额是否同为必答（T05b 标 alt_measure） | 2 | Q50-1、Q99-1 |
| T05b 必答、Codex 非必答（T05b 无角色） | 1 | Q65-2 |
| 一方把排序依据列（含名次列）标成必答 | 1 | Q78-1 |
| 一方把 T05b 判为「题目没问的量」的列标成必答 | 1 | Q83-1 |

## 分歧逐份（列号从 0 开始）

| 参考 | T05b 必答 | Codex 必答 | 分歧列 | Codex 边界 |
|---|---|---|---|---|
| Q50-1 | [3] | [2, 3] | [2] | 是 |
| Q65-2 | [0, 1] | [0] | [1] | 是 |
| Q78-1 | [0, 3] | [0, 2, 3] | [2] | 是 |
| Q83-1 | [1, 2] | [0, 1, 2] | [0] | 否 |
| Q99-1 | [0, 4] | [0, 3, 4] | [3] | 是 |

## 边界标记

- Codex 标「边界」：13 份；T05b 没有边界标记字段（v4 只有备注），**两边都标边界：0 份**
- Codex 边界且分歧：4 份（Q50-1、Q65-2、Q78-1、Q99-1）
- Codex 边界但一致：9 份（Q22-1、Q38-2、Q67-1、Q69-1、Q85-1、Q92-1、Q98-1、Q98-2、Q100-1）——请用户过一眼
- 分歧但 Codex 未标边界：1 份（Q83-1）
