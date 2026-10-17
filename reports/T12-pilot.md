# T12 试跑结果（自动生成）

- 题库：`eval-v1` = `07dca9af414295205b0ae5f4a220bda44682af71`；试跑 24 题；低区分度 ['Q17', 'Q68', 'Q76']；judge 题（行集待离线评分、不进准确率分母）['Q40']
- 运行：deepseek-flash → `runs/20261018-T12-pilot-flash-01/`；deepseek-v4-pro → `runs/20261018-T12-pilot-pro-01/`

## 准确率（correct / 可评作答）

| 模型 | 单元 | 含低区分度 | 不含低区分度（选模型用） | 首答即对（不含低区分度） |
|---|---|---|---|---|
| deepseek-flash | SQL-R | 16/69 = 23.2% | 16/60 = 26.7% | 15/60 = 25.0% |
| deepseek-flash | SQL-L1 | 34/72 = 47.2% | 30/63 = 47.6% | 24/63 = 38.1% |
| deepseek-v4-pro | SQL-R | 10/69 = 14.5% | 7/60 = 11.7% | 7/60 = 11.7% |
| deepseek-v4-pro | SQL-L1 | 25/71 = 35.2% | 20/62 = 32.3% | 18/62 = 29.0% |

## 按 Q 级（不含低区分度 / 含）

| 模型 | 单元 | Q1 | Q2 | Q3 |
|---|---|---|---|---|
| deepseek-flash | SQL-R | 9/18 = 50.0%（含 9/21 = 42.9%） | 4/21 = 19.0%（含 4/24 = 16.7%） | 3/21 = 14.3%（含 3/24 = 12.5%） |
| deepseek-flash | SQL-L1 | 13/21 = 61.9%（含 15/24 = 62.5%） | 10/21 = 47.6%（含 12/24 = 50.0%） | 7/21 = 33.3%（含 7/24 = 29.2%） |
| deepseek-v4-pro | SQL-R | 5/18 = 27.8%（含 8/21 = 38.1%） | 1/21 = 4.8%（含 1/24 = 4.2%） | 1/21 = 4.8%（含 1/24 = 4.2%） |
| deepseek-v4-pro | SQL-L1 | 15/20 = 75.0%（含 18/23 = 78.3%） | 5/21 = 23.8%（含 7/24 = 29.2%） | 0/21 = 0.0%（含 0/24 = 0.0%） |

## 四种结果占比（全部作答，含低区分度；pending = judge 题返回了行集）

| 模型 | 单元 | 作答 | correct | wrong | exec_error | refused | pending | 非 done 行 |
|---|---|---:|---|---|---|---|---|---|
| deepseek-flash | SQL-R | 72 | 16（22%） | 53（74%） | 0（0%） | 0（0%） | 3（4%） | 0 |
| deepseek-flash | SQL-L1 | 72 | 34（47%） | 32（44%） | 3（4%） | 3（4%） | 0（0%） | 0 |
| deepseek-v4-pro | SQL-R | 72 | 10（14%） | 59（82%） | 0（0%） | 0（0%） | 3（4%） | 0 |
| deepseek-v4-pro | SQL-L1 | 72 | 25（35%） | 42（58%） | 2（3%） | 2（3%） | 1（1%） | 0 |

### 最终执行错误的分类

| 模型 | 单元 | 分类 |
|---|---|---|
| deepseek-flash | SQL-R | 无；触发修一次 5 次，修后正确 1 次 |
| deepseek-flash | SQL-L1 | {'engine_error': 3}；触发修一次 14 次，修后正确 6 次 |
| deepseek-v4-pro | SQL-R | 无；触发修一次 1 次，修后正确 0 次 |
| deepseek-v4-pro | SQL-L1 | {'engine_error': 2}；触发修一次 8 次，修后正确 2 次 |

## 逐题正确次数（/3）

| 题 | Q级 | 低区分度 | deepseek-flash SQL-R | deepseek-flash SQL-L1 | deepseek-v4-pro SQL-R | deepseek-v4-pro SQL-L1 |
|---|---|---|---|---|---|---|
| Q102 | Q1 |  | 0/3 | 0/3 | 0/3 | 0/3 |
| Q28 | Q1 |  | 0/3 | 3/3 | 1/3 | 3/3 |
| Q66 | Q1 |  | 1/3 | 1/3 | 0/3 | 3/3 |
| Q40 | Q1 |  | pending | refused/refused/refused | pending | refused/pending/refused |
| Q08 | Q1 |  | 3/3 | 3/3 | 1/3 | 3/3 |
| Q15 | Q1 |  | 2/3 | 3/3 | 0/3 | 3/3 |
| Q68 | Q1 | 是 | 0/3 | 2/3 | 3/3 | 3/3 |
| Q51 | Q1 |  | 3/3 | 3/3 | 3/3 | 3/3 |
| Q74 | Q2 |  | 0/3 | 2/3 | 0/3 | 1/3 |
| Q73 | Q2 |  | 1/3 | 3/3 | 0/3 | 1/3 |
| Q82 | Q2 |  | 0/3 | 1/3 | 0/3 | 0/3 |
| Q17 | Q2 | 是 | 0/3 | 2/3 | 0/3 | 2/3 |
| Q71 | Q2 |  | 0/3 | 0/3 | 0/3 | 0/3 |
| Q70 | Q2 |  | 0/3 | 2/3 | 0/3 | 0/3 |
| Q69 | Q2 |  | 0/3 | 0/3 | 0/3 | 0/3 |
| Q75 | Q2 |  | 3/3 | 2/3 | 1/3 | 3/3 |
| Q100 | Q3 |  | 0/3 | 0/3 | 0/3 | 0/3 |
| Q34 | Q3 |  | 0/3 | 0/3 | 0/3 | 0/3 |
| Q76 | Q3 | 是 | 0/3 | 0/3 | 0/3 | 0/3 |
| Q81 | Q3 |  | 0/3 | 0/3 | 0/3 | 0/3 |
| Q117 | Q3 |  | 1/3 | 1/3 | 1/3 | 0/3 |
| Q50 | Q3 |  | 2/3 | 3/3 | 0/3 | 0/3 |
| Q80 | Q3 |  | 0/3 | 3/3 | 0/3 | 0/3 |
| Q49 | Q3 |  | 0/3 | 0/3 | 0/3 | 0/3 |

## token 分布（每次调用；均值 / 中位 / P90 / 最大，括号内为合计）

| 模型 | 单元 | 调用 | reasoning | completion | 缓存未命中输入 | prompt |
|---|---|---:|---|---|---|---|
| deepseek-flash | SQL-R | 77 | 1,721 / 1,262 / 4,038 / 6,512（合计 132,484） | 1,967 / 1,462 / 4,319 / 7,224（合计 151,496） | 282 / 248 / 259 / 4,215（合计 21,708） | 4,269 / 4,226 / 4,257 / 5,153（合计 328,746） |
| deepseek-flash | SQL-L1 | 86 | 1,230 / 475 / 3,512 / 9,208（合计 105,749） | 1,514 / 730 / 3,860 / 9,994（合计 130,214） | 719 / 163 / 348 / 43,159（合计 61,813） | 46,320 / 46,243 / 46,555 / 47,119（合计 3,983,477） |
| deepseek-v4-pro | SQL-R | 73 | 4,113 / 3,316 / 7,191 / 26,602（合计 300,260） | 4,334 / 3,578 / 7,520 / 27,578（合计 316,352） | 61 / 55 / 66 / 424（合计 4,438） | 4,285 / 4,279 / 4,290 / 4,648（合计 312,790） |
| deepseek-v4-pro | SQL-L1 | 80 | 3,884 / 3,083 / 7,912 / 17,748（合计 310,758） | 4,147 / 3,376 / 8,207 / 18,281（合计 331,769） | 715 / 88 / 212 / 46,284（合计 57,232） | 46,346 / 46,296 / 46,400 / 47,250（合计 3,707,664） |

### 冷启动（缓存未命中 > prompt 的一半的调用）与费用

| 模型 | 单元 | 冷启动次数 | 冷启动费用 | 热调用费用均值 | 总费用（元） |
|---|---|---:|---:|---:|---:|
| deepseek-flash | SQL-R | 1 | 0.0054 | 0.0083 | 0.6338 |
| deepseek-flash | SQL-L1 | 1 | 0.0439 | 0.0073 | 0.6611 |
| deepseek-v4-pro | SQL-R | 0 | 0.0000 | 0.0594 | 4.3370 |
| deepseek-v4-pro | SQL-L1 | 1 | 0.2354 | 0.0639 | 5.2840 |

## 指纹

| 模型 | system_fingerprint（调用次数） | 无指纹调用 |
|---|---|---:|
| deepseek-flash | {'e72d3c7f663d3e1383b00b3884cb4501': 163} | 0 |
| deepseek-v4-pro | {'a307abda487cd1b463329ccb945ce396': 153} | 0 |

## T13 预算模型（按冷启动次数）

费用 = 调用数 × 热调用单价 + 冷启动次数 × 前缀 token × (未命中价 − 命中价)。前缀 token 用 dry-run 估算 × 实测/估算比 1.132（SQL-L1 实测）。T13 单元：SQL-L0, SQL-R, SQL-L1, SQL-L1c, SQL-L1.5W, SQL-L1.5S, SQL-R-EN, SQL-L1c-EN；中文 122 题、英文 99 题，各 3 次；错峰价。

| 模型 | 每次作答调用数 | 每次调用输出 token | 热调用未命中输入 | 热调用部分（元） | 每冷启动一轮全部单元（元） | 冷启动 8 次 | 24 次 | 100 次 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-flash | 1.13 | 1,728 | 225 | 23.8 | 0.16 | 24.0 | 24.3 | 25.8 |
| deepseek-v4-pro | 1.06 | 4,236 | 101 | 180.0 | 0.69 | 180.7 | 182.1 | 188.7 |

（冷启动 N 次按各单元平均前缀计；8 次 = 每单元只冷启动一次。）

## 缓存过期时间窗（`harness/cache_probe.py`）

每个间隔一份独立前缀：预热一次，隔 d 秒再调一次；命中 = 第二次调用的 `prompt_cache_hit_tokens`。

| run | 模型 | 间隔 | 实际间隔（秒） | 命中 | 未命中 |
|---|---|---:|---:|---:|---:|
| 20261018-T12-cache-flash-01 | deepseek-flash | 10 s | 20.0 | 46080 | 182 |
| 20261018-T12-cache-flash-01 | deepseek-flash | 5 min | 300.0 | 46080 | 182 |
| 20261018-T12-cache-flash-01 | deepseek-flash | 15 min | 899.9 | 46080 | 182 |
| 20261018-T12-cache-flash-01 | deepseek-flash | 30 min | 1799.9 | 46080 | 183 |

## 列口径诊断（`scripts/t12_column_diagnostic.py`，上界，非评分）

```
('flash', 'SQL-R')
   Q117 2 skipped (multi-ref/selection/top_n)
   Q117 3 skipped (multi-ref/selection/top_n)
   Q50 1 cand 1 cols / ref 3; no subset matches
   Q70 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q70 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q70 3 cand 3 cols / ref 4; matches after dropping ref cols [1, 3] (['amount', 'count'])
   Q80 1 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q80 2 cand 2 cols / ref 3; matches after dropping ref cols [1, 2] (['count', 'other'])
   Q81 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q80 3 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q81 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q81 3 cand 3 cols / ref 4; matches after dropping ref cols [2, 3] (['amount', 'amount'])
('flash', 'SQL-L1')
   Q70 3 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q81 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q81 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q81 3 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
('pro', 'SQL-R')
   Q117 3 skipped (multi-ref/selection/top_n)
   Q17 1 cand 2 cols / ref 3; matches after dropping ref cols [0, 1] (['other', 'amount'])
   Q117 1 skipped (multi-ref/selection/top_n)
   Q17 2 cand 2 cols / ref 3; matches after dropping ref cols [0, 1] (['other', 'amount'])
   Q50 2 cand 1 cols / ref 3; matches after dropping ref cols [0, 1] (['amount', 'amount'])
   Q50 1 cand 2 cols / ref 3; matches after dropping ref cols [0, 1] (['amount', 'amount'])
   Q50 3 cand 1 cols / ref 3; no subset matches
   Q70 3 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q70 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q73 1 skipped (multi-ref/selection/top_n)
   Q73 3 skipped (multi-ref/selection/top_n)
   Q70 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q74 1 skipped (multi-ref/selection/top_n)
   Q80 1 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q80 3 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q81 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q80 2 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q81 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q81 3 cand 3 cols / ref 4; matches after dropping ref cols [2, 3] (['amount', 'amount'])
('pro', 'SQL-L1')
   Q117 2 skipped (multi-ref/selection/top_n)
   Q34 3 cand 2 cols / ref 5; matches after dropping ref cols [0, 1, 2] (['other', 'amount', 'other'])
   Q117 3 skipped (multi-ref/selection/top_n)
   Q50 1 cand 2 cols / ref 3; matches after dropping ref cols [0, 1] (['amount', 'amount'])
   Q50 2 cand 1 cols / ref 3; matches after dropping ref cols [0, 1] (['amount', 'amount'])
   Q50 3 cand 1 cols / ref 3; matches after dropping ref cols [0, 1] (['amount', 'amount'])
   Q70 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q70 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q70 3 cand 3 cols / ref 4; matches after dropping ref cols [3] (['count'])
   Q73 1 skipped (multi-ref/selection/top_n)
   Q80 1 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q80 2 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q80 3 cand 2 cols / ref 3; matches after dropping ref cols [1] (['count'])
   Q81 3 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q81 1 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
   Q81 2 cand 3 cols / ref 4; matches after dropping ref cols [3] (['amount'])
```
