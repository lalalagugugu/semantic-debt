# 通用交付检查：引用检查 + 覆盖表，以及按覆盖表修的 L1.5S 缺口（2026-10-19）

- 依据：`decisions/2026-10-19-l15s-reporting-l2-ladder-dax-checklist.md` 第一节第 3 条（汇总层交付质量合格是跨档位比较的前提）、第三节第 3 条（通用交付检查在 DAX 单元上跑通）。
- 范围：只读 `semantic/` 与渲染出的 `build/contexts/`；不读题库，不开 chDB，不调模型，0 元。
- 复现：

  ```
  uv run python render/render_all.py
  uv run python render/check_references.py     # (a) 引用检查
  uv run python render/check_conventions.py    # (b) 覆盖表 → reports/validation/delivery_coverage.md
  ```

## 结论

1. **(a) 引用检查**：10 个渲染上下文都是 0 缺口（`6f5be3e` 修了 L1.5S 的坪效、门店人均销售额两处）。DAX-L0/L1/L2、JSON-L2 也都跑过，都是 0 缺口。
2. **(b) 约定 × 档位**：L1、L1.5W、L2 的 15 条约定都落到了可见对象上。DAX-L1、DAX-L2、JSON-L2 逐格与对应的 SQL 单元相同。**L1.5S 修前有两处缺口：**
   - **约定 1（未说明渠道 = 线上销售）只有指标文字点名**。4 张 `ads_online_*` 表没有一张说自己就是约定 1 的线上销售。
   - **8 张由全渠道销售汇总的表，只有 1 张点名约定 2**，没有一张说明自己的「渠道 = Online」不是电商的线上销售。L1 里讲这件事的两段说明，`FactOnlineSales.differs_from` 和 `data_quality / online-sales-mismatch`，L1.5S 都没带过去（L1.5S 不渲染 data_quality 和 differs_from）。
   - PR #138（`reports/results/l15s-covered-analysis.md`）找到的主要失分就在这里：L1.5S 在覆盖内题上少对 22 次，其中 9 次是用全渠道表的 `渠道 = 'Online'` 代替电商销售。
3. **已修（约定 1、2）**：在 `semantic/summary/summary.yaml` 给这 12 张表的表说明末尾各加一句来源，都是追加，原文不动。
   - 4 张 `ads_online_*`：「来源：线上销售（电商订单明细）」，未说明渠道时按约定 1 用这几张表；全渠道表的 Online 渠道与它对不上，不能互相替代，也不能相加。
   - 8 张全渠道表（`ads_sales_*`、`ads_promotion_month_channel`、`ads_quota_month_channel_store_category`）：「来源：全渠道销售（约定 2）」；「渠道 = Online」是三家线上虚拟店在全渠道销售里的记录，**不是**电商的线上销售。
   - 两句里的数字（2,677,599,035.07 对 2,718,202,629.81）照抄 L1 的 `online-sales-mismatch`，没有重新测。
   - 重新渲染后**只有 `SQL-L1.5S.yaml` 变了**，其余 9 个上下文逐字节不变。L1.5S 上下文从 27,334 增到 28,300 token（`context_sizes.md`）。修后 12 张表都点名了自己那条约定，约定 1、2 在全部档位都判「对象」。
4. **约定 6（金额一律为美元）已补（用户同意，做法同约定 1、2）**：修前 L1.5S 只有条文。现在 16 张汇总表的表说明末尾各加一句：「金额一律为美元（约定 6）：来源事实表的币种只有美元，汇总表不带币种列，不需要换算。」重渲后只有 `SQL-L1.5S.yaml` 变了；`check_conventions.py` 现在 0 处缺口。
5. **(b) 汇总表 × 指标层**：L2 的 92 个可调用对象（指标 × 数据集）中：
   - 43 个在同来源的汇总表里直接存着；
   - 22 个可由一张表里的分子分母现算；
   - 3 个是维度指标，在维度视图上；
   - 24 个未自动匹配。

   未自动匹配**不等于答不了**，分三种：
   - 靠筛选列得到的，如客户分层、是否新客，表说明里写了「不另设列」；
   - 跨期、跨行才能算的，如同比、环比、占比、同店；
   - 汇总层确实没有数据的，如 IT 成本、停机。

   能否回答以 T06 的覆盖标注为准，这张表只用来对照 L2 与 L1.5S 的落点。
6. **(b) DAX × Cube**：92 个可调用对象两边都有实现，SQL-L2、JSON-L2、DAX-L2 三个上下文给出的调用写法个数一致。读法差异照 `metric-text-vs-impl.md` 引用：
   - A 类 15 个，两边选了同一种文字没写明的读法；
   - B 类 9 个，两边不一致或引擎做不到。

   B 类按 DAX 开跑前检查清单第 2 条（第四节规则）处理，本次不动。

## semantic-v1.4 第二节第 1 条：逐个核对 69 个指标的范围或变体

- 结果并入 `reports/validation/delivery_coverage.md` 第 3 节「L1 写明的范围或变体」，每个指标一行；生成脚本 `render/check_conventions.py` 的 `variant_audit`。
- 69 个指标里，13 个的 L1 文字写了范围或变体。表里引的 L1 原文，由测试核对逐字出自 `source.yaml`。
- 其中 6 个缺实现，照 L1 文字补成「变体调用名」（`semantic/metrics.yaml` 的 `variants`），共 9 个，DAX 与 Cube 各一份实现：
  - **销售额占比**：L1 写「分母的范围由问题决定（全公司、某渠道、某品类内）」，两边原来只有全公司（查询筛选后的全部）。补「渠道内」「品类内」：父组分母去掉下一层（门店，或产品与子类），其余分组和筛选不变。全渠道表补两个，线上表补「品类内」一个（线上只有一个渠道）。
  - **销售额环比增长率**：L1 写「期的长度由问题的粒度决定（月、季）」。DAX 原度量值本来就按期取，Cube 原成员固定为月。补「按季」：Cube 偏移一季，DAX 同补一个，两边对称。
  - **目标销售额、目标销量、目标毛利、计划收入**：L1 写「默认取预算场景」。DAX 原度量值在查询筛了场景时按查询取，Cube 原成员固定预算。补「按查询场景」：不套预算，场景由查询筛选。
  - 另 7 个 L1 写了的（同比、新客 3 个、同店 2 个、计划金额），已由主调用名覆盖，或属已记的引擎限制，不加变体。
- 不改 L1 文字，不加 L1 没有的口径；L2 三个上下文的 `callables` 里，变体带一个 `scope` 字段写明范围。只有 SQL-L2、JSON-L2、DAX-L2 的上下文变了，L1 系列不变。
- **打 tag 前必须实测**：
  - Cube 的父组分母是多阶段成员，用 `reduce_by` 去掉下一层的维度（含连接进来的 cube 的维度）。这类成员只能在 Cube 里运行，本地的 `verify_cube.py` 也只核普通聚合，所以要请 T16 在 Cube 上加载模型、逐个实测。
  - DAX 变体请 T17 在 Power BI 上实测。
  - `reduce_by` 引用连接 cube 的维度如果不被 Cube 接受，整个模型会加载失败，必须先实测再打 tag。

## 对运行的影响

- `semantic/summary/summary.yaml` 属于语义层内容，现有的 `--semantic-tag` 校验会拒绝在这份内容上开跑 L1.5S，需要新 tag。tag 名由协调会话定（phase1-replan 第四节的「不出 semantic-v1.4」说的是 L1 文字，这次改的是 L1.5S 文档）。
- 按裁决第一节第 3 条，L1.5S 覆盖内题的数字修前、修后都要报。修前就是 T13 现有的结果。修后要重跑 SQL-L1.5S（覆盖内题即可），预算由用户批。

## 产物

| 文件 | 内容 |
|---|---|
| `render/check_references.py` | (a) 引用检查（`6f5be3e`） |
| `render/check_conventions.py` | (b) 三张覆盖表；任一单元有「仅条文」的约定、或销售汇总表没点名来源时，退出码 1 |
| `reports/validation/delivery_coverage.md` | (b) 的生成报告（三张表全文） |
| `semantic/summary/summary.yaml` | 12 张销售汇总表的来源说明 |
| `tests/test_render.py` | 新增 3 个测试：引用写法解析、判定与选表检查的合成用例、真实上下文上约定 1、2 与 DAX × Cube 的检查 |
