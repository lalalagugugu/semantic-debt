"""T26 step 6 rules, fixed before any per-question L3a outcome was read.

Entry -> question: an entry "involves" a question when the entry's signature
regex (case-insensitive) matches the reference SQL of any of the question's refs.
Signatures name only the entry's own anchor columns / tables / literals, so a
question answered through other columns (e.g. toMonth(DateKey) instead of
DimDate.MonthNumber) is not counted. Rules are applied mechanically; no question
text is read by this module.

Outcome per question (v2 final scoring, run 20261025-T22b-l1plus-l3a-03-rescore-01):
  wrong  = fewer than 3 of 3 attempts correct (at least one non-correct);
  all_wrong = 0 of 3 correct.
Both the 109-question set and the 98-question main set are reported; SQL-L1plus
is reported alongside on the same questions.

"Written wrong" entries are those judged 不一致 in step 3 or implicated by a
step 2 finding; "shallow" candidates are the annotation-retained entries listed
in FORMALIZABLE (judged from the L1+ text alone).
"""

# Anchor signatures of the 30 formalized entries.
FORMAL = {
    "E01": r"\bchannelKey\b|\bChannelName\b",
    "E02": r"\bStoreKey\s*(=|IN\s*\()\s*[^)]*?\b(199|306|307)\b",
    "E03": r"\bContinentName\b",
    "E04": r"\bRegionCountryName\b",
    "E05": r"\bProductCategoryName\b|\bProductSubcategoryName\b",
    "E06": r"\bBrandName\b",
    "E07": r"\bColorName\b",
    "E08": r"\bClassName\b|\bStockTypeName\b",
    "E09": r"\bPromotionKey\b|\bPromotionName\b",
    "E10": r"Season\b",
    "E11": r"\bScenarioKey\b|\bScenarioName\b",
    "E12": r"\bAccountKey\b|\bAccountName\b",
    "E13": r"\b(Gender|MaritalStatus|Education|Occupation|HouseOwnerFlag)\b",
    "E14": r"\b(CalendarHalfYearLabel|CalendarQuarterLabel|MonthNumber|CalendarDayOfWeekLabel|IsWorkDay|IsHoliday)\b",
    "E15": r"(?s)(?=.*\bDimStore\b).*\bStatus\b",
    "E16": r"\bMachineType\b",
    "E17": r"\bTitle\b",
    "H01": r"\bSalesQuantity\s*(>|=|>=)\s*0\b|\bReturnQuantity\b|\bchannelKey\s*=\s*2\b",
    "H02": r"(?s)(?=.*\bDimStore\b).*\b(StoreType|Status|GeographyKey|EmployeeKey|EntityKey)\b",
    "H03": r"(?s)(?=.*\bDimProduct\b).*\b(Status|ProductSubcategoryKey)\b|\bDimProductCategory\b",
    "H04": r"\bDimGeography\b",
    "H05": r"\bDimEntity\b",
    "H06": r"\bDimEmployee\b",
    "H07": r"\bAccountKey\b|\bDimAccount\b",
    "H08": r"\bCustomerKey\b",
    "H09": r"\bPromotionKey\b",
    "H10": r"\bScenarioKey\b|\bScenarioName\b|\bDimScenario\b",
    "H11": r"\bIsWorkDay\b|\bIsHoliday\b",
    "H12": r"\bFactInventory\b",
    "H13": r"\bDimMachine\b|\bFactITMachine\b|\bMachineType\b|\bCostType\b",
}

# Annotation-retained entries whose core content has a ready-made OWL / SHACL
# idiom, judged from the L1+ text only: (construct, signature).
FORMALIZABLE = {
    "A17": ("类定义 sh:not [sh:hasValue 1]（打折交易 = PromotionKey != 1）；比率本身不可",
            r"\bPromotionKey\s*(!=|<>|>|=)\s*1\b"),
    "A19": ("基数 / 函数性：促销键 → 促销名 sh:maxCount 1，每个打折促销名 sh:qualifiedMinCount 3",
            r"\bDimPromotion\b"),
    "A24": ("sh:lessThan（在手 < 安全库存）、sh:hasValue 0（零库存）；跨店汇总不可",
            r"\bSafetyStockQuantity\b|\bOnHandQuantity\s*=\s*0\b"),
    "A27": ("互斥覆盖 owl:disjointUnionOf（三层覆盖分层客户集合）；末购日分层不可",
            r"(?s)(?=.*\bCustomerKey\b).*dateDiff\s*\(\s*'month'"),
    "A33": ("固定取值 sh:in（计划表 17 个叶子科目）、sh:minExclusive 0（Amount 为正）、传递祖先属性",
            r"\bAccountKey\b|\bDimAccount\b"),
    "A34": ("固定取值 sh:in / hasValue（CostType 两值）", r"\bCostType\b|\bFactITMachine\b"),
    "A38": ("层级：员工实例树（同 H07 写法）+ 根 18 + 无环 SHACL-SPARQL", r"\bDimEmployee\b"),
    "A40": ("实例断言：子类 19 属于品类 Computers", r"\bProductCategoryName\b|\bDimProductCategory\b"),
    "A41": ("层级：断环后的科目树（H07 已有实例树）+ 无环 SHACL-SPARQL", r"\bAccountKey\b|\bDimAccount\b"),
    "D05": ("基数 owl:minQualifiedCardinality 2（≥ 2 个订单）；窗口不可",
            r"(?s)(?=.*\bSalesOrderNumber\b).*(>=\s*2|>\s*1)\b"),
    "D05b": ("同 D05，限定 SalesQuantity > 0 的订单", r"(?s)(?=.*\bSalesOrderNumber\b).*(>=\s*2|>\s*1)\b"),
    "D09": ("互斥覆盖（同 A27）；比率不可", r"(?s)(?=.*\bCustomerKey\b).*dateDiff\s*\(\s*'month'"),
    "D10": ("取值区间分档 sh:minInclusive / sh:maxExclusive", r"\bBirthDate\b"),
    "D11": ("取值区间分档 sh:minInclusive / sh:maxExclusive", r"\bYearlyIncome\b"),
    "D23": ("固定取值 hasValue 'Off' + rdfs:subClassOf 实体店（12 家全是实体店）",
            r"\bCloseDate\b|\bStatus\s*=\s*'Off'"),
    "D32": ("层级：费用叶子集合 = 科目树传递闭包；减法不可", r"\bAccountKey\b|\bDimAccount\b"),
}
