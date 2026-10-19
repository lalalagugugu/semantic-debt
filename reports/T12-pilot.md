# T12 试跑结果（自动生成）

<!-- final-rescore:begin -->

## 最终重评（eval-v1.1，G3 选模型依据）

- 题库：`eval-v1.1` = `938957f`（只读 worktree）；评分器：main `ea90587`（含 #91）；重评日志 `runs/20261018-T12-pilot-{flash,pro}-01-rescore-01/`（`harness.rescore`，离线，不调用模型、不执行查询）
- 范围：试跑全部 288 条作答（2 模型 × SQL-L1、SQL-R × 24 题 × 3 轮），一条不漏
- judge 题 ['Q40'] 不进任何分母（拒答、pending 一并拿出）；低区分度 ['Q17', 'Q68', 'Q69', 'Q76'] 不进主表，单列
- 本轮改写过题面的题在试跑里只有 ['Q69']（12 条）。`harness.rescore` 默认拒绝题面已变的行，这 12 条用显式开关 `--allow-changed-question` 按 eval-v1.1 参考评分、日志行标 `question_changed`；该开关只用于这 12 条。它们作答针对的是旧题面，单列，且 Q69 本就是低区分度题，不进主表
- **严格**：eval-v1.1 下评分器的原始判定（日志里的 `final`）
- **最终**：在严格的基础上，对旧系统提示下不能要求的项不扣分（`scripts/t12_final_rescore.py` 的通用放宽，加上逐条手核，见 `scripts/t12_final_verdicts.yaml`）：只给编码的按键核对对象；截断、自造标签、季度写法、宽表按内容核对；第 13–15 条的约定列（变化量的绝对值与百分比、名次、分母）只看有没有。约定列的界定是通用的：eval-v1.1 新增为必答、且不在基础标注里（或追加在 eval-v1 参考之后）的列，标识键除外

### 准确率：严格

| 模型 | 单元 | 主表（不含低区分度、judge） | 含低区分度 | 首答即对（主表） |
|---|---|---|---|---|
| deepseek-flash | SQL-L1 | 40/57 = 70.2% | 44/69 = 63.8% | 34/57 = 59.6% |
| deepseek-flash | SQL-R | 25/57 = 43.9% | 25/69 = 36.2% | 25/57 = 43.9% |
| deepseek-v4-pro | SQL-L1 | 35/57 = 61.4% | 39/69 = 56.5% | 33/57 = 57.9% |
| deepseek-v4-pro | SQL-R | 22/57 = 38.6% | 25/69 = 36.2% | 22/57 = 38.6% |

### 准确率：最终

| 模型 | 单元 | 主表（不含低区分度、judge） | 含低区分度 | 首答即对（主表） |
|---|---|---|---|---|
| deepseek-flash | SQL-L1 | 49/57 = 86.0% | 57/69 = 82.6% | 41/57 = 71.9% |
| deepseek-flash | SQL-R | 31/57 = 54.4% | 36/69 = 52.2% | 28/57 = 49.1% |
| deepseek-v4-pro | SQL-L1 | 48/57 = 84.2% | 54/69 = 78.3% | 44/57 = 77.2% |
| deepseek-v4-pro | SQL-R | 30/57 = 52.6% | 36/69 = 52.2% | 30/57 = 52.6% |

### 按 Q 级（主表；括号内为含低区分度）

| 口径 | 模型 | 单元 | Q1 | Q2 | Q3 |
|---|---|---|---|---|---|
| 严格 | deepseek-flash | SQL-L1 | 17/18 = 94.4%（19/21 = 90.5%） | 10/18 = 55.6%（10/24 = 41.7%） | 13/21 = 61.9%（15/24 = 62.5%） |
| 严格 | deepseek-flash | SQL-R | 9/18 = 50.0%（9/21 = 42.9%） | 8/18 = 44.4%（8/24 = 33.3%） | 8/21 = 38.1%（8/24 = 33.3%） |
| 严格 | deepseek-v4-pro | SQL-L1 | 15/18 = 83.3%（18/21 = 85.7%） | 10/18 = 55.6%（10/24 = 41.7%） | 10/21 = 47.6%（11/24 = 45.8%） |
| 严格 | deepseek-v4-pro | SQL-R | 5/18 = 27.8%（8/21 = 38.1%） | 8/18 = 44.4%（8/24 = 33.3%） | 9/21 = 42.9%（9/24 = 37.5%） |
| 最终 | deepseek-flash | SQL-L1 | 18/18 = 100.0%（21/21 = 100.0%） | 16/18 = 88.9%（19/24 = 79.2%） | 15/21 = 71.4%（17/24 = 70.8%） |
| 最终 | deepseek-flash | SQL-R | 10/18 = 55.6%（12/21 = 57.1%） | 9/18 = 50.0%（12/24 = 50.0%） | 12/21 = 57.1%（12/24 = 50.0%） |
| 最终 | deepseek-v4-pro | SQL-L1 | 18/18 = 100.0%（21/21 = 100.0%） | 14/18 = 77.8%（16/24 = 66.7%） | 16/21 = 76.2%（17/24 = 70.8%） |
| 最终 | deepseek-v4-pro | SQL-R | 6/18 = 33.3%（9/21 = 42.9%） | 10/18 = 55.6%（13/24 = 54.2%） | 14/21 = 66.7%（14/24 = 58.3%） |

### 四种结果占比（全部 72 条作答，含低区分度与 judge；pending = judge 题返回了行集）

| 口径 | 模型 | 单元 | correct | wrong | exec_error | refused | pending |
|---|---|---|---|---|---|---|---|
| 严格 | deepseek-flash | SQL-L1 | 44（61%） | 22（31%） | 3（4%） | 3（4%） | 0（0%） |
| 严格 | deepseek-flash | SQL-R | 25（35%） | 44（61%） | 0（0%） | 0（0%） | 3（4%） |
| 严格 | deepseek-v4-pro | SQL-L1 | 39（54%） | 28（39%） | 2（3%） | 2（3%） | 1（1%） |
| 严格 | deepseek-v4-pro | SQL-R | 25（35%） | 44（61%） | 0（0%） | 0（0%） | 3（4%） |
| 最终 | deepseek-flash | SQL-L1 | 57（79%） | 9（12%） | 3（4%） | 3（4%） | 0（0%） |
| 最终 | deepseek-flash | SQL-R | 36（50%） | 33（46%） | 0（0%） | 0（0%） | 3（4%） |
| 最终 | deepseek-v4-pro | SQL-L1 | 54（75%） | 13（18%） | 2（3%） | 2（3%） | 1（1%） |
| 最终 | deepseek-v4-pro | SQL-R | 36（50%） | 33（46%） | 0（0%） | 0（0%） | 3（4%） |

### 低区分度题（不进主表）

| 题 | 模型 | 单元 | 严格 | 最终 |
|---|---|---|---|---|
| Q17 | deepseek-flash | SQL-L1 | 0/3 | 3/3 |
| Q17 | deepseek-flash | SQL-R | 0/3 | 3/3 |
| Q17 | deepseek-v4-pro | SQL-L1 | 0/3 | 2/3 |
| Q17 | deepseek-v4-pro | SQL-R | 0/3 | 3/3 |
| Q68 | deepseek-flash | SQL-L1 | 2/3 | 3/3 |
| Q68 | deepseek-flash | SQL-R | 0/3 | 2/3 |
| Q68 | deepseek-v4-pro | SQL-L1 | 3/3 | 3/3 |
| Q68 | deepseek-v4-pro | SQL-R | 3/3 | 3/3 |
| Q69（作答针对旧题面） | deepseek-flash | SQL-L1 | 0/3 | 0/3 |
| Q69（作答针对旧题面） | deepseek-flash | SQL-R | 0/3 | 0/3 |
| Q69（作答针对旧题面） | deepseek-v4-pro | SQL-L1 | 0/3 | 0/3 |
| Q69（作答针对旧题面） | deepseek-v4-pro | SQL-R | 0/3 | 0/3 |
| Q76 | deepseek-flash | SQL-L1 | 2/3 | 2/3 |
| Q76 | deepseek-flash | SQL-R | 0/3 | 0/3 |
| Q76 | deepseek-v4-pro | SQL-L1 | 1/3 | 1/3 |
| Q76 | deepseek-v4-pro | SQL-R | 0/3 | 0/3 |

### judge 题（不进任何分母）

| 题 | 模型 | 单元 | 三轮结果 |
|---|---|---|---|
| Q40 | deepseek-flash | SQL-L1 | refused / refused / refused |
| Q40 | deepseek-flash | SQL-R | pending / pending / pending |
| Q40 | deepseek-v4-pro | SQL-L1 | pending / refused / refused |
| Q40 | deepseek-v4-pro | SQL-R | pending / pending / pending |

### 判定变化一：试跑原判定（eval-v1、旧评分器）→ 严格（eval-v1.1）

共 88 处：对 → 错 20、错 → 对 68，其他 0。原因按「最终」口径下能否救回给出。

**从对变错（单列）**

| 题 | 模型 | 单元 | 轮次 | 原因 |
|---|---|---|---|---|
| Q17 | flash | SQL-L1 | r1 | eval-v1.1 新增要求 → 约定列只看有没有（total_sales_amount） |
| Q17 | flash | SQL-L1 | r2 | eval-v1.1 新增要求 → 约定列只看有没有（total_sales_amount） |
| Q17 | v4-pro | SQL-L1 | r1 | eval-v1.1 新增要求 → 约定列只看有没有（total_sales_amount） |
| Q17 | v4-pro | SQL-L1 | r2 | eval-v1.1 新增要求 → 约定列只看有没有（total_sales_amount） |
| Q66 | flash | SQL-L1 | r2 | eval-v1.1 新增要求 → 展示差异（季度写法）：季度写成 1–4，参考 Q1–Q4；4 个季度的折扣金额全对 |
| Q66 | flash | SQL-R | r1 | eval-v1.1 新增要求 → 展示差异（季度写法）：同上 |
| Q66 | v4-pro | SQL-L1 | r1 | eval-v1.1 新增要求 → 展示差异（季度写法）：同上 |
| Q66 | v4-pro | SQL-L1 | r2 | eval-v1.1 新增要求 → 展示差异（季度写法）：同上 |
| Q66 | v4-pro | SQL-L1 | r3 | eval-v1.1 新增要求 → 展示差异（季度写法）：同上 |
| Q73 | flash | SQL-L1 | r1 | eval-v1.1 新增要求 → 约定列只看有没有（rank） |
| Q73 | flash | SQL-L1 | r2 | eval-v1.1 新增要求 → 约定列只看有没有（rank） |
| Q73 | flash | SQL-L1 | r3 | eval-v1.1 新增要求 → 约定列只看有没有（rank） |
| Q73 | flash | SQL-R | r1 | eval-v1.1 新增要求 → 约定列只看有没有（rank） |
| Q73 | v4-pro | SQL-L1 | r2 | eval-v1.1 新增要求 → 约定列只看有没有（rank） |
| Q74 | flash | SQL-L1 | r1 | eval-v1.1 新增要求 → 约定列只看有没有（rank、store_total_sales） |
| Q74 | flash | SQL-L1 | r2 | eval-v1.1 新增要求 → 约定列只看有没有（rank、store_total_sales） |
| Q74 | v4-pro | SQL-L1 | r1 | eval-v1.1 新增要求 → 约定列只看有没有（rank、store_total_sales） |
| Q117 | flash | SQL-L1 | r3 | eval-v1.1 新增要求 → 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | flash | SQL-R | r1 | eval-v1.1 新增要求 → 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | v4-pro | SQL-R | r2 | eval-v1.1 新增要求 → 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |

**从错变对**

| 题 | 模型 | 单元 | 轮次 | 原因 |
|---|---|---|---|---|
| Q34 | flash | SQL-L1 | r1 | 参考补收 4 个有库存、无销售、周转率为 0 的产品（eval-v1.1） |
| Q50 | v4-pro | SQL-L1 | r1 | 必答列只剩增长率与增长额（两年销售额不再必答），参考补了增长额 |
| Q50 | v4-pro | SQL-R | r1 | 必答列只剩增长率与增长额（两年销售额不再必答），参考补了增长额 |
| Q66 | flash | SQL-L1 | r1 | 季度统一写成 Q1–Q4，作答正用这种写法 |
| Q66 | flash | SQL-L1 | r3 | 季度统一写成 Q1–Q4，作答正用这种写法 |
| Q66 | flash | SQL-R | r2 | 季度统一写成 Q1–Q4，作答正用这种写法 |
| Q70 | flash | SQL-L1 | r3 | 必答列：没问的门店数不再必答 |
| Q70 | flash | SQL-R | r1 | 必答列：没问的门店数不再必答 |
| Q70 | flash | SQL-R | r2 | 必答列：没问的门店数不再必答 |
| Q70 | v4-pro | SQL-L1 | r1 | 必答列：没问的门店数不再必答 |
| Q70 | v4-pro | SQL-L1 | r2 | 必答列：没问的门店数不再必答 |
| Q70 | v4-pro | SQL-L1 | r3 | 必答列：没问的门店数不再必答 |
| Q70 | v4-pro | SQL-R | r1 | 必答列：没问的门店数不再必答 |
| Q70 | v4-pro | SQL-R | r2 | 必答列：没问的门店数不再必答 |
| Q70 | v4-pro | SQL-R | r3 | 必答列：没问的门店数不再必答 |
| Q71 | flash | SQL-L1 | r1 | 参考删去 NULL 品类那一行 |
| Q71 | flash | SQL-L1 | r2 | 参考删去 NULL 品类那一行 |
| Q71 | flash | SQL-L1 | r3 | 参考删去 NULL 品类那一行 |
| Q71 | flash | SQL-R | r1 | 参考删去 NULL 品类那一行 |
| Q71 | flash | SQL-R | r2 | 参考删去 NULL 品类那一行 |
| Q71 | flash | SQL-R | r3 | 参考删去 NULL 品类那一行 |
| Q71 | v4-pro | SQL-L1 | r1 | 参考删去 NULL 品类那一行 |
| Q71 | v4-pro | SQL-L1 | r2 | 参考删去 NULL 品类那一行 |
| Q71 | v4-pro | SQL-R | r1 | 参考删去 NULL 品类那一行 |
| Q71 | v4-pro | SQL-R | r2 | 参考删去 NULL 品类那一行 |
| Q71 | v4-pro | SQL-R | r3 | 参考删去 NULL 品类那一行 |
| Q75 | v4-pro | SQL-R | r2 | 必答列：增长率不再必答（只比姓名与客户键） |
| Q76 | flash | SQL-L1 | r1 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q76 | flash | SQL-L1 | r2 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q76 | v4-pro | SQL-L1 | r3 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q80 | flash | SQL-R | r1 | 必答列：没问的客户数不再必答 |
| Q80 | flash | SQL-R | r3 | 必答列：没问的客户数不再必答 |
| Q80 | v4-pro | SQL-L1 | r1 | 必答列：没问的客户数不再必答 |
| Q80 | v4-pro | SQL-L1 | r2 | 必答列：没问的客户数不再必答 |
| Q80 | v4-pro | SQL-L1 | r3 | 必答列：没问的客户数不再必答 |
| Q80 | v4-pro | SQL-R | r1 | 必答列：没问的客户数不再必答 |
| Q80 | v4-pro | SQL-R | r2 | 必答列：没问的客户数不再必答 |
| Q80 | v4-pro | SQL-R | r3 | 必答列：没问的客户数不再必答 |
| Q81 | flash | SQL-L1 | r1 | 必答列：没问的终身价值总额不再必答 |
| Q81 | flash | SQL-L1 | r2 | 必答列：没问的终身价值总额不再必答 |
| Q81 | flash | SQL-L1 | r3 | 必答列：没问的终身价值总额不再必答 |
| Q81 | flash | SQL-R | r1 | 必答列：没问的终身价值总额不再必答 |
| Q81 | flash | SQL-R | r2 | 必答列：没问的终身价值总额不再必答 |
| Q81 | v4-pro | SQL-L1 | r1 | 必答列：没问的终身价值总额不再必答 |
| Q81 | v4-pro | SQL-L1 | r2 | 必答列：没问的终身价值总额不再必答 |
| Q81 | v4-pro | SQL-L1 | r3 | 必答列：没问的终身价值总额不再必答 |
| Q81 | v4-pro | SQL-R | r1 | 必答列：没问的终身价值总额不再必答 |
| Q81 | v4-pro | SQL-R | r2 | 必答列：没问的终身价值总额不再必答 |
| Q82 | flash | SQL-L1 | r1 | 名、姓相邻两列可拼成全名（#91）；职位不再必答 |
| Q82 | v4-pro | SQL-L1 | r1 | 名、姓相邻两列可拼成全名（#91）；职位不再必答 |
| Q82 | v4-pro | SQL-L1 | r2 | 名、姓相邻两列可拼成全名（#91）；职位不再必答 |
| Q100 | flash | SQL-L1 | r1 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | flash | SQL-L1 | r2 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | flash | SQL-L1 | r3 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | flash | SQL-R | r1 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | flash | SQL-R | r2 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | v4-pro | SQL-L1 | r1 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | v4-pro | SQL-L1 | r2 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | v4-pro | SQL-L1 | r3 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | v4-pro | SQL-R | r1 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | v4-pro | SQL-R | r2 | 参考补客户键并标为必答（姓名是占位值） |
| Q100 | v4-pro | SQL-R | r3 | 参考补客户键并标为必答（姓名是占位值） |
| Q102 | flash | SQL-L1 | r1 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q102 | flash | SQL-L1 | r2 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q102 | flash | SQL-L1 | r3 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q102 | v4-pro | SQL-L1 | r1 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q102 | v4-pro | SQL-L1 | r2 | 空值参考标签可匹配不冲突的字符串（#91） |
| Q102 | v4-pro | SQL-L1 | r3 | 空值参考标签可匹配不冲突的字符串（#91） |

### 判定变化二：严格 → 最终（逐条）

共 50 处，全部是错 → 对（最终只放宽、不收紧，没有对 → 错）。

| 题 | 模型 | 单元 | 轮次 | 原因 |
|---|---|---|---|---|
| Q17 | flash | SQL-L1 | r1 | 约定列只看有没有（total_sales_amount） |
| Q17 | flash | SQL-L1 | r2 | 约定列只看有没有（total_sales_amount） |
| Q17 | flash | SQL-L1 | r3 | 展示差异（标签改写）：WeekEnd/WorkDay 写成 周末/节假日、工作日；占比 28.47/71.53 全对 |
| Q17 | flash | SQL-R | r1 | 展示差异（标签改写）：写成 周末/工作日；全渠道口径，占比 28.5/71.5 落在评分器容差内 |
| Q17 | flash | SQL-R | r2 | 展示差异（宽表）：一行两列（周末占比、工作日占比）28.5/71.5，参考两行；落在容差内 |
| Q17 | flash | SQL-R | r3 | 展示差异（标签改写）：写成 Weekend/Weekday；占比全对 |
| Q17 | v4-pro | SQL-L1 | r1 | 约定列只看有没有（total_sales_amount） |
| Q17 | v4-pro | SQL-L1 | r2 | 约定列只看有没有（total_sales_amount） |
| Q17 | v4-pro | SQL-R | r1 | 展示差异（标签改写）：写成 周末/工作日，占比写成小数 0.285/0.715（评分器接受）；全渠道口径，落在容差内 |
| Q17 | v4-pro | SQL-R | r2 | 展示差异（标签改写）：写成 周末/工作日；全渠道口径，占比落在容差内 |
| Q17 | v4-pro | SQL-R | r3 | 展示差异（宽表）：同上 |
| Q28 | v4-pro | SQL-R | r3 | 展示差异（宽表）：一行两列 238.67 / 214.10，与参考两行 Store / Online 一致 |
| Q34 | v4-pro | SQL-L1 | r1 | 约定列只看有没有（avg_inventory） |
| Q34 | v4-pro | SQL-L1 | r2 | 约定列只看有没有（avg_inventory） |
| Q50 | flash | SQL-R | r1 | 展示差异（约定列（变化量只给了一种））：只给增长额 -392,072,435.45，与参考增长额一致；百分比与增长额互为第 13 条的约定列，只看有没有 |
| Q50 | v4-pro | SQL-L1 | r2 | 约定列只看有没有（growth_amount） |
| Q50 | v4-pro | SQL-L1 | r3 | 约定列只看有没有（growth_amount） |
| Q50 | v4-pro | SQL-R | r2 | 约定列只看有没有（growth_amount） |
| Q50 | v4-pro | SQL-R | r3 | 展示差异（约定列（变化量只给了一种））：同上 |
| Q66 | flash | SQL-L1 | r2 | 展示差异（季度写法）：季度写成 1–4，参考 Q1–Q4；4 个季度的折扣金额全对 |
| Q66 | flash | SQL-R | r1 | 展示差异（季度写法）：同上 |
| Q66 | v4-pro | SQL-L1 | r1 | 展示差异（季度写法）：同上 |
| Q66 | v4-pro | SQL-L1 | r2 | 展示差异（季度写法）：同上 |
| Q66 | v4-pro | SQL-L1 | r3 | 展示差异（季度写法）：同上 |
| Q68 | flash | SQL-L1 | r1 | 展示差异（标签改写）：Yes/No 写成 节假日/非节假日；订单数、营收全对 |
| Q68 | flash | SQL-R | r2 | 展示差异（标签改写）：同上 |
| Q68 | flash | SQL-R | r3 | 展示差异（标签改写）：同上 |
| Q73 | flash | SQL-L1 | r1 | 约定列只看有没有（rank） |
| Q73 | flash | SQL-L1 | r2 | 约定列只看有没有（rank） |
| Q73 | flash | SQL-L1 | r3 | 约定列只看有没有（rank） |
| Q73 | flash | SQL-R | r1 | 约定列只看有没有（rank） |
| Q73 | v4-pro | SQL-L1 | r1 | 约定列只看有没有（rank） |
| Q73 | v4-pro | SQL-L1 | r2 | 约定列只看有没有（rank） |
| Q74 | flash | SQL-L1 | r1 | 约定列只看有没有（rank、store_total_sales） |
| Q74 | flash | SQL-L1 | r2 | 约定列只看有没有（rank、store_total_sales） |
| Q74 | v4-pro | SQL-L1 | r1 | 约定列只看有没有（rank、store_total_sales） |
| Q74 | v4-pro | SQL-L1 | r3 | 约定列只看有没有（rank、store_total_sales） |
| Q74 | v4-pro | SQL-R | r1 | 约定列只看有没有（rank、store_total_sales） |
| Q74 | v4-pro | SQL-R | r2 | 约定列只看有没有（rank、store_total_sales） |
| Q75 | flash | SQL-L1 | r3 | 截断（自加 LIMIT，返回行全在参考里） |
| Q117 | flash | SQL-L1 | r2 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | flash | SQL-L1 | r3 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | flash | SQL-R | r1 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | flash | SQL-R | r2 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | flash | SQL-R | r3 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | v4-pro | SQL-L1 | r2 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | v4-pro | SQL-L1 | r3 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | v4-pro | SQL-R | r1 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | v4-pro | SQL-R | r2 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank） |
| Q117 | v4-pro | SQL-R | r3 | 约定列只看有没有（category_decline_pct、category_rank、store_decline_amount、store_rank）；只给键、没给名称（按键核对对象） |

汇总：conv 30；conv+key 1；pres:季度写法 5；pres:宽表 3；pres:标签改写 8；pres:约定列（变化量只给了一种） 2；trunc 1

### 归因：SQL-L1

最终口径下仍不对的每一条（wrong、exec_error、refused）。judge 题的拒答也列出，但不进分母。

| 模型 | SQL 真错 | 语义层差距 | 指令遵循 | 参考问题 | 执行错误/超时/拒答 |
|---|---|---|---|---|---|
| deepseek-flash | 2 | 3（另 低区分度 1） | 0 | 0（另 低区分度 3） | 3（另 judge 3） |
| deepseek-v4-pro | 1 | 6（另 低区分度 3） | 0 | 0（另 低区分度 3） | 2（另 judge 2） |

（数字是主表内的条数；括号里是低区分度题和 judge 题的条数。）

| 题 | 模型 | 轮次 | 结果 | 类别 | 证据 |
|---|---|---|---|---|---|
| Q17（低区分度） | v4-pro | r3 | wrong | 语义层差距 | 照约定 4 用日均销售算占比（50.01/49.99），参考按合计（28.47/71.53）；约定 4 没说占比类问题不适用，调优候选 |
| Q34 | flash | r2 | wrong | SQL 真错 | 只列 2009 年有销售的产品（2,504 行），漏了 4 个有库存、无销售、周转率为 0 的产品（eval-v1.1 已收）；其余数值一致 |
| Q34 | flash | r3 | exec_error | 执行错误/超时/拒答 | 修一次后仍引用了不存在的列（engine_error · sha256:e5e70d16700dc29c） |
| Q34 | v4-pro | r3 | wrong | SQL 真错 | 同 Flash r2 漏 4 个周转率为 0 的产品；另外只给键、没给名称（展示差异，不单独计） |
| Q40（judge） | flash | r1 | refused | 执行错误/超时/拒答 | judge 题，拒答：L1 写着汇率表用不上，且缺日汇率没有约定（semantic-v1.2 已改） |
| Q40（judge） | flash | r2 | refused | 执行错误/超时/拒答 | 同上 |
| Q40（judge） | flash | r3 | refused | 执行错误/超时/拒答 | 同上 |
| Q40（judge） | v4-pro | r2 | refused | 执行错误/超时/拒答 | 同上 |
| Q40（judge） | v4-pro | r3 | refused | 执行错误/超时/拒答 | 同上 |
| Q49 | flash | r1 | wrong | 语义层差距 | 集团实体父键指向自身，L1 没写；按层级汇总时集团算两次（17,884,462,022.63 对 12,413,657,608.89）；另输出成按层级的 4 行合计 |
| Q49 | flash | r2 | exec_error | 执行错误/超时/拒答 | 递归查询撞上引擎的递归层数上限，根因同上：集团自环（语义层差距）（engine_error · sha256:a531bbe69c441ad8） |
| Q49 | flash | r3 | wrong | 语义层差距 | 420 行中 417 行一致，3 个集团因自环重复计算 |
| Q49 | v4-pro | r1 | wrong | 语义层差距 | 集团金额对，但没有州的门店归进一个 N/A「州」，多 1 行；根因同上（层级结构 L1 没写全） |
| Q49 | v4-pro | r2 | wrong | 语义层差距 | 3 个集团因自环重复计算 |
| Q49 | v4-pro | r3 | exec_error | 执行错误/超时/拒答 | 修一次后仍引用了子查询外不可见的列（engine_error · sha256:6726726953d5b5e9） |
| Q69（低区分度） | flash | r1 | wrong | 参考问题 | 题目退化（低区分度，已标）：按 PromotionCategory 排除无折扣后只剩 1 行，作答改按促销名分组（9 行）；作答针对旧题面 |
| Q69（低区分度） | flash | r2 | wrong | 参考问题 | 同上 |
| Q69（低区分度） | flash | r3 | wrong | 参考问题 | 同上 |
| Q69（低区分度） | v4-pro | r1 | wrong | 参考问题 | 同上 |
| Q69（低区分度） | v4-pro | r2 | wrong | 参考问题 | 同上 |
| Q69（低区分度） | v4-pro | r3 | wrong | 参考问题 | 同上（同时输出了促销名和类别） |
| Q71 | v4-pro | r3 | wrong | 语义层差距 | 照 L1「保住总额用左连接」把缺失产品归为「未知品类」一组（9 行），eval-v1.1 参考已去掉这一组；左连接说明的适用范围不清，调优候选 |
| Q73 | v4-pro | r3 | wrong | 语义层差距 | 「差额」取 安全库存 − 当前库存（缺口最大），参考取 当前库存 − 安全库存；当前库存口径照约定 11，正确。差额方向是口径选择（names-required-by-system-prompt 第三节），L1 没写；调优候选，不补参考（用户裁决） |
| Q74 | flash | r3 | wrong | 语义层差距 | 按 L1 对 7 家渠道虚拟门店的描述只保留实体店（897 行，参考 925 行含虚拟门店）；L1 没说「按门店」是否含虚拟门店，调优候选 |
| Q74 | v4-pro | r2 | wrong | 语义层差距 | 同上，StoreType = 'Store'，897 行 |
| Q76（低区分度） | flash | r3 | wrong | 语义层差距 | 丢掉缺失产品那一组（8 行），参考保留为 NULL 品类；与 Q71 相反，同一条左连接说明的适用范围不清 |
| Q76（低区分度） | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q76（低区分度） | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q82 | flash | r2 | wrong | SQL 真错 | dateDiff('year') 取整年，平均任期 10.01 对参考 10.83 |
| Q82 | v4-pro | r3 | wrong | 语义层差距 | 把「团队」理解为全部下级（含间接下属）算平均任期，参考只算直属下属；直属人数全对。「团队」算直属还是全部下级是组织口径，L1 没写；调优候选，不补参考（用户裁决） |
| Q117 | flash | r1 | exec_error | 执行错误/超时/拒答 | 修一次后仍引用了不存在的列（engine_error · sha256:3ff8a407800785d7） |
| Q117 | v4-pro | r1 | exec_error | 执行错误/超时/拒答 | 同上（engine_error · sha256:1f2183c586acf87a） |

### 归因：SQL-R（语义层差距即「缺约定（档位差距）」：约定写在 L1，R 没有）

最终口径下仍不对的每一条（wrong、exec_error、refused）。judge 题的拒答也列出，但不进分母。

| 模型 | SQL 真错 | 语义层差距 | 指令遵循 | 参考问题 | 执行错误/超时/拒答 |
|---|---|---|---|---|---|
| deepseek-flash | 1 | 25（另 低区分度 7） | 0 | 0 | 0 |
| deepseek-v4-pro | 0 | 27（另 低区分度 6） | 0 | 0 | 0 |

（数字是主表内的条数；括号里是低区分度题和 judge 题的条数。）

| 题 | 模型 | 轮次 | 结果 | 类别 | 证据 |
|---|---|---|---|---|---|
| Q08 | v4-pro | r1 | wrong | 语义层差距 | IsSalesPerson 猜成 'True'，0 行；R 没有枚举值 |
| Q08 | v4-pro | r2 | wrong | 语义层差距 | IsSalesPerson 猜成 '1'，0 行；R 没有枚举值 |
| Q15 | flash | r2 | wrong | 语义层差距 | 国家按门店地理归属（3 行），参考按客户国家（29 行）；R 没有这条约定 |
| Q15 | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q15 | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q15 | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q28 | flash | r1 | wrong | 语义层差距 | 平均单价取 UnitPrice 简单平均（329.85/287.68），参考按 销售额 ÷ 数量；另为宽表 |
| Q28 | flash | r2 | wrong | 语义层差距 | 同上（简单平均） |
| Q28 | flash | r3 | wrong | 语义层差距 | 同上（简单平均） |
| Q28 | v4-pro | r2 | wrong | 语义层差距 | 线上取 FactOnlineSales（216.98），参考取全渠道表的 Online 渠道（214.10） |
| Q34 | flash | r1 | wrong | 语义层差距 | 内连接产品表丢掉缺失产品（2,220 行）；缺失产品与左连接的说明在 L1 |
| Q34 | flash | r2 | wrong | 语义层差距 | 同上 |
| Q34 | flash | r3 | wrong | 语义层差距 | 同上 |
| Q34 | v4-pro | r1 | wrong | 语义层差距 | 同上（2,220 行） |
| Q34 | v4-pro | r2 | wrong | 语义层差距 | 同上（2,220 行） |
| Q34 | v4-pro | r3 | wrong | 语义层差距 | 同上（2,233 行） |
| Q49 | flash | r1 | wrong | 语义层差距 | 只输出门店级 306 行，没有沿实体树上卷；层级结构说明在 L1 |
| Q49 | flash | r2 | wrong | 语义层差距 | 同上 |
| Q49 | flash | r3 | wrong | 语义层差距 | 同上 |
| Q49 | v4-pro | r1 | wrong | 语义层差距 | 同上（另把线上与全渠道销售相加） |
| Q49 | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q49 | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q66 | flash | r3 | wrong | 语义层差距 | 未说明渠道时用了全渠道表；约定 1（默认线上）在 L1 |
| Q66 | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q66 | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q66 | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q68（低区分度） | flash | r1 | wrong | 语义层差距 | IsHoliday 猜成 'Holiday'，只剩 1 行；R 没有枚举值 |
| Q69（低区分度） | flash | r1 | wrong | 语义层差距 | 保留了无折扣一行（2 行）；约定 10（排除无折扣）在 L1。题目已标低区分度，作答针对旧题面 |
| Q69（低区分度） | flash | r2 | wrong | 语义层差距 | 同上 |
| Q69（低区分度） | flash | r3 | wrong | 语义层差距 | 同上 |
| Q69（低区分度） | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q69（低区分度） | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q69（低区分度） | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q70 | flash | r3 | wrong | 语义层差距 | 把全渠道表和线上表相加，线上重复计算；两表关系在 L1 |
| Q73 | flash | r2 | wrong | 语义层差距 | 当前库存取全表最新日期的快照，参考按约定 11 取每个门店 × 产品最近一次快照 |
| Q73 | flash | r3 | wrong | 语义层差距 | 同上 |
| Q73 | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q73 | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q73 | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q74 | flash | r1 | wrong | 语义层差距 | 内连接产品表丢掉缺失产品（918 行），部分门店前 3 名随之改变 |
| Q74 | flash | r2 | wrong | 语义层差距 | 同上 |
| Q74 | flash | r3 | wrong | 语义层差距 | 同上 |
| Q74 | v4-pro | r3 | wrong | 语义层差距 | 用线上表（9 行），按门店的问题应走全渠道（约定 2 在 L1） |
| Q75 | v4-pro | r3 | wrong | 语义层差距 | 消费额按扣退货的净额，1,488 行对参考 1,470 行；消费额口径在 L1 |
| Q76（低区分度） | flash | r1 | wrong | 语义层差距 | 丢掉缺失产品那一组（8 行）；左连接说明在 L1 |
| Q76（低区分度） | flash | r2 | wrong | 语义层差距 | 同上 |
| Q76（低区分度） | flash | r3 | wrong | 语义层差距 | 同上 |
| Q76（低区分度） | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q76（低区分度） | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q76（低区分度） | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q80 | flash | r2 | wrong | 语义层差距 | 只算 SalesQuantity > 0 的行（988.14 对 988.28）；「全部行均算交易」的约定在 L1 |
| Q81 | flash | r3 | wrong | 语义层差距 | 终身价值扣了退货（142,511.02 对 144,060.93）；口径在 L1 |
| Q81 | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q82 | flash | r1 | wrong | 语义层差距 | 入职年限算到今天（27 年左右），约定 3 以 2009-12-31 为今天 |
| Q82 | flash | r2 | wrong | 语义层差距 | 同上 |
| Q82 | flash | r3 | wrong | 语义层差距 | 同上 |
| Q82 | v4-pro | r1 | wrong | 语义层差距 | 同上 |
| Q82 | v4-pro | r2 | wrong | 语义层差距 | 同上 |
| Q82 | v4-pro | r3 | wrong | 语义层差距 | 同上 |
| Q100 | flash | r3 | wrong | SQL 真错 | 用近似分位函数 quantile(0.9) 定门槛，109 行；同单元 r1 用 quantileExact 得 108 行 |
| Q102 | flash | r1 | wrong | 语义层差距 | 全渠道表、内连接丢缺失产品（8 行）；约定 1 与缺失产品说明在 L1 |
| Q102 | flash | r2 | wrong | 语义层差距 | 同上 |
| Q102 | flash | r3 | wrong | 语义层差距 | 「今年」按当前自然年，0 行；约定 3 在 L1 |
| Q102 | v4-pro | r1 | wrong | 语义层差距 | 全渠道表、另扣折扣、内连接（8 行） |
| Q102 | v4-pro | r2 | wrong | 语义层差距 | 「今年」按当前自然年，0 行 |
| Q102 | v4-pro | r3 | wrong | 语义层差距 | 同上 |

**按裁决判错：只给键、没给名称。** 严格口径下只因此判错的：Q117 v4-pro SQL-R r3。旧提示没要求给名称，最终口径按键核对对象后算对（上表「只给键」）。SQL-L1 没有这一类：Pro SQL-L1 Q34 r3 也只给了键，但同时漏了 4 个产品，归 SQL 真错。

暂时归不了类的：无。Pro SQL-L1 Q73 r3（差额方向）与 Q82 r3（「团队」含不含间接下属）起初归「参考问题 · 题面歧义」，用户裁决改为语义层差距：都是 L1 没写的口径选择，记为调优候选，不补参考。

### 选模型（卡片规则）

规则：Flash SQL-L1 < 50%，或 Pro 比 Flash 高 10 个百分点以上，就选 Pro；否则选 Flash。按主表（不含低区分度、judge）判。

| 口径 | Flash SQL-L1 | Pro SQL-L1 | Pro − Flash | Flash < 50%？ | Pro 高 10 点以上？ | 结论 |
|---|---|---|---|---|---|---|
| 严格 | 40/57 = 70.2% | 35/57 = 61.4% | -8.8 点 | 否 | 否 | **Flash** |
| 最终 | 49/57 = 86.0% | 48/57 = 84.2% | -1.8 点 | 否 | 否 | **Flash** |

两套数结论一致：**Flash**。

<!-- final-rescore:end -->

## 附：试跑原判定（eval-v1、旧评分器；历史，选模型不用）

- 题库：`eval-v1` = `07dca9af414295205b0ae5f4a220bda44682af71`；试跑 24 题；低区分度 ['Q17', 'Q68', 'Q76']；judge 题（单列一档，所有单元都不进准确率分母，拒答、执行报错一并拿出）['Q40']
- 运行：deepseek-flash → `runs/20261018-T12-pilot-flash-01/`；deepseek-v4-pro → `runs/20261018-T12-pilot-pro-01/`

## 准确率（correct / 确定性评分题的作答；judge 题不计）

| 模型 | 单元 | 含低区分度 | 不含低区分度（选模型用） | 首答即对（不含低区分度） |
|---|---|---|---|---|
| deepseek-flash | SQL-R | 16/69 = 23.2% | 16/60 = 26.7% | 15/60 = 25.0% |
| deepseek-flash | SQL-L1 | 34/69 = 49.3% | 30/60 = 50.0% | 24/60 = 40.0% |
| deepseek-v4-pro | SQL-R | 10/69 = 14.5% | 7/60 = 11.7% | 7/60 = 11.7% |
| deepseek-v4-pro | SQL-L1 | 25/69 = 36.2% | 20/60 = 33.3% | 18/60 = 30.0% |

## 按 Q 级（不含低区分度 / 含）

| 模型 | 单元 | Q1 | Q2 | Q3 |
|---|---|---|---|---|
| deepseek-flash | SQL-R | 9/18 = 50.0%（含 9/21 = 42.9%） | 4/21 = 19.0%（含 4/24 = 16.7%） | 3/21 = 14.3%（含 3/24 = 12.5%） |
| deepseek-flash | SQL-L1 | 13/18 = 72.2%（含 15/21 = 71.4%） | 10/21 = 47.6%（含 12/24 = 50.0%） | 7/21 = 33.3%（含 7/24 = 29.2%） |
| deepseek-v4-pro | SQL-R | 5/18 = 27.8%（含 8/21 = 38.1%） | 1/21 = 4.8%（含 1/24 = 4.2%） | 1/21 = 4.8%（含 1/24 = 4.2%） |
| deepseek-v4-pro | SQL-L1 | 15/18 = 83.3%（含 18/21 = 85.7%） | 5/21 = 23.8%（含 7/24 = 29.2%） | 0/21 = 0.0%（含 0/24 = 0.0%） |

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
| 20261018-T12-cache-flash-01 | deepseek-flash | 1 h | 3600.0 | 46080 | 183 |
| 20261018-T12-cache-flash-01 | deepseek-flash | 2 h | 7200.5 | 46080 | 183 |
| 20261018-T12-cache-flash-01 | deepseek-flash | 4 h | 14400.0 | 46080 | 183 |

结论：Flash 的前缀缓存在测到的最长间隔 4 小时仍全部命中（46,080 token），未见过期；T13 按单元连续跑，冷启动次数可按「每单元一次」估。Pro 按裁决不测。

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
