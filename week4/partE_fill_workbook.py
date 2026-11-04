"""Part E - fill the cream cells of the W4 workbook from the CSVs in ./outputs and ./data.

Numbers come from partA-D output; the written answers are in this file. Grey cells and existing formulas are untouched.
Writes ./outputs/W4_Schema_TEAM.xlsx
"""
import math
import pandas as pd
import openpyxl
from openpyxl.styles import Alignment
from common import *

wb = openpyxl.load_workbook(WORKBOOK_IN)
WRAP = Alignment(wrap_text=True, vertical="top")

def put(ws, ref, value, wrap=False):
    ws[ref].value = value
    if wrap:
        ws[ref].alignment = WRAP

def height(ws, row, texts_widths, line=15.0, minimum=30.0):
    """Set row height so the longest wrapped text fits: texts_widths = [(text, column width in chars)]."""
    lines = max(math.ceil(len(t) / max(w - 2, 1)) for t, w in texts_widths)
    ws.row_dimensions[row].height = max(minimum, lines * line)

# ======================================================= T1
ws = wb["T1 Hop Count"]
t1 = pd.read_csv(OUTPUT_DIR / "t1_hops.csv")
touch = {
    1: "DimDate",
    2: "DimCity (origin role)",
    3: "star: DimCity | snow: DimCity, DimProvince",
    4: "star: DimCity | snow: DimCity, DimProvince, DimCountry",
    5: "star: DimCity, DimDate | snow: DimCity, DimProvince, DimDate",
    6: "DimMode, DimStatus",
    7: "DimRoute",
    8: "star: DimCity (dest role), DimMode | snow: + DimProvince",
}
why = {
    1: "Month is a column on DimDate and no city is read, so the city chain is never touched.",
    2: "CityName stays on DimCity in both schemas. Only Province and Region move out.",
    3: "Province is a column on DimCity in the star (1 join). In the snowflake the name lives on DimProvince, so DimCity -> DimProvince is 2.",
    4: "The Week 3 DimCity has no Country column; in a star it would be one constant text column (all 14 cities are Pakistan), so 1 join. Snowflake: DimCity -> DimProvince -> DimCountry is 3.",
    5: "Date side is unchanged (1). Province adds DimProvince in the snowflake: 2 becomes 3.",
    6: "Neither dimension has anything to do with city, province or country.",
    7: "Corridor and DistanceBand sit on DimRoute. Cost per kg is SUM(FreightCostPKR) / SUM(WeightKG) on the fact, so no extra table.",
    8: "Destination province is read through DestCityKey -> DimCity, then DimProvince: one extra hop (2 becomes 3). DimMode is not affected.",
}
for r, row in t1.iterrows():
    x = 7 + r
    put(ws, f"C{x}", touch[row.Q], True)
    put(ws, f"D{x}", int(row.StarJoins))
    put(ws, f"E{x}", int(row.SnowJoins))
    put(ws, f"G{x}", why[row.Q], True)
    height(ws, x, [(touch[row.Q], 38), (why[row.Q], 38)], minimum=45)
t1_text = ("The eight questions need 5 more joins in total in the snowflake (16 against 11), and all 5 sit in four questions: "
           "Q3 +1, Q4 +2, Q5 +1, Q8 +1. That number says nothing about which schema is faster. It counts join operations, not what each one costs. "
           "DimProvince has 6 rows and DimCountry has 2 (Pakistan and Unknown), so every extra join resolves against a table far smaller "
           "than the 34-row fact table and adds almost no work. The count also ignores join order (the three small tables can be folded together "
           "before the fact table is read), compression and caching. A join count measures how complicated the query and the model are, "
           "not elapsed time; speed has to be measured on a real data volume, and at 34 fact rows neither schema can be told apart by a stopwatch.")
put(ws, "B25", t1_text, True)
for r in (25, 26, 27): ws.row_dimensions[r].height = 40

# ======================================================= T2
ws = wb["T2 Snowflake It"]
prov = pd.read_csv(SNOW_DIR / "DimProvince.csv")
for i, row in prov.iterrows():
    x = 7 + i
    put(ws, f"A{x}", int(row.ProvinceKey)); put(ws, f"B{x}", row.ProvinceName)
    put(ws, f"C{x}", row.RegionName); put(ws, f"D{x}", int(row.CountryKey))
cty = pd.read_csv(SNOW_DIR / "DimCountry.csv")
for i, row in cty.iterrows():
    x = 17 + i
    put(ws, f"A{x}", int(row.CountryKey)); put(ws, f"B{x}", row.CountryName); put(ws, f"C{x}", row.RegionGroup)
cn = pd.read_csv(SNOW_DIR / "DimCity_normalized.csv")
for i, row in cn.iterrows():
    x = 23 + i
    put(ws, f"A{x}", int(row.CityKey)); put(ws, f"B{x}", row.CityName); put(ws, f"C{x}", int(row.ProvinceKey))
    put(ws, f"D{x}", row.IsPortCity); put(ws, f"E{x}", row.FacilityType)
put(ws, "E41", "Flatten")
t2_text = (
    "Flatten. Three reasons, in order of weight. (1) The joins: T1 shows the snowflake costs 5 extra joins (11 to 16) across Q3, Q4, Q5 and Q8, "
    "and the country question goes from 1 join to 3. (2) The bytes: T3 shows the snowflake is 36 bytes bigger at 15 rows (332 against 296), because "
    "DimProvince costs 96 bytes in pointers and keys (6 rows x 16 bytes) before it saves anything. It breaks even above 24 city rows and then saves "
    "4 bytes per row. At 50,000,000 cities that is 199,999,904 bytes, 0.1% of a 200 GB fact table. DimCountry has 1 row excluding Unknown (Pakistan) and "
    "DimProvince has 5, so we would build, relate, index and back up two more tables to store the word Pakistan once. (3) Region does not belong to Province in this data: "
    "Punjab has cities in North and Central, Sindh in South and Central, Balochistan in South and West. DimProvince can hold one region per province, "
    "so moving the column changes the region of 4 of the 14 cities (Multan, Faisalabad, Sukkur, Quetta). I used the region held by most of a province's cities, "
    "ties to the lowest CityKey. The split loses information as well as adding joins. Province is a text column describing a city, not a dimension at a different grain, "
    "so none of the four legitimate cases in T6 applies."
)
put(ws, "A42", t2_text, True)
for r in range(42, 46): ws.row_dimensions[r].height = 42

# ======================================================= T3
ws = wb["T3 Storage"]
t3 = pd.read_csv(OUTPUT_DIR / "t3_storage.csv")
DICT, OVER = 176, 96     # dictionary bytes (88 chars x 2) and DimProvince key + pointer bytes (6 rows x 16)
notes = {
    15: "Snowflake is 36 bytes bigger. 15 rows save 60 bytes of pointers but DimProvince costs 96.",
    1000: "Saves 3,904 bytes. Break-even is 24 rows: the saving is 4 x rows - 96.",
    100000: "Saves 399,904 bytes, about 390 KB on a flat-encoded table of 800,176 bytes.",
    5000000: "Saves 19,999,904 bytes (about 19 MB); the 96-byte DimProvince cost is now invisible.",
    50000000: "Saves 199,999,904 bytes, almost exactly half of the 400,000,176 flat-encoded bytes. Still a fixed 4 bytes per row.",
}
for i, row in t3.iterrows():
    x = 13 + i
    if i == 0:
        put(ws, f"B{x}", "=2*211")                       # 211 characters written out across the 15 real rows
    else:
        put(ws, f"B{x}", f"=A{x}*2*211/15")              # per-row average of the 15 real rows, scaled, unrounded
    put(ws, f"C{x}", f"={DICT}+2*4*A{x}")                # dictionary + two 4-byte pointers per row
    put(ws, f"D{x}", f"=4*A{x}+{DICT}+{OVER}")           # ProvinceKey per city row + dictionary + DimProvince keys/pointers
    put(ws, f"G{x}", notes[int(row.DimCityRows)], True)
    for col in "BCD": ws[f"{col}{x}"].number_format = "#,##0.##"
    ws.row_dimensions[x].height = 45
put(ws, "D20", "No - 36 bytes bigger")
put(ws, "D21", 4)
ctx = pd.read_csv(OUTPUT_DIR / "t3_context.csv")
for i, x in enumerate((26, 27)):
    src = 13 if i == 0 else 17
    put(ws, f"B{x}", f"=E{src}")
    put(ws, f"C{x}", f"=A{x}*100*40")
    put(ws, f"D{x}", f"=B{x}/C{x}*100")
    ws[f"B{x}"].number_format = "#,##0"; ws[f"C{x}"].number_format = "#,##0"; ws[f"D{x}"].number_format = '0.0000"%"'
t3_text = (
    "The storage argument pays for a join only when the repeated text is wide and high-cardinality, so a dictionary cannot collapse it, in a dimension that is large next to the fact table. "
    "PakFreight meets neither: province names are 5 to 18 characters with 5 distinct values, and even at 50,000,000 city rows the saving is 0.1000% of the fact table "
    "(199,999,904 of 200,000,000,000 bytes). The T6 customer dimension (50 million rows carrying a 400-character segment description) is the kind of case that qualifies."
)
put(ws, "A30", t3_text, True)
for r in (30, 31, 32): ws.row_dimensions[r].height = 36

# ======================================================= T4
ws = wb["T4 Relationships"]
reg_text = [
    "Time axis for every measure. DimDate (28 rows, gapless, February 2026) is marked as the date table, so day and month filters reach the fact.",
    "Origin role, the default city path. The Province matrix and checks 10 to 13 read origin cities.",
    "Destination role. Power BI allows one active path between two tables and OriginCityKey already holds it, so this one stays inactive and is switched on per measure with USERELATIONSHIP.",
    "Corridor and DistanceBand slicing, and cost per kg by corridor. 21 rows: 20 corridors plus Unknown (-1).",
    "Mode slicer and the mode split. 4 rows: Marine, Rail, Road, Unknown.",
    "Delivered, In Transit and Delayed split. 4 rows including Unknown (-1).",
]
for i, ((one, many, active), why_) in enumerate(zip(REGISTER, reg_text)):
    x = 7 + i
    put(ws, f"B{x}", one); put(ws, f"C{x}", many); put(ws, f"D{x}", "* : 1"); put(ws, f"E{x}", "Single")
    put(ws, f"F{x}", "Yes" if active else "No"); put(ws, f"G{x}", why_, True)
    height(ws, x, [(why_, 44)], minimum=32)
put(ws, "D23", "1 - activate per measure")
t4b = (
    "Answer 1, one DimCity with the destination relationship inactive. Origin is the role nearly every question uses, and the model's own checks assume it "
    "(Province matrix, 4 origin provinces, Sindh 484,350 kg). Only destination questions need the other path, and those become a measure: "
    "Weight by Dest = CALCULATE([Total Weight], USERELATIONSHIP(FactShipment[DestCityKey], DimCity[CityKey])). That keeps a single 15-row DimCity to maintain and "
    "keeps the register at 6 relationships, 5 active, 1 inactive, which is what T7 expects. Answer 2 (DimOriginCity and DimDestCity) would read better with two slicers on one page, but it doubles a 15-row table, "
    "gives 7 relationships and 6 active, and nobody in the 8 T1 questions needs origin and destination on screen together. Answer 3 puts city names on the fact table and breaks the star. "
    "The cost of answer 1: a DimCity slicer filters origin only, and anyone adding a destination visual has to use the destination measure."
)
put(ws, "A24", t4b, True)
for r in (24, 25, 26): ws.row_dimensions[r].height = 36

# ======================================================= T5
ws = wb["T5 Cross-Filter"]
t5 = [
    ("Single", "The default * : 1 direction already runs DimMode -> FactShipment, so the slicer reaches every visual. Both would add nothing here and would also let the fact table filter DimMode back, so the slicer would shrink as other slicers are used."),
    ("Single", "Two Both relationships give the fact table two bidirectional routes between DimCity and DimMode. Power BI refuses the second as ambiguous. Set both back to Single; forcing it through by switching something else off would change numbers in measures that used that path."),
    ("Measure-level", "The real case for bidirectional behaviour: a dimension filtering another dimension through the fact. Making the relationship Both changes every visual in the model. Instead use a measure such as COUNTROWS(FactShipment) as a visual-level 'is not blank' filter on the Mode slicer, or CALCULATE(..., CROSSFILTER(FactShipment[ModeKey], DimMode[ModeKey], Both)) inside one measure. Only that measure changes."),
    ("Measure-level", "DISTINCTCOUNT(FactShipment[OriginCityKey]) answers it directly (8 origin cities, against 14 real cities in DimCity). Counting rows of DimCity under Both would give the same number but would change the model-wide filter direction for one card."),
    ("Single", "A security rule on DimCity[Province] flows down to the fact through the single direction already. Both would make the filter travel back up the model and into other dimensions, so slicer contents and totals would depend on the path. Single keeps the rule one-way and easy to test."),
    ("Single", "With FactFuelSpend sharing DimCity and DimDate, Both on those relationships would let FactShipment filter FactFuelSpend through the shared dimensions (fact -> dimension -> fact). That creates ambiguous paths between the two fact tables and fuel totals filtered by shipment rows. Keep Single, and compare the two facts through the shared dimensions in measures."),
]
for i, (v, w) in enumerate(t5):
    x = 7 + i
    put(ws, f"C{x}", v); put(ws, f"D{x}", w, True)
    height(ws, x, [(w, 60)], minimum=45)

# ======================================================= T6
ws = wb["T6 When To Snowflake"]
t6 = [
    ("Flatten", "none", "Province is a text attribute of the city, and DimProvince would hold 5 rows for 15 city rows. It has no grain, owner or load cadence of its own, so it is not one of the four cases. T3 shows 36 bytes extra at 15 rows."),
    ("Snowflake", "case 1", "The month a corridor opened is a calendar attribute at month grain, which is a dimension in its own right (DimDate / a month table). It is an outrigger, so reference it by key rather than storing date text on DimRoute."),
    ("Snowflake", "case 2", "50 million rows repeating a 400-character description is wide text the dictionary cannot shrink if the values are mostly distinct. Moving the segment out to its own table saves real bytes in the big table."),
    ("Snowflake", "case 3", "The two levels are loaded on different schedules (nightly and monthly) from different source systems. Separate tables let each load on its own cadence without rebuilding the other."),
    ("Bridge", "case 4", "One shipment with several hazard classes is a multi-valued attribute. A single column cannot hold it without repeating the fact row, so it needs a bridge table between FactShipment and a hazard class dimension. This is not a snowflake."),
    ("Flatten", "none", "A tidier diagram is not one of the four cases. The extra join and extra table would be paid for on every query to improve a picture."),
]
for i, (v, c, w) in enumerate(t6):
    x = 7 + i
    put(ws, f"C{x}", v); put(ws, f"D{x}", c); put(ws, f"E{x}", w, True)
    height(ws, x, [(w, 58)], minimum=45)
t6_test = (
    "Two conditions, and both have to be true. First, the attribute has to be a dimension in its own right: a different grain, a different owner or load cadence, "
    "or text so wide and varied that it will not compress, or a multi-valued attribute that needs a bridge. Second, the saving or independence has to be bigger than the cost of the extra join, "
    "and nobody can be waiting on that join, meaning the hop does not land on the questions people ask most. If either fails, flatten."
)
put(ws, "A20", t6_test, True)
for r in (20, 21, 22): ws.row_dimensions[r].height = 36

# ======================================================= T7
ws = wb["T7 Reconcile"]
t7 = pd.read_csv(OUTPUT_DIR / "t7_reconcile.csv")
for i, row in t7.iterrows():
    put(ws, f"C{7 + i}", int(row.Computed))

wb.calculation.fullCalcOnLoad = True
wb.save(WORKBOOK_OUT)
print("saved", WORKBOOK_OUT)
