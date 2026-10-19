"""DAX and Cube implementations of every callable in semantic/metrics.yaml.

The text definitions are in semantic/source.yaml (metrics); metrics.yaml fixes the
names. This module only says *how* each callable is computed in each engine, so
both engines implement the same text. Nothing here adds a definition: every
filter, scenario and window below is the one written in the metric's text.

Shared choices, written once here instead of per measure:
  - Ratios divide with DIVIDE / nullIf, so an empty denominator gives blank / NULL.
  - "Default Budget scenario" (目标销售额、目标销量、目标毛利、计划收入): DAX applies
    Budget unless the query filters the scenario itself. Cube cannot see the query's
    filters from inside a measure, so the Cube members are fixed to Budget.
  - 销售额环比增长率: DAX picks the period from the dates in context (month, quarter
    or year). Cube's time_shift needs a fixed interval, so the Cube member shifts by
    one month (it is called *_mom_pct).
  - 新客 (convention 14): the cut-off is the last date of the query window, capped at
    2009-12-31. DAX counts every customer whose first purchase falls in the 90 days;
    Cube only sees customers with rows in the window.
These differences are engine capability limits, recorded in render/README.md.
"""

from __future__ import annotations

from render.common import metrics_file, source, variant_callables, variant_key

AS_OF = "2009-12-31"


def _names() -> dict[tuple[str, str], tuple[str, str]]:
    """(metric, dataset) → (dax measure without brackets, cube member)."""
    out = {}
    for m in metrics_file()["metrics"]:
        out[(m["name"], m["dataset"])] = (m["dax_measure"][1:-1], m["cube_member"])
        if m.get("alternate_dataset"):
            out[(m["name"], m["alternate_dataset"])] = (m["alternate_dax_measure"][1:-1], m["alternate_cube_member"])
        for vid, ds, dax, cube, _ in variant_callables(m):
            out[(variant_key(m["name"], vid), ds)] = (dax[1:-1], cube)
    return out


NAMES = _names()


def D(metric: str, dataset: str) -> str:
    """DAX reference to another measure."""
    return f"[{NAMES[(metric, dataset)][0]}]"


def C(metric: str, dataset: str) -> str:
    """Cube reference to another member of the same cube."""
    return "{" + NAMES[(metric, dataset)][1].split(".", 1)[1] + "}"


# ---------------------------------------------------------------------------
# DAX
# ---------------------------------------------------------------------------
_PERIOD_PRIOR = """VAR _first = MIN ( 'DimDate'[DateKey] )
VAR _last = MAX ( 'DimDate'[DateKey] )
VAR _isMonth = _first = DATE ( YEAR ( _first ), MONTH ( _first ), 1 ) && _last = EOMONTH ( _first, 0 )
VAR _isQuarter = _first = DATE ( YEAR ( _first ), MONTH ( _first ), 1 ) && MOD ( MONTH ( _first ) - 1, 3 ) = 0 && _last = EOMONTH ( _first, 2 )
VAR _isYear = _first = DATE ( YEAR ( _first ), 1, 1 ) && _last = DATE ( YEAR ( _first ), 12, 31 )
VAR _cur = {cur}
VAR _prev =
    SWITCH (
        TRUE (),
        _isMonth, CALCULATE ( {cur}, DATEADD ( 'DimDate'[DateKey], -1, MONTH ) ),
        _isQuarter, CALCULATE ( {cur}, DATEADD ( 'DimDate'[DateKey], -1, QUARTER ) ),
        _isYear, CALCULATE ( {cur}, DATEADD ( 'DimDate'[DateKey], -1, YEAR ) )
    )
RETURN
    DIVIDE ( _cur - _prev, _prev )"""


def _new_customers(t: str) -> str:
    return f"""VAR _cutoff = MIN ( MAX ( 'DimDate'[DateKey] ), DATE ( 2009, 12, 31 ) )
VAR _customers = CALCULATETABLE ( VALUES ( {t}[CustomerKey] ), REMOVEFILTERS ( 'DimDate' ) )
VAR _new =
    FILTER (
        _customers,
        VAR _firstBuy = CALCULATE ( MIN ( {t}[DateKey] ), REMOVEFILTERS ( 'DimDate' ) )
        RETURN _firstBuy >= _cutoff - 89 && _firstBuy <= _cutoff
    )"""


def _scenario_default(expr: str, extra: str = "") -> str:
    extra_arg = f", {extra}" if extra else ""
    return (
        "IF (\n"
        "    ISFILTERED ( 'DimScenario'[ScenarioName] ) || ISFILTERED ( 'DimScenario'[ScenarioKey] ),\n"
        f"    CALCULATE ( {expr}{extra_arg} ),\n"
        f"    CALCULATE ( {expr}{extra_arg}, 'DimScenario'[ScenarioName] = \"Budget\" )\n"
        ")"
    )


_LATEST = "'FactInventory'[IsLatestSnapshot] = TRUE (), REMOVEFILTERS ( 'DimDate' ), REMOVEFILTERS ( 'FactInventory'[DateKey] )"


def dax_measures() -> dict[tuple[str, str], tuple[str, str]]:
    """(metric, dataset) → (home table, DAX expression)."""
    out: dict[tuple[str, str], tuple[str, str]] = {}

    for t in ("FactOnlineSales", "FactSales"):
        q = f"'{t}'"
        m = {
            "销售额": f"SUM ( {q}[SalesAmount] )",
            "销售数量": f"SUM ( {q}[SalesQuantity] )",
            "总成本": f"SUM ( {q}[TotalCost] )",
            "平均单价": f"DIVIDE ( {D('销售额', t)}, {D('销售数量', t)} )",
            "退货金额": f"SUM ( {q}[ReturnAmount] )",
            "退货数量": f"SUM ( {q}[ReturnQuantity] )",
            "净销售额": f"{D('销售额', t)} - {D('退货金额', t)}",
            "退货率": f"DIVIDE ( {D('退货数量', t)}, {D('销售数量', t)} )",
            "折扣金额": f"CALCULATE ( SUM ( {q}[DiscountAmount] ), KEEPFILTERS ( {q}[PromotionKey] <> 1 ) )",
            "折扣数量": f"CALCULATE ( SUM ( {q}[DiscountQuantity] ), KEEPFILTERS ( {q}[PromotionKey] <> 1 ) )",
            "折扣前原价": f"{D('销售额', t)} + SUM ( {q}[DiscountAmount] )",
            "折扣率": f"DIVIDE ( {D('折扣金额', t)}, CALCULATE ( {D('折扣前原价', t)}, KEEPFILTERS ( {q}[PromotionKey] <> 1 ) ) )",
            "打折销售额": f"CALCULATE ( {D('销售额', t)}, KEEPFILTERS ( {q}[PromotionKey] <> 1 ) )",
            "打折销售额占比": f"DIVIDE ( {D('打折销售额', t)}, {D('销售额', t)} )",
            "毛利": f"{D('销售额', t)} - {D('总成本', t)}",
            "毛利率": f"DIVIDE ( {D('毛利', t)}, {D('销售额', t)} )",
            "有销售天数": f"DISTINCTCOUNT ( {q}[DateKey] )",
            "日均销售额": f"DIVIDE ( {D('销售额', t)}, {D('有销售天数', t)} )",
            "日均销售数量": f"DIVIDE ( {D('销售数量', t)}, {D('有销售天数', t)} )",
            "产品数": f"DISTINCTCOUNT ( {q}[ProductKey] )",
            "销售额同比增长率": (
                f"VAR _cur = {D('销售额', t)}\n"
                f"VAR _prev = CALCULATE ( {D('销售额', t)}, SAMEPERIODLASTYEAR ( 'DimDate'[DateKey] ) )\n"
                "RETURN\n    DIVIDE ( _cur - _prev, _prev )"
            ),
            "销售额环比增长率": _PERIOD_PRIOR.replace("{cur}", D("销售额", t)),
            "销售额占比": f"DIVIDE ( {D('销售额', t)}, CALCULATE ( {D('销售额', t)}, ALLSELECTED () ) )",
        }
        for name, expr in m.items():
            out[(name, t)] = (t, expr)

    o = "'FactOnlineSales'"
    recency = "CALCULATE ( MAX ( 'FactOnlineSales'[DateKey] ), REMOVEFILTERS ( 'DimDate' ) )"

    def tier(cond: str) -> str:
        return (f"COUNTROWS (\n    FILTER (\n        VALUES ( {o}[CustomerKey] ),\n"
                f"        VAR _m = DATEDIFF ( {recency}, DATE ( 2009, 12, 31 ), MONTH )\n"
                f"        RETURN {cond}\n    )\n)")

    online = {
        "订单数": f"DISTINCTCOUNT ( {o}[SalesOrderNumber] )",
        "订单行数": f"COUNTROWS ( {o} )",
        "每单行数": f"DIVIDE ( {D('订单行数', 'FactOnlineSales')}, {D('订单数', 'FactOnlineSales')} )",
        "客单价": f"DIVIDE ( {D('销售额', 'FactOnlineSales')}, {D('订单数', 'FactOnlineSales')} )",
        "客户数": f"DISTINCTCOUNT ( {o}[CustomerKey] )",
        "客均销售额": f"DIVIDE ( {D('销售额', 'FactOnlineSales')}, {D('客户数', 'FactOnlineSales')} )",
        "客均订单数": f"DIVIDE ( {D('订单数', 'FactOnlineSales')}, {D('客户数', 'FactOnlineSales')} )",
        "客户最近购买月数": f"DATEDIFF ( {recency}, DATE ( 2009, 12, 31 ), MONTH )",
        "活跃客户数": tier("_m <= 6"),
        "有流失风险客户数": tier("_m >= 7 && _m <= 12"),
        "已流失客户数": tier("_m > 12"),
        "新客数": _new_customers(o) + "\nRETURN\n    COUNTROWS ( _new )",
        "新客销售额": _new_customers(o) + f"\nRETURN\n    CALCULATE ( {D('销售额', 'FactOnlineSales')}, KEEPFILTERS ( _new ) )",
        "新客销售额占比": f"DIVIDE ( {D('新客销售额', 'FactOnlineSales')}, {D('销售额', 'FactOnlineSales')} )",
    }
    for name, expr in online.items():
        out[(name, "FactOnlineSales")] = ("FactOnlineSales", expr)

    s = "'FactSales'"
    sales = D("销售额", "FactSales")

    def store_sum(col: str) -> str:
        return (f"SUMX ( VALUES ( {s}[StoreKey] ), "
                f"LOOKUPVALUE ( 'DimStore'[{col}], 'DimStore'[StoreKey], {s}[StoreKey] ) )")

    def same_store_set(year_expr: str, other_year: str) -> str:
        return (f"FILTER (\n"
                f"        CALCULATETABLE ( VALUES ( {s}[StoreKey] ), REMOVEFILTERS ( 'DimDate' ), 'DimDate'[CalendarYear] = {year_expr} ),\n"
                f"        CALCULATE ( NOT ISEMPTY ( {s} ), REMOVEFILTERS ( 'DimDate' ), 'DimDate'[CalendarYear] = {other_year} )\n"
                f"    )")

    store = {
        "门店数": f"DISTINCTCOUNT ( {s}[StoreKey] )",
        "店均销售额": f"DIVIDE ( {sales}, {D('门店数', 'FactSales')} )",
        "坪效": f"DIVIDE ( {sales}, {store_sum('SellingAreaSize')} )",
        "门店人均销售额": f"DIVIDE ( {sales}, {store_sum('EmployeeCount')} )",
        "同店销售额": (
            "SUMX (\n    VALUES ( 'DimDate'[CalendarYear] ),\n"
            "    VAR _y = 'DimDate'[CalendarYear]\n"
            f"    VAR _stores = {same_store_set('_y', '_y - 1')}\n"
            f"    RETURN CALCULATE ( {sales}, KEEPFILTERS ( _stores ) )\n)"
        ),
        "同店销售额增长率": (
            f"VAR _cur = {D('同店销售额', 'FactSales')}\n"
            "VAR _prev =\n    SUMX (\n        VALUES ( 'DimDate'[CalendarYear] ),\n"
            "        VAR _y = 'DimDate'[CalendarYear]\n"
            f"        VAR _stores = {same_store_set('_y', '_y - 1')}\n"
            f"        RETURN CALCULATE ( {sales}, KEEPFILTERS ( _stores ), SAMEPERIODLASTYEAR ( 'DimDate'[DateKey] ) )\n    )\n"
            "RETURN\n    DIVIDE ( _cur - _prev, _prev )"
        ),
    }
    for name, expr in store.items():
        out[(name, "FactSales")] = ("FactSales", expr)

    p = "'DimProduct'"
    out[("产品标价", "DimProduct")] = ("DimProduct", f"AVERAGE ( {p}[UnitPrice] )")
    out[("产品单位成本", "DimProduct")] = ("DimProduct", f"AVERAGE ( {p}[UnitCost] )")
    out[("产品利润率", "DimProduct")] = ("DimProduct", f"DIVIDE ( SUM ( {p}[UnitPrice] ) - SUM ( {p}[UnitCost] ), SUM ( {p}[UnitPrice] ) )")

    i = "'FactInventory'"
    below = f"KEEPFILTERS ( FILTER ( ALL ( {i}[OnHandQuantity], {i}[SafetyStockQuantity] ), {i}[OnHandQuantity] < {i}[SafetyStockQuantity] ) )"
    inv = {
        "当前在手库存数量": f"CALCULATE ( SUM ( {i}[OnHandQuantity] ), {_LATEST} )",
        "当前在手库存金额": f"CALCULATE ( SUMX ( {i}, {i}[OnHandQuantity] * {i}[UnitCost] ), {_LATEST} )",
        "当前在订库存数量": f"CALCULATE ( SUM ( {i}[OnOrderQuantity] ), {_LATEST} )",
        "当前安全库存数量": f"CALCULATE ( SUM ( {i}[SafetyStockQuantity] ), {_LATEST} )",
        "低于安全库存的门店产品数": f"CALCULATE ( COUNTROWS ( {i} ), {_LATEST}, {below} )",
        "快照日在手库存数量": f"SUM ( {i}[OnHandQuantity] )",
        "快照日在订库存数量": f"SUM ( {i}[OnOrderQuantity] )",
        "快照日安全库存数量": f"SUM ( {i}[SafetyStockQuantity] )",
        "快照日低于安全库存的门店产品数": f"CALCULATE ( COUNTROWS ( {i} ), {below} )",
        "门店产品组合数": f"COUNTROWS ( SUMMARIZE ( {i}, {i}[StoreKey], {i}[ProductKey] ) )",
        "快照日在手库存金额": f"SUMX ( {i}, {i}[OnHandQuantity] * {i}[UnitCost] )",
        "平均在手库存金额": f"AVERAGEX ( VALUES ( {i}[DateKey] ), {D('快照日在手库存金额', 'FactInventory')} )",
        "库存周转率": f"DIVIDE ( {D('总成本', 'FactSales')}, {D('平均在手库存金额', 'FactInventory')} )",
    }
    for name, expr in inv.items():
        out[(name, "FactInventory")] = ("FactInventory", expr)

    qt = "'FactSalesQuota'"
    budget_quota = f"CALCULATE ( SUM ( {qt}[SalesAmountQuota] ), 'DimScenario'[ScenarioName] = \"Budget\" )"
    quota = {
        "目标销售额": _scenario_default(f"SUM ( {qt}[SalesAmountQuota] )"),
        "目标销量": _scenario_default(f"SUM ( {qt}[SalesQuantityQuota] )"),
        "目标毛利": _scenario_default(f"SUM ( {qt}[GrossMarginQuota] )"),
    }
    for name, expr in quota.items():
        out[(name, "FactSalesQuota")] = ("FactSalesQuota", expr)
    # numerator on FactSales, denominator on FactSalesQuota; the measure lives with the quota
    out[("目标达成率", "FactSales")] = ("FactSalesQuota", f"DIVIDE ( {sales}, {budget_quota} )")
    out[("目标差异", "FactSales")] = ("FactSalesQuota", f"{sales} - {budget_quota}")

    sp = "'FactStrategyPlan'"
    out[("计划金额", "FactStrategyPlan")] = ("FactStrategyPlan", f"SUM ( {sp}[Amount] )")
    out[("计划收入", "FactStrategyPlan")] = (
        "FactStrategyPlan", _scenario_default(f"SUM ( {sp}[Amount] )", "'DimAccount'[AccountName] = \"Sale Revenue\""))

    out[("IT 成本", "FactITMachine")] = ("FactITMachine", "SUM ( 'FactITMachine'[CostAmount] )")
    out[("停机时长", "FactITSLA")] = ("FactITSLA", "SUM ( 'FactITSLA'[DownTime] )")
    out[("故障次数", "FactITSLA")] = ("FactITSLA", "COUNTROWS ( 'FactITSLA' )")

    # Variants the L1 text states (metrics.yaml ``variants``; semantic-v1.4 range/variant check).
    for t in ("FactOnlineSales", "FactSales"):
        sales = D("销售额", t)
        cats = (f"VAR _cats = CALCULATETABLE ( VALUES ( 'DimProductSubcategory'[ProductCategoryKey] ),\n"
                f"    TREATAS ( VALUES ( 'DimProduct'[ProductSubcategoryKey] ), 'DimProductSubcategory'[ProductSubcategoryKey] ) )\n")
        out[(variant_key("销售额占比", "品类内"), t)] = (t, cats + (
            f"RETURN\n    DIVIDE ( {sales}, CALCULATE ( {sales}, REMOVEFILTERS ( 'DimProduct' ), "
            f"REMOVEFILTERS ( 'DimProductSubcategory' ), _cats ) )"))
        out[(variant_key("销售额环比增长率", "按季"), t)] = (t, (
            f"VAR _cur = {sales}\n"
            f"VAR _prev = CALCULATE ( {sales}, DATEADD ( 'DimDate'[DateKey], -1, QUARTER ) )\n"
            "RETURN\n    DIVIDE ( _cur - _prev, _prev )"))
    out[(variant_key("销售额占比", "渠道内"), "FactSales")] = ("FactSales", (
        f"DIVIDE ( {D('销售额', 'FactSales')}, CALCULATE ( {D('销售额', 'FactSales')}, REMOVEFILTERS ( 'DimStore' ), "
        "VALUES ( 'FactSales'[channelKey] ) ) )"))
    for name, col in (("目标销售额", "SalesAmountQuota"), ("目标销量", "SalesQuantityQuota"), ("目标毛利", "GrossMarginQuota")):
        out[(variant_key(name, "按查询场景"), "FactSalesQuota")] = ("FactSalesQuota", f"SUM ( {qt}[{col}] )")
    out[(variant_key("计划收入", "按查询场景"), "FactStrategyPlan")] = (
        "FactStrategyPlan", f"CALCULATE ( SUM ( {sp}[Amount] ), 'DimAccount'[AccountName] = \"Sale Revenue\" )")
    return out


# Hidden calculated column the current-inventory measures need (L2 model only).
DAX_CALCULATED_COLUMNS = {
    "FactInventory": [(
        "IsLatestSnapshot",
        "'FactInventory'[DateKey] = CALCULATE ( MAX ( 'FactInventory'[DateKey] ), "
        "ALLEXCEPT ( 'FactInventory', 'FactInventory'[StoreKey], 'FactInventory'[ProductKey] ) )",
        "boolean",
    )],
}


# ---------------------------------------------------------------------------
# Cube
# ---------------------------------------------------------------------------
# Cubes whose SQL is more than the plain table. Extra columns are prefixed with
# an underscore-free CamelCase name and are never exposed as dimensions.
CUBE_SQL = {
    "FactOnlineSales": (
        "SELECT f.*, c.FirstPurchaseDate, c.LastPurchaseDate\n"
        "FROM retail.FactOnlineSales AS f\n"
        "LEFT JOIN (\n"
        "    SELECT CustomerKey AS ck, min(DateKey) AS FirstPurchaseDate, max(DateKey) AS LastPurchaseDate\n"
        "    FROM retail.FactOnlineSales GROUP BY CustomerKey\n"
        ") AS c ON f.CustomerKey = c.ck"
    ),
    "FactSales": (
        "SELECT f.*, s.SellingAreaSize AS StoreSellingAreaSize, s.EmployeeCount AS StoreEmployeeCount,\n"
        "       y.StoreYears\n"
        "FROM retail.FactSales AS f\n"
        "LEFT JOIN (SELECT StoreKey AS sk, SellingAreaSize, EmployeeCount FROM retail.DimStore) AS s ON f.StoreKey = s.sk\n"
        "LEFT JOIN (\n"
        "    SELECT StoreKey AS yk, groupUniqArray(toYear(DateKey)) AS StoreYears\n"
        "    FROM retail.FactSales GROUP BY StoreKey\n"
        ") AS y ON f.StoreKey = y.yk"
    ),
    # Inventory snapshots plus the all-channel sales cost on the same keys, so the
    # turnover ratio (cost ÷ average on-hand value) can be computed in one cube.
    # IsInventoryRow separates the two; every inventory measure filters on it.
    "FactInventory": (
        "SELECT *, if(IsInventoryRow = 1,\n"
        "             DateKey = max(DateKey) OVER (PARTITION BY StoreKey, ProductKey, IsInventoryRow), 0) AS IsLatestSnapshot\n"
        "FROM (\n"
        "    SELECT InventoryKey, DateKey, StoreKey, ProductKey, CurrencyKey, OnHandQuantity, OnOrderQuantity,\n"
        "           SafetyStockQuantity, UnitCost, DaysInStock, MinDayInStock, MaxDayInStock, Aging,\n"
        "           toFloat64(0) AS SalesTotalCost, toUInt8(1) AS IsInventoryRow\n"
        "    FROM retail.FactInventory\n"
        "    UNION ALL\n"
        "    SELECT -SalesKey, DateKey, StoreKey, ProductKey, CurrencyKey, 0, 0, 0, 0, NULL, NULL, NULL, NULL,\n"
        "           TotalCost, toUInt8(0)\n"
        "    FROM retail.FactSales\n"
        ")"
    ),
    # Quota rows plus the all-channel actual sales on the same keys (no scenario),
    # so attainment (actual ÷ Budget quota) can be computed in one cube.
    "FactSalesQuota": (
        "SELECT q.*, sc.ScenarioName\n"
        "FROM (\n"
        "    SELECT SalesQuotaKey, ChannelKey, StoreKey, ProductKey, DateKey, CurrencyKey, toNullable(ScenarioKey) AS ScenarioKey,\n"
        "           SalesQuantityQuota, SalesAmountQuota, GrossMarginQuota, toFloat64(0) AS ActualSalesAmount, toUInt8(1) AS IsQuotaRow\n"
        "    FROM retail.FactSalesQuota\n"
        "    UNION ALL\n"
        "    SELECT -SalesKey, channelKey, StoreKey, ProductKey, DateKey, CurrencyKey, NULL,\n"
        "           NULL, NULL, NULL, SalesAmount, toUInt8(0)\n"
        "    FROM retail.FactSales\n"
        ") AS q\n"
        "LEFT JOIN (SELECT ScenarioKey AS sck, ScenarioName FROM retail.DimScenario) AS sc ON q.ScenarioKey = sc.sck"
    ),
    "FactStrategyPlan": (
        "SELECT p.*, sc.ScenarioName, a.AccountName\n"
        "FROM retail.FactStrategyPlan AS p\n"
        "LEFT JOIN (SELECT ScenarioKey AS sck, ScenarioName FROM retail.DimScenario) AS sc ON p.ScenarioKey = sc.sck\n"
        "LEFT JOIN (SELECT AccountKey AS ak, AccountName FROM retail.DimAccount) AS a ON p.AccountKey = a.ak"
    ),
}


def _f(sql: str) -> list[dict]:
    return [{"sql": sql}]


def cube_measures() -> dict[tuple[str, str], list[dict]]:
    """(metric, dataset) → list of Cube measure definitions; the first is the public
    member, the rest are hidden helpers it needs (public: false)."""
    out: dict[tuple[str, str], list[dict]] = {}
    promo = "{CUBE}.PromotionKey != 1"

    def member(metric: str, dataset: str) -> str:
        return NAMES[(metric, dataset)][1].split(".", 1)[1]

    def add(metric: str, dataset: str, spec: dict, *helpers: dict) -> None:
        out[(metric, dataset)] = [{"name": member(metric, dataset), **spec}, *helpers]

    for t in ("FactOnlineSales", "FactSales"):
        c = lambda name: C(name, t)  # noqa: E731
        add("销售额", t, {"type": "sum", "sql": "{CUBE}.SalesAmount"})
        add("销售数量", t, {"type": "sum", "sql": "{CUBE}.SalesQuantity"})
        add("总成本", t, {"type": "sum", "sql": "{CUBE}.TotalCost"})
        add("平均单价", t, {"type": "number", "sql": f"{c('销售额')} / nullIf({c('销售数量')}, 0)"})
        add("退货金额", t, {"type": "sum", "sql": "{CUBE}.ReturnAmount"})
        add("退货数量", t, {"type": "sum", "sql": "{CUBE}.ReturnQuantity"})
        add("净销售额", t, {"type": "number", "sql": f"{c('销售额')} - {c('退货金额')}"})
        add("退货率", t, {"type": "number", "sql": f"{c('退货数量')} / nullIf({c('销售数量')}, 0)"})
        add("折扣金额", t, {"type": "sum", "sql": "{CUBE}.DiscountAmount", "filters": _f(promo)})
        add("折扣数量", t, {"type": "sum", "sql": "{CUBE}.DiscountQuantity", "filters": _f(promo)})
        add("折扣前原价", t, {"type": "sum", "sql": "{CUBE}.SalesAmount + {CUBE}.DiscountAmount"})
        add("折扣率", t, {"type": "number", "sql": f"{c('折扣金额')} / nullIf({{discounted_list_amount}}, 0)"},
            {"name": "discounted_list_amount", "type": "sum", "sql": "{CUBE}.SalesAmount + {CUBE}.DiscountAmount",
             "filters": _f(promo), "public": False})
        add("打折销售额", t, {"type": "sum", "sql": "{CUBE}.SalesAmount", "filters": _f(promo)})
        add("打折销售额占比", t, {"type": "number", "sql": f"{c('打折销售额')} / nullIf({c('销售额')}, 0)"})
        add("毛利", t, {"type": "number", "sql": f"{c('销售额')} - {c('总成本')}"})
        add("毛利率", t, {"type": "number", "sql": f"{c('毛利')} / nullIf({c('销售额')}, 0)"})
        add("有销售天数", t, {"type": "count_distinct", "sql": "{CUBE}.DateKey"})
        add("日均销售额", t, {"type": "number", "sql": f"{c('销售额')} / nullIf({c('有销售天数')}, 0)"})
        add("日均销售数量", t, {"type": "number", "sql": f"{c('销售数量')} / nullIf({c('有销售天数')}, 0)"})
        add("产品数", t, {"type": "count_distinct", "sql": "{CUBE}.ProductKey"})
        add("销售额同比增长率", t,
            {"type": "number", "multi_stage": True,
             "sql": f"({c('销售额')} - {{sales_amount_prior_year}}) / nullIf({{sales_amount_prior_year}}, 0)"},
            {"name": "sales_amount_prior_year", "type": "number", "multi_stage": True, "sql": c("销售额"),
             "time_shift": [{"time_dimension": "DateKey", "interval": "1 year", "type": "prior"}], "public": False})
        add("销售额环比增长率", t,
            {"type": "number", "multi_stage": True,
             "sql": f"({c('销售额')} - {{sales_amount_prior_month}}) / nullIf({{sales_amount_prior_month}}, 0)"},
            {"name": "sales_amount_prior_month", "type": "number", "multi_stage": True, "sql": c("销售额"),
             "time_shift": [{"time_dimension": "DateKey", "interval": "1 month", "type": "prior"}], "public": False})
        add("销售额占比", t,
            {"type": "number", "multi_stage": True,
             "sql": f"{c('销售额')} / nullIf({{sales_amount_in_scope}}, 0)"},
            {"name": "sales_amount_in_scope", "type": "sum", "multi_stage": True, "sql": c("销售额"),
             "group_by": [], "public": False})

    o = "FactOnlineSales"
    c = lambda name: C(name, o)  # noqa: E731
    recency = f"dateDiff('month', {{CUBE}}.LastPurchaseDate, toDate('{AS_OF}'))"
    cutoff = f"least(max({{CUBE}}.DateKey), toDate('{AS_OF}'))"
    new_rows = ("arrayFilter((t, m) -> t.2 >= m - 89 AND t.2 <= m, "
                "groupArray(({CUBE}.CustomerKey, {CUBE}.FirstPurchaseDate, {CUBE}.SalesAmount)), "
                f"arrayWithConstant(count(), {cutoff}))")
    add("订单数", o, {"type": "count_distinct", "sql": "{CUBE}.SalesOrderNumber"})
    add("订单行数", o, {"type": "count"})
    add("每单行数", o, {"type": "number", "sql": f"{c('订单行数')} / nullIf({c('订单数')}, 0)"})
    add("客单价", o, {"type": "number", "sql": f"{c('销售额')} / nullIf({c('订单数')}, 0)"})
    add("客户数", o, {"type": "count_distinct", "sql": "{CUBE}.CustomerKey"})
    add("客均销售额", o, {"type": "number", "sql": f"{c('销售额')} / nullIf({c('客户数')}, 0)"})
    add("客均订单数", o, {"type": "number", "sql": f"{c('订单数')} / nullIf({c('客户数')}, 0)"})
    add("客户最近购买月数", o, {"type": "number", "sql": f"dateDiff('month', max({{CUBE}}.LastPurchaseDate), toDate('{AS_OF}'))"})
    add("活跃客户数", o, {"type": "count_distinct", "sql": "{CUBE}.CustomerKey", "filters": _f(f"{recency} <= 6")})
    add("有流失风险客户数", o, {"type": "count_distinct", "sql": "{CUBE}.CustomerKey",
                         "filters": _f(f"{recency} >= 7 AND {recency} <= 12")})
    add("已流失客户数", o, {"type": "count_distinct", "sql": "{CUBE}.CustomerKey", "filters": _f(f"{recency} > 12")})
    add("新客数", o, {"type": "number", "sql": f"length(arrayDistinct(arrayMap(t -> t.1, {new_rows})))"})
    add("新客销售额", o, {"type": "number", "sql": f"arraySum(arrayMap(t -> t.3, {new_rows}))"})
    add("新客销售额占比", o, {"type": "number", "sql": f"{c('新客销售额')} / nullIf({c('销售额')}, 0)"})

    s = "FactSales"
    c = lambda name: C(name, s)  # noqa: E731

    def store_sum(col: str) -> str:
        return f"arraySum(t -> t.2, groupUniqArray(({{CUBE}}.StoreKey, coalesce({{CUBE}}.{col}, 0))))"

    add("门店数", s, {"type": "count_distinct", "sql": "{CUBE}.StoreKey"})
    add("店均销售额", s, {"type": "number", "sql": f"{c('销售额')} / nullIf({c('门店数')}, 0)"})
    add("坪效", s, {"type": "number", "sql": f"sum({{CUBE}}.SalesAmount) / nullIf({store_sum('StoreSellingAreaSize')}, 0)"})
    add("门店人均销售额", s, {"type": "number", "sql": f"sum({{CUBE}}.SalesAmount) / nullIf({store_sum('StoreEmployeeCount')}, 0)"})
    add("同店销售额", s, {"type": "sum", "sql": "{CUBE}.SalesAmount",
                       "filters": _f("has({CUBE}.StoreYears, toYear({CUBE}.DateKey) - 1)")})
    add("同店销售额增长率", s,
        {"type": "number", "multi_stage": True,
         "sql": f"({c('同店销售额')} - {{same_store_base_prior_year}}) / nullIf({{same_store_base_prior_year}}, 0)"},
        {"name": "same_store_base", "type": "sum", "sql": "{CUBE}.SalesAmount",
         "filters": _f("has({CUBE}.StoreYears, toYear({CUBE}.DateKey) + 1)"), "public": False},
        {"name": "same_store_base_prior_year", "type": "number", "multi_stage": True, "sql": "{same_store_base}",
         "time_shift": [{"time_dimension": "DateKey", "interval": "1 year", "type": "prior"}], "public": False})

    p = "DimProduct"
    add("产品标价", p, {"type": "avg", "sql": "{CUBE}.UnitPrice"})
    add("产品单位成本", p, {"type": "avg", "sql": "{CUBE}.UnitCost"})
    add("产品利润率", p, {"type": "number",
                     "sql": "(sum({CUBE}.UnitPrice) - sum({CUBE}.UnitCost)) / nullIf(sum({CUBE}.UnitPrice), 0)"})

    i = "FactInventory"
    c = lambda name: C(name, i)  # noqa: E731
    inv_row = "{CUBE}.IsInventoryRow = 1"
    latest = [{"sql": inv_row}, {"sql": "{CUBE}.IsLatestSnapshot = 1"}]
    below = {"sql": "{CUBE}.OnHandQuantity < {CUBE}.SafetyStockQuantity"}
    add("当前在手库存数量", i, {"type": "sum", "sql": "{CUBE}.OnHandQuantity", "filters": latest})
    add("当前在手库存金额", i, {"type": "sum", "sql": "{CUBE}.OnHandQuantity * {CUBE}.UnitCost", "filters": latest})
    add("当前在订库存数量", i, {"type": "sum", "sql": "{CUBE}.OnOrderQuantity", "filters": latest})
    add("当前安全库存数量", i, {"type": "sum", "sql": "{CUBE}.SafetyStockQuantity", "filters": latest})
    add("低于安全库存的门店产品数", i, {"type": "count", "filters": latest + [below]})
    add("快照日在手库存数量", i, {"type": "sum", "sql": "{CUBE}.OnHandQuantity", "filters": _f(inv_row)})
    add("快照日在订库存数量", i, {"type": "sum", "sql": "{CUBE}.OnOrderQuantity", "filters": _f(inv_row)})
    add("快照日安全库存数量", i, {"type": "sum", "sql": "{CUBE}.SafetyStockQuantity", "filters": _f(inv_row)})
    add("快照日低于安全库存的门店产品数", i, {"type": "count", "filters": [{"sql": inv_row}, below]})
    add("门店产品组合数", i, {"type": "number",
                         "sql": "uniqExactIf(({CUBE}.StoreKey, {CUBE}.ProductKey), {CUBE}.IsInventoryRow = 1)"})
    add("快照日在手库存金额", i, {"type": "sum", "sql": "{CUBE}.OnHandQuantity * {CUBE}.UnitCost", "filters": _f(inv_row)})
    avg_value = ("sumIf({CUBE}.OnHandQuantity * {CUBE}.UnitCost, {CUBE}.IsInventoryRow = 1) "
                 "/ nullIf(uniqExactIf({CUBE}.DateKey, {CUBE}.IsInventoryRow = 1), 0)")
    add("平均在手库存金额", i, {"type": "number", "sql": avg_value})
    add("库存周转率", i, {"type": "number", "sql": f"sum({{CUBE}}.SalesTotalCost) / nullIf({avg_value}, 0)"})

    q = "FactSalesQuota"
    budget = [{"sql": "{CUBE}.IsQuotaRow = 1"}, {"sql": "{CUBE}.ScenarioName = 'Budget'"}]
    add("目标销售额", q, {"type": "sum", "sql": "{CUBE}.SalesAmountQuota", "filters": budget})
    add("目标销量", q, {"type": "sum", "sql": "{CUBE}.SalesQuantityQuota", "filters": budget})
    add("目标毛利", q, {"type": "sum", "sql": "{CUBE}.GrossMarginQuota", "filters": budget})
    actual = "sumIf({CUBE}.ActualSalesAmount, {CUBE}.IsQuotaRow = 0)"
    budget_quota = "sumIf({CUBE}.SalesAmountQuota, {CUBE}.IsQuotaRow = 1 AND {CUBE}.ScenarioName = 'Budget')"
    add("目标达成率", "FactSales", {"type": "number", "sql": f"{actual} / nullIf({budget_quota}, 0)"})
    add("目标差异", "FactSales", {"type": "number", "sql": f"{actual} - {budget_quota}"})

    sp = "FactStrategyPlan"
    add("计划金额", sp, {"type": "sum", "sql": "{CUBE}.Amount"})
    add("计划收入", sp, {"type": "sum", "sql": "{CUBE}.Amount",
                     "filters": [{"sql": "{CUBE}.AccountName = 'Sale Revenue'"}, {"sql": "{CUBE}.ScenarioName = 'Budget'"}]})

    add("IT 成本", "FactITMachine", {"type": "sum", "sql": "{CUBE}.CostAmount"})
    add("停机时长", "FactITSLA", {"type": "sum", "sql": "{CUBE}.DownTime"})
    add("故障次数", "FactITSLA", {"type": "count"})

    # Variants the L1 text states (metrics.yaml ``variants``). Parent-group shares drop the child
    # levels from the denominator's grouping (reduce_by) and keep every other dimension and filter.
    def dims(dataset: str, cube: str) -> list[str]:
        ds = next(d for d in source()["datasets"] if d["name"] == dataset)
        return [f"{cube}.{col['name']}" for col in ds["columns"]]

    for t, own in (("FactOnlineSales", "online_sales"), ("FactSales", "sales")):
        c = lambda name: C(name, t)  # noqa: E731
        product_levels = [f"{own}.ProductKey", *dims("DimProduct", "product"),
                          *dims("DimProductSubcategory", "product_subcategory")]
        add(variant_key("销售额占比", "品类内"), t,
            {"type": "number", "multi_stage": True, "sql": f"{c('销售额')} / nullIf({{sales_amount_in_category}}, 0)"},
            {"name": "sales_amount_in_category", "type": "sum", "multi_stage": True, "sql": c("销售额"),
             "reduce_by": product_levels, "public": False})
        add(variant_key("销售额环比增长率", "按季"), t,
            {"type": "number", "multi_stage": True,
             "sql": f"({c('销售额')} - {{sales_amount_prior_quarter}}) / nullIf({{sales_amount_prior_quarter}}, 0)"},
            {"name": "sales_amount_prior_quarter", "type": "number", "multi_stage": True, "sql": c("销售额"),
             "time_shift": [{"time_dimension": "DateKey", "interval": "1 quarter", "type": "prior"}], "public": False})
    c = lambda name: C(name, "FactSales")  # noqa: E731
    add(variant_key("销售额占比", "渠道内"), "FactSales",
        {"type": "number", "multi_stage": True, "sql": f"{c('销售额')} / nullIf({{sales_amount_in_channel}}, 0)"},
        {"name": "sales_amount_in_channel", "type": "sum", "multi_stage": True, "sql": c("销售额"),
         "reduce_by": ["sales.StoreKey", *dims("DimStore", "store")], "public": False})
    quota_rows = [{"sql": "{CUBE}.IsQuotaRow = 1"}]
    add(variant_key("目标销售额", "按查询场景"), q, {"type": "sum", "sql": "{CUBE}.SalesAmountQuota", "filters": quota_rows})
    add(variant_key("目标销量", "按查询场景"), q, {"type": "sum", "sql": "{CUBE}.SalesQuantityQuota", "filters": quota_rows})
    add(variant_key("目标毛利", "按查询场景"), q, {"type": "sum", "sql": "{CUBE}.GrossMarginQuota", "filters": quota_rows})
    add(variant_key("计划收入", "按查询场景"), sp, {"type": "sum", "sql": "{CUBE}.Amount",
                                              "filters": [{"sql": "{CUBE}.AccountName = 'Sale Revenue'"}]})
    return out


def cube_of_member(member: str) -> str:
    return member.split(".", 1)[0]
