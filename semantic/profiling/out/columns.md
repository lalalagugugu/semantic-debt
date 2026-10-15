# 逐列探查结果

由 `semantic/profiling/profile_columns.py` 生成，不要手改。

- chDB / ClickHouse 版本：`26.9.2.1`
- 低基数判定线：不同取值 ≤ 50 就列出全部取值
- 「空值率」只统计 SQL NULL；空字符串算一个取值，在取值表里看得到

## DimAccount

行数：24

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `AccountKey` | Int32 | 24 | 0.00% | `1`(1)；`2`(1)；`3`(1)；`4`(1)；`5`(1)；`6`(1)；`7`(1)；`8`(1)；`9`(1)；`10`(1)；`11`(1)；`12`(1)；`13`(1)；`14`(1)；`15`(1)；`16`(1)；`17`(1)；`18`(1)；`19`(1)；`20`(1)；`21`(1)；`22`(1)；`23`(1)；`24`(1) |
| `ParentAccountKey` | Nullable(Float64) | 7 | 0.00% | `1`(2)；`2`(1)；`3`(2)；`6`(7)；`13`(5)；`14`(4)；`24`(3) |
| `AccountName` | String | 24 | 0.00% | `Administration Expense`(1)；`Back-to-School Ad Cost`(1)；`Business Ad Cost`(1)；`Cost of Goods Sold`(1)；`Expense`(1)；`Holiday Ad Cost`(1)；`Human Capital`(1)；`IT Cost`(1)；`Income`(1)；`Internet`(1)；`Light, Heat, Communication Cost`(1)；`Marketing Cost`(1)；`Other`(1)；`Other Expenses`(1)；`Print`(1)；`Profit and Loss after tax`(1)；`Profit and Loss before tax`(1)；`Property Costs`(1)；`Radio & TV`(1)；`Sale Revenue`(1)；`Selling, General & Administrative Expenses`(1)；`Spring Ad Cost`(1)；`Tax Time / Summer Ad Cost`(1)；`Taxation`(1) |
| `AccountDescription` | String | 24 | 0.00% | `Administration Expense`(1)；`Back-to-School Ad Cost`(1)；`Business Ad Cost`(1)；`Cost of Goods Sold`(1)；`Expense`(1)；`Holiday Ad Cost`(1)；`Holiday Ad Cost by Internet`(1)；`Holiday Ad Cost by Other`(1)；`Holiday Ad Cost by Print`(1)；`Holiday Ad Cost by Radio & TV`(1)；`Human Capital`(1)；`IT Cost`(1)；`Income`(1)；`Light, Heat, Communication Cost`(1)；`Marketing & Advertisement Cost`(1)；`Other Expenses`(1)；`Profit and Loss after tax`(1)；`Profit and Loss before tax`(1)；`Property Costs`(1)；`Sale Revenue`(1)；`Selling, General & Administrative Expenses`(1)；`Spring Ad Cost`(1)；`Tax Time / Summer Ad Cost`(1)；`Taxation`(1) |
| `AccountType` | String | 3 | 0.00% | `Expense`(19)；`Income`(4)；`Taxation`(1) |
| `ValueType` | String | 3 | 0.00% | `Expense`(19)；`Income`(4)；`Taxation`(1) |

## DimChannel

行数：4

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ChannelKey` | Int32 | 4 | 0.00% | `1`(1)；`2`(1)；`3`(1)；`4`(1) |
| `ChannelName` | String | 4 | 0.00% | `Catalog`(1)；`Online`(1)；`Reseller`(1)；`Store`(1) |
| `ChannelDescription` | String | 4 | 0.00% | `Catalog`(1)；`Online`(1)；`Reseller`(1)；`Store`(1) |

## DimCurrency

行数：28

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `CurrencyKey` | Int32 | 28 | 0.00% | `1`(1)；`2`(1)；`3`(1)；`4`(1)；`5`(1)；`6`(1)；`7`(1)；`8`(1)；`9`(1)；`10`(1)；`11`(1)；`12`(1)；`13`(1)；`14`(1)；`15`(1)；`16`(1)；`17`(1)；`18`(1)；`19`(1)；`20`(1)；`21`(1)；`22`(1)；`23`(1)；`24`(1)；`25`(1)；`26`(1)；`27`(1)；`28`(1) |
| `CurrencyName` | String | 28 | 0.00% | `AMD`(1)；`AUD`(1)；`BTN`(1)；`CAD`(1)；`CHF`(1)；`CNY`(1)；`DKK`(1)；`EUR`(1)；`GBP`(1)；`HKD`(1)；`INR`(1)；`IRR`(1)；`JPY`(1)；`KGS`(1)；`KRW`(1)；`MTL`(1)；`PKR`(1)；`PLN`(1)；`ROL`(1)；`RUB`(1)；`SEK`(1)；`SGD`(1)；`SIT`(1)；`SYP`(1)；`THB`(1)；`TMM`(1)；`TWD`(1)；`USD`(1) |
| `CurrencyDescription` | String | 28 | 0.00% | `Armenian Dram`(1)；`Australian Dollar`(1)；`Bhutan Ngultrum`(1)；`British Pound`(1)；`Canadian Dollar`(1)；`Danish Krone`(1)；`EURO`(1)；`Hong Kong Dollar`(1)；`Indian Rupee`(1)；`Iranian Rial`(1)；`Japanese Yen`(1)；`Maltese Lira`(1)；`Pakistan Rupee`(1)；`Polish Zloty`(1)；`Renminbi Yuan`(1)；`Romanian Leu`(1)；`Russian Ruble`(1)；`Singapore Dollar`(1)；`Slovenian Tolar`(1)；`Som`(1)；`South Korean Won`(1)；`Swedish Krona`(1)；`Swiss Franc`(1)；`Syrian Pound`(1)；`Taiwan Dollar`(1)；`Thai Baht`(1)；`Turkmenistan Manat`(1)；`US Dollar`(1) |

## DimCustomer

行数：18,869

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `RowNum` | Int32 | 18,869 | 0.00% | 0 ~ 18868 |
| `CustomerKey` | Int32 | 18,869 | 0.00% | 1 ~ 19145 |
| `GeographyKey` | Int32 | 476 | 0.00% | 423 ~ 952 |
| `FirstName` | String | 671 | 0.00% | 最常见：`Not Provided`、`Marcus`、`Katherine`、`Richard`、`Lucas` |
| `LastName` | String | 376 | 0.00% | 最常见：`Not Provided`、`Diaz`、`Hernandez`、`Sanchez`、`Torres` |
| `BirthDate` | Nullable(String) | 8,452 | 0.00% | 最常见：`1967-05-14`、`1966-03-18`、`1965-04-02`、`1972-03-13`、`1965-08-27` |
| `MaritalStatus` | Nullable(String) | 2 | 0.00% | `M`(10,188)；`S`(8,681) |
| `Gender` | Nullable(String) | 2 | 0.00% | `M`(9,525)；`F`(9,344) |
| `YearlyIncome` | Nullable(Float64) | 17 | 0.00% | `10000`(1,155)；`20000`(1,767)；`30000`(2,287)；`40000`(2,747)；`50000`(670)；`60000`(3,127)；`70000`(2,349)；`80000`(1,342)；`90000`(842)；`100000`(571)；`110000`(474)；`120000`(332)；`130000`(512)；`150000`(103)；`160000`(94)；`170000`(112)；`10000000`(385) |
| `TotalChildren` | Nullable(Float64) | 6 | 0.00% | `0`(5,236)；`1`(3,674)；`2`(3,852)；`3`(2,257)；`4`(2,374)；`5`(1,476) |
| `NumberChildrenAtHome` | Nullable(Float64) | 6 | 0.00% | `0`(11,185)；`1`(2,528)；`2`(1,704)；`3`(1,274)；`4`(1,136)；`5`(1,042) |
| `Education` | Nullable(String) | 5 | 0.00% | `Bachelors`(5,448)；`Partial College`(5,138)；`High School`(3,362)；`Graduate Degree`(3,260)；`Partial High School`(1,661) |
| `Occupation` | Nullable(String) | 5 | 0.00% | `Professional`(5,606)；`Skilled Manual`(4,649)；`Management`(3,147)；`Clerical`(3,014)；`Manual`(2,453) |
| `HouseOwnerFlag` | Nullable(Float64) | 2 | 0.00% | `0`(6,165)；`1`(12,704) |
| `NumberCarsOwned` | Nullable(Float64) | 5 | 0.00% | `0`(4,302)；`1`(4,973)；`2`(6,530)；`3`(1,726)；`4`(1,338) |

## DimDate

行数：2,556

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `DateKey` | Date | 2,556 | 0.00% | 2005-01-01 ~ 2011-12-31 |
| `CalendarYear` | Int32 | 7 | 0.00% | `2005`(365)；`2006`(365)；`2007`(365)；`2008`(366)；`2009`(365)；`2010`(365)；`2011`(365) |
| `CalendarYearLabel` | String | 7 | 0.00% | `Year 2008`(366)；`Year 2005`(365)；`Year 2006`(365)；`Year 2007`(365)；`Year 2009`(365)；`Year 2010`(365)；`Year 2011`(365) |
| `CalendarHalfYearLabel` | String | 2 | 0.00% | `H2`(1,288)；`H1`(1,268) |
| `CalendarQuarterLabel` | String | 4 | 0.00% | `Q3`(644)；`Q4`(644)；`Q2`(637)；`Q1`(631) |
| `CalendarMonthLabel` | String | 12 | 0.00% | `August`(217)；`December`(217)；`January`(217)；`July`(217)；`March`(217)；`May`(217)；`October`(217)；`April`(210)；`June`(210)；`November`(210)；`September`(210)；`February`(197) |
| `CalendarWeekLabel` | String | 53 | 0.00% | 最常见：`Week 4`、`Week 32`、`Week 33`、`Week 6`、`Week 12` |
| `CalendarDayOfWeekLabel` | String | 7 | 0.00% | `Saturday`(366)；`Friday`(365)；`Monday`(365)；`Sunday`(365)；`Thursday`(365)；`Tuesday`(365)；`Wednesday`(365) |
| `FiscalYear` | Int32 | 7 | 0.00% | `2005`(365)；`2006`(365)；`2007`(365)；`2008`(366)；`2009`(365)；`2010`(365)；`2011`(365) |
| `FiscalYearLabel` | String | 7 | 0.00% | `FiscalYear 2008`(366)；`FiscalYear 2005`(365)；`FiscalYear 2006`(365)；`FiscalYear 2007`(365)；`FiscalYear 2009`(365)；`FiscalYear 2010`(365)；`FiscalYear 2011`(365) |
| `FiscalHalfYearLabel` | String | 2 | 0.00% | `H2`(1,288)；`H1`(1,268) |
| `FiscalQuarterLabel` | String | 4 | 0.00% | `Q3`(644)；`Q4`(644)；`Q2`(637)；`Q1`(631) |
| `FiscalMonthLabel` | String | 12 | 0.00% | `Month 1`(217)；`Month 10`(217)；`Month 12`(217)；`Month 3`(217)；`Month 5`(217)；`Month 7`(217)；`Month 8`(217)；`Month 11`(210)；`Month 4`(210)；`Month 6`(210)；`Month 9`(210)；`Month 2`(197) |
| `IsWorkDay` | String | 2 | 0.00% | `WorkDay`(1,825)；`WeekEnd`(731) |
| `IsHoliday` | String | 2 | 0.00% | `No`(1,825)；`Yes`(731) |
| `EuropeSeason` | String | 4 | 0.00% | `Holiday`(861)；`No Season`(847)；`Back to School`(434)；`Spring/Business`(414) |
| `NorthAmericaSeason` | String | 4 | 0.00% | `No Season`(854)；`Back to School`(644)；`Spring/Back to Business`(631)；`Holiday`(427) |
| `AsiaSeason` | String | 4 | 0.00% | `No Season`(1,071)；`Holiday`(644)；`Spring/Back to School`(624)；`Tax Time/Summer`(217) |
| `MonthNumber` | Int32 | 12 | 0.00% | `1`(217)；`2`(197)；`3`(217)；`4`(210)；`5`(217)；`6`(210)；`7`(217)；`8`(217)；`9`(210)；`10`(217)；`11`(210)；`12`(217) |
| `CalendarDayOfWeekNumber` | Int32 | 7 | 0.00% | `1`(365)；`2`(365)；`3`(365)；`4`(365)；`5`(365)；`6`(366)；`7`(365) |

## DimEmployee

行数：293

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `EmployeeKey` | Int32 | 293 | 0.00% | 1 ~ 296 |
| `ParentEmployeeKey` | Nullable(Float64) | 11 | 0.00% | `1`(7)；`2`(6)；`3`(5)；`4`(3)；`5`(3)；`6`(65)；`7`(33)；`8`(33)；`9`(89)；`10`(44)；`18`(5) |
| `FirstName` | String | 234 | 0.00% | 最常见：`Michael`、`David`、`Jeff`、`Daniel`、`Chris` |
| `LastName` | String | 288 | 0.00% | 最常见：`Garcia`、`Brown`、`Smith`、`Alexander`、`Richardson` |
| `Title` | Nullable(String) | 4 | 0.00% | `Sales Store Manager`(264)；`Sales State Manager`(23)；`Sales Region Manager`(5)；`Sales Group Manager`(1) |
| `HireDate` | Nullable(String) | 164 | 0.00% | 最常见：`2001-07-01`、`1999-03-30`、`1999-01-08`、`1999-03-12`、`1999-03-04` |
| `BirthDate` | Nullable(String) | 276 | 0.00% | 最常见：`1968-03-13`、`1966-02-06`、`1977-03-13`、`1976-10-11`、`1976-11-01` |
| `EmailAddress` | Nullable(String) | 293 | 0.00% | 最常见：`anibal0@contoso.com`、`suchitra0@contoso.com`、`stefen0@contoso.com`、`jack1@contoso.com`、`michael1@contoso.com` |
| `Phone` | Nullable(String) | 285 | 0.00% | 最常见：`210-555-0193`、`612-555-0100`、`615-555-0110`、`913-555-0172`、`208-555-0114` |
| `EmergencyContactName` | Nullable(String) | 293 | 0.00% | 最常见：`Tien Dung Thoi`、`Terri Chudzik`、`David Campbell`、`Dushyant Bansal`、`Ian Palangio` |
| `EmergencyContactPhone` | Nullable(String) | 285 | 0.00% | 最常见：`210-555-0193`、`612-555-0100`、`615-555-0110`、`913-555-0172`、`208-555-0114` |
| `Gender` | Nullable(String) | 2 | 0.00% | `Male`(206)；`Female`(87) |
| `PayFrequency` | Nullable(String) | 2 | 0.00% | `1`(147)；`2`(146) |
| `BaseRate` | Nullable(Float64) | 4 | 0.00% | `25`(264)；`55`(23)；`72.45`(5)；`125`(1) |
| `VacationHours` | Nullable(Float64) | 99 | 0.00% | 0 ~ 99 |
| `DepartmentName` | Nullable(String) | 17 | 0.00% | `Production`(176)；`Sales`(18)；`Purchasing`(13)；`Finance`(10)；`Information Services`(10)；`Marketing`(10)；`Facilities and Maintenance`(7)；`Production Control`(7)；`Engineering`(6)；`Human Resources`(6)；`Quality Assurance`(6)；`Shipping and Receiving`(6)；`Document Control`(5)；`Tool Design`(5)；`Research and Development`(4)；`Executive`(3)；`'Human Resources Contral`(1) |
| `StartDate` | Nullable(String) | 170 | 0.00% | 最常见：`2001-07-01`、`1999-01-08`、`1999-03-30`、`1999-03-12`、`1999-01-13` |
| `Status` | Nullable(String) | 1 | 0.00% | `Current`(293) |
| `SalaryStatus` | Nullable(String) | 2 | 0.00% | `Not Salaried`(237)；`Salaried`(56) |
| `IsSalesPerson` | Nullable(String) | 2 | 0.00% | `No`(276)；`Yes`(17) |
| `IsMarried` | Nullable(String) | 2 | 0.00% | `No`(147)；`Yes`(146) |

## DimEntity

行数：421

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `EntityKey` | Int32 | 421 | 0.00% | 1 ~ 949 |
| `ParentEntityKey` | Nullable(Float64) | 114 | 0.00% | 1 ~ 943 |
| `ParentEntityLabel` | Nullable(String) | 113 | 0.00% | 最常见：`Texas`、`Colorado`、`Wisconsin`、`Massachusetts`、`Washington` |
| `EntityName` | String | 419 | 0.00% | 最常见：`Contoso Singapore`、`Contoso Taiwan`、`Contoso Montreal No.1 Store`、`Contoso Hong Kong`、`Contoso Everett Store` |
| `EntityDescription` | Nullable(String) | 419 | 0.00% | 最常见：`Contoso Taiwan`、`Contoso Singapore`、`Contoso Appleton Store`、`Contoso Longview Store`、`Contoso Cheney Store` |
| `EntityType` | Nullable(String) | 4 | 0.00% | `Store`(306)；`State`(79)；`Country/Region`(33)；`Group`(3) |
| `StartDate` | Nullable(String) | 166 | 0.00% | 最常见：`2003-07-01 00:00:00.000`、`2002-11-01 00:00:00.000`、`2003-04-15 00:00:00.000`、`2001-07-01 00:00:00.000`、`1999-02-14 00:00:00.000` |
| `Status` | Nullable(String) | 1 | 0.00% | `Current`(421) |

## DimGeography

行数：674

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `GeographyKey` | Int32 | 674 | 0.00% | 1 ~ 952 |
| `GeographyType` | String | 4 | 0.00% | `City`(517)；`State/Province`(120)；`Country/Region`(34)；`Continent`(3) |
| `ContinentName` | String | 3 | 0.00% | `North America`(339)；`Europe`(221)；`Asia`(114) |
| `CityName` | Nullable(String) | 511 | 23.29% | 最常见：`Saint Ouen`、`Columbus`、`Frankfurt`、`Burbank`、`Birmingham` |
| `StateProvinceName` | Nullable(String) | 125 | 5.49% | 最常见：`California`、`England`、`Washington`、`Texas`、`Massachusetts` |
| `RegionCountryName` | String | 35 | 0.00% | `United States`(312)；`France`(65)；`Germany`(54)；`Australia`(47)；`United Kingdom`(47)；`Canada`(26)；`Japan`(13)；`China`(11)；`Italy`(11)；`India`(7)；`Russia`(7)；`South Korea`(5)；``(3)；`Armenia`(3)；`Bhutan`(3)；`Denmark`(3)；`Greece`(3)；`Iran`(3)；`Ireland`(3)；`Kyrgyzstan`(3)；`Malta`(3)；`Pakistan`(3)；`Poland`(3)；`Portugal`(3)；`Romania`(3)；`Singapore`(3)；`Slovenia`(3)；`Spain`(3)；`Sweden`(3)；`Switzerland`(3)；`Syria`(3)；`Taiwan`(3)；`Thailand`(3)；`Turkmenistan`(3)；`the Netherlands`(3) |

## DimMachine

行数：7,816

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `MachineKey` | Int32 | 7,816 | 0.00% | 1 ~ 7816 |
| `StoreKey` | Int32 | 303 | 0.00% | 1 ~ 307 |
| `MachineType` | String | 9 | 0.00% | `WSR01`(3,040)；`POS01`(2,679)；`WSR02`(1,060)；`HUB01`(460)；`MSR01`(346)；`POS02`(102)；`POS03`(73)；`POS04`(46)；`RUT01`(10) |
| `MachineName` | String | 9 | 0.00% | `Fabrikam NAS Web Server`(3,040)；`Fabrikam Point of Sale 4-in-1`(1,945)；`Fabrikam Imperium SVIXV9080H Server`(1,060)；`A. Datum Corporation DUB-H7 High Speed USB 2.0 7-Port Hub`(460)；`Fabrikam Point of Sale System 2.0`(383)；`Fabrikam Point of Sale System`(359)；`Fabrikam 250GB Mail Server Mail Server`(346)；`Fabrikam Point of Sale High Version 1.0`(213)；`A. Datum Corporation ME1004-R Wireless Cable/DSL Router`(10) |
| `MachineDescription` | Nullable(String) | 9 | 0.00% | `4GB DDR2 Memory; 250GB Hard Drives; Windows 2003 Web Server`(3,040)；`Kit contains one convenient box, barcode scanner, receipt printer, cash drawer and keyboard.`(1,945)；`Dual Contoso 2.00GHz Core Processors; Windows 2008 Web Server`(1,060)；`PC and Mac Compatible; Up to 40 Times Faster than USB 1.1`(460)；`Kit contains 15" LCD screen, Cash Drawer, Barcode Scanner and Receipt Printer.`(383)；`Kit contains 15" LCD screen, 1 cash drawer port and 5 USB ports.`(359)；`Contoso 2.00GHz Core Processor; Windows 2003`(346)；`Kit contains 15" LCD screen, Cash Drawer, Barcode Scanner, Receipt Printer,Power Supply and Magstripe Reader.`(213)；`Offers backward-compatibility with all 802.11b devices`(10) |
| `VendorName` | Nullable(String) | 2 | 0.00% | `Fabrikam, Inc.`(7,346)；`A. Datum Corporation`(470) |
| `MachineOS` | Nullable(String) | 7 | 0.00% | `Windows Server 2003`(3,386)；`Linux2.6`(2,304)；`Windows Server 2008`(1,060)；`UNKNOWN`(460)；`Windows Embedded for Point of Service`(383)；`Windows Embedded POSReady 2009`(213)；`Router OS`(10) |
| `MachineSource` | Nullable(String) | 3 | 0.00% | `Online Data Center`(4,341)；`Store`(2,900)；`Catalog Data Center`(575) |
| `MachineHardware` | Nullable(String) | 9 | 0.00% | `4GB DDR2 Memory; 250GB Hard Drives`(3,040)；`15" LCD screen; 4 USB ports (USB 1.0)`(1,945)；`Dual 2.33GHz Core Processor; 8GB DDR2 667MHz PC5400 Memory;`(1,060)；`7-Port (each port can be used as either an RJ-45 10/100 port)`(460)；`15" LCD screen;Cash Drawer, Barcode Scanner, Receipt Printer`(383)；`15" LCD screen;1 cash drawer port;5 USB ports (USB 2.0)`(359)；`Contoso 2.00GHz Core Processors; 4GB Memory; 250GB Hard Drives`(346)；`15" LCD screen;Cash Drawer, Barcode Scanner,Receipt Printer,Power Supply, Magstripe Reader`(213)；`4-port (Wireless Cable/DSL access point)`(10) |
| `MachineSoftware` | Nullable(String) | 7 | 0.00% | `Windows Server 2003`(3,386)；`Linux2.6`(2,304)；`Windows Server 2008`(1,060)；`UNKNOWN`(460)；`Windows Embedded for Point of Service`(383)；`Windows Embedded POSReady 2009`(213)；`Router OS; NAT and SPI firewall`(10) |
| `Status` | Nullable(String) | 1 | 0.00% | `Used`(7,816) |
| `ServiceStartDate` | Nullable(String) | 160 | 0.00% | 最常见：`2004-08-25 00:00:00.000`、`2004-10-26 00:00:00.000`、`2004-02-18 00:00:00.000`、`2004-07-02 00:00:00.000`、`2004-02-19 00:00:00.000` |
| `DecommissionDate` | Nullable(String) | 28 | 0.00% | `2011-06-17 00:00:00.000`(1,098)；`2013-06-16 00:00:00.000`(805)；`2013-06-17 00:00:00.000`(805)；`2014-06-16 00:00:00.000`(781)；`2012-06-16 00:00:00.000`(717)；`2012-06-17 00:00:00.000`(683)；`2010-06-16 00:00:00.000`(673)；`2011-06-16 00:00:00.000`(414)；`2013-06-18 00:00:00.000`(396)；`2012-06-18 00:00:00.000`(356)；`2015-01-01 00:00:00.000`(277)；`2011-06-18 00:00:00.000`(208)；`2014-06-17 00:00:00.000`(101)；`2012-07-10 00:00:00.000`(88)；`2016-06-16 00:00:00.000`(81)；`2016-06-17 00:00:00.000`(81)；`2012-07-06 00:00:00.000`(49)；`2014-06-18 00:00:00.000`(44)；`2016-06-18 00:00:00.000`(41)；`2015-06-16 00:00:00.000`(28)；`2015-06-17 00:00:00.000`(28)；`2015-06-18 00:00:00.000`(13)；`2012-03-15 00:00:00.000`(10)；`2012-06-07 00:00:00.000`(10)；`2014-07-10 00:00:00.000`(9)；`2012-09-19 00:00:00.000`(8)；`2012-09-20 00:00:00.000`(8)；`2014-07-06 00:00:00.000`(4) |
| `LastModifiedDate` | Nullable(String) | 9 | 0.00% | `2009-06-16 00:00:00.000`(2,733)；`2009-06-17 00:00:00.000`(2,170)；`2009-07-10 00:00:00.000`(1,413)；`2009-06-18 00:00:00.000`(822)；`2009-07-06 00:00:00.000`(629)；`2009-07-17 00:00:00.000`(40)；`2008-12-10 00:00:00.000`(4)；`2009-05-10 00:00:00.000`(3)；`2008-01-01 00:00:00.000`(2) |

## DimOutage

行数：303

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `OutageKey` | Int32 | 303 | 0.00% | 293 ~ 595 |
| `OutageName` | String | 28 | 0.00% | `Move/Add/Change`(47)；`Change Management`(42)；`Hardware`(30)；`Incident`(30)；`Deployment`(24)；`Security`(24)；`Request`(21)；`Network Device`(14)；`Change/Maintenance`(12)；`Network Configuration`(7)；`Network Capacity`(6)；`Maintenance`(5)；`Investigation`(4)；`Network`(4)；`Network error`(4)；`CPU Failure`(3)；`Disk Failure`(3)；`Motherboard Failure`(3)；`Network Adapter Failure`(3)；`OS Failed`(3)；`RAM Failure`(3)；`Software`(3)；`Database Error`(2)；`HM-Network`(2)；`Hub Port light is blinking`(1)；`Hub Power Down`(1)；`Infrastructure`(1)；`Network HW Failure-test`(1) |
| `OutageType` | String | 55 | 0.00% | 最常见：`Hardware`、`Software`、`Network`、`Configuration Management`、`OS` |
| `OutageTypeDescription` | Nullable(String) | 53 | 0.00% | 最常见：`Hardware`、`Crash`、`Software`、`Network`、`Configuration Management` |
| `OutageSubType` | Nullable(String) | 159 | 0.00% | 最常见：`Upgrade`、`Other`、`Install/Update Software`、`Memory`、`Vulnerability` |

## DimProduct

行数：2,233

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ProductKey` | Int32 | 2,233 | 0.00% | 1 ~ 2517 |
| `ProductName` | String | 2,233 | 0.00% | 最常见：`Contoso SLR Camera X144 Silver Grey`、`Fabrikam SLR Camera 35" X358 Grey`、`Litware Desktop Wind Tower Oscillating Fan E1201 Brown`、`Litware Home Theater System 5.1 Channel M515 Black`、`Adventure Works Coffee Maker 5C E090 Black` |
| `ProductDescription` | Nullable(String) | 653 | 0.00% | 最常见：`1080i/p or 720p high definition or standard definition`、`6-hour rechargeable battery, 180-degree swivel and flip screen`、`Store your CDs or DVDs in these beautiful binders, designed to look like books`、`Digital camera - SLR with live view mode`、`Collapsible rectangular natural silk shade, walnut box frame, 1 x 150 Watt` |
| `ProductSubcategoryKey` | Nullable(Float64) | 30 | 0.00% | `1`(45)；`4`(20)；`6`(50)；`9`(50)；`10`(26)；`11`(100)；`13`(46)；`15`(78)；`18`(78)；`19`(103)；`20`(101)；`22`(99)；`23`(100)；`24`(100)；`27`(103)；`28`(55)；`29`(92)；`31`(62)；`32`(101)；`33`(27)；`35`(90)；`38`(46)；`41`(70)；`42`(86)；`43`(102)；`44`(31)；`45`(74)；`46`(158)；`47`(62)；`48`(78) |
| `Manufacturer` | Nullable(String) | 11 | 0.00% | `Contoso, Ltd`(644)；`Fabrikam, Inc.`(267)；`Litware, Inc.`(264)；`Proseware, Inc.`(244)；`Adventure Works`(170)；`The Phone Company`(152)；`Wide World Importers`(150)；`Southridge Video`(139)；`A. Datum Corporation`(132)；`Northwind Traders`(47)；`Tailspin Toys`(24) |
| `BrandName` | Nullable(String) | 11 | 0.00% | `Contoso`(644)；`Fabrikam`(267)；`Litware`(264)；`Proseware`(244)；`Adventure Works`(170)；`The Phone Company`(152)；`Wide World Importers`(150)；`Southridge Video`(139)；`A. Datum`(132)；`Northwind Traders`(47)；`Tailspin Toys`(24) |
| `ClassID` | Nullable(Float64) | 3 | 0.00% | `1`(718)；`2`(1,189)；`3`(326) |
| `ClassName` | Nullable(String) | 3 | 0.00% | `Regular`(1,189)；`Economy`(718)；`Deluxe`(326) |
| `StyleID` | Nullable(Float64) | 16 | 0.00% | `1`(1,136)；`2`(224)；`3`(475)；`4`(126)；`5`(261)；`6`(1)；`7`(1)；`8`(1)；`9`(1)；`10`(1)；`11`(1)；`12`(1)；`13`(1)；`14`(1)；`15`(1)；`16`(1) |
| `StyleName` | Nullable(String) | 2,233 | 0.00% | 最常见：`Product0501042`、`Product0602089`、`Product0501023`、`Product0501080`、`Product0205043` |
| `ColorID` | Nullable(Float64) | 16 | 0.00% | `1`(14)；`2`(540)；`3`(150)；`4`(66)；`5`(4)；`6`(96)；`7`(357)；`8`(454)；`9`(53)；`10`(63)；`11`(271)；`12`(14)；`13`(29)；`14`(72)；`15`(49)；`16`(1) |
| `ColorName` | Nullable(String) | 17 | 0.00% | `Black`(540)；`White`(454)；`Silver`(357)；`Grey`(271)；`Blue`(148)；`Red`(96)；`Green`(72)；`Brown`(66)；`Pink`(63)；`Orange`(53)；`Gold`(49)；`Yellow`(29)；`Azure`(14)；`Silver Grey`(14)；`Purple`(4)；`blue`(2)；`Transparent`(1) |
| `Weight` | Nullable(Float64) | 296 | 0.00% | 0.17 ~ 239 |
| `WeightUnitMeasureID` | Nullable(String) | 3 | 0.00% | `pounds`(1,822)；`ounces`(401)；`grams`(10) |
| `UnitOfMeasureID` | Nullable(Float64) | 2 | 0.00% | `1`(2,221)；`2`(12) |
| `UnitOfMeasureName` | Nullable(String) | 2 | 0.00% | `inches`(2,221)；`mm`(12) |
| `StockTypeID` | Nullable(Float64) | 3 | 0.00% | `1`(1,314)；`2`(658)；`3`(261) |
| `StockTypeName` | Nullable(String) | 3 | 0.00% | `High`(1,314)；`Mid`(658)；`Low`(261) |
| `UnitCost` | Nullable(Float64) | 424 | 0.00% | 1.5 ~ 1060.22 |
| `UnitPrice` | Nullable(Float64) | 376 | 0.00% | 2.94 ~ 3199.99 |
| `AvailableForSaleDate` | Nullable(String) | 332 | 0.00% | 最常见：`2008-01-04`、`2005-02-09`、`2006-03-08`、`2007-03-08`、`2006-02-09` |
| `Status` | Nullable(String) | 2 | 0.00% | `On`(1,938)；`Off`(295) |

## DimProductCategory

行数：8

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ProductCategoryKey` | Int32 | 8 | 0.00% | `1`(1)；`2`(1)；`3`(1)；`4`(1)；`5`(1)；`6`(1)；`7`(1)；`8`(1) |
| `ProductCategoryName` | String | 8 | 0.00% | `Audio`(1)；`Cameras and camcorders`(1)；`Cell phones`(1)；`Computers`(1)；`Games and Toys`(1)；`Home Appliances`(1)；`Music, Movies and Audio Books`(1)；`TV and Video`(1) |

## DimProductSubcategory

行数：44

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ProductSubcategoryKey` | Int32 | 44 | 0.00% | `1`(1)；`2`(1)；`3`(1)；`4`(1)；`5`(1)；`6`(1)；`7`(1)；`8`(1)；`9`(1)；`10`(1)；`11`(1)；`13`(1)；`14`(1)；`15`(1)；`16`(1)；`17`(1)；`18`(1)；`19`(1)；`20`(1)；`21`(1)；`22`(1)；`23`(1)；`24`(1)；`25`(1)；`27`(1)；`28`(1)；`29`(1)；`31`(1)；`32`(1)；`33`(1)；`34`(1)；`35`(1)；`36`(1)；`38`(1)；`39`(1)；`40`(1)；`41`(1)；`42`(1)；`43`(1)；`44`(1)；`45`(1)；`46`(1)；`47`(1)；`48`(1) |
| `ProductSubcategoryName` | String | 44 | 0.00% | `Air Conditioners`(1)；`Audio Accessories`(1)；`Audio Books`(1)；`Bluetooth Headphones`(1)；`Boxed Games`(1)；`Camcorders`(1)；`Cameras & Camcorders Accessories`(1)；`Car Video`(1)；`Cell phones Accessories`(1)；`Coffee Machines`(1)；`Computer Setup & Service`(1)；`Computers Accessories`(1)；`Desktops`(1)；`Digital Cameras`(1)；`Digital SLR Cameras`(1)；`Download Games`(1)；`Fans`(1)；`Film Cameras`(1)；`Games Accessories`(1)；`Headphones`(1)；`Home & Office Phones`(1)；`Home Theater System`(1)；`Lamps`(1)；`Laptops`(1)；`MP4&MP3`(1)；`Microwaves`(1)；`Monitors`(1)；`Movie DVD`(1)；`Music CD`(1)；`Netbooks`(1)；`Printers, Scanners & Fax`(1)；`Projectors & Screens`(1)；`Radio`(1)；`Recorder`(1)；`Recording Pen`(1)；`Refrigerators`(1)；`Smart phones & PDAs`(1)；`Speakers`(1)；`TV & Video Accessories`(1)；`Televisions`(1)；`Touch Screen Phones`(1)；`VCD & DVD`(1)；`Washers & Dryers`(1)；`Water Heaters`(1) |
| `ProductCategoryKey` | Int32 | 8 | 0.00% | `1`(8)；`2`(5)；`3`(8)；`4`(5)；`5`(4)；`6`(3)；`7`(3)；`8`(8) |

## DimPromotion

行数：28

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `PromotionKey` | Int32 | 28 | 0.00% | `1`(1)；`2`(1)；`3`(1)；`4`(1)；`5`(1)；`6`(1)；`7`(1)；`8`(1)；`9`(1)；`10`(1)；`11`(1)；`12`(1)；`13`(1)；`14`(1)；`15`(1)；`16`(1)；`17`(1)；`18`(1)；`19`(1)；`20`(1)；`21`(1)；`22`(1)；`23`(1)；`24`(1)；`25`(1)；`26`(1)；`27`(1)；`28`(1) |
| `PromotionName` | String | 10 | 0.00% | `Asian Holiday Promotion`(3)；`Asian Spring Promotion`(3)；`Asian Summer Promotion`(3)；`European Back-to-Scholl Promotion`(3)；`European Holiday Promotion`(3)；`European Spring Promotion`(3)；`North America Back-to-School Promotion`(3)；`North America Holiday Promotion`(3)；`North America Spring Promotion`(3)；`No Discount`(1) |
| `DiscountPercent` | Nullable(Float64) | 6 | 0.00% | `0`(1)；`0.05`(3)；`0.07`(3)；`0.1`(9)；`0.15`(3)；`0.2`(9) |
| `PromotionType` | Nullable(String) | 2 | 0.00% | `Seasonal Discount`(27)；`No Discount`(1) |
| `PromotionCategory` | Nullable(String) | 2 | 0.00% | `Store`(27)；`No Discount`(1) |

## DimSalesTerritory

行数：265

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `SalesTerritoryKey` | Int32 | 265 | 0.00% | 1 ~ 274 |
| `GeographyKey` | Int32 | 265 | 0.00% | 424 ~ 952 |
| `SalesTerritoryName` | String | 265 | 0.00% | 最常见：`Fort Worth`、`Queens`、`Guangzhou`、`Hingham`、`Taipei` |
| `SalesTerritoryRegion` | Nullable(String) | 80 | 0.00% | 最常见：`Texas`、`Colorado`、`Massachusetts`、`Washington`、`Wisconsin` |
| `SalesTerritoryCountry` | Nullable(String) | 33 | 0.00% | `United States`(179)；`UK`(14)；`Germany`(11)；`France`(7)；`Japan`(7)；`Greater China`(6)；`Canada`(5)；`Italy`(5)；`India`(3)；`Russia`(3)；`Australia`(2)；`South Korea`(2)；`Armenia`(1)；`Bhutan`(1)；`Denmark`(1)；`Greece`(1)；`Iran`(1)；`Ireland`(1)；`Kyrgyzstan`(1)；`Malta`(1)；`Pakistan`(1)；`Poland`(1)；`Portugal`(1)；`Romania`(1)；`Singapore`(1)；`Slovenia`(1)；`Spain`(1)；`Sweden`(1)；`Switzerland`(1)；`Syria`(1)；`Thailand`(1)；`Turkmenistan`(1)；`the Netherlands`(1) |
| `SalesTerritoryGroup` | Nullable(String) | 3 | 0.00% | `North America`(184)；`Europe`(52)；`Asia`(29) |
| `SalesTerritoryLevel` | Nullable(String) | 1 | 0.00% | `4`(265) |
| `SalesTerritoryManager` | Nullable(String) | 264 | 0.00% | 最常见：`66`、`122`、`130`、`138`、`180` |
| `Status` | Nullable(String) | 1 | 0.00% | `Current`(265) |
| `EmployeeKey` | Nullable(Float64) | 264 | 0.00% | 14 ~ 296 |

## DimScenario

行数：3

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ScenarioKey` | Int32 | 3 | 0.00% | `1`(1)；`2`(1)；`3`(1) |
| `ScenarioName` | String | 3 | 0.00% | `Actual`(1)；`Budget`(1)；`Forecast`(1) |

## DimStore

行数：306

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `StoreKey` | Int32 | 306 | 0.00% | 1 ~ 310 |
| `GeographyKey` | Int32 | 263 | 0.00% | 424 ~ 952 |
| `StoreManager` | Nullable(String) | 262 | 0.00% | 最常见：`88`、`75`、`292`、`65`、`35` |
| `StoreType` | Nullable(String) | 4 | 0.00% | `Store`(299)；`Online`(3)；`Reseller`(3)；`Catalog`(1) |
| `StoreName` | String | 306 | 0.00% | 最常见：`Contoso Alexandria Store`、`Contoso Damascus No.1 Store`、`Contoso Attleboro Store`、`Contoso Tokyo No.1 Store`、`Contoso Berlin Store` |
| `Status` | Nullable(String) | 2 | 0.00% | `On`(294)；`Off`(12) |
| `OpenDate` | Nullable(String) | 165 | 0.00% | 最常见：`2004-02-18`、`2004-07-02`、`2004-04-20`、`2004-02-19`、`2004-08-25` |
| `CloseDate` | Nullable(String) | 8 | 0.00% | `2090-12-31`(294)；`2009-07-12`(5)；`2009-05-12`(2)；`2008-09-22`(1)；`2008-12-12`(1)；`2009-02-12`(1)；`2009-04-12`(1)；`2009-07-02`(1) |
| `EntityKey` | Nullable(Float64) | 306 | 0.00% | 58 ~ 949 |
| `StorePhone` | Nullable(String) | 295 | 0.00% | 最常见：`1 (11) 500 555-`、`210-555-0193`、`612-555-0100`、`208-555-0114`、`913-555-0172` |
| `StoreFax` | Nullable(String) | 295 | 0.00% | 最常见：`1 (11) 500 555`、`210-555-0193`、`612-555-0100`、`913-555-0172`、`208-555-0114` |
| `CloseReason` | Nullable(String) | 3 | 0.00% | `Not Yet Closed`(294)；`Relocation`(10)；`Store`(2) |
| `EmployeeCount` | Nullable(Float64) | 46 | 0.00% | `7`(1)；`8`(1)；`10`(1)；`11`(3)；`12`(2)；`13`(3)；`15`(7)；`17`(29)；`18`(2)；`19`(26)；`20`(1)；`21`(1)；`22`(25)；`23`(3)；`24`(3)；`25`(42)；`26`(33)；`27`(1)；`28`(2)；`29`(2)；`32`(2)；`33`(27)；`34`(1)；`35`(8)；`36`(2)；`42`(1)；`43`(1)；`45`(1)；`47`(25)；`50`(7)；`53`(1)；`55`(1)；`62`(1)；`64`(1)；`65`(1)；`68`(3)；`71`(1)；`77`(1)；`78`(1)；`80`(1)；`86`(1)；`90`(1)；`95`(26)；`120`(1)；`131`(1)；`325`(1) |
| `SellingAreaSize` | Nullable(Float64) | 15 | 0.00% | `450`(1)；`455`(26)；`460`(10)；`462`(19)；`480`(54)；`490`(1)；`500`(42)；`551`(1)；`560`(26)；`630`(1)；`680`(60)；`700`(37)；`1000`(1)；`1125`(25)；`93800`(2) |
| `LastRemodelDate` | Nullable(String) | 29 | 0.00% | `2009-06-17 00:00:00`(111)；`2009-06-16 00:00:00`(107)；`2009-06-18 00:00:00`(61)；`2008-06-05 00:00:00`(2)；`2008-11-05 00:00:00`(1)；`2009-06-18 01:00:00`(1)；`2009-06-18 02:00:00`(1)；`2009-06-18 03:00:00`(1)；`2009-06-18 04:00:00`(1)；`2009-06-18 05:00:00`(1)；`2009-06-18 06:00:00`(1)；`2009-06-18 07:00:00`(1)；`2009-06-18 08:00:00`(1)；`2009-06-18 09:00:00`(1)；`2009-06-18 10:00:00`(1)；`2009-06-18 11:00:00`(1)；`2009-06-18 12:00:00`(1)；`2009-06-18 13:00:00`(1)；`2009-06-18 14:00:00`(1)；`2009-06-18 15:00:00`(1)；`2009-06-18 16:00:00`(1)；`2009-06-18 17:00:00`(1)；`2009-06-18 18:00:00`(1)；`2009-06-18 19:00:00`(1)；`2009-06-18 20:00:00`(1)；`2009-06-18 21:00:00`(1)；`2009-06-18 22:00:00`(1)；`2009-06-19 00:00:00`(1)；`2009-06-20 00:00:00`(1) |
| `EmployeeKey` | Nullable(Float64) | 262 | 0.00% | 14 ~ 296 |

## FactExchangeRate

行数：773

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ExchangeRateKey` | Int32 | 773 | 0.00% | 1 ~ 774 |
| `CurrencyKey` | Int32 | 25 | 0.00% | `1`(31)；`2`(31)；`3`(31)；`4`(31)；`5`(31)；`6`(31)；`7`(31)；`8`(31)；`9`(31)；`10`(31)；`11`(31)；`12`(31)；`13`(31)；`15`(31)；`16`(31)；`17`(31)；`18`(31)；`19`(31)；`20`(31)；`21`(31)；`22`(31)；`23`(30)；`24`(30)；`25`(31)；`26`(31) |
| `DateKey` | Date | 31 | 0.00% | 2007-01-01 ~ 2009-07-01 |
| `AverageRate` | Float64 | 638 | 0.00% | 0.21338 ~ 10114.86 |
| `EndOfDayRate` | Float64 | 609 | 0.00% | 0.2885 ~ 10199 |

## FactITMachine

行数：23,283

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ITMachinekey` | Int32 | 23,283 | 0.00% | 1 ~ 23283 |
| `MachineKey` | Int32 | 7,816 | 0.00% | 1 ~ 7816 |
| `DateKey` | Date | 3 | 0.00% | 2007-01-01 ~ 2009-01-01 |
| `CostAmount` | Float64 | 23 | 0.00% | `390`(102)；`400`(73)；`500`(2,679)；`700`(2,679)；`900`(102)；`975`(46)；`1095`(73)；`1200`(2,679)；`1425`(102)；`12600`(460)；`13470`(1,060)；`13550`(460)；`13700`(346)；`14820`(10)；`14930`(3,040)；`15335`(1,060)；`15632`(3,040)；`15777`(10)；`16300`(346)；`16553`(460)；`16600`(1,060)；`17700`(356)；`18499`(3,040) |
| `CostType` | String | 2 | 0.00% | `Annual Maintenance Cost`(23,062)；`Equipment Costs`(221) |

## FactITSLA

行数：4,925

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `ITSLAkey` | Int32 | 4,925 | 0.00% | 1 ~ 4925 |
| `DateKey` | Date | 1,046 | 0.00% | 2007-01-01 ~ 2009-12-31 |
| `StoreKey` | Int32 | 299 | 0.00% | 1 ~ 307 |
| `MachineKey` | Int32 | 2,553 | 0.00% | 2 ~ 7808 |
| `OutageKey` | Int32 | 294 | 0.00% | 293 ~ 595 |
| `OutageStartTime` | Nullable(String) | 4,915 | 0.00% | 最常见：`2008-03-12 05:15:00`、`2008-09-08 04:24:00`、`2007-05-18 06:31:00`、`2008-07-09 07:28:00`、`2009-05-12 02:15:00` |
| `OutageEndTime` | Nullable(String) | 4,908 | 0.00% | 最常见：`2009-06-20 16:22:00`、`2008-12-24 21:31:00`、`2008-08-23 20:19:00`、`2008-12-29 08:32:00`、`2009-05-27 17:05:00` |
| `DownTime` | Nullable(Float64) | 364 | 0.00% | 1 ~ 1433 |

## FactInventory

行数：8,013,099

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `InventoryKey` | Int32 | 8,013,099 | 0.00% | 1 ~ 8013099 |
| `DateKey` | Date | 156 | 0.00% | 2007-01-06 ~ 2009-12-26 |
| `StoreKey` | Int32 | 306 | 0.00% | 1 ~ 310 |
| `ProductKey` | Int32 | 2,516 | 0.00% | 1 ~ 2517 |
| `CurrencyKey` | Int32 | 1 | 0.00% | `1`(8,013,099) |
| `OnHandQuantity` | Int32 | 1,541 | 0.00% | 0 ~ 5517 |
| `OnOrderQuantity` | Int32 | 810 | 0.00% | 0 ~ 2770 |
| `SafetyStockQuantity` | Int32 | 483 | 0.00% | 3 ~ 3228 |
| `UnitCost` | Float64 | 480 | 0.00% | 0.48 ~ 1060.22 |
| `DaysInStock` | Nullable(Float64) | 115 | 0.00% | 5 ~ 119 |
| `MinDayInStock` | Nullable(Float64) | 55 | 0.00% | 5 ~ 59 |
| `MaxDayInStock` | Nullable(Float64) | 60 | 0.00% | 60 ~ 119 |
| `Aging` | Nullable(Float64) | 7 | 0.00% | `1`(121)；`2`(943)；`3`(18,037)；`4`(9,960)；`5`(362,428)；`6`(2,357,475)；`7`(5,264,135) |

## FactOnlineSales

行数：12,627,608

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `OnlineSalesKey` | Int64 | 12,627,608 | 0.00% | 19560484 ~ 32188091 |
| `DateKey` | Date | 1,096 | 0.00% | 2007-01-01 ~ 2009-12-31 |
| `StoreKey` | Int32 | 3 | 0.00% | `199`(4,645,792)；`306`(3,847,281)；`307`(4,134,535) |
| `ProductKey` | Int32 | 2,516 | 0.00% | 1 ~ 2517 |
| `PromotionKey` | Int32 | 28 | 0.00% | `1`(3,899,892)；`2`(391,375)；`3`(415,119)；`4`(284,483)；`5`(407,124)；`6`(221,509)；`7`(199,501)；`8`(412,848)；`9`(189,706)；`10`(459,408)；`11`(248,253)；`12`(371,207)；`13`(268,960)；`14`(409,501)；`15`(250,752)；`16`(225,364)；`17`(309,133)；`18`(176,053)；`19`(325,569)；`20`(336,441)；`21`(489,743)；`22`(343,276)；`23`(370,997)；`24`(358,538)；`25`(327,442)；`26`(370,337)；`27`(240,468)；`28`(324,609) |
| `CurrencyKey` | Int32 | 1 | 0.00% | `1`(12,627,608) |
| `CustomerKey` | Int32 | 18,869 | 0.00% | 1 ~ 19145 |
| `SalesOrderNumber` | String | 1,674,320 | 0.00% | 最常见：`200912105CS943`、`200905145CS713`、`200911175CS932`、`200906175CS751`、`200911015CS729` |
| `SalesOrderLineNumber` | Int32 | 4,972 | 0.00% | 1 ~ 4972 |
| `SalesQuantity` | Int32 | 2 | 0.00% | `0`(100,166)；`1`(12,527,442) |
| `SalesAmount` | Float64 | 2,470 | 0.00% | 0 ~ 3199.99 |
| `ReturnQuantity` | Int32 | 2 | 0.00% | `0`(12,527,442)；`1`(100,166) |
| `ReturnAmount` | Float64 | 2,447 | 0.00% | 0 ~ 3199.99 |
| `DiscountQuantity` | Int32 | 2 | 0.00% | `0`(3,899,892)；`1`(8,727,716) |
| `DiscountAmount` | Float64 | 1,906 | 0.00% | 0 ~ 639.998 |
| `TotalCost` | Float64 | 481 | 0.00% | 0.48 ~ 1060.22 |
| `UnitCost` | Float64 | 480 | 0.00% | 0.48 ~ 1060.22 |
| `UnitPrice` | Float64 | 426 | 0.00% | 0.95 ~ 3199.99 |

## FactSales

行数：3,406,089

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `SalesKey` | Int64 | 3,406,089 | 0.00% | 1 ~ 3406089 |
| `DateKey` | Date | 1,096 | 0.00% | 2007-01-01 ~ 2009-12-31 |
| `channelKey` | Int32 | 4 | 0.00% | `1`(2,173,872)；`2`(629,223)；`3`(194,976)；`4`(408,018) |
| `StoreKey` | Int32 | 306 | 0.00% | 1 ~ 310 |
| `ProductKey` | Int32 | 2,516 | 0.00% | 1 ~ 2517 |
| `PromotionKey` | Int32 | 28 | 0.00% | `1`(1,166,300)；`2`(201,246)；`3`(199,968)；`4`(137,721)；`5`(69,829)；`6`(52,641)；`7`(36,286)；`8`(80,329)；`9`(55,515)；`10`(132,984)；`11`(150,031)；`12`(154,272)；`13`(102,644)；`14`(58,931)；`15`(57,652)；`16`(37,263)；`17`(47,284)；`18`(35,343)；`19`(65,275)；`20`(112,819)；`21`(119,447)；`22`(79,349)；`23`(42,235)；`24`(58,693)；`25`(39,880)；`26`(38,115)；`27`(28,958)；`28`(45,079) |
| `CurrencyKey` | Int32 | 1 | 0.00% | `1`(3,406,089) |
| `UnitCost` | Float64 | 480 | 0.00% | 0.48 ~ 1060.22 |
| `UnitPrice` | Float64 | 426 | 0.00% | 0.95 ~ 3199.99 |
| `SalesQuantity` | Int32 | 139 | 0.00% | 2 ~ 2880 |
| `ReturnQuantity` | Int32 | 6 | 0.00% | `0`(2,925,146)；`1`(468,730)；`2`(11,807)；`3`(382)；`4`(23)；`5`(1) |
| `ReturnAmount` | Float64 | 977 | 0.00% | 0 ~ 9996 |
| `DiscountQuantity` | Int32 | 25 | 0.00% | `0`(1,612,977)；`1`(398,997)；`2`(408,077)；`3`(419,529)；`4`(430,871)；`5`(43,543)；`6`(34,973)；`7`(26,040)；`8`(16,603)；`9`(5,680)；`10`(3,946)；`11`(2,391)；`12`(1,285)；`13`(505)；`14`(335)；`15`(170)；`16`(83)；`17`(41)；`18`(11)；`19`(16)；`20`(6)；`21`(4)；`22`(3)；`23`(1)；`24`(2) |
| `DiscountAmount` | Float64 | 10,739 | 0.00% | 0 ~ 7958.7 |
| `TotalCost` | Float64 | 17,221 | 0.00% | 1.92 ~ 137117.76 |
| `SalesAmount` | Float64 | 68,708 | 0.00% | 3.04 ~ 408016.02 |

## FactSalesQuota

行数：7,465,911

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `SalesQuotaKey` | Int32 | 7,465,911 | 0.00% | 1 ~ 7465911 |
| `ChannelKey` | Int32 | 4 | 0.00% | `1`(6,086,478)；`2`(617,448)；`3`(206,361)；`4`(555,624) |
| `StoreKey` | Int32 | 306 | 0.00% | 1 ~ 310 |
| `ProductKey` | Int32 | 2,516 | 0.00% | 1 ~ 2517 |
| `DateKey` | Date | 36 | 0.00% | 2007-01-01 ~ 2009-12-01 |
| `CurrencyKey` | Int32 | 1 | 0.00% | `1`(7,465,911) |
| `ScenarioKey` | Int32 | 3 | 0.00% | `1`(2,488,637)；`2`(2,488,637)；`3`(2,488,637) |
| `SalesQuantityQuota` | Nullable(Float64) | 1,101 | 0.00% | 1 ~ 6264 |
| `SalesAmountQuota` | Nullable(Float64) | 613,799 | 0.00% | 2.9684 ~ 1142709.2197 |
| `GrossMarginQuota` | Nullable(Float64) | 944,795 | 0.00% | -1620.9545 ~ 736727.1041 |

## FactStrategyPlan

行数：2,750,628

| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |
|---|---|---:|---:|---|
| `StrategyPlanKey` | Int32 | 2,750,628 | 0.00% | 1 ~ 3181386 |
| `DateKey` | Date | 36 | 0.00% | 2007-01-01 ~ 2009-12-01 |
| `EntityKey` | Int32 | 306 | 0.00% | 58 ~ 949 |
| `ScenarioKey` | Int32 | 3 | 0.00% | `1`(916,876)；`2`(916,876)；`3`(916,876) |
| `AccountKey` | Int32 | 17 | 0.00% | `4`(253,722)；`5`(253,722)；`7`(259,800)；`8`(259,800)；`9`(259,800)；`10`(259,800)；`11`(259,800)；`12`(82,056)；`15`(85,944)；`16`(129,456)；`17`(64,440)；`18`(64,728)；`19`(259,800)；`20`(64,440)；`21`(64,440)；`22`(64,440)；`23`(64,440) |
| `CurrencyKey` | Int32 | 1 | 0.00% | `1`(2,750,628) |
| `ProductCategoryKey` | Int32 | 8 | 0.00% | `1`(343,776)；`2`(344,088)；`3`(345,348)；`4`(344,094)；`5`(344,088)；`6`(343,800)；`7`(341,340)；`8`(344,094) |
| `Amount` | Float64 | 2,042,832 | 0.00% | 0.324 ~ 25931992.5114 |
