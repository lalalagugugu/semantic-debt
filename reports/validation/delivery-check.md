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
4. **还剩 1 处，没修，待用户定**：**约定 6（金额一律为美元）在 L1.5S 只有条文**。L1 里是 4 张事实表的币种列写着「只有 USD（约定 6）」，而汇总表不带币种列，没有一张表或一个指标点名约定 6。指标的 `unit: USD` 在 L1.5S 里还在，所以实际风险小（模型不会去找汇率表）。不在交接的修复范围里，没有动。
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
