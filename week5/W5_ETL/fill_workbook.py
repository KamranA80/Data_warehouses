"""Fills the cream cells of PakFreight_W5_ETLLab_STUDENT.xlsx (T1-T7).
Kamran Khan Hussain | BSDS030 | 7A
Numbers in T4/T7 are the ones W5_BSDS030.py measured and asserted - see outputs/run_report.txt.
"""
import math
from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter, column_index_from_string

SRC = Path("PakFreight_W5_ETLLab_STUDENT.xlsx")
DST = Path("outputs/W5_ETL_BSDS030.xlsx")

wb = openpyxl.load_workbook(SRC)
need = {}            # (sheet, row) -> lines needed, so row heights can be set at the end


def merged_span(ws, coord):
    for rng in ws.merged_cells.ranges:
        if coord in rng:
            return rng
    return None


def put(ws, coord, value, wrap=True, center=False, fmt=None):
    c = ws[coord]
    c.value = value
    old = c.alignment
    c.alignment = Alignment(horizontal="center" if center else old.horizontal,
                            vertical="top" if wrap and not center else (old.vertical or "center"),
                            wrap_text=wrap)
    if center:
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=wrap)
    if fmt:
        c.number_format = fmt
    if isinstance(value, str) and wrap:
        rng = merged_span(ws, coord)
        cols = range(rng.min_col, rng.max_col + 1) if rng else [c.column]
        width = sum((ws.column_dimensions[get_column_letter(i)].width or 9) for i in cols)
        cpl = max(width * 1.02, 4)
        lines = sum(max(1, math.ceil(len(part) / cpl)) for part in value.split("\n"))
        rows = (rng.max_row - rng.min_row + 1) if rng else 1
        need.setdefault(ws.title, []).append((c.row, rows, lines))


def widen(ws, col, width):
    ws.column_dimensions[col].width = width


def finish_heights(ws):
    per_row = {}
    for row, nrows, lines in need.get(ws.title, []):
        per_row.setdefault(row, []).append((nrows, lines))
    for row, items in per_row.items():
        for nrows, lines in items:
            h_needed = lines * 12.8 + 8
            current = sum((ws.row_dimensions[r].height or 15) for r in range(row, row + nrows))
            if h_needed > current:
                extra = (h_needed - current) / nrows
                for r in range(row, row + nrows):
                    ws.row_dimensions[r].height = (ws.row_dimensions[r].height or 15) + extra


# --------------------------------------------------------------------- header
ws = wb["Start Here"]
ws["A3"].value = ("Student: Kamran Khan Hussain  |  Roll no: BSDS030  |  BSDS (Data Science), Section 7A  |  "
                  "Lab done on the Python (pandas) track: W5_BSDS030.py")
ws["A3"].font = Font(italic=True, size=9, color="FF555555")

# ------------------------------------------------------------------------- T1
ws = wb["T1 Defect Census"]
widen(ws, "D", 15); widen(ws, "E", 30); widen(ws, "F", 11)
t1 = [
    ("Structural", "T2 · RenamedToContract",
     "Quiet",
     "Append without renaming gives a 20-column table, two thirds empty in every column. Append never complains, so nothing is raised."),
    ("Structural", "T1 · SkippedTitleRows, then PromotedHeaders",
     "Loud",
     "Promote first and the header row becomes 'Pakistan Railways Freight…' / Column1. The rename step then cannot find 'Consignment No' and the refresh errors, so somebody is told."),
    ("Type & Unit", "T6 · ConvertedTonsToKG (rail query, before the append)",
     "Quiet",
     "28.75 tons loads as 28.75 'kg'. SUM(WeightKG) = 283,695.25 instead of 578,650. The load succeeds, the number is wrong."),
    ("Type & Unit", "T5 · TypedDates, Using Locale en-GB (format='%d/%m/%Y' in pandas)",
     "Both",
     "13/02/2026 errors under en-US (loud), but ten other rows quietly land in the wrong month with no message. Both totals still pass to the rupee."),
    ("String", "T3 · TrimmedText (and CleanedStatus for the status column)",
     "Quiet",
     "'Karachi Port ' fails the alias lookup and 'DELIVERED ' counts as another status. Rows drift to Unknown or split across slicer entries; the load is green."),
    ("String", "T4 · CleanedStatus (Clean, Trim, Proper Case)",
     "Quiet",
     "17 strings for 3 statuses. The slicer offers 17 choices and every by-status breakdown is split into pieces."),
    ("Conform", "T10 · MergedOriginAlias / MergedDestAlias (left outer), null -> -1",
     "Quiet",
     "Karachi shows up as five different cities in every route report. A spelling the map misses becomes -1 without a sound (or disappears on an inner join)."),
    ("Structural", "T1 · RemovedBlankRows and RemovedTotalRow (two named steps)",
     "Quiet",
     "TOTAL loads as a shipment: SUM(WeightKG) = 661,650 (+83,000). The blank row alone gives 35 rows with both totals right and a (Blank) in every slicer."),
    ("Conform", "T9 · DedupedOnShipmentID (after the trim, on the business key)",
     "Quiet",
     "rd-505 is counted twice: 35 rows, SUM(WeightKG) = 584,750 (+6,100) and PKR 4,855,000 (+47,000)."),
    ("Derived", "T7 · AddedModeKey (assigned per source, before the append)",
     "n/a",
     "Nothing is wrong with the files. No source carries a mode, so the pipeline has to produce one from which query the row came through; without it the fact cannot join DimMode."),
]
for i, (cls, step, verdict, breaks) in enumerate(t1):
    r = 7 + i
    put(ws, f"D{r}", cls); put(ws, f"E{r}", step); put(ws, f"F{r}", verdict, center=True); put(ws, f"G{r}", breaks)

put(ws, "B26",
    "Defect 10, the missing transport mode. It is on the list because the fact table needs a ModeKey and nothing in the "
    "three files supplies one, so it is a column the pipeline produces, not a fault in the data. I marked it Derived / n/a "
    "instead of loud or quiet because there is nothing to ignore: the files are not wrong, and the column has to be "
    "manufactured while the pipeline still knows which file a row came from (before the append).")
put(ws, "B30",
    "Defect 8 (TOTAL footer): the 83,000 kg on that line is correct arithmetic, it is just a different grain. A human reading "
    "the spreadsheet wants a subtotal; a fact table that is one row per shipment cannot hold it. Nothing in the file says "
    "'not a shipment' except our decision about the grain, and the line is still useful afterwards as a control total "
    "(83,000 kg / PKR 652,000 equals the sum of the 13 real rows, duplicate included). The blank row is dirt, the TOTAL is a "
    "judgement, which is why they are two separate named steps.\n"
    "Defect 9 (rd-505 twice): two identical rows could be one trip keyed twice or two real trips, and the file cannot say. "
    "We treat ShipmentID as the business key and keep the first copy, which is a rule we chose and can defend, not something "
    "provable from the data. A wrong call either way moves the totals (6,100 kg and PKR 47,000 on this file).")
finish_heights(ws)

# ------------------------------------------------------------------------- T2
ws = wb["T2 Stage Ownership"]
t2 = [
    ("Extract", "Opening the connection and reading the named sheet is all extract does. Nothing is changed on the way in."),
    ("Violation", "Breaks 'extract must not clean'. If the trim happens while reading, there is no untouched copy to prove the source against, and a source problem cannot be told from one of ours."),
    ("Extract", "Source, time and row count (12 / 10 / 15 = 37 landed) are extract's own audit trail. Reconciliation at the end compares against this log."),
    ("Transform", "Shape work: skip the two title rows, then promote row 3 to headers. It runs on the landed copy, never on the workbook itself."),
    ("Violation", "Breaks 'transform must not write to the source'. The railway's database is theirs to fix. We conform the spelling on our side through the alias map and leave their data as it is."),
    ("Transform", "Type and unit conversion (tons to kilograms) on the landed rail copy, before the append."),
    ("Transform", "A conformance decision. 'Port Qasim means Karachi' is business knowledge, held as a lookup in DimCity's RawAliases, not a rule you can write over the characters."),
    ("Transform", "Left outer join then null -> -1 is a deliberate conform decision, made once and counted. By the time load runs, the row already carries its key."),
    ("Load", "Dependency order: the four independent dimensions go in first so every key the fact carries already exists. No decisions, only sequence."),
    ("Violation", "Breaks 'load must not decide anything'. A blank status should already have been resolved in transform (to Unknown, -1); load writes what it is handed."),
    ("Load", "The transaction boundary: all six writes land or none do. It is mechanical and involves no judgement."),
    ("Violation", "No stage may do this. Staging is raw, unreconciled working data (TOTAL row, duplicates, 17 status spellings, tons), so publishing it hands out wrong numbers. See the paragraph below."),
]
for i, (verdict, why) in enumerate(t2):
    r = 7 + i
    put(ws, f"C{r}", verdict, center=True); put(ws, f"D{r}", why)
put(ws, "B29",
    "Staging is the state the data has to be in for the pipeline to work, not a state anybody should read. It still holds the "
    "TOTAL row, the repeated rd-505, seventeen spellings of three statuses and rail weights in tons, and every one of those "
    "gives a plausible, confident, wrong number (584,750 or 661,650 kg instead of 578,650). If the sales team starts querying "
    "it, those numbers get quoted, then we fix the pipeline and the figures change under them. It also carries no keys, so it "
    "cannot join to the star. It is a working surface, and it stays out of sight. In Power Query the setting that enforces "
    "that is right-click > Enable load, unticked, which makes the query connection-only: it still runs on every refresh and "
    "feeds the queries below it, but it never shows up as a table in the model (six tables, ten queries behind them). In my "
    "pandas version there is no such setting, so the boundary is written in the script header: only FactShipment and the "
    "dimensions are written out, and the landed copies and step frames stay in memory.")
finish_heights(ws)

# ------------------------------------------------------------------------- T3
ws = wb["T3 Seventeen Steps"]
t3 = {   # row: (run order, stage, cadence, defects, why)
    7:  (10, "Transform", "per source", "10", "Last per-source step. Only here does the pipeline still know which file a row came through; after the append that is gone."),
    8:  (11, "Transform", "once", "-", "First step on the combined table. Needs the same seven names on all three (constraint 1) and tons already in kg (constraint 3)."),
    9:  (13, "Transform", "once", "7", "Needs trimmed text and one deduplicated table. Left outer join, then null -> -1, so no shipment can vanish."),
    10: (1, "Extract", "per source", "-", "Nothing starts without a connection. Read-only, nothing is changed."),
    11: (9, "Transform", "per source", "3", "Type and unit, so after text. Rail is the only file in tons and only its own query knows that (constraint 3)."),
    12: (2, "Extract", "per source", "-", "Keeps an untouched copy so the 37-row ladder has something to prove against. Extract corrects nothing."),
    13: (15, "Load", "once", "-", "Routes are pairs of city keys, so it cannot load before DimCity, and the fact needs RouteKey to exist."),
    14: (16, "Load", "once", "-", "Last write. Every dimension it points at is already there."),
    15: (14, "Load", "once", "-", "DimDate, DimMode, DimStatus and DimCity depend on nothing, so they go first."),
    16: (3, "Extract", "per source", "-", "Row counts (12 / 10 / 15) are written the moment the files land, before any transform can change them."),
    17: (7, "Transform", "per source", "6", "Text comes before type. After trim and clean, 17 status strings become 3, and the append then sees one vocabulary."),
    18: (8, "Transform", "per source", "4", "A type step, so after text. dd/MM/yyyy exists only in marine, so it is read with an explicit en-GB locale per source."),
    19: (4, "Transform", "per source", "2, 8", "Shape comes first. Skip the two rail title rows before promoting, then drop the blank row and TOTAL from road."),
    20: (17, "Load", "once", "-", "Runs after the write: loaded rows and totals (34 / 578,650 / 4,808,000) against what was extracted. Fails the run, not the dashboard."),
    21: (12, "Transform", "once", "9", "Runs on the combined table, after the trim (constraint 2). Needs clean text before 'the same row' means anything."),
    22: (5, "Transform", "per source", "1", "Shape. Has to happen before the append (constraint 1), and it lets every later step use one set of names."),
    23: (6, "Transform", "per source", "5", "Text before type before keys. Runs before the dedup (constraint 2) and before the alias lookup."),
}
for r, (order, stage, cad, defects, why) in t3.items():
    put(ws, f"C{r}", order, center=True); put(ws, f"D{r}", stage, center=True)
    put(ws, f"E{r}", cad, center=True); put(ws, f"F{r}", defects, center=True); put(ws, f"G{r}", why)

cons = {
    36: ("Rename every column to the common contract", "Append the three queries into one table",
         "20 columns instead of 7, two thirds empty in each, and no error",
         "Append matches on column name and fills the gaps with null instead of complaining. The three files share only 'Status', so 7 + 7 + 7 - 1 = 20 unique names."),
    37: ("Trim and clean all text columns", "Remove duplicates",
         "A duplicate survives: night2 gives 36 rows / 591,550 kg instead of 35 / 584,950 (+6,600 kg, the second rd-508)",
         "Two rows are only 'the same' once their text is clean. 'in transit' and 'in transit ' compare as different until the trim has run."),
    38: ("Convert rail tons to kilograms", "Append the three queries into one table",
         "SUM(WeightKG) = 283,695.25 kg instead of 578,650 (short by 294,954.75)",
         "After the append, tons and kilograms sit in one column and nothing says which is which. Only the rail query still knows. Same reason ModeKey is added per source."),
}
for r, (b, a, cost, why) in cons.items():
    put(ws, f"C{r}", b); put(ws, f"D{r}", a); put(ws, f"E{r}", cost); put(ws, f"G{r}", why)
widen(ws, "C", 20); widen(ws, "D", 20)       # C/D also carry the before/after text on rows 36-38
put(ws, "B42",
    "Because tonight's file cannot tell the two orders apart. Both rd-505 rows are byte-identical (same ID, date, cities, "
    "weight, cost, even the same status text), so they compare equal trimmed or untrimmed and every order gives 34. That is "
    "luck about this file, not a property of the rule.\n"
    "Equality is only defined once the text is clean. On night2 the second rd-508 differs from the first by one trailing "
    "space ('in transit ' vs 'in transit'), so a whole-row dedup that runs first keeps both: 36 rows, 591,550 kg, no error. "
    "Even a dedup on ShipmentID alone is only safe by accident: it happens to work on night2 because both IDs are spelled "
    "the same, but an ID that arrives as 'rd-508 ' or 'Rd-508' is a different key until it has been trimmed and uppercased.\n"
    "A preference gives the same answer whichever way round you do it. A constraint is one where the wrong order produces a "
    "wrong number on some file you have not seen yet, and nothing on night one would ever warn you.")
finish_heights(ws)

# ------------------------------------------------------------------------- T4
ws = wb["T4 Row Arithmetic"]
widen(ws, "D", 40)
ladder = {8: (12, 206500, 1618000), 9: (10, 295250, 2585000), 10: (15, 83000, 652000),
          11: (37, "-", "-"), 12: (35, 584750, 4855000), 13: (34, 578650, 4808000)}
for r, (rows, kg, pkr) in ladder.items():
    put(ws, f"C{r}", rows, wrap=False); put(ws, f"D{r}", kg, wrap=False); put(ws, f"E{r}", pkr, wrap=False)
    for col in "CDE":
        ws[f"{col}{r}"].alignment = Alignment(horizontal="right", vertical="center")

gap = {
    20: (34, "206,500 (marine) + 76,900 (road, duplicate removed) + 295.25 (rail, still in tons) = 283,695.25",
         -294954.75, "T6",
         "Rail weights were never multiplied by 1,000, so 295,250 kg went in as 295.25. The row count is right (34), only the unit is wrong. Run ConvertedTonsToKG on the rail query before the append."),
    21: (35, "578,650 + 6,100 (the second RD-505 survived)", 6100, "T9",
         "Duplicate road row not removed: dedup missing, or run on untrimmed text. Remove duplicates on ShipmentID, after the trim."),
    22: (35, "578,650 + 83,000 (the road TOTAL footer counted as a shipment; 34 real rows + TOTAL)", 83000, "T1",
         "The TOTAL line loaded as a shipment. Filter it out in the road query (RemovedTotalRow); it is a grain problem, not a typo."),
}
for r, (rows, arith, g, step, cause) in gap.items():
    put(ws, f"C{r}", rows, wrap=False); ws[f"C{r}"].alignment = Alignment(horizontal="right", vertical="top")
    put(ws, f"D{r}", arith)
    put(ws, f"E{r}", g, wrap=False, fmt='+#,##0.00;-#,##0.00' if r == 20 else '+#,##0;-#,##0')
    ws[f"E{r}"].alignment = Alignment(horizontal="right", vertical="top")
    put(ws, f"F{r}", step, center=True); put(ws, f"G{r}", cause)
put(ws, "C25",
    "Rail: headers were promoted before the two title rows were skipped, so the title line became the header and the real "
    "ones turned into data. Remove top 2 rows first (SkippedTitleRows), then promote. Shape comes first; this is T1.")
put(ws, "C26",
    "The blank road row loaded (RemovedBlankRows missing). It has no weight and no cost, so it moves COUNTROWS but neither "
    "total, and it shows up as (Blank) in every slicer. A row count is not a total and a total is not a row count, which is "
    "why check 5 stands apart from checks 7 and 8.")
finish_heights(ws)

# ------------------------------------------------------------------------- T5
ws = wb["T5 Locale Trap"]
us_month = ["January", "February", "March", "April", "May", "June", "July", "September", "October", "November", "December", "Error"]
days = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13]
why5 = [
    "Day 1, month 2 is read as month 1, day 2.",
    "Day and month are both 2, so swapping them changes nothing. Right by luck.",
    "3 February is read as 2 March.",
    "4 February is read as 2 April.",
    "5 February is read as 2 May.",
    "6 February is read as 2 June.",
    "7 February is read as 2 July.",
    "No 8th in the file (nobody shipped on the 8th), so August never appears and September stands in for the 9th.",
    "10 February is read as 2 October.",
    "11 February is read as 2 November.",
    "12 February is read as 2 December. Last day that still looks like a valid US date.",
    "There is no month 13, so en-US cannot read it. The only loud one, and the reason this bug is findable at all.",
]
for i, d in enumerate(days):
    r = 7 + i
    put(ws, f"C{r}", date(2026, 2, d), wrap=False, center=True, fmt="yyyy-mm-dd")
    if d == 13:
        put(ws, f"D{r}", "Error", wrap=False, center=True); verdict = "Error"
    else:
        # en-US reads dd/02/2026 as month=dd, day=2
        put(ws, f"D{r}", date(2026, d, 2), wrap=False, center=True, fmt="yyyy-mm-dd")
        verdict = "Right by luck" if d == 2 else "Wrong month"
    put(ws, f"E{r}", verdict, center=True)
    put(ws, f"F{r}", us_month[i], center=True)
    put(ws, f"G{r}", why5[i])

# the three given questions sit in narrow column B and overflow their rows, so give them room
widen(ws, "B", 26)
for qrow in (29, 33, 37):
    q = ws[f"B{qrow}"].value
    qlines = math.ceil(len(q) / (26 * 0.9))
    ws.row_dimensions[qrow].height = max(ws.row_dimensions[qrow].height or 15, qlines * 13.5 + 6)
put(ws, "B30",
    "Marine, and only marine. Its dates are text in dd/MM/yyyy, so something has to interpret them with a locale. All 12 marine "
    "rows are at risk, 12 of the 34 loaded: under en-US ten land in the wrong month, one is right by luck and one errors.\n"
    "Road is safe because its dates are ISO yyyy-MM-dd, which reads the same in every locale. Rail is safe for a different "
    "reason: its dates are real Excel date values, not text, so there is nothing to parse.")
put(ws, "B34",
    "The totals add up WeightKG and FreightCostPKR over every row, and a row weighs and costs the same whichever month it is "
    "filed under. Moving a row from February to January changes the bucket it falls into, not what it contributes to the sum, "
    "so 578,650 and PKR 4,808,000 stay exact while every monthly report is wrong (all of it actually shipped in February). "
    "Looking at the month list is not enough either: the wrong dates cover eleven months with only August missing, which "
    "reads like a quiet August. What catches it is a test on the date column itself, a range check: every date in February "
    "and the latest day is the 13th.")
put(ws, "B38",
    "The click: Change Type > Using Locale > Date > English (United Kingdom), never plain Change Type. The M carries 'en-GB' as "
    "a literal argument, so the step is right on any machine whatever its regional settings. In pandas it is the same idea, "
    "format='%d/%m/%Y' stated explicitly (a bare pd.to_datetime or dayfirst=True is only a guess).\n"
    "If I forget, check 4 from slide 41 catches it: the months in ShipDate must be {February} only and the latest day must "
    "read 13. Under en-US the slicer shows January to December and the 13th is an error.")
finish_heights(ws)

# ------------------------------------------------------------------------- T6
ws = wb["T6 Loud Or Quiet"]
widen(ws, "C", 14); widen(ws, "D", 44); widen(ws, "E", 56)
t6 = [
    ("Quiet", "Check 4. The latest ShipDate stops moving. Every other check keeps passing on last night's data, which is the danger.",
     "A freshness test: alert when the extract log has no row for tonight, and stamp every report with its as-of date. A job that never starts raises no error by itself."),
    ("Quiet", "Checks 5, 7 and 8. 68 rows instead of 34 and both totals exactly double.",
     "An idempotent load: truncate-and-reload, or upsert on ShipmentID, plus the dedup on the business key. A rerun then gives the same 34 rows."),
    ("Quiet", "Checks 5, 7 and 8, but only if the rows landed are compared with what the source says it holds (road's own TOTAL: 83,000 kg / PKR 652,000).",
     "Extract only a finished file: arrival marker, size-stable check or atomic rename. Reconcile against the source's control totals so a short read fails the run."),
    ("Both", "Check 4. The months in ShipDate must be {February} and the latest day 13. Checks 7 and 8 pass to the rupee.",
     "Type the date Using Locale en-GB (explicit format in pandas), and make check 4 an assertion so one error is not the only warning."),
    ("Quiet", "Check 3. Distinct StatusRaw reads 17 instead of 3.",
     "Trim, Clean and Proper Case before anything compares values, then let check 3 refuse a load that still has more than 3."),
    ("Loud", "None needed to find it: the refresh itself errors ('column not found') and the run stops. Check 1 (seven contract columns per query) confirms the repair.",
     "Nothing to build. The warehouse stays as it was and the 08:00 report shows yesterday's number with a stale stamp. Named steps say which step broke."),
]
for i, (verdict, check, safe) in enumerate(t6):
    r = 7 + i
    put(ws, f"C{r}", verdict, center=True); put(ws, f"D{r}", check); put(ws, f"E{r}", safe)
put(ws, "B22",
    "If everybody prefers the loud failure, then the loud failure needs almost no engineering, because it takes care of "
    "itself: the job goes red and somebody looks. So that is not where the effort goes. Nearly all of it goes into the quiet "
    "failures, and most of the checks, reconciliations, assertions, the -1 log, explicit locales, idempotent loads and "
    "freshness alerts exist to turn a quiet failure into a loud one. The transform logic is the cheaper half of a pipeline; "
    "the monitoring around it is the expensive half.\n"
    "A green dashboard only shows that nothing raised an error, not that the numbers are right: the date bug passes checks 7 "
    "and 8 to the rupee. A pipeline that never fails is not reliable, it is unmonitored.")
finish_heights(ws)

# ------------------------------------------------------------------------- T7
ws = wb["T7 Definition Of Done"]
for r, v in zip(range(7, 15), [7, 295250, 3, 13, 34, 0, 578650, 4808000]):
    put(ws, f"C{r}", v, wrap=False)
    ws[f"C{r}"].alignment = Alignment(horizontal="right", vertical="center")
put(ws, "B21",
    "I counted it instead of assuming it. After the two left outer merges I filter for OriginCityKey = -1 or DestCityKey = -1; "
    "the script prints that count and writes the rows to outputs/unknown_city_log_night1.csv (header only when the count is "
    "0). It is 0 because all 23 spellings in these files are in the alias map, and I also assert that AliasLookup is "
    "exactly 23 rows with 14 keys and no blank spelling, because a blank alias would send blank cities to -1 uncounted.\n"
    "On night2 the same pipeline reports 1: RD-513, origin 'Chaman Border', which no alias resolves. The row is kept in the "
    "fact with key -1 (6,300 kg, PKR 52,000), not deleted, since the shipment happened and dropping it would move 584,950. "
    "Chaman Border gets added to DimCity tomorrow, on purpose, once someone confirms whether it is a city of its own or a "
    "border post of Quetta.")
for r, v in zip(range(30, 36), [35, 584950, 4860000, 3, 1, 5]):
    put(ws, f"C{r}", v, wrap=False)
    ws[f"C{r}"].alignment = Alignment(horizontal="right", vertical="center")
finish_heights(ws)

wb.calculation.fullCalcOnLoad = True
DST.parent.mkdir(exist_ok=True)
wb.save(DST)
print("saved", DST)
