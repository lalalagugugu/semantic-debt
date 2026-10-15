-- L1.5S 汇总层（ADS 风格）
--
-- 规矩（任务卡 T08 交付物 3）：
--   * 每张汇总表对应 semantic/summary/requirements.md 里的一份或几份报表；
--     **不为「可能被问到的问题」建表**。
--   * 只汇总 semantic/source.yaml 的 metrics 节里已定义过的指标，没有新口径。
--   * 比率**同时存分子和分母**，不存比率本身（各行的比率不能相加）。
--   * 去重计数（客户数、订单数、门店数、产品数、有销售天数）标明「不能跨行相加」，
--     说明写在 summary.yaml 的列描述里。
--   * 维度属性（名称、层级、面积、员工数）反范式化进汇总表。
--   * `ads` 库里**不得出现任何明细事实表**；维度另建视图。
--
-- 产品维度缺 284 行而事实表引用了这些键（source.yaml 的 data_quality / missing-products）。
-- 所有按产品层级汇总的表都用 `LEFT JOIN` + `SETTINGS join_use_nulls = 1`，把未命中的
-- 产品归到一个明确的「未知（产品维度缺行）」组，这样各组之和仍然等于大盘
-- （实测未命中 338,898 行，与孤儿行数完全一致）。
--
-- 重建与核对：uv run python render/build_summary.py
-- 冻结：G1 打 tag `semantic-v1` 之后不得再改。

-- 整库重建。用 DROP DATABASE 而不是逐表 DROP：改了粒度、删掉一张表之后，
-- 逐表 DROP 会把上一版的表留在 ads 里（实测踩过：T03 拆成两张之后，旧的
-- ads_plan_month_store_category_account 还在，而它正是那张不该存在的明细表）。
-- ads 完全可由本文件重建，整库删掉没有风险。
DROP DATABASE IF EXISTS ads;
CREATE DATABASE ads;

-- ===========================================================================
-- 维度视图（`ads` 库里只放汇总表和维度，明细事实表不在这里）
-- ===========================================================================

CREATE OR REPLACE VIEW ads.dim_date AS
SELECT
    DateKey                   AS `日期`,
    CalendarYear              AS `年`,
    MonthNumber               AS `月`,
    CalendarMonthLabel        AS `月名`,
    CalendarQuarterLabel      AS `季度`,
    CalendarHalfYearLabel     AS `半年`,
    CalendarWeekLabel         AS `周`,
    toMonday(DateKey)         AS `周起始日`,
    toStartOfMonth(DateKey)   AS `月起始日`,
    toStartOfQuarter(DateKey) AS `季起始日`,
    CalendarDayOfWeekLabel    AS `星期`,
    CalendarDayOfWeekNumber   AS `星期序号`,
    IsWorkDay                 AS `是否工作日`,
    IsHoliday                 AS `是否节假日`,
    EuropeSeason              AS `欧洲季节`,
    NorthAmericaSeason        AS `北美季节`,
    AsiaSeason                AS `亚洲季节`
FROM retail.DimDate;

CREATE OR REPLACE VIEW ads.dim_channel AS
SELECT ChannelKey AS `渠道键`, ChannelName AS `渠道`
FROM retail.DimChannel;

CREATE OR REPLACE VIEW ads.dim_store AS
SELECT
    s.StoreKey                            AS `门店键`,
    s.StoreName                           AS `门店名`,
    s.StoreType                           AS `门店类型`,
    s.Status                              AS `门店状态`,
    s.OpenDate                            AS `门店开业日`,
    s.SellingAreaSize                     AS `门店营业面积`,
    s.EmployeeCount                       AS `门店员工数`,
    concat(e.FirstName, ' ', e.LastName)  AS `门店经理`,
    e.Title                               AS `门店经理职级`,
    g.CityName                            AS `门店城市`,
    g.StateProvinceName                   AS `门店省州`,
    g.RegionCountryName                   AS `门店国家`,
    g.ContinentName                       AS `门店大洲`
FROM retail.DimStore AS s
LEFT JOIN retail.DimEmployee  AS e ON toInt32(s.EmployeeKey) = e.EmployeeKey
LEFT JOIN retail.DimGeography AS g ON s.GeographyKey = g.GeographyKey;

CREATE OR REPLACE VIEW ads.dim_product AS
SELECT
    p.ProductKey                 AS `产品键`,
    p.ProductName                AS `产品名`,
    p.BrandName                  AS `品牌`,
    p.Manufacturer               AS `厂商`,
    p.ColorName                  AS `颜色`,
    p.ClassName                  AS `产品档位`,
    p.StockTypeName              AS `备货档位`,
    p.UnitPrice                  AS `产品标价`,
    p.UnitCost                   AS `产品单位成本`,
    p.Status                     AS `产品状态`,
    psc.ProductSubcategoryName   AS `子类`,
    pc.ProductCategoryName       AS `品类`
FROM retail.DimProduct AS p
LEFT JOIN retail.DimProductSubcategory AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT JOIN retail.DimProductCategory    AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey;

CREATE OR REPLACE VIEW ads.dim_product_category AS
SELECT ProductCategoryKey AS `品类键`, ProductCategoryName AS `品类`
FROM retail.DimProductCategory;

CREATE OR REPLACE VIEW ads.dim_promotion AS
SELECT
    PromotionKey      AS `促销键`,
    PromotionName     AS `促销名`,
    DiscountPercent   AS `名义折扣率`,
    PromotionType     AS `促销类型`,
    PromotionKey != 1 AS `是否打折促销`
FROM retail.DimPromotion;

CREATE OR REPLACE VIEW ads.dim_scenario AS
SELECT ScenarioKey AS `场景键`, ScenarioName AS `场景`
FROM retail.DimScenario;

CREATE OR REPLACE VIEW ads.dim_account AS
SELECT
    AccountKey                    AS `科目键`,
    AccountName                   AS `科目`,
    AccountType                   AS `科目方向`,
    ParentAccountKey IS NOT NULL  AS `科目有父级`
FROM retail.DimAccount;

CREATE OR REPLACE VIEW ads.dim_customer AS
SELECT
    c.CustomerKey         AS `客户键`,
    c.Gender              AS `客户性别`,
    c.MaritalStatus       AS `客户婚姻状况`,
    c.Education           AS `客户学历`,
    c.Occupation          AS `客户职业`,
    c.YearlyIncome        AS `客户年收入档`,
    c.TotalChildren       AS `客户子女数`,
    c.HouseOwnerFlag      AS `客户是否有房`,
    g.CityName            AS `客户城市`,
    g.StateProvinceName   AS `客户省州`,
    g.RegionCountryName   AS `客户国家`,
    g.ContinentName       AS `客户大洲`
FROM retail.DimCustomer AS c
LEFT JOIN retail.DimGeography AS g ON c.GeographyKey = g.GeographyKey;


-- ===========================================================================
-- T01 集团经营月报（R01）
--    粒度：月 × 渠道
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_sales_month_channel;
CREATE TABLE ads.ads_sales_month_channel
ENGINE = MergeTree ORDER BY (`月起始日`, `渠道`) AS
SELECT
    toStartOfMonth(f.DateKey)                           AS `月起始日`,
    toYear(f.DateKey)                                   AS `年`,
    toMonth(f.DateKey)                                  AS `月`,
    ch.ChannelName                                      AS `渠道`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(f.ReturnQuantity)                               AS `退货数量`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.ReturnAmount, 6))            AS `净销售额`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    sum(toDecimal128(f.DiscountAmount, 6))                               AS `折扣金额`,
    sum(toDecimal128(f.DiscountAmount, 6)) + sum(toDecimal128(f.SalesAmount, 6))          AS `折扣前原价`,
    sumIf(toDecimal128(f.SalesAmount, 6), f.PromotionKey != 1)           AS `打折销售额`,
    uniqExact(f.DateKey)                                AS `有销售天数`,
    uniqExact(f.StoreKey)                               AS `门店数`,
    uniqExact(f.ProductKey)                             AS `产品数`
FROM retail.FactSales AS f
INNER JOIN retail.DimChannel AS ch ON f.channelKey = ch.ChannelKey
GROUP BY `月起始日`, `年`, `月`, `渠道`;

-- ===========================================================================
-- T02 渠道与区域周报（R02）
--    粒度：周 × 渠道 × 门店国家
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_sales_week_channel_country;
CREATE TABLE ads.ads_sales_week_channel_country
ENGINE = MergeTree ORDER BY (`周起始日`, `渠道`, `门店国家`) AS
SELECT
    toMonday(f.DateKey)                                 AS `周起始日`,
    toYear(f.DateKey)                                   AS `年`,
    ch.ChannelName                                      AS `渠道`,
    g.ContinentName                                     AS `门店大洲`,
    g.RegionCountryName                                 AS `门店国家`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(f.ReturnQuantity)                               AS `退货数量`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    uniqExact(f.DateKey)                                AS `有销售天数`,
    uniqExact(f.StoreKey)                               AS `门店数`
FROM retail.FactSales AS f
INNER JOIN retail.DimChannel   AS ch ON f.channelKey = ch.ChannelKey
INNER JOIN retail.DimStore     AS s  ON f.StoreKey = s.StoreKey
INNER JOIN retail.DimGeography AS g  ON s.GeographyKey = g.GeographyKey
GROUP BY `周起始日`, `年`, `渠道`, `门店大洲`, `门店国家`;

-- ===========================================================================
-- T03a 预算执行月报 · 按门店（R03）
--    粒度：月 × 门店 × 科目 × 场景
--    为什么不含品类：战略计划事实表的粒度就是 月 × 实体 × 场景 × 科目 × 品类，而实体与
--    门店一一对应。把品类留在粒度里，汇总表会和事实表一样是 2,750,628 行——那就是明细
--    事实表换了个列名，违反「ads 库里不得出现任何明细事实表」。品类视角另出 T03b。
--    场景和科目必须留在粒度里（约定 12：不筛会把三份金额、收入与费用加在一起）。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_plan_month_store_account;
CREATE TABLE ads.ads_plan_month_store_account
ENGINE = MergeTree ORDER BY (`月起始日`, `场景`, `科目`, `门店名`) AS
SELECT
    sp.DateKey                                AS `月起始日`,
    toYear(sp.DateKey)                        AS `年`,
    toMonth(sp.DateKey)                       AS `月`,
    sc.ScenarioName                           AS `场景`,
    a.AccountName                             AS `科目`,
    a.AccountType                             AS `科目方向`,
    a.ParentAccountKey IS NOT NULL            AS `科目有父级`,
    s.StoreName                               AS `门店名`,
    s.StoreType                               AS `门店类型`,
    ent.ParentEntityLabel                     AS `门店所属上级`,
    g.RegionCountryName                       AS `门店国家`,
    g.ContinentName                           AS `门店大洲`,
    sum(toDecimal128(sp.Amount, 6))           AS `计划金额`
FROM retail.FactStrategyPlan AS sp
INNER JOIN retail.DimScenario  AS sc  ON sp.ScenarioKey = sc.ScenarioKey
INNER JOIN retail.DimAccount   AS a   ON sp.AccountKey = a.AccountKey
INNER JOIN retail.DimEntity    AS ent ON sp.EntityKey = ent.EntityKey
INNER JOIN retail.DimStore     AS s   ON sp.EntityKey = toInt32(s.EntityKey)
INNER JOIN retail.DimGeography AS g   ON s.GeographyKey = g.GeographyKey
GROUP BY `月起始日`, `年`, `月`, `场景`, `科目`, `科目方向`, `科目有父级`,
         `门店名`, `门店类型`, `门店所属上级`, `门店国家`, `门店大洲`;

-- ===========================================================================
-- T03b 预算执行月报 · 按品类（R03）
--    粒度：月 × 品类 × 科目 × 场景。集团层面按品类看损益计划，不到门店。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_plan_month_category_account;
CREATE TABLE ads.ads_plan_month_category_account
ENGINE = MergeTree ORDER BY (`月起始日`, `场景`, `科目`, `品类`) AS
SELECT
    sp.DateKey                                AS `月起始日`,
    toYear(sp.DateKey)                        AS `年`,
    toMonth(sp.DateKey)                       AS `月`,
    sc.ScenarioName                           AS `场景`,
    a.AccountName                             AS `科目`,
    a.AccountType                             AS `科目方向`,
    a.ParentAccountKey IS NOT NULL            AS `科目有父级`,
    pc.ProductCategoryName                    AS `品类`,
    sum(toDecimal128(sp.Amount, 6))           AS `计划金额`
FROM retail.FactStrategyPlan AS sp
INNER JOIN retail.DimScenario        AS sc ON sp.ScenarioKey = sc.ScenarioKey
INNER JOIN retail.DimAccount         AS a  ON sp.AccountKey = a.AccountKey
INNER JOIN retail.DimProductCategory AS pc ON sp.ProductCategoryKey = pc.ProductCategoryKey
GROUP BY `月起始日`, `年`, `月`, `场景`, `科目`, `科目方向`, `科目有父级`, `品类`;

-- ===========================================================================
-- T04 销售目标达成月报（R04）
--    粒度：月 × 渠道 × 门店 × 品类
--    实际（全渠道销售）与目标（销售目标表的预算场景）在同一张表上，分子分母都存。
--    两边都按「未知（产品维度缺行）」保全总额；用 FULL OUTER JOIN，哪一边有行都不丢。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_quota_month_channel_store_category;
CREATE TABLE ads.ads_quota_month_channel_store_category
ENGINE = MergeTree ORDER BY (`月起始日`, `渠道`, `门店名`, `品类`) AS
WITH actual AS (
    SELECT
        toStartOfMonth(f.DateKey)                                  AS m,
        ch.ChannelName                                             AS channel,
        s.StoreName                                                AS store,
        s.StoreType                                                AS store_type,
        g.RegionCountryName                                        AS country,
        coalesce(pc.ProductCategoryName, '未知（产品维度缺行）')    AS category,
        sum(toDecimal128(f.SalesAmount, 6))                                         AS sales_amount,
        sum(f.SalesQuantity)                                       AS sales_qty,
        sum(toDecimal128(f.TotalCost, 6))                                           AS total_cost
    FROM retail.FactSales AS f
    INNER JOIN retail.DimChannel           AS ch  ON f.channelKey = ch.ChannelKey
    INNER JOIN retail.DimStore             AS s   ON f.StoreKey = s.StoreKey
    INNER JOIN retail.DimGeography         AS g   ON s.GeographyKey = g.GeographyKey
    LEFT  JOIN retail.DimProduct           AS p   ON f.ProductKey = p.ProductKey
    LEFT  JOIN retail.DimProductSubcategory AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
    LEFT  JOIN retail.DimProductCategory   AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
    GROUP BY m, channel, store, store_type, country, category
),
quota AS (
    SELECT
        q.DateKey                                                  AS m,
        ch.ChannelName                                             AS channel,
        s.StoreName                                                AS store,
        s.StoreType                                                AS store_type,
        g.RegionCountryName                                        AS country,
        coalesce(pc.ProductCategoryName, '未知（产品维度缺行）')    AS category,
        sum(toDecimal128(q.SalesAmountQuota, 6))                                    AS amount_quota,
        sum(toDecimal128(q.SalesQuantityQuota, 6))                                  AS qty_quota,
        sum(toDecimal128(q.GrossMarginQuota, 6))                                    AS margin_quota
    FROM retail.FactSalesQuota AS q
    INNER JOIN retail.DimScenario          AS sc  ON q.ScenarioKey = sc.ScenarioKey
    INNER JOIN retail.DimChannel           AS ch  ON q.ChannelKey = ch.ChannelKey
    INNER JOIN retail.DimStore             AS s   ON q.StoreKey = s.StoreKey
    INNER JOIN retail.DimGeography         AS g   ON s.GeographyKey = g.GeographyKey
    LEFT  JOIN retail.DimProduct           AS p   ON q.ProductKey = p.ProductKey
    LEFT  JOIN retail.DimProductSubcategory AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
    LEFT  JOIN retail.DimProductCategory   AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
    WHERE sc.ScenarioName = 'Budget'
    GROUP BY m, channel, store, store_type, country, category
)
-- FULL OUTER JOIN + join_use_nulls = 1 让两边的列都成了 Nullable 类型，
-- 而 MergeTree 的排序键不接受 Nullable 列。coalesce 之后一定非空
-- （外连接保证至少有一边有行），所以用 assumeNotNull 把类型摘回来。
SELECT
    assumeNotNull(coalesce(a.m, q.m))                   AS `月起始日`,
    toYear(assumeNotNull(coalesce(a.m, q.m)))           AS `年`,
    toMonth(assumeNotNull(coalesce(a.m, q.m)))          AS `月`,
    assumeNotNull(coalesce(a.channel, q.channel))       AS `渠道`,
    assumeNotNull(coalesce(a.store, q.store))           AS `门店名`,
    assumeNotNull(coalesce(a.store_type, q.store_type)) AS `门店类型`,
    assumeNotNull(coalesce(a.country, q.country))       AS `门店国家`,
    assumeNotNull(coalesce(a.category, q.category))     AS `品类`,
    assumeNotNull(coalesce(a.sales_amount, 0))          AS `销售额`,
    assumeNotNull(coalesce(a.sales_qty, 0))             AS `销售数量`,
    assumeNotNull(coalesce(a.total_cost, 0))            AS `总成本`,
    assumeNotNull(coalesce(q.amount_quota, 0))          AS `目标销售额`,
    assumeNotNull(coalesce(q.qty_quota, 0))             AS `目标销量`,
    assumeNotNull(coalesce(q.margin_quota, 0))          AS `目标毛利`
FROM actual AS a
FULL OUTER JOIN quota AS q
    ON  a.m = q.m AND a.channel = q.channel AND a.store = q.store
    AND a.country = q.country AND a.category = q.category AND a.store_type = q.store_type
SETTINGS join_use_nulls = 1;

-- ===========================================================================
-- T05 门店经营月报（R05）
--    粒度：月 × 门店。坪效和人均的分母（营业面积、员工数）反范式化进来。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_sales_month_store;
CREATE TABLE ads.ads_sales_month_store
ENGINE = MergeTree ORDER BY (`月起始日`, `门店名`) AS
SELECT
    toStartOfMonth(f.DateKey)                           AS `月起始日`,
    toYear(f.DateKey)                                   AS `年`,
    toMonth(f.DateKey)                                  AS `月`,
    s.StoreName                                         AS `门店名`,
    s.StoreType                                         AS `门店类型`,
    s.Status                                            AS `门店状态`,
    ch.ChannelName                                      AS `渠道`,
    concat(e.FirstName, ' ', e.LastName)                AS `门店经理`,
    e.Title                                             AS `门店经理职级`,
    g.CityName                                          AS `门店城市`,
    g.StateProvinceName                                 AS `门店省州`,
    g.RegionCountryName                                 AS `门店国家`,
    g.ContinentName                                     AS `门店大洲`,
    any(s.SellingAreaSize)                              AS `门店营业面积`,
    any(s.EmployeeCount)                                AS `门店员工数`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(f.ReturnQuantity)                               AS `退货数量`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.ReturnAmount, 6))            AS `净销售额`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    sum(toDecimal128(f.DiscountAmount, 6))                               AS `折扣金额`,
    uniqExact(f.DateKey)                                AS `有销售天数`,
    uniqExact(f.ProductKey)                             AS `产品数`
FROM retail.FactSales AS f
INNER JOIN retail.DimStore     AS s  ON f.StoreKey = s.StoreKey
INNER JOIN retail.DimChannel   AS ch ON f.channelKey = ch.ChannelKey
INNER JOIN retail.DimGeography AS g  ON s.GeographyKey = g.GeographyKey
LEFT  JOIN retail.DimEmployee  AS e  ON toInt32(s.EmployeeKey) = e.EmployeeKey
GROUP BY `月起始日`, `年`, `月`, `门店名`, `门店类型`, `门店状态`, `渠道`,
         `门店经理`, `门店经理职级`, `门店城市`, `门店省州`, `门店国家`, `门店大洲`;

-- ===========================================================================
-- T06 门店年度汇总（R05 的同店口径用）
--    粒度：年 × 门店。
--    约定 15 的同店只比较「两个对比年份都有销售的门店」，这是一个关于**年份对**的条件，
--    放不进月报的一行里。所以单出这张年 × 门店表：报表侧自连接两个年份、取两边都有行的
--    门店，就得到同店口径，而且不写死具体年份。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_sales_year_store;
CREATE TABLE ads.ads_sales_year_store
ENGINE = MergeTree ORDER BY (`年`, `门店名`) AS
SELECT
    toYear(f.DateKey)                                   AS `年`,
    s.StoreName                                         AS `门店名`,
    s.StoreType                                         AS `门店类型`,
    ch.ChannelName                                      AS `渠道`,
    g.RegionCountryName                                 AS `门店国家`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    uniqExact(f.DateKey)                                AS `有销售天数`
FROM retail.FactSales AS f
INNER JOIN retail.DimStore     AS s  ON f.StoreKey = s.StoreKey
INNER JOIN retail.DimChannel   AS ch ON f.channelKey = ch.ChannelKey
INNER JOIN retail.DimGeography AS g  ON s.GeographyKey = g.GeographyKey
GROUP BY `年`, `门店名`, `门店类型`, `渠道`, `门店国家`;

-- ===========================================================================
-- T07 门店日销周报（R06）
--    粒度：日 × 门店。全清单里最细的一张（约 33 万行），仍然是汇总
--    （原始事实表按天 × 店 × 品 × 促销，340 万行）。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_sales_day_store;
CREATE TABLE ads.ads_sales_day_store
ENGINE = MergeTree ORDER BY (`日期`, `门店名`) AS
SELECT
    f.DateKey                                           AS `日期`,
    toYear(f.DateKey)                                   AS `年`,
    toMonth(f.DateKey)                                  AS `月`,
    toMonday(f.DateKey)                                 AS `周起始日`,
    d.CalendarDayOfWeekLabel                            AS `星期`,
    d.CalendarDayOfWeekNumber                           AS `星期序号`,
    d.IsWorkDay                                         AS `是否工作日`,
    d.IsHoliday                                         AS `是否节假日`,
    d.EuropeSeason                                      AS `欧洲季节`,
    d.NorthAmericaSeason                                AS `北美季节`,
    d.AsiaSeason                                        AS `亚洲季节`,
    s.StoreName                                         AS `门店名`,
    s.StoreType                                         AS `门店类型`,
    ch.ChannelName                                      AS `渠道`,
    g.RegionCountryName                                 AS `门店国家`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(f.ReturnQuantity)                               AS `退货数量`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.ReturnAmount, 6))            AS `净销售额`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    sum(toDecimal128(f.DiscountAmount, 6))                               AS `折扣金额`
FROM retail.FactSales AS f
INNER JOIN retail.DimDate      AS d  ON f.DateKey = d.DateKey
INNER JOIN retail.DimStore     AS s  ON f.StoreKey = s.StoreKey
INNER JOIN retail.DimChannel   AS ch ON f.channelKey = ch.ChannelKey
INNER JOIN retail.DimGeography AS g  ON s.GeographyKey = g.GeographyKey
GROUP BY `日期`, `年`, `月`, `周起始日`, `星期`, `星期序号`, `是否工作日`, `是否节假日`,
         `欧洲季节`, `北美季节`, `亚洲季节`, `门店名`, `门店类型`, `渠道`, `门店国家`;

-- ===========================================================================
-- T08 电商运营周报（R07）
--    粒度：周 × 线上店。订单数和客户数是去重计数，**不能跨行相加**
--    （实测有 2,034 个订单号挂在多个客户上）：全站的值要重新按全站粒度算，
--    不能把三家线上店的值加起来。所以另出一张全站周表 T09。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_online_week_store;
CREATE TABLE ads.ads_online_week_store
ENGINE = MergeTree ORDER BY (`周起始日`, `线上店名`) AS
SELECT
    toMonday(f.DateKey)                                 AS `周起始日`,
    toYear(f.DateKey)                                   AS `年`,
    s.StoreName                                         AS `线上店名`,
    g.ContinentName                                     AS `线上店大洲`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(f.ReturnQuantity)                               AS `退货数量`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.ReturnAmount, 6))            AS `净销售额`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    sum(toDecimal128(f.DiscountAmount, 6))                               AS `折扣金额`,
    sum(toDecimal128(f.DiscountAmount, 6)) + sum(toDecimal128(f.SalesAmount, 6))          AS `折扣前原价`,
    sumIf(toDecimal128(f.SalesAmount, 6), f.PromotionKey != 1)           AS `打折销售额`,
    count()                                             AS `订单行数`,
    uniqExact(f.SalesOrderNumber)                       AS `订单数`,
    uniqExact(f.CustomerKey)                            AS `客户数`,
    uniqExact(f.DateKey)                                AS `有销售天数`
FROM retail.FactOnlineSales AS f
INNER JOIN retail.DimStore     AS s ON f.StoreKey = s.StoreKey
INNER JOIN retail.DimGeography AS g ON s.GeographyKey = g.GeographyKey
GROUP BY `周起始日`, `年`, `线上店名`, `线上店大洲`;

-- ===========================================================================
-- T09 电商全站周报（R07 的总行）
--    粒度：周。去重计数在全站粒度上重新算，供报表直接取总行用。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_online_week_total;
CREATE TABLE ads.ads_online_week_total
ENGINE = MergeTree ORDER BY `周起始日` AS
SELECT
    toMonday(DateKey)                                   AS `周起始日`,
    toYear(DateKey)                                     AS `年`,
    sum(toDecimal128(SalesAmount, 6))                                    AS `销售额`,
    sum(SalesQuantity)                                  AS `销售数量`,
    sum(toDecimal128(ReturnAmount, 6))                                   AS `退货金额`,
    sum(ReturnQuantity)                                 AS `退货数量`,
    sum(toDecimal128(SalesAmount, 6)) - sum(toDecimal128(ReturnAmount, 6))                AS `净销售额`,
    sum(toDecimal128(TotalCost, 6))                                      AS `总成本`,
    sum(toDecimal128(SalesAmount, 6)) - sum(toDecimal128(TotalCost, 6))                   AS `毛利`,
    sum(toDecimal128(DiscountAmount, 6))                                 AS `折扣金额`,
    count()                                             AS `订单行数`,
    uniqExact(SalesOrderNumber)                         AS `订单数`,
    uniqExact(CustomerKey)                              AS `客户数`,
    uniqExact(DateKey)                                  AS `有销售天数`
FROM retail.FactOnlineSales
GROUP BY `周起始日`, `年`;

-- ===========================================================================
-- T10 电商客户月报（R08）
--    粒度：月 × 客户分层 × 是否新客
--    客户分层按约定 13（以 2009-12-31 为基准日，是客户的固定属性）；
--    是否新客按约定 14（首次购买日落在当月最后一天往前 90 天内，逐月判定）。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_online_customer_month_tier;
CREATE TABLE ads.ads_online_customer_month_tier
ENGINE = MergeTree ORDER BY (`月起始日`, `客户分层`, `是否新客`) AS
WITH customer_profile AS (
    SELECT
        CustomerKey,
        min(DateKey) AS first_buy,
        dateDiff('month', max(DateKey), toDate('2009-12-31')) AS recency_months
    FROM retail.FactOnlineSales
    GROUP BY CustomerKey
)
SELECT
    toStartOfMonth(f.DateKey)                                   AS `月起始日`,
    toYear(f.DateKey)                                           AS `年`,
    toMonth(f.DateKey)                                          AS `月`,
    multiIf(cp.recency_months <= 6, '活跃',
            cp.recency_months <= 12, '有流失风险',
            '已流失')                                            AS `客户分层`,
    cp.first_buy > toDate(toLastDayOfMonth(f.DateKey)) - 90
        AND cp.first_buy <= toLastDayOfMonth(f.DateKey)          AS `是否新客`,
    sum(toDecimal128(f.SalesAmount, 6))                                          AS `销售额`,
    sum(f.SalesQuantity)                                        AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                         AS `退货金额`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.ReturnAmount, 6))                    AS `净销售额`,
    sum(toDecimal128(f.TotalCost, 6))                                            AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))                       AS `毛利`,
    count()                                                     AS `订单行数`,
    uniqExact(f.SalesOrderNumber)                               AS `订单数`,
    uniqExact(f.CustomerKey)                                    AS `客户数`
FROM retail.FactOnlineSales AS f
INNER JOIN customer_profile AS cp ON f.CustomerKey = cp.CustomerKey
GROUP BY `月起始日`, `年`, `月`, `客户分层`, `是否新客`;

-- ===========================================================================
-- T11 客户画像季报（R09）
--    粒度：季 × 客户属性 × 客户国家（按**客户所在地**，约定 5 的默认分支）
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_online_customer_profile_quarter;
CREATE TABLE ads.ads_online_customer_profile_quarter
ENGINE = MergeTree ORDER BY (`季起始日`, `客户性别`, `客户学历`, `客户职业`) AS
-- MergeTree 的排序键不接受 Nullable 列，而 DimCustomer 的这几列在建表语句里是
-- Nullable(String)。实测空值率都是 0%（semantic/profiling/out/columns.md），
-- 所以用 coalesce 兜一个 '未填写' 既满足类型要求、又不会把真实取值改掉：
-- 数据里没有这种行，这个组不会出现。不用 assumeNotNull，万一以后有空值它会给出垃圾值。
SELECT
    toStartOfQuarter(f.DateKey)                         AS `季起始日`,
    toYear(f.DateKey)                                   AS `年`,
    toQuarter(f.DateKey)                                AS `季`,
    coalesce(c.Gender, '未填写')                         AS `客户性别`,
    coalesce(c.MaritalStatus, '未填写')                  AS `客户婚姻状况`,
    coalesce(c.Education, '未填写')                      AS `客户学历`,
    coalesce(c.Occupation, '未填写')                     AS `客户职业`,
    c.YearlyIncome                                      AS `客户年收入档`,
    g.ContinentName                                     AS `客户大洲`,
    g.RegionCountryName                                 AS `客户国家`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                 AS `退货金额`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`,
    count()                                             AS `订单行数`,
    uniqExact(f.SalesOrderNumber)                       AS `订单数`,
    uniqExact(f.CustomerKey)                            AS `客户数`
FROM retail.FactOnlineSales AS f
INNER JOIN retail.DimCustomer  AS c ON f.CustomerKey = c.CustomerKey
INNER JOIN retail.DimGeography AS g ON c.GeographyKey = g.GeographyKey
GROUP BY `季起始日`, `年`, `季`, `客户性别`, `客户婚姻状况`, `客户学历`,
         `客户职业`, `客户年收入档`, `客户大洲`, `客户国家`;

-- ===========================================================================
-- T12 商品销售月报（R10）
--    粒度：月 × 品类 × 子类 × 品牌 × 渠道
--    产品维度缺行的那些事实行归到「未知（产品维度缺行）」，各组之和仍等于大盘。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_sales_month_product;
CREATE TABLE ads.ads_sales_month_product
ENGINE = MergeTree ORDER BY (`月起始日`, `品类`, `子类`, `品牌`, `渠道`) AS
SELECT
    toStartOfMonth(f.DateKey)                                   AS `月起始日`,
    toYear(f.DateKey)                                           AS `年`,
    toMonth(f.DateKey)                                          AS `月`,
    ch.ChannelName                                              AS `渠道`,
    coalesce(pc.ProductCategoryName, '未知（产品维度缺行）')      AS `品类`,
    coalesce(psc.ProductSubcategoryName, '未知（产品维度缺行）')  AS `子类`,
    coalesce(p.BrandName, '未知（产品维度缺行）')                 AS `品牌`,
    coalesce(p.Manufacturer, '未知（产品维度缺行）')              AS `厂商`,
    sum(toDecimal128(f.SalesAmount, 6))                                          AS `销售额`,
    sum(f.SalesQuantity)                                        AS `销售数量`,
    sum(toDecimal128(f.ReturnAmount, 6))                                         AS `退货金额`,
    sum(f.ReturnQuantity)                                       AS `退货数量`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.ReturnAmount, 6))                    AS `净销售额`,
    sum(toDecimal128(f.TotalCost, 6))                                            AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))                       AS `毛利`,
    sum(toDecimal128(f.DiscountAmount, 6))                                       AS `折扣金额`,
    sum(toDecimal128(f.DiscountAmount, 6)) + sum(toDecimal128(f.SalesAmount, 6))                  AS `折扣前原价`,
    sumIf(toDecimal128(f.SalesAmount, 6), f.PromotionKey != 1)                   AS `打折销售额`,
    uniqExact(f.ProductKey)                                     AS `产品数`
FROM retail.FactSales AS f
INNER JOIN retail.DimChannel            AS ch  ON f.channelKey = ch.ChannelKey
LEFT  JOIN retail.DimProduct            AS p   ON f.ProductKey = p.ProductKey
LEFT  JOIN retail.DimProductSubcategory AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT  JOIN retail.DimProductCategory    AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
GROUP BY `月起始日`, `年`, `月`, `渠道`, `品类`, `子类`, `品牌`, `厂商`
SETTINGS join_use_nulls = 1;

-- ===========================================================================
-- T13 库存周报（R11 第一张）
--    粒度：快照日 × 门店 × 品类
--    **半可加**：库存不能跨快照日相加（约定 11）。要看趋势只能逐快照日看。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_inventory_week_store_category;
CREATE TABLE ads.ads_inventory_week_store_category
ENGINE = MergeTree ORDER BY (`快照日期`, `门店名`, `品类`) AS
SELECT
    i.DateKey                                                   AS `快照日期`,
    toYear(i.DateKey)                                           AS `年`,
    toMonth(i.DateKey)                                          AS `月`,
    s.StoreName                                                 AS `门店名`,
    s.StoreType                                                 AS `门店类型`,
    g.RegionCountryName                                         AS `门店国家`,
    coalesce(pc.ProductCategoryName, '未知（产品维度缺行）')      AS `品类`,
    sum(i.OnHandQuantity)                                       AS `在手数量`,
    sum(toDecimal128(i.OnHandQuantity, 6) * toDecimal128(i.UnitCost, 6))                          AS `在手库存金额`,
    sum(i.OnOrderQuantity)                                      AS `在订数量`,
    sum(i.SafetyStockQuantity)                                  AS `安全库存数量`,
    countIf(i.OnHandQuantity < i.SafetyStockQuantity)           AS `低于安全库存的门店产品数`
FROM retail.FactInventory AS i
INNER JOIN retail.DimStore              AS s   ON i.StoreKey = s.StoreKey
INNER JOIN retail.DimGeography          AS g   ON s.GeographyKey = g.GeographyKey
LEFT  JOIN retail.DimProduct            AS p   ON i.ProductKey = p.ProductKey
LEFT  JOIN retail.DimProductSubcategory AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT  JOIN retail.DimProductCategory    AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
GROUP BY `快照日期`, `年`, `月`, `门店名`, `门店类型`, `门店国家`, `品类`
SETTINGS join_use_nulls = 1;

-- ===========================================================================
-- T14 当前库存（R11 第二张）
--    粒度：门店 × 品类，取每个门店 × 产品**最近一次**快照后再汇总（约定 11）。
--    不带日期维度——「当前」只有一个。各门店 × 产品的最后一次快照不在同一天，
--    所以这张表的行里混着不同的快照日，另存一列「最早 / 最晚快照日」说明覆盖区间。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_inventory_current_store_category;
CREATE TABLE ads.ads_inventory_current_store_category
ENGINE = MergeTree ORDER BY (`门店名`, `品类`) AS
WITH latest AS (
    SELECT StoreKey, ProductKey, max(DateKey) AS d
    FROM retail.FactInventory
    GROUP BY StoreKey, ProductKey
)
SELECT
    s.StoreName                                                 AS `门店名`,
    s.StoreType                                                 AS `门店类型`,
    g.RegionCountryName                                         AS `门店国家`,
    g.ContinentName                                             AS `门店大洲`,
    coalesce(pc.ProductCategoryName, '未知（产品维度缺行）')      AS `品类`,
    min(i.DateKey)                                              AS `最早快照日`,
    max(i.DateKey)                                              AS `最晚快照日`,
    sum(i.OnHandQuantity)                                       AS `在手数量`,
    sum(toDecimal128(i.OnHandQuantity, 6) * toDecimal128(i.UnitCost, 6))                          AS `在手库存金额`,
    sum(i.OnOrderQuantity)                                      AS `在订数量`,
    sum(i.SafetyStockQuantity)                                  AS `安全库存数量`,
    countIf(i.OnHandQuantity < i.SafetyStockQuantity)           AS `低于安全库存的门店产品数`,
    count()                                                     AS `门店产品组合数`
FROM retail.FactInventory AS i
INNER JOIN latest AS l
        ON i.StoreKey = l.StoreKey AND i.ProductKey = l.ProductKey AND i.DateKey = l.d
INNER JOIN retail.DimStore              AS s   ON i.StoreKey = s.StoreKey
INNER JOIN retail.DimGeography          AS g   ON s.GeographyKey = g.GeographyKey
LEFT  JOIN retail.DimProduct            AS p   ON i.ProductKey = p.ProductKey
LEFT  JOIN retail.DimProductSubcategory AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT  JOIN retail.DimProductCategory    AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
GROUP BY `门店名`, `门店类型`, `门店国家`, `门店大洲`, `品类`
SETTINGS join_use_nulls = 1;

-- ===========================================================================
-- T15 促销效果月报（R12）
--    粒度：月 × 促销 × 渠道
--    **把无折扣那一档也留着**（促销键 1），作为对比基线，并用「是否打折促销」标出来：
--    打折销售额占比的分母要含无折扣交易，筛掉就算不出来了。
--    筛选依据是促销键不是折扣金额（约定 10）。
-- ===========================================================================
DROP TABLE IF EXISTS ads.ads_promotion_month_channel;
CREATE TABLE ads.ads_promotion_month_channel
ENGINE = MergeTree ORDER BY (`月起始日`, `渠道`, `促销名`) AS
SELECT
    toStartOfMonth(f.DateKey)                           AS `月起始日`,
    toYear(f.DateKey)                                   AS `年`,
    toMonth(f.DateKey)                                  AS `月`,
    ch.ChannelName                                      AS `渠道`,
    pr.PromotionName                                    AS `促销名`,
    pr.PromotionType                                    AS `促销类型`,
    pr.DiscountPercent                                  AS `名义折扣率`,
    f.PromotionKey != 1                                 AS `是否打折促销`,
    sum(toDecimal128(f.SalesAmount, 6))                                  AS `销售额`,
    sum(f.SalesQuantity)                                AS `销售数量`,
    sum(toDecimal128(f.DiscountAmount, 6))                               AS `折扣金额`,
    sum(f.DiscountQuantity)                             AS `折扣数量`,
    sum(toDecimal128(f.DiscountAmount, 6)) + sum(toDecimal128(f.SalesAmount, 6))          AS `折扣前原价`,
    sum(toDecimal128(f.TotalCost, 6))                                    AS `总成本`,
    sum(toDecimal128(f.SalesAmount, 6)) - sum(toDecimal128(f.TotalCost, 6))               AS `毛利`
FROM retail.FactSales AS f
INNER JOIN retail.DimChannel   AS ch ON f.channelKey = ch.ChannelKey
INNER JOIN retail.DimPromotion AS pr ON f.PromotionKey = pr.PromotionKey
GROUP BY `月起始日`, `年`, `月`, `渠道`, `促销名`, `促销类型`, `名义折扣率`, `是否打折促销`;
