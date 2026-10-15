-- 由 render/build_l0.py 从 semantic/l0_map.yaml 生成，不要手改。
-- L0 劣化视图：只改名、追加技术字段；底层仍是 retail 原表，不动数据行。

DROP DATABASE IF EXISTS l0;
CREATE DATABASE l0;

CREATE VIEW l0.fct_ol_sls AS
SELECT
    `OnlineSalesKey` AS row_id,
    `DateKey` AS dk,
    `StoreKey` AS stk,
    `ProductKey` AS prk,
    `PromotionKey` AS pmk,
    `CurrencyKey` AS cyk,
    `CustomerKey` AS csk,
    `SalesOrderNumber` AS ord_no,
    `SalesOrderLineNumber` AS ln_no,
    `SalesQuantity` AS qty1,
    `SalesAmount` AS amt1,
    `ReturnQuantity` AS qty2,
    `ReturnAmount` AS amt2,
    `DiscountQuantity` AS qty3,
    `DiscountAmount` AS amt3,
    `TotalCost` AS amt4,
    `UnitCost` AS uc,
    `UnitPrice` AS up,
    toUInt32(toYYYYMMDD(DateKey)) AS etl_btch_id,
    'ECOM01' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactOnlineSales;

CREATE VIEW l0.fct_sls AS
SELECT
    `SalesKey` AS row_id,
    `DateKey` AS dk,
    `channelKey` AS chnk,
    `StoreKey` AS stk,
    `ProductKey` AS prk,
    `PromotionKey` AS pmk,
    `CurrencyKey` AS cyk,
    `UnitCost` AS uc,
    `UnitPrice` AS up,
    `SalesQuantity` AS qty1,
    `ReturnQuantity` AS qty2,
    `ReturnAmount` AS amt2,
    `DiscountQuantity` AS qty3,
    `DiscountAmount` AS amt3,
    `TotalCost` AS amt4,
    `SalesAmount` AS amt1,
    toUInt32(toYYYYMMDD(DateKey)) AS etl_btch_id,
    'POS02' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactSales;

CREATE VIEW l0.fct_inv_snp AS
SELECT
    `InventoryKey` AS row_id,
    `DateKey` AS dk,
    `StoreKey` AS stk,
    `ProductKey` AS prk,
    `CurrencyKey` AS cyk,
    `OnHandQuantity` AS qty1,
    `OnOrderQuantity` AS qty2,
    `SafetyStockQuantity` AS qty3,
    `UnitCost` AS uc,
    `DaysInStock` AS d1,
    `MinDayInStock` AS d2,
    `MaxDayInStock` AS d3,
    `Aging` AS d4,
    toUInt32(toYYYYMMDD(DateKey)) AS etl_btch_id,
    'WMS01' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactInventory;

CREATE VIEW l0.fct_sls_qta AS
SELECT
    `SalesQuotaKey` AS row_id,
    `ChannelKey` AS chk,
    `StoreKey` AS stk,
    `ProductKey` AS prk,
    `DateKey` AS dk,
    `CurrencyKey` AS cyk,
    `ScenarioKey` AS scnk,
    `SalesQuantityQuota` AS qty1,
    `SalesAmountQuota` AS amt1,
    `GrossMarginQuota` AS amt2,
    toUInt32(toYYYYMMDD(DateKey)) AS etl_btch_id,
    'PLN01' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactSalesQuota;

CREATE VIEW l0.fct_stg_pln AS
SELECT
    `StrategyPlanKey` AS row_id,
    `DateKey` AS dk,
    `EntityKey` AS enk,
    `ScenarioKey` AS scnk,
    `AccountKey` AS acct_k,
    `CurrencyKey` AS cyk,
    `ProductCategoryKey` AS pck,
    `Amount` AS amt1,
    toUInt32(toYYYYMMDD(DateKey)) AS etl_btch_id,
    'PLN02' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactStrategyPlan;

CREATE VIEW l0.fct_fx AS
SELECT
    `ExchangeRateKey` AS row_id,
    `CurrencyKey` AS cyk,
    `DateKey` AS dk,
    `AverageRate` AS rt1,
    `EndOfDayRate` AS rt2,
    'TRS01' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactExchangeRate;

CREATE VIEW l0.fct_it_mch AS
SELECT
    `ITMachinekey` AS row_id,
    `MachineKey` AS mck,
    `DateKey` AS dk,
    `CostAmount` AS amt1,
    `CostType` AS tp_cd,
    'ITAM01' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactITMachine;

CREATE VIEW l0.fct_it_sla AS
SELECT
    `ITSLAkey` AS row_id,
    `DateKey` AS dk,
    `StoreKey` AS stk,
    `MachineKey` AS mck,
    `OutageKey` AS otk,
    `OutageStartTime` AS ts1,
    `OutageEndTime` AS ts2,
    `DownTime` AS dur,
    'ITSM01' AS src_sys_cd,
    toDateTime(DateKey, 'UTC') + toIntervalHour(26) AS load_dttm
FROM retail.FactITSLA;

CREATE VIEW l0.d_prd AS
SELECT
    `ProductKey` AS prk,
    `ProductName` AS pr_nm,
    `ProductDescription` AS pr_ds,
    `ProductSubcategoryKey` AS psck,
    `Manufacturer` AS mfr,
    `BrandName` AS brd,
    `ClassID` AS cls_id,
    `ClassName` AS cls_nm,
    `StyleID` AS sty_id,
    `StyleName` AS sty_nm,
    `ColorID` AS clr_id,
    `ColorName` AS clr_nm,
    `Weight` AS wt,
    `WeightUnitMeasureID` AS wt_uom,
    `UnitOfMeasureID` AS uom_id,
    `UnitOfMeasureName` AS uom_nm,
    `StockTypeID` AS stck_tp_id,
    `StockTypeName` AS stck_tp_nm,
    `UnitCost` AS uc,
    `UnitPrice` AS up,
    `AvailableForSaleDate` AS afs_dt,
    `Status` AS stat
FROM retail.DimProduct;

CREATE VIEW l0.d_str AS
SELECT
    `StoreKey` AS stk,
    `GeographyKey` AS gk,
    `StoreManager` AS mgr,
    `StoreType` AS st_tp,
    `StoreName` AS st_nm,
    `Status` AS stat,
    `OpenDate` AS opn_dt,
    `CloseDate` AS cls_dt,
    `EntityKey` AS enk,
    `StorePhone` AS tel,
    `StoreFax` AS fax,
    `CloseReason` AS cls_rsn,
    `EmployeeCount` AS emp_n,
    `SellingAreaSize` AS area,
    `LastRemodelDate` AS rmd_dt,
    `EmployeeKey` AS emk
FROM retail.DimStore;

CREATE VIEW l0.d_cst AS
SELECT
    `RowNum` AS rn,
    `CustomerKey` AS csk,
    `GeographyKey` AS gk,
    `FirstName` AS fnm,
    `LastName` AS lnm,
    `BirthDate` AS bdt,
    `MaritalStatus` AS ms_cd,
    `Gender` AS gdr,
    `YearlyIncome` AS inc_y,
    `TotalChildren` AS chld_t,
    `NumberChildrenAtHome` AS chld_h,
    `Education` AS edu,
    `Occupation` AS ocp,
    `HouseOwnerFlag` AS ho_flg,
    `NumberCarsOwned` AS car_n
FROM retail.DimCustomer;

CREATE VIEW l0.d_dt AS
SELECT
    `DateKey` AS dk,
    `CalendarYear` AS c_yr,
    `CalendarYearLabel` AS c_yr_lb,
    `CalendarHalfYearLabel` AS c_hy_lb,
    `CalendarQuarterLabel` AS c_qtr_lb,
    `CalendarMonthLabel` AS c_mo_lb,
    `CalendarWeekLabel` AS c_wk_lb,
    `CalendarDayOfWeekLabel` AS c_dow_lb,
    `FiscalYear` AS f_yr,
    `FiscalYearLabel` AS f_yr_lb,
    `FiscalHalfYearLabel` AS f_hy_lb,
    `FiscalQuarterLabel` AS f_qtr_lb,
    `FiscalMonthLabel` AS f_mo_lb,
    `IsWorkDay` AS wd_flg,
    `IsHoliday` AS hol_flg,
    `EuropeSeason` AS ssn_eu,
    `NorthAmericaSeason` AS ssn_na,
    `AsiaSeason` AS ssn_as,
    `MonthNumber` AS mo_no,
    `CalendarDayOfWeekNumber` AS dow_no
FROM retail.DimDate;

CREATE VIEW l0.d_geo AS
SELECT
    `GeographyKey` AS gk,
    `GeographyType` AS geo_tp,
    `ContinentName` AS cont_nm,
    `CityName` AS cty_nm,
    `StateProvinceName` AS prov_nm,
    `RegionCountryName` AS ctry_nm
FROM retail.DimGeography;

CREATE VIEW l0.d_chn AS
SELECT
    `ChannelKey` AS chk,
    `ChannelName` AS ch_nm,
    `ChannelDescription` AS ch_ds
FROM retail.DimChannel;

CREATE VIEW l0.d_prm AS
SELECT
    `PromotionKey` AS pmk,
    `PromotionName` AS pm_nm,
    `DiscountPercent` AS dsc_pct,
    `PromotionType` AS pm_tp,
    `PromotionCategory` AS pm_cat
FROM retail.DimPromotion;

CREATE VIEW l0.d_scn AS
SELECT
    `ScenarioKey` AS scnk,
    `ScenarioName` AS scn_nm
FROM retail.DimScenario;

CREATE VIEW l0.d_acct AS
SELECT
    `AccountKey` AS acct_k,
    `ParentAccountKey` AS p_acct,
    `AccountName` AS acct_nm,
    `AccountDescription` AS acct_ds,
    `AccountType` AS acct_tp,
    `ValueType` AS val_tp
FROM retail.DimAccount;

CREATE VIEW l0.d_ccy AS
SELECT
    `CurrencyKey` AS cyk,
    `CurrencyName` AS cy_nm,
    `CurrencyDescription` AS cy_ds
FROM retail.DimCurrency;

CREATE VIEW l0.d_prd_cat AS
SELECT
    `ProductCategoryKey` AS pck,
    `ProductCategoryName` AS pc_nm
FROM retail.DimProductCategory;

CREATE VIEW l0.d_prd_sub AS
SELECT
    `ProductSubcategoryKey` AS psck,
    `ProductSubcategoryName` AS psc_nm,
    `ProductCategoryKey` AS pck
FROM retail.DimProductSubcategory;

CREATE VIEW l0.d_emp AS
SELECT
    `EmployeeKey` AS emk,
    `ParentEmployeeKey` AS p_emp,
    `FirstName` AS fnm,
    `LastName` AS lnm,
    `Title` AS ttl,
    `HireDate` AS hr_dt,
    `BirthDate` AS bdt,
    `EmailAddress` AS eml,
    `Phone` AS tel,
    `EmergencyContactName` AS ec_nm,
    `EmergencyContactPhone` AS ec_tel,
    `Gender` AS gdr,
    `PayFrequency` AS pay_frq,
    `BaseRate` AS rt_b,
    `VacationHours` AS vac_h,
    `DepartmentName` AS dpt_nm,
    `StartDate` AS st_dt,
    `Status` AS stat,
    `SalaryStatus` AS sal_st,
    `IsSalesPerson` AS sp_flg,
    `IsMarried` AS mar_flg
FROM retail.DimEmployee;

CREATE VIEW l0.d_ent AS
SELECT
    `EntityKey` AS enk,
    `ParentEntityKey` AS p_ent,
    `ParentEntityLabel` AS p_ent_lb,
    `EntityName` AS ent_nm,
    `EntityDescription` AS ent_ds,
    `EntityType` AS ent_tp,
    `StartDate` AS st_dt,
    `Status` AS stat
FROM retail.DimEntity;

CREATE VIEW l0.d_sls_ter AS
SELECT
    `SalesTerritoryKey` AS terk,
    `GeographyKey` AS gk,
    `SalesTerritoryName` AS ter_nm,
    `SalesTerritoryRegion` AS ter_rgn,
    `SalesTerritoryCountry` AS ter_ctry,
    `SalesTerritoryGroup` AS ter_grp,
    `SalesTerritoryLevel` AS ter_lvl,
    `SalesTerritoryManager` AS ter_mgr,
    `Status` AS stat,
    `EmployeeKey` AS emk
FROM retail.DimSalesTerritory;

CREATE VIEW l0.d_mch AS
SELECT
    `MachineKey` AS mck,
    `StoreKey` AS stk,
    `MachineType` AS mc_tp,
    `MachineName` AS mc_nm,
    `MachineDescription` AS mc_ds,
    `VendorName` AS vnd_nm,
    `MachineOS` AS mc_os,
    `MachineSource` AS mc_src,
    `MachineHardware` AS mc_hw,
    `MachineSoftware` AS mc_sw,
    `Status` AS stat,
    `ServiceStartDate` AS svc_st_dt,
    `DecommissionDate` AS dcm_dt,
    `LastModifiedDate` AS lm_dt
FROM retail.DimMachine;

CREATE VIEW l0.d_otg AS
SELECT
    `OutageKey` AS otk,
    `OutageName` AS ot_nm,
    `OutageType` AS ot_tp,
    `OutageTypeDescription` AS ot_tp_ds,
    `OutageSubType` AS ot_stp
FROM retail.DimOutage;
