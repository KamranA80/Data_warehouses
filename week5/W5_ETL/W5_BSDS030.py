"""
PakFreight - Week 5: The ETL Process (Python / pandas track)

Student : Kamran Khan Hussain
Roll no : BSDS030
Program : BSDS (Data Science), Section 7A
Course  : Data Warehousing & Business Intelligence

Run it from the folder that holds source/ and dims/ (it also changes into its
own folder first, so it works if you launch it from somewhere else):

    python W5_BSDS030.py

What it does, in order
    1. extract the three night-one files (nothing corrected on the way in)
    2. transform each source with its own named STEPS list
    3. append -> dedup on ShipmentID -> alias lookup -> keys, null -> -1
    4. run the eight checks as assertions and report the -1 count
    5. the refresh test: same code pointed at source/night2
       (the wrong-order numbers in the workbook are reproduced separately in
       W5_BSDS030_traps.py, so this file only ever contains the correct choices)

Staging vs published (there is no "Enable load: off" in pandas, so I mark it):
    intermediate / staging -> `landed`, every frame inside `frames`, the
                              per-source tables, FactStaging steps
    published              -> outputs/FactShipment.csv (+ the step-9 keyed copy)
                              and the five dimensions read from dims/
    Nothing in the intermediate group is ever written for users to find.
"""
import copy
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SOURCE = Path("source")          # the only constant that changes for the refresh test
DIMS = Path("dims")
OUT = Path("outputs")

# ---------------------------------------------------------------- the contract
CONTRACT = ["ShipmentID", "ShipDate", "OriginRaw", "DestRaw",
            "WeightKG", "FreightCostPKR", "StatusRaw"]

RENAME = {
    "marine": {"Shipment_ID": "ShipmentID", "Ship_Date": "ShipDate",
               "Origin_Port": "OriginRaw", "Dest_Port": "DestRaw",
               "Weight_KG": "WeightKG", "Cost_PKR": "FreightCostPKR",
               "Status": "StatusRaw"},
    "road":   {"trip_id": "ShipmentID", "trip_date": "ShipDate",
               "from_city": "OriginRaw", "to_city": "DestRaw",
               "weight_kg": "WeightKG", "cost_pkr": "FreightCostPKR",
               "status": "StatusRaw"},
    # rail weight is TONS, so it is NOT called WeightKG until step ConvertedTonsToKG
    "rail":   {"Consignment No": "ShipmentID", "Dispatch Date": "ShipDate",
               "From Station": "OriginRaw", "To Station": "DestRaw",
               "Weight (Tons)": "WeightTons",
               "Freight Charges (PKR)": "FreightCostPKR", "Status": "StatusRaw"},
}
MODE = {"marine": 1, "rail": 2, "road": 3}          # no file carries a mode, we assign it

# every date format stated out loud - this is the Python version of "Using Locale"
DATE_FMT = {"marine": "%d/%m/%Y",                   # dd/MM/yyyy text
            "road":   "%Y-%m-%d",                   # ISO text
            "rail":   "%Y-%m-%d"}                   # real Excel dates, format is only a guard

# rows sitting above the first data row in each file (title rows + header)
LEAD_ROWS = {"marine": 1, "road": 1, "rail": 3}

FILES = {"marine": "marine_shipments.csv",
         "rail":   "rail_shipments.xlsx",
         "road":   "road_shipments.csv"}

REPORT = []          # everything printed also lands in outputs/run_report.txt


def say(msg=""):
    print(msg)
    REPORT.append(msg)


# ============================================================ E1-E3 : extract
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def read_source(name, path):
    # everything comes in as text / raw cell values. no type guessing, no trimming:
    # extract corrects nothing, so 37 rows arrive and 37 rows land
    if name == "rail":
        # whole workbook as {sheet: frame}; picking the sheet is its own named step
        return pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    return pd.read_csv(path, header=None, dtype=str, keep_default_na=False)


# ===================================================== T1-T7 : per-source steps
# each step is (name, function). names are what I would have typed over
# "FilteredRows1" in the applied-steps pane
def promote_headers(df):
    out = df.iloc[1:].reset_index(drop=True)
    out.columns = list(df.iloc[0])
    return out


def skip_title_rows(df):
    # rail only: two title rows sit above the real header, skip them BEFORE promoting
    return df.iloc[2:].reset_index(drop=True)


def make_rename(name):
    def rename_to_contract(df):
        # DataFrame.rename ignores keys it cannot find, which would turn the one
        # defect that is supposed to fail loudly into a silent one. so check first
        missing = set(RENAME[name]) - set(df.columns)
        if missing:
            raise KeyError(f"{name}: column(s) not found, source layout changed: {sorted(missing)}")
        return df.rename(columns=RENAME[name])
    return rename_to_contract


def remove_blank_rows(df):
    # a blank row is dirt in any pipeline - keyed on the ID column
    ids = df.ShipmentID.astype(str).str.strip()
    return df[(ids != "") & (ids.str.lower() != "nan")].reset_index(drop=True)


def remove_total_row(df):
    # different decision from the blank row: TOTAL is a grain problem, not dirt.
    # it is a subtotal sitting in a one-row-per-shipment table
    ids = df.ShipmentID.astype(str).str.strip()
    return df[ids.str.upper() != "TOTAL"].reset_index(drop=True)


def trim_text(df):
    df = df.copy()
    for c in ("OriginRaw", "DestRaw"):          # these feed the alias lookup later
        df[c] = df[c].astype(str).str.strip()
    return df


def clean_status(df):
    df = df.copy()
    # \s+ -> " " covers tabs and the double space in "In  Transit" (Trim alone would not)
    df["StatusRaw"] = (df.StatusRaw.astype(str)
                       .str.replace(r"\s+", " ", regex=True)
                       .str.strip()
                       .str.title())
    return df


def uppercase_ids(df):
    df = df.copy()
    df["ShipmentID"] = df.ShipmentID.astype(str).str.strip().str.upper()   # rd-505 -> RD-505
    return df


def prefix_rail_ids(df):
    # rail ids arrive as bare integers (45012), the star stores RL-45012.
    # the one place all week where a value's meaning is changed on purpose
    df = df.copy()
    df["ShipmentID"] = df.ShipmentID.map(lambda v: f"RL-{int(float(v))}")
    return df


def make_type_dates(name):
    def type_dates(df):
        df = df.copy()
        # explicit format on purpose. bare pd.to_datetime("01/02/2026") reads 2 Jan
        df["ShipDate"] = pd.to_datetime(df.ShipDate, format=DATE_FMT[name])
        return df
    return type_dates


def make_type_numbers(name):
    def type_numbers(df):
        df = df.copy()
        weight = "WeightTons" if name == "rail" else "WeightKG"
        # to_numeric raises on junk, so a bad value is loud
        df["FreightCostPKR"] = pd.to_numeric(df.FreightCostPKR).astype("int64")
        if name == "rail":
            df["WeightTons"] = pd.to_numeric(df.WeightTons).astype("float64")
        else:
            df[weight] = pd.to_numeric(df[weight]).astype("int64")
        return df
    return type_numbers


def convert_tons_to_kg(df):
    # has to happen on the rail query itself. after the append kilograms and tons
    # sit in one column and nothing says which is which
    df = df.copy()
    kg = df.WeightTons * 1000
    assert ((kg - kg.round()).abs() < 1e-6).all(), "tons x 1000 left a fractional kilogram"
    df["WeightKG"] = kg.round().astype("int64")
    return df


def remove_weight_tons(df):
    return df.drop(columns=["WeightTons"])


def make_add_mode(name):
    def add_mode(df):
        df = df.copy()
        df["ModeKey"] = MODE[name]          # known only before the append, so it is added here
        return df[CONTRACT + ["ModeKey"]]
    return add_mode


def build_steps(name, path):
    """The named applied-steps list for one source (marine 9, road 11, rail 13)."""
    steps = [("Source", lambda _: read_source(name, path))]
    if name == "rail":
        steps += [("NavigatedToRailSheet", lambda sheets: sheets["Rail"]),
                  ("SkippedTitleRows", skip_title_rows)]
    steps += [("PromotedHeaders", promote_headers),
              ("RenamedToContract", make_rename(name))]
    if name == "road":
        steps += [("RemovedBlankRows", remove_blank_rows),
                  ("RemovedTotalRow", remove_total_row)]
    steps += [("TrimmedText", trim_text),
              ("CleanedStatus", clean_status)]
    if name == "rail":
        steps += [("PrefixedRailIDs", prefix_rail_ids)]
    else:
        steps += [("UppercasedIDs", uppercase_ids)]
    steps += [("TypedDates", make_type_dates(name)),
              ("TypedNumbers", make_type_numbers(name))]
    if name == "rail":
        steps += [("ConvertedTonsToKG", convert_tons_to_kg),
                  ("RemovedWeightTons", remove_weight_tons)]
    steps += [("AddedModeKey", make_add_mode(name))]
    return steps


def run_steps(steps, stop_after=None):
    """Replay the steps in order, keeping every intermediate frame so I can
    look at step 7 instead of guessing (frames['TrimmedText'] etc.)."""
    frames, cur = {}, None
    for step_name, fn in steps:
        cur = fn(cur)
        frames[step_name] = copy.deepcopy(cur)
        if step_name == stop_after:
            break
    return cur, frames


# ======================================================== T10 : alias lookup
def build_alias_lookup():
    dim = pd.read_csv(DIMS / "DimCity.csv", dtype={"RawAliases": str})
    out = (dim[["CityKey", "RawAliases"]]
           .assign(RawAliases=lambda d: d.RawAliases.fillna("").str.split(" | ", regex=False))
           .explode("RawAliases"))
    out["RawAliases"] = out.RawAliases.str.strip()
    out = out[out.RawAliases != ""]                      # the Unknown row leaves one blank behind
    out = out.rename(columns={"RawAliases": "RawSpelling"}).reset_index(drop=True)

    # the blank alias would silently swallow every future blank city name into -1
    assert len(out) == 23, f"AliasLookup should have 23 rows, got {len(out)}"
    assert out.CityKey.nunique() == 14, "AliasLookup should have 14 distinct keys"
    assert out.RawSpelling.is_unique, "duplicate spelling would multiply fact rows in the merge"

    # cross-check against the instructor's alias_lookup.csv (checking only, not importing)
    ref = pd.read_csv("alias_lookup.csv")
    mine = set(zip(out.RawSpelling, out.CityKey))
    theirs = set(zip(ref.RawSpelling, ref.CityKey))
    assert mine == theirs, f"alias map differs from alias_lookup.csv: {mine ^ theirs}"
    return out


# =========================================================== the whole pipeline
def run_pipeline(src, label):
    """E1-E3 -> T1-T7 per source -> T8-T10 once. Returns everything I need to check."""
    res = {"label": label, "src": src, "extract_log": [], "frames": {}, "per_source": {}, "landed": {}}
    stamp = datetime.now().isoformat(timespec="seconds")

    # ---- E1/E2/E3: connect, land a faithful copy, log it
    for name in ("marine", "rail", "road"):
        path = src / FILES[name]
        raw = read_source(name, path)
        sheet = raw["Rail"] if name == "rail" else raw
        res["landed"][name] = copy.deepcopy(raw)                     # untouched copy
        res["extract_log"].append({
            "run": label, "source": FILES[name], "extracted_at": stamp,
            "sha256_12": sha(path), "rows_landed": len(sheet) - LEAD_ROWS[name]})

    # ---- T1-T7: each source through its own named steps
    for name in ("marine", "rail", "road"):
        final, frames = run_steps(build_steps(name, src / FILES[name]))
        res["per_source"][name] = final
        res["frames"][name] = frames

    # ---- T8: append (guard first - append never complains about mismatched columns)
    marine, rail, road = (res["per_source"][n] for n in ("marine", "rail", "road"))
    for n, df in res["per_source"].items():
        assert list(df.columns) == CONTRACT + ["ModeKey"], f"{n} is not on the contract: {list(df.columns)}"

    alias = build_alias_lookup()
    res["alias"] = alias

    fact_steps = {}
    appended = pd.concat([marine, rail, road], ignore_index=True)
    fact_steps["AppendedQueries"] = appended
    res["appended_rows"] = len(appended)

    # ---- T9: dedup on the business key, after the trim and uppercase (never a bare drop_duplicates)
    deduped = appended.drop_duplicates(subset=["ShipmentID"], keep="first").reset_index(drop=True)
    fact_steps["DedupedOnShipmentID"] = deduped
    dropped = appended[appended.duplicated(subset=["ShipmentID"], keep="first")]
    res["dropped_dupes"] = dropped
    # a duplicate that is NOT identical on weight/cost is a judgement call, so say so out loud
    for _, d in dropped.iterrows():
        first = appended[appended.ShipmentID == d.ShipmentID].iloc[0]
        if (first.WeightKG, first.FreightCostPKR) != (d.WeightKG, d.FreightCostPKR):
            say(f"  WARNING {d.ShipmentID}: repeated row differs in weight/cost - dropped the later copy, review it")

    # ---- T10: conform spellings to keys. left join so no shipment can disappear
    cur = deduped
    for raw_col, key_col, step in (("OriginRaw", "OriginCityKey", "MergedOriginAlias"),
                                   ("DestRaw", "DestCityKey", "MergedDestAlias")):
        before = len(cur)
        cur = cur.merge(alias.rename(columns={"RawSpelling": raw_col, "CityKey": key_col}),
                        on=raw_col, how="left")                          # how="left", never "inner"
        assert len(cur) == before, "merge changed the row count"
        fact_steps[step] = cur
    cur = cur.copy()
    for key_col in ("OriginCityKey", "DestCityKey"):
        cur[key_col] = cur[key_col].fillna(-1).astype("int64")           # unresolved -> Unknown member
    fact_steps["ReplacedNullKeysWithUnknown"] = cur

    res["frames"]["FactStaging"] = fact_steps
    res["fact"] = cur.reset_index(drop=True)

    # the -1 rows are counted and kept, never dropped
    unk = res["fact"][(res["fact"].OriginCityKey == -1) | (res["fact"].DestCityKey == -1)]
    res["unknown_rows"] = unk
    spell = []
    for _, r in unk.iterrows():
        if r.OriginCityKey == -1:
            spell.append(("OriginRaw", r.ShipmentID, r.OriginRaw))
        if r.DestCityKey == -1:
            spell.append(("DestRaw", r.ShipmentID, r.DestRaw))
    res["unknown_spellings"] = spell
    return res


# ============================================================= the eight checks
def run_checks(res):
    fact, ps = res["fact"], res["per_source"]
    rows = []

    def chk(n, label, got, want):
        rows.append((n, label, got, want, got == want))

    chk(1, "contract columns in each query (marine/rail/road)",
        tuple(len([c for c in ps[n].columns if c in CONTRACT]) for n in ("marine", "rail", "road")), (7, 7, 7))
    chk(2, "rail subtotal kg, before the append", int(ps["rail"].WeightKG.sum()), 295_250)
    chk(3, "distinct StatusRaw", int(fact.StatusRaw.nunique()), 3)
    # 4 is two questions: which months (the locale) and how far the range runs
    chk(4, "months present in ShipDate (set, not a list)", set(fact.ShipDate.dt.month), {2})
    chk(4, "latest day in ShipDate", int(fact.ShipDate.dt.day.max()), 13)
    chk(5, "rows in FactShipment", len(fact), 34)
    chk(7, "SUM(WeightKG)", int(fact.WeightKG.sum()), 578_650)
    chk(8, "SUM(FreightCostPKR)", int(fact.FreightCostPKR.sum()), 4_808_000)
    return rows


def print_checks(rows, title):
    say(f"\n{title}")
    say(f"  {'#':<3}{'check':<52}{'got':<22}{'expected':<22}result")
    for n, label, got, want, ok in rows:
        say(f"  {n:<3}{label:<52}{str(got):<22}{str(want):<22}{'pass' if ok else 'FAIL'}")
    bad = [r for r in rows if not r[4]]
    assert not bad, f"{len(bad)} check(s) failed - read the troubleshooting table, do not adjust the check: {bad}"


# =========================================================================== main
def main():
    os.chdir(Path(__file__).resolve().parent)       # so Path('source') / Path('dims') always resolve
    for need in (SOURCE, DIMS, SOURCE / "night2", Path("alias_lookup.csv")):
        if not need.exists():
            sys.exit(f"cannot find {need} - run this from the lab folder (source/, dims/, alias_lookup.csv)")
    OUT.mkdir(exist_ok=True)

    # source files must come out exactly as they went in (transform never writes to the source)
    watched = [p for p in list(SOURCE.glob("*.*")) + list((SOURCE / "night2").glob("*.*"))]
    before = {p: sha(p) for p in watched}

    say("PakFreight Week 5 - ETL run | Kamran Khan Hussain | BSDS030 | 7A")
    say(f"run started {datetime.now():%Y-%m-%d %H:%M:%S}")

    # ---------------------------------------------------------------- night one
    n1 = run_pipeline(SOURCE, "night1")
    say("\nE3 extract log (night1)")
    log1 = pd.DataFrame(n1["extract_log"])
    say(log1.to_string(index=False))
    landed = int(log1.rows_landed.sum())
    assert landed == 37, f"extract should land 37 rows, landed {landed}"
    assert list(log1.rows_landed) == [12, 10, 15]

    say("\nrow ladder (T4 part A), night1")
    ps = n1["per_source"]
    road_real = n1["frames"]["road"]["RemovedTotalRow"]
    rows = [
        ("marine, as extracted", 12, int(ps["marine"].WeightKG.sum()), int(ps["marine"].FreightCostPKR.sum())),
        ("rail, as extracted", 10, int(ps["rail"].WeightKG.sum()), int(ps["rail"].FreightCostPKR.sum())),
        ("road, as extracted (15 land, 13 real)", 15, int(ps["road"].WeightKG.sum()), int(ps["road"].FreightCostPKR.sum())),
        ("raw rows landed in staging", landed, None, None),
        ("appended", n1["appended_rows"],
         int(pd.concat(ps.values()).WeightKG.sum()), int(pd.concat(ps.values()).FreightCostPKR.sum())),
        ("loaded into FactShipment", len(n1["fact"]), int(n1["fact"].WeightKG.sum()), int(n1["fact"].FreightCostPKR.sum())),
    ]
    for label, r, w, c in rows:
        say(f"  {label:<40}{r:>4}   {'' if w is None else format(w, ',')!s:>10}   {'' if c is None else format(c, ',')!s:>12}")
    assert len(road_real) == 13 and rows[4][1:] == (35, 584_750, 4_855_000)
    say(f"  duplicates removed: {sorted(set(n1['dropped_dupes'].ShipmentID))}")

    checks1 = run_checks(n1)
    print_checks(checks1, "the eight checks - night1 (check 6 is counted, not asserted)")
    minus1_n1 = len(n1["unknown_rows"])
    say(f"  6  rows routed to Unknown (-1): {minus1_n1}")
    assert len(n1["alias"]) == 23

    # --------------------------------------------------------------- publish
    published = ["ShipmentID", "ShipDate", "OriginRaw", "DestRaw", "WeightKG", "FreightCostPKR",
                 "StatusRaw", "ModeKey", "OriginCityKey", "DestCityKey"]
    n1["fact"][published].to_csv(OUT / "FactShipment.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(n1["extract_log"]).to_csv(OUT / "extract_log_night1.csv", index=False)
    n1["unknown_rows"][["ShipmentID", "OriginRaw", "DestRaw"]].to_csv(OUT / "unknown_city_log_night1.csv", index=False)

    # ------------------------------------------------- step 9 (homework): the other keys
    keyed = add_step9_keys(n1["fact"], say)
    keyed.to_csv(OUT / "FactShipment_step9_keys.csv", index=False, date_format="%Y-%m-%d")

    # --------------------------------------------------------------- night two
    say("\n" + "=" * 78)
    say("REFRESH TEST - same code, source pointed at source/night2, nothing edited")
    n2 = run_pipeline(SOURCE / "night2", "night2")
    log2 = pd.DataFrame(n2["extract_log"])
    say(log2.to_string(index=False))

    f2 = n2["fact"]
    t2 = [
        ("rows in FactShipment", len(f2), 35),
        ("SUM(WeightKG)", int(f2.WeightKG.sum()), 584_950),
        ("SUM(FreightCostPKR)", int(f2.FreightCostPKR.sum()), 4_860_000),
        ("distinct StatusRaw", int(f2.StatusRaw.nunique()), 3),
        ("rows carrying a -1 city key", len(n2["unknown_rows"]), 1),
        ("rows with status Delayed", int((f2.StatusRaw == "Delayed").sum()), 5),
    ]
    say(f"\n  {'refresh check':<34}{'got':>12}{'expected':>12}  result")
    for label, got, want in t2:
        say(f"  {label:<34}{got:>12,}{want:>12,}  {'pass' if got == want else 'FAIL'}")
    assert all(g == w for _, g, w in t2), "refresh test failed"
    say(f"  unresolved spellings -> -1 : {[(c, i, s) for c, i, s in n2['unknown_spellings']]}")
    say(f"  duplicates removed on night2: {sorted(set(n2['dropped_dupes'].ShipmentID))}")
    n2["unknown_rows"][["ShipmentID", "OriginRaw", "DestRaw"]].to_csv(OUT / "unknown_city_log_night2.csv", index=False)
    pd.DataFrame(n2["extract_log"]).to_csv(OUT / "extract_log_night2.csv", index=False)
    f2[published].to_csv(OUT / "FactShipment_night2.csv", index=False, date_format="%Y-%m-%d")

    # ---------------------------------------------------------------- wrap up
    after = {p: sha(p) for p in watched}
    assert before == after, "a source file changed during the run"
    say("\nsource files byte-for-byte unchanged after both runs")

    say("\nSUMMARY")
    say(f"  night1: {len(n1['fact'])} rows | {int(n1['fact'].WeightKG.sum()):,} kg | "
        f"PKR {int(n1['fact'].FreightCostPKR.sum()):,} | rows on -1 key: {minus1_n1}")
    say(f"  night2: {len(f2)} rows | {int(f2.WeightKG.sum()):,} kg | "
        f"PKR {int(f2.FreightCostPKR.sum()):,} | rows on -1 key: {len(n2['unknown_rows'])}")
    (OUT / "run_report.txt").write_text("\n".join(REPORT) + "\n", encoding="utf-8")


def add_step9_keys(fact, say):
    """DateKey / StatusKey / RouteKey, and a rebuild of DimRoute to compare with Week 4's."""
    f = fact.copy()
    # arithmetic for a key (merge-columns is lossy in one direction)
    f["DateKey"] = (f.ShipDate.dt.year * 10000 + f.ShipDate.dt.month * 100 + f.ShipDate.dt.day).astype("int64")
    dim_date = pd.read_csv(DIMS / "DimDate.csv")
    assert f.DateKey.isin(dim_date.DateKey).all(), "a DateKey is missing from DimDate"

    dim_status = pd.read_csv(DIMS / "DimStatus.csv")[["StatusKey", "StatusName"]]
    f = f.merge(dim_status.rename(columns={"StatusName": "StatusRaw"}), on="StatusRaw", how="left")
    f["StatusKey"] = f.StatusKey.fillna(-1).astype("int64")

    dim_route = pd.read_csv(DIMS / "DimRoute.csv")[["RouteKey", "OriginCityKey", "DestCityKey"]]
    f = f.merge(dim_route, on=["OriginCityKey", "DestCityKey"], how="left")
    f["RouteKey"] = f.RouteKey.fillna(-1).astype("int64")

    # rebuild DimRoute: distinct pairs from the keyed fact vs the Week 4 file
    mine = set(zip(f.OriginCityKey, f.DestCityKey))
    theirs = set(zip(dim_route.OriginCityKey, dim_route.DestCityKey)) - {(-1, -1)}
    say("\nstep 9 - keys beyond the cities")
    say(f"  rows with StatusKey = -1: {int((f.StatusKey == -1).sum())} | RouteKey = -1: {int((f.RouteKey == -1).sum())}")
    say(f"  distinct city pairs in the fact: {len(mine)}; Week 4 DimRoute pairs (excl. Unknown): {len(theirs)}; "
        f"identical sets: {mine == theirs}")
    return f


if __name__ == "__main__":
    main()
