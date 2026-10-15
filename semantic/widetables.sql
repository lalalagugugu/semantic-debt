-- L1.5W 明细宽表（DWD 风格）
--
-- 规矩（任务卡 T08 交付物 2）：
--   * 只做**关联**和**行级派生列**，不做任何聚合。每个视图的行数必须与对应事实表相同。
--   * 唯一的例外是「当前库存」，它只做**行筛选**（每个门店 × 产品最近一次快照），
--     所以行数比事实表少，这是设计使然。
--   * 每个派生列的逻辑必须在 semantic/source.yaml 的文字里已经定义过
--     （净销售额、毛利、折扣前原价、是否打折、库存金额、是否低于安全库存、客户地理、门店地理）。
--   * 原始表仍然可见：这些视图建在独立库 `dwd` 里，`retail` 库不动。
--
-- 为什么每个维度连接都是 LEFT JOIN：产品维度缺 284 行，而四张事实表都引用了缺失的键
-- （见 source.yaml 的 data_quality / missing-products）。用 INNER JOIN 会让
-- wide_all_channel_sales 少 338,898 行、wide_online_sales 少 1,715,380 行，
-- 既违反「行数一致」的验收项，也会让销售总额偏低。
--
-- 重建：uv run python render/build_widetables.py
-- 冻结：G1 打 tag `semantic-v1` 之后不得再改。

CREATE DATABASE IF NOT EXISTS dwd;

-- ---------------------------------------------------------------------------
-- 公共子查询说明
--
-- ClickHouse 里一条 SELECT 不能复用同一个 JOIN 结果，所以产品层级和门店地理
-- 在每个视图里各自展开一次。两者都是多对一且父表键唯一，不会放大行数。
-- ---------------------------------------------------------------------------


-- ===========================================================================
-- 1. 线上销售明细宽表
--    主题：线上订单行。粒度与 retail.FactOnlineSales 相同（一行 = 一个订单行）。
--    行数应等于 12,627,608。
-- ===========================================================================
CREATE OR REPLACE VIEW dwd.wide_online_sales AS
SELECT
    -- ---- 事实（原样） ----
    f.DateKey                                   AS `订单日期`,
    f.SalesOrderNumber                          AS `订单号`,
    f.SalesOrderLineNumber                      AS `订单行号`,
    f.SalesQuantity                             AS `销售数量`,
    f.SalesAmount                               AS `销售金额`,
    f.ReturnQuantity                            AS `退货数量`,
    f.ReturnAmount                              AS `退货金额`,
    f.DiscountQuantity                          AS `折扣数量`,
    f.DiscountAmount                            AS `折扣金额`,
    f.TotalCost                                 AS `总成本`,
    f.UnitPrice                                 AS `成交单价`,
    f.UnitCost                                  AS `成交单位成本`,

    -- ---- 行级派生列（source.yaml 已定义的口径） ----
    f.SalesAmount - f.ReturnAmount              AS `净销售金额`,          -- 约定 7
    f.SalesAmount - f.TotalCost                 AS `毛利`,                -- 约定 7
    f.SalesAmount + f.DiscountAmount            AS `折扣前原价`,
    f.PromotionKey != 1                         AS `是否打折`,            -- 约定 10
    f.SalesQuantity = 0                         AS `是否退货行`,          -- 线上退货写在独立行上

    -- ---- 时间 ----
    d.CalendarYear                              AS `年`,
    d.MonthNumber                               AS `月`,
    d.CalendarMonthLabel                        AS `月名`,
    d.CalendarQuarterLabel                      AS `季度`,
    d.CalendarHalfYearLabel                     AS `半年`,
    d.CalendarWeekLabel                         AS `周`,
    d.CalendarDayOfWeekLabel                    AS `星期`,
    d.CalendarDayOfWeekNumber                   AS `星期序号`,
    d.IsWorkDay                                 AS `是否工作日`,
    d.IsHoliday                                 AS `是否节假日`,          -- 本库里等于周末
    d.EuropeSeason                              AS `欧洲季节`,
    d.NorthAmericaSeason                        AS `北美季节`,
    d.AsiaSeason                                AS `亚洲季节`,

    -- ---- 产品层级 ----
    p.ProductName                               AS `产品名`,
    p.BrandName                                 AS `品牌`,
    p.Manufacturer                              AS `厂商`,
    p.ColorName                                 AS `颜色`,
    p.ClassName                                 AS `产品档位`,
    p.StockTypeName                             AS `备货档位`,
    p.UnitPrice                                 AS `产品标价`,            -- 约定 9：产品利润率用这个
    p.UnitCost                                  AS `产品单位成本`,        -- 约定 9
    p.Status                                    AS `产品状态`,
    psc.ProductSubcategoryName                  AS `子类`,
    pc.ProductCategoryName                      AS `品类`,

    -- ---- 促销 ----
    pr.PromotionName                            AS `促销名`,
    pr.DiscountPercent                          AS `名义折扣率`,
    pr.PromotionType                            AS `促销类型`,

    -- ---- 客户与客户地理（约定 5 的默认分支） ----
    c.FirstName                                 AS `客户名`,
    c.LastName                                  AS `客户姓`,
    c.Gender                                    AS `客户性别`,
    c.MaritalStatus                             AS `客户婚姻状况`,
    c.Education                                 AS `客户学历`,
    c.Occupation                                AS `客户职业`,
    c.YearlyIncome                              AS `客户年收入`,
    c.TotalChildren                             AS `客户子女数`,
    c.HouseOwnerFlag                            AS `客户是否有房`,
    c.BirthDate                                 AS `客户出生日期`,
    cg.CityName                                 AS `客户城市`,
    cg.StateProvinceName                        AS `客户省州`,
    cg.RegionCountryName                        AS `客户国家`,
    cg.ContinentName                            AS `客户大洲`,

    -- ---- 线上店（只有三家虚拟店，用来区分大洲业务） ----
    s.StoreName                                 AS `线上店名`,
    s.StoreType                                 AS `线上店类型`
FROM retail.FactOnlineSales AS f
LEFT JOIN retail.DimDate                 AS d   ON f.DateKey    = d.DateKey
LEFT JOIN retail.DimProduct              AS p   ON f.ProductKey = p.ProductKey
LEFT JOIN retail.DimProductSubcategory   AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT JOIN retail.DimProductCategory      AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
LEFT JOIN retail.DimPromotion            AS pr  ON f.PromotionKey = pr.PromotionKey
LEFT JOIN retail.DimCustomer             AS c   ON f.CustomerKey  = c.CustomerKey
LEFT JOIN retail.DimGeography            AS cg  ON c.GeographyKey = cg.GeographyKey
LEFT JOIN retail.DimStore                AS s   ON f.StoreKey     = s.StoreKey;


-- ===========================================================================
-- 2. 全渠道销售宽表
--    主题：全渠道销售汇总行。粒度与 retail.FactSales 相同
--    （一行 = 一天 × 门店 × 产品 × 促销）。行数应等于 3,406,089。
--    注意这张表没有订单号也没有客户，所以没有客户地理列。
-- ===========================================================================
CREATE OR REPLACE VIEW dwd.wide_all_channel_sales AS
SELECT
    -- ---- 事实（原样） ----
    f.DateKey                                   AS `销售日期`,
    f.SalesQuantity                             AS `销售数量`,
    f.SalesAmount                               AS `销售金额`,
    f.ReturnQuantity                            AS `退货数量`,
    f.ReturnAmount                              AS `退货金额`,
    f.DiscountQuantity                          AS `折扣数量`,
    f.DiscountAmount                            AS `折扣金额`,
    f.TotalCost                                 AS `总成本`,
    f.UnitPrice                                 AS `成交单价`,
    f.UnitCost                                  AS `成交单位成本`,

    -- ---- 行级派生列 ----
    f.SalesAmount - f.ReturnAmount              AS `净销售金额`,          -- 约定 7
    f.SalesAmount - f.TotalCost                 AS `毛利`,                -- 约定 7
    f.SalesAmount + f.DiscountAmount            AS `折扣前原价`,
    f.PromotionKey != 1                         AS `是否打折`,            -- 约定 10（以促销键为准）

    -- ---- 渠道 ----
    ch.ChannelName                              AS `渠道`,

    -- ---- 时间 ----
    d.CalendarYear                              AS `年`,
    d.MonthNumber                               AS `月`,
    d.CalendarMonthLabel                        AS `月名`,
    d.CalendarQuarterLabel                      AS `季度`,
    d.CalendarHalfYearLabel                     AS `半年`,
    d.CalendarWeekLabel                         AS `周`,
    d.CalendarDayOfWeekLabel                    AS `星期`,
    d.CalendarDayOfWeekNumber                   AS `星期序号`,
    d.IsWorkDay                                 AS `是否工作日`,
    d.IsHoliday                                 AS `是否节假日`,
    d.EuropeSeason                              AS `欧洲季节`,
    d.NorthAmericaSeason                        AS `北美季节`,
    d.AsiaSeason                                AS `亚洲季节`,

    -- ---- 门店与门店地理（约定 5 的门店分支） ----
    s.StoreName                                 AS `门店名`,
    s.StoreType                                 AS `门店类型`,
    s.Status                                    AS `门店状态`,
    s.OpenDate                                  AS `门店开业日`,
    s.SellingAreaSize                           AS `门店营业面积`,
    s.EmployeeCount                             AS `门店员工数`,
    concat(e.FirstName, ' ', e.LastName)        AS `门店经理`,            -- 不用 StoreManager，那是员工号
    e.Title                                     AS `门店经理职级`,
    sg.CityName                                 AS `门店城市`,
    sg.StateProvinceName                        AS `门店省州`,
    sg.RegionCountryName                        AS `门店国家`,
    sg.ContinentName                            AS `门店大洲`,

    -- ---- 产品层级 ----
    p.ProductName                               AS `产品名`,
    p.BrandName                                 AS `品牌`,
    p.Manufacturer                              AS `厂商`,
    p.ColorName                                 AS `颜色`,
    p.ClassName                                 AS `产品档位`,
    p.StockTypeName                             AS `备货档位`,
    p.UnitPrice                                 AS `产品标价`,
    p.UnitCost                                  AS `产品单位成本`,
    p.Status                                    AS `产品状态`,
    psc.ProductSubcategoryName                  AS `子类`,
    pc.ProductCategoryName                      AS `品类`,

    -- ---- 促销 ----
    pr.PromotionName                            AS `促销名`,
    pr.DiscountPercent                          AS `名义折扣率`,
    pr.PromotionType                            AS `促销类型`
FROM retail.FactSales AS f
LEFT JOIN retail.DimChannel              AS ch  ON f.channelKey = ch.ChannelKey
LEFT JOIN retail.DimDate                 AS d   ON f.DateKey    = d.DateKey
LEFT JOIN retail.DimStore                AS s   ON f.StoreKey   = s.StoreKey
LEFT JOIN retail.DimEmployee             AS e   ON toInt32(s.EmployeeKey) = e.EmployeeKey
LEFT JOIN retail.DimGeography            AS sg  ON s.GeographyKey = sg.GeographyKey
LEFT JOIN retail.DimProduct              AS p   ON f.ProductKey = p.ProductKey
LEFT JOIN retail.DimProductSubcategory   AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT JOIN retail.DimProductCategory      AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey
LEFT JOIN retail.DimPromotion            AS pr  ON f.PromotionKey = pr.PromotionKey;


-- ===========================================================================
-- 3. 当前库存宽表
--    主题：每个门店 × 产品**最近一次**快照（约定 11）。
--    这是唯一做行筛选的视图：行数 = 门店 × 产品组合数（600,241），
--    而不是事实表的 8,013,099 行。筛选条件是「该组合的 DateKey = 该组合的最大 DateKey」，
--    不是「全局最后一个快照日」——各组合的最后一次快照并不在同一天。
--    仍然不做任何聚合：每个门店 × 产品只剩一行，列都是那一行的原值或行级派生。
-- ===========================================================================
CREATE OR REPLACE VIEW dwd.wide_current_inventory AS
WITH latest AS (
    SELECT StoreKey, ProductKey, max(DateKey) AS LastSnapshotDate
    FROM retail.FactInventory
    GROUP BY StoreKey, ProductKey
)
SELECT
    i.DateKey                                   AS `快照日期`,
    i.OnHandQuantity                            AS `在手数量`,
    i.OnOrderQuantity                           AS `在订数量`,
    i.SafetyStockQuantity                       AS `安全库存水位`,
    i.UnitCost                                  AS `库存单位成本`,
    i.DaysInStock                               AS `在库天数`,

    -- ---- 行级派生列 ----
    i.OnHandQuantity * i.UnitCost               AS `在手库存金额`,
    i.OnHandQuantity < i.SafetyStockQuantity    AS `是否低于安全库存`,

    -- ---- 门店与门店地理 ----
    s.StoreName                                 AS `门店名`,
    s.StoreType                                 AS `门店类型`,
    s.Status                                    AS `门店状态`,
    sg.CityName                                 AS `门店城市`,
    sg.StateProvinceName                        AS `门店省州`,
    sg.RegionCountryName                        AS `门店国家`,
    sg.ContinentName                            AS `门店大洲`,

    -- ---- 产品层级 ----
    p.ProductName                               AS `产品名`,
    p.BrandName                                 AS `品牌`,
    p.ColorName                                 AS `颜色`,
    p.ClassName                                 AS `产品档位`,
    p.StockTypeName                             AS `备货档位`,
    p.Status                                    AS `产品状态`,
    psc.ProductSubcategoryName                  AS `子类`,
    pc.ProductCategoryName                      AS `品类`
FROM retail.FactInventory AS i
INNER JOIN latest AS l
        ON i.StoreKey = l.StoreKey
       AND i.ProductKey = l.ProductKey
       AND i.DateKey = l.LastSnapshotDate
LEFT JOIN retail.DimStore                AS s   ON i.StoreKey   = s.StoreKey
LEFT JOIN retail.DimGeography            AS sg  ON s.GeographyKey = sg.GeographyKey
LEFT JOIN retail.DimProduct              AS p   ON i.ProductKey = p.ProductKey
LEFT JOIN retail.DimProductSubcategory   AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT JOIN retail.DimProductCategory      AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey;


-- ===========================================================================
-- 4. 销售目标宽表
--    主题：门店 × 产品 × 月 × 渠道 × 场景的销售目标（约定 12）。
--    粒度与 retail.FactSalesQuota 相同，行数应等于 7,465,911。
--    **场景没有被筛掉**：三个场景都在，用的时候必须按 `场景` 列筛，
--    否则金额会放大三倍。筛选交给查询，这里不替它做决定（宽表不做聚合也不做业务筛选）。
-- ===========================================================================
CREATE OR REPLACE VIEW dwd.wide_sales_quota AS
SELECT
    q.DateKey                                   AS `目标月份`,
    q.SalesAmountQuota                          AS `目标销售额`,
    q.SalesQuantityQuota                        AS `目标销量`,
    q.GrossMarginQuota                          AS `目标毛利`,

    sc.ScenarioName                             AS `场景`,                -- Budget 才是正式目标
    ch.ChannelName                              AS `渠道`,

    d.CalendarYear                              AS `年`,
    d.MonthNumber                               AS `月`,
    d.CalendarMonthLabel                        AS `月名`,
    d.CalendarQuarterLabel                      AS `季度`,

    s.StoreName                                 AS `门店名`,
    s.StoreType                                 AS `门店类型`,
    sg.CityName                                 AS `门店城市`,
    sg.StateProvinceName                        AS `门店省州`,
    sg.RegionCountryName                        AS `门店国家`,
    sg.ContinentName                            AS `门店大洲`,

    p.ProductName                               AS `产品名`,
    p.BrandName                                 AS `品牌`,
    psc.ProductSubcategoryName                  AS `子类`,
    pc.ProductCategoryName                      AS `品类`
FROM retail.FactSalesQuota AS q
LEFT JOIN retail.DimScenario             AS sc  ON q.ScenarioKey = sc.ScenarioKey
LEFT JOIN retail.DimChannel              AS ch  ON q.ChannelKey  = ch.ChannelKey
LEFT JOIN retail.DimDate                 AS d   ON q.DateKey     = d.DateKey
LEFT JOIN retail.DimStore                AS s   ON q.StoreKey    = s.StoreKey
LEFT JOIN retail.DimGeography            AS sg  ON s.GeographyKey = sg.GeographyKey
LEFT JOIN retail.DimProduct              AS p   ON q.ProductKey  = p.ProductKey
LEFT JOIN retail.DimProductSubcategory   AS psc ON toInt32(p.ProductSubcategoryKey) = psc.ProductSubcategoryKey
LEFT JOIN retail.DimProductCategory      AS pc  ON psc.ProductCategoryKey = pc.ProductCategoryKey;


-- ===========================================================================
-- 5. 战略计划宽表
--    主题：门店（实体）× 品类 × 科目 × 月 × 场景的计划金额（约定 12）。
--    粒度与 retail.FactStrategyPlan 相同，行数应等于 2,750,628。
--    场景和科目都没有被筛掉，用的时候必须筛：不筛场景会放大三倍，不筛科目会把
--    收入和各类费用加在一起。另外科目有父子关系，父子一起求和会重复计算。
--    这里把门店接上了（经 DimEntity ← DimStore.EntityKey），这是计划和门店之间唯一的桥梁。
-- ===========================================================================
CREATE OR REPLACE VIEW dwd.wide_strategy_plan AS
SELECT
    sp.DateKey                                  AS `计划月份`,
    sp.Amount                                   AS `计划金额`,

    sc.ScenarioName                             AS `场景`,
    a.AccountName                               AS `科目`,
    a.AccountType                               AS `科目方向`,
    a.ParentAccountKey IS NOT NULL              AS `科目有父级`,          -- 提醒父子不能同时求和

    d.CalendarYear                              AS `年`,
    d.MonthNumber                               AS `月`,
    d.CalendarMonthLabel                        AS `月名`,
    d.CalendarQuarterLabel                      AS `季度`,

    ent.EntityName                              AS `实体名`,
    ent.EntityType                              AS `实体层级`,
    ent.ParentEntityLabel                       AS `实体所属上级`,        -- 门店级实体这里是州名

    s.StoreName                                 AS `门店名`,
    s.StoreType                                 AS `门店类型`,
    sg.CityName                                 AS `门店城市`,
    sg.StateProvinceName                        AS `门店省州`,
    sg.RegionCountryName                        AS `门店国家`,
    sg.ContinentName                            AS `门店大洲`,

    pc.ProductCategoryName                      AS `品类`
FROM retail.FactStrategyPlan AS sp
LEFT JOIN retail.DimScenario        AS sc  ON sp.ScenarioKey = sc.ScenarioKey
LEFT JOIN retail.DimAccount         AS a   ON sp.AccountKey  = a.AccountKey
LEFT JOIN retail.DimDate            AS d   ON sp.DateKey     = d.DateKey
LEFT JOIN retail.DimEntity          AS ent ON sp.EntityKey   = ent.EntityKey
LEFT JOIN retail.DimStore           AS s   ON sp.EntityKey   = toInt32(s.EntityKey)
LEFT JOIN retail.DimGeography       AS sg  ON s.GeographyKey = sg.GeographyKey
LEFT JOIN retail.DimProductCategory AS pc  ON sp.ProductCategoryKey = pc.ProductCategoryKey;
