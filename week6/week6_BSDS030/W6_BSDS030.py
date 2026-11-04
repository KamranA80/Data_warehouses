"""
W6_BSDS030.py  --  Week 6 Quality Lab, the dual-route load
Kamran Khan Hussain | BSDS030 | BSDS (Data Science) 7A | Data Warehousing & BI

Tool used: pandas (the marks are the same for pandas / Power Query / Power BI).

What it does, in the order it does it
    1. EXTRACT   land the three March files untouched, tag every row with file + line
    2. PROFILE   count what is wrong BEFORE any value is changed (T2)
    3. TRANSFORM trim, type, units, conform (alias map, status, customer)
    4. ROUTE     reject (24) | route to Unknown (21) | remove duplicate (60) | load
    5. BUILD     DimCustomer (40 + Unknown), DimDate (90, gapless), FactShipment_March
    6. PROVE     print the ladder, assert the identity and the ten T7 checks

Run it from the folder that holds the data:
    python W6_BSDS030.py
It looks for the inputs in ./data, ./assignments/data or the current folder,
and writes everything into ./output
"""
import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------------
# paths -- relative only, so it runs on any machine that has the repo layout
# ----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def _find_data_root() -> Path:
    for cand in (HERE / "data", HERE / "assignments" / "data", HERE):
        if (cand / "alias_lookup.csv").exists():
            return cand
    raise FileNotFoundError("alias_lookup.csv not found in ./data, ./assignments/data or .")


DATA = _find_data_root()
MARCH = DATA / "march" if (DATA / "march").exists() else DATA
DIMS = DATA / "dims" if (DATA / "dims").exists() else DATA
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

LOAD_BATCH = "2026-03"
CONTRACT = ["ShipmentID", "ShipDate", "Origin", "Destination",
            "WeightKG", "FreightCostPKR", "StatusRaw", "CustomerID"]


# ----------------------------------------------------------------------------
# 1. EXTRACT -- nothing is corrected here, only renamed to the contract
# ----------------------------------------------------------------------------
def extract() -> pd.DataFrame:
    # marine: structurally clean, everything read as text so nothing gets "helped"
    marine = pd.read_csv(MARCH / "marine_march.csv", dtype=str, keep_default_na=False)
    marine.columns = CONTRACT
    marine["SourceFile"] = "marine_march.csv"
    marine["SourceLine"] = marine.index + 2          # header is line 1

    # road: keep the blank line so the line numbers stay honest, then drop the two
    # structural lines (blank + TOTAL footer) -- they are not shipments
    road_all = pd.read_csv(MARCH / "road_march.csv", dtype=str,
                           keep_default_na=False, skip_blank_lines=False)
    road_all.columns = CONTRACT
    road_all["SourceFile"] = "road_march.csv"
    road_all["SourceLine"] = road_all.index + 2
    is_blank = road_all[CONTRACT].apply(lambda r: "".join(r).strip() == "", axis=1)
    is_footer = road_all["ShipmentID"].str.strip().str.upper().eq("TOTAL")
    structural = road_all[is_blank | is_footer]
    road = road_all[~(is_blank | is_footer)].copy()
    print(f"[extract] road: skipped {len(structural)} structural lines "
          f"(blank line + TOTAL footer) at file lines {structural.SourceLine.tolist()}")
    # the footer is a control total from the source system -- use it before throwing it away
    footer = road_all[is_footer].iloc[0]
    road_w = sum(float(v) for v in road.WeightKG.str.strip() if PLAIN_NUMBER.match(v))
    road_c = sum(float(v) for v in road.FreightCostPKR.str.strip() if PLAIN_NUMBER.match(v))
    print(f"[extract] road control total: footer says {float(footer.WeightKG):,.0f} kg / "
          f"PKR {float(footer.FreightCostPKR):,.0f}; column sums to {road_w:,.0f} kg / PKR {road_c:,.0f}")
    assert (road_w, road_c) == (float(footer.WeightKG), float(footer.FreightCostPKR)), \
        "road footer does not reconcile to the road rows"

    # rail: two title rows, header on row 3, so data starts on excel row 4
    rail = pd.read_excel(MARCH / "rail_march.xlsx", header=2, dtype=object)
    rail.columns = CONTRACT
    rail["SourceFile"] = "rail_march.xlsx"
    rail["SourceLine"] = rail.index + 4
    # cells that excel typed as dates come through as datetimes; keep them as ISO text
    rail["ShipDate"] = rail["ShipDate"].map(
        lambda v: v.strftime("%Y-%m-%d") if isinstance(v, (datetime, pd.Timestamp)) else v)
    # numbers stay numbers in the raw layer but as text, so the rule checks see the same thing
    for c in ("ShipmentID", "WeightKG", "FreightCostPKR"):
        rail[c] = rail[c].map(lambda v: "" if pd.isna(v) else (
            str(int(v)) if isinstance(v, float) and float(v).is_integer() else str(v)))
    for c in CONTRACT:
        rail[c] = rail[c].map(lambda v: "" if pd.isna(v) else str(v))

    marine["Mode"], rail["Mode"], road["Mode"] = "Marine", "Rail", "Road"
    staging = pd.concat([marine, rail, road], ignore_index=True)
    staging["StageRow"] = range(1, len(staging) + 1)
    return staging


# ----------------------------------------------------------------------------
# rules (used by profile AND by transform, so the two can never disagree)
# ----------------------------------------------------------------------------
PLAIN_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")      # 1.2e4 and '6,5OO' are deliberately not numbers


def parse_date(raw: str, mode: str):
    raw = raw.strip()
    fmt = {"Marine": "%d/%m/%Y", "Road": "%Y-%m-%d", "Rail": "%Y-%m-%d"}[mode]
    for f in (fmt, "%d/%m/%Y") if mode == "Rail" else (fmt,):
        try:
            d = datetime.strptime(raw, f).date()
        except ValueError:
            continue
        # the file is the March file: a real date outside March is still a failed rule
        return d if (d.year, d.month) == (2026, 3) else None
    return None


def weight_state(raw: str) -> str:
    s = raw.strip()
    if not PLAIN_NUMBER.match(s):
        return "text"
    return "negative" if float(s) < 0 else ("zero" if float(s) == 0 else "ok")


# ----------------------------------------------------------------------------
# 2. PROFILE -- before a single value changes
# ----------------------------------------------------------------------------
def conformed_id(row) -> str:
    """ShipmentID the way it should look: trimmed, upper case, RL- put back on rail."""
    s = row["ShipmentID"].strip().upper()
    if s and row["Mode"] == "Rail" and not s.startswith("RL-"):
        s = "RL-" + s
    return s


def profile(staging, alias_map, status_map, cust_id_to_key):
    s = staging
    p = {}
    nonblank_ids = s[s.ShipmentID.str.strip() != ""]
    norm = nonblank_ids.apply(conformed_id, axis=1)
    p["ShipmentID"] = dict(
        blank=int((s.ShipmentID.str.strip() == "").sum()),
        distinct=int(nonblank_ids.ShipmentID.nunique()),
        fails=int((s.ShipmentID.str.strip() == "").sum()) + int(norm.duplicated().sum()),
        transform=int((nonblank_ids.ShipmentID != norm).sum()))

    parsed = s.apply(lambda r: parse_date(r.ShipDate, r.Mode), axis=1)
    p["ShipDate"] = dict(blank=int((s.ShipDate.str.strip() == "").sum()),
                         distinct=int(s.ShipDate.nunique()),
                         fails=int(parsed.isna().sum()), transform=None)

    for col in ("Origin", "Destination"):
        key = s[col].str.strip().str.lower().map(alias_map)
        p[col] = dict(blank=int((s[col].str.strip() == "").sum()),
                      distinct=int(s[col].nunique()),
                      fails=int(key.isna().sum()),
                      # right city, other spelling: resolves, but the string is not the city name
                      transform=int(((key.notna()) & (s[col].str.strip() != s[col].str.strip().map(
                          lambda v: CITY_NAME.get(alias_map.get(v.lower()))))).sum()))

    ws = s.WeightKG.map(weight_state)
    p["WeightKG"] = dict(blank=int((s.WeightKG.str.strip() == "").sum()),
                         distinct=int(s.WeightKG.nunique()),
                         fails=int((ws != "ok").sum()), transform=None)
    # cost: only 'is it a number' is a rule; a negative is a credit note
    cs = s.FreightCostPKR.map(lambda v: bool(PLAIN_NUMBER.match(v.strip())))
    p["FreightCostPKR"] = dict(blank=int((s.FreightCostPKR.str.strip() == "").sum()),
                               distinct=int(s.FreightCostPKR.nunique()),
                               fails=int((~cs).sum()), transform=None)

    st = s.StatusRaw.str.strip().str.lower().map(status_map)
    canon_status = {"delivered": "Delivered", "in transit": "In Transit", "delayed": "Delayed"}
    p["StatusRaw"] = dict(blank=int((s.StatusRaw.str.strip() == "").sum()),
                          distinct=int(s.StatusRaw.nunique()),
                          fails=int(st.isna().sum()),
                          transform=int(((st.notna()) & (s.StatusRaw != s.StatusRaw.str.strip().str.lower()
                                         .map(canon_status))).sum()))

    ck = s.CustomerID.str.strip().str.upper().map(cust_id_to_key)
    p["CustomerID"] = dict(blank=int((s.CustomerID.str.strip() == "").sum()),
                           distinct=int(s.CustomerID.nunique()),
                           fails=int(ck.isna().sum()), transform=None)
    return p


# ----------------------------------------------------------------------------
# dimensions
# ----------------------------------------------------------------------------
CITY_NAME = {}


def load_dims():
    alias = pd.read_csv(DATA / "alias_lookup.csv")
    dim_city = pd.read_csv(DIMS / "DimCity.csv")
    dim_route = pd.read_csv(DIMS / "DimRoute.csv")
    dim_mode = pd.read_csv(DIMS / "DimMode.csv")
    dim_status = pd.read_csv(DIMS / "DimStatus.csv")
    stale_date = pd.read_csv(DIMS / "DimDate.csv")
    # the alias map must point at cities that really exist in the conformed dimension
    assert set(alias.CityKey) <= set(dim_city.CityKey), "alias map points at a missing city"
    CITY_NAME.clear()
    CITY_NAME.update(dict(zip(dim_city.CityKey, dim_city.CityName)))
    alias_map = {k.strip().lower(): int(v) for k, v in zip(alias.RawSpelling, alias.CityKey)}
    status_map = {n.strip().lower(): int(k) for k, n in zip(dim_status.StatusKey, dim_status.StatusName)
                  if int(k) != -1}
    return alias_map, status_map, dim_city, dim_route, dim_mode, dim_status, stale_date


def _norm_name(name: str) -> str:
    """Conform a customer name so INDUS TEXTILES LIMITED == Indus Textiles Ltd."""
    n = name.lower()
    n = re.sub(r"\(pvt\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)                  # dots, brackets
    words = [{"ltd": "limited", "co": "company"}.get(w, w) for w in n.split()]
    words = [w for w in words if w not in ("pvt", "limited", "company")]
    return " ".join(words)


def build_dim_customer():
    reg = pd.read_csv(DATA / "customers_master.csv", dtype=str)
    reg["Conformed"] = reg.CustomerName.map(_norm_name)
    reg["Num"] = reg.CustomerID.str[3:].astype(int)
    reg = reg.sort_values("Num")
    rows, id_to_key = [], {}
    # survivor = lowest registry number (the CU-1xx id); the later ids become aliases
    groups = sorted(reg.groupby("Conformed"), key=lambda kv: kv[1].Num.min())
    for key, (conf, g) in enumerate(groups, start=1):
        g = g.sort_values("Num")
        survivor = g.iloc[0]
        assert g.City.nunique() == 1, f"{conf}: same name, different city -- not safe to merge"
        others = g.iloc[1:]
        rows.append(dict(
            CustomerKey=key, CustomerID=survivor.CustomerID, CustomerName=survivor.CustomerName,
            City=survivor.City, Sector=survivor.Sector, SignedUp=g.SignedUp.min(),
            AliasIDs=" | ".join(others.CustomerID), AliasNames=" | ".join(others.CustomerName)))
        for cid in g.CustomerID:
            id_to_key[cid] = key
    dim = pd.DataFrame(rows)
    unknown = dict(CustomerKey=-1, CustomerID="Unknown", CustomerName="Unknown", City="Unknown",
                   Sector="Unknown", SignedUp="", AliasIDs="", AliasNames="")
    dim = pd.concat([dim, pd.DataFrame([unknown])], ignore_index=True)
    return dim, id_to_key, reg


def build_dim_date(start=date(2026, 1, 1), end=date(2026, 3, 31)) -> pd.DataFrame:
    # Q1 2026, gapless. Same columns and conventions as the Week 4 file (Sunday = 1).
    # Holidays: only the two fixed-date public holidays I can stand behind -- 5 Feb
    # (already flagged in the Week 4 file) and 23 Mar (Pakistan Day). Eid dates move with
    # the moon so I have not guessed them.
    holidays = {date(2026, 2, 5), date(2026, 3, 23)}
    rows, d = [], start
    while d <= end:
        dow = (d.weekday() + 1) % 7 + 1               # Mon=0 -> 2 ... Sun=6 -> 1
        rows.append(dict(
            DateKey=int(d.strftime("%Y%m%d")), FullDate=d.isoformat(), Year=d.year,
            Quarter=(d.month - 1) // 3 + 1, MonthNumber=d.month, MonthName=d.strftime("%B"),
            DayOfMonth=d.day, DayOfWeek=dow, DayName=d.strftime("%A"),
            IsWeekend="Yes" if dow in (1, 7) else "No",
            IsHoliday="Yes" if d in holidays else "No"))
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# 3 + 4. TRANSFORM and ROUTE
# ----------------------------------------------------------------------------
def run(write=True, verbose=True):
    alias_map, status_map, dim_city, dim_route, dim_mode, dim_status, stale_date = load_dims()
    dim_customer, cust_id_to_key, registry = build_dim_customer()
    dim_date = build_dim_date()

    staging = extract()
    prof = profile(staging, alias_map, status_map, cust_id_to_key)

    s = staging.copy()
    # --- transforms (each one named, the Week 5 rule has not been repealed) ---
    s["ShipmentID_clean"] = s.apply(conformed_id, axis=1)             # trim, upper, RL- prefix
    s["Date_parsed"] = s.apply(lambda r: parse_date(r.ShipDate, r.Mode), axis=1)
    s["W_state"] = s.WeightKG.map(weight_state)
    s["Weight_num"] = pd.to_numeric(s.WeightKG.str.strip().where(s.W_state.isin(["ok", "negative"])),
                                    errors="coerce")
    # rail is in TONNES: x1000 per row, on the typed number, before anything is summed
    s["WeightKG_clean"] = s.Weight_num.where(s.Mode != "Rail", s.Weight_num * 1000)
    s["Cost_num"] = pd.to_numeric(s.FreightCostPKR.str.strip(), errors="coerce")
    s["OriginCityKey"] = s.Origin.str.strip().str.lower().map(alias_map)
    s["DestCityKey"] = s.Destination.str.strip().str.lower().map(alias_map)
    s["StatusKey"] = s.StatusRaw.str.strip().str.lower().map(status_map)
    s["CustomerKey"] = s.CustomerID.str.strip().str.upper().map(cust_id_to_key)

    # --- reject route: the row cannot be loaded at all ---
    def reject_reasons(r):
        out = []
        if r.ShipmentID.strip() == "":
            out.append(("ShipmentID", "blank ShipmentID"))
        if pd.isna(r.Date_parsed):
            out.append(("ShipDate", f"ShipDate does not parse as a March 2026 date: '{r.ShipDate}'"))
        if r.W_state == "text":
            out.append(("WeightKG", f"WeightKG is not a number: '{r.WeightKG}'"))
        if r.W_state == "negative":
            out.append(("WeightKG", f"WeightKG is negative: {r.WeightKG.strip()}"))
        if r.W_state == "zero":
            out.append(("WeightKG", "WeightKG is zero"))
        return out

    s["_rej"] = s.apply(reject_reasons, axis=1)
    s["IsReject"] = s["_rej"].map(len) > 0
    assert (s["_rej"].map(len) <= 1).all(), "a row failed two reject rules - check the log text"

    # a negative COST is a credit note -> not a reject. it loads as a negative.
    credit_notes = s[(~s.IsReject) & (s.Cost_num < 0)]

    rejects = s[s.IsReject].copy()
    reject_log = pd.DataFrame({
        "RejectID": range(1, len(rejects) + 1),
        "LoadBatch": LOAD_BATCH,
        "SourceFile": rejects.SourceFile.values,
        "SourceLine": rejects.SourceLine.values,
        "FailedColumn": rejects._rej.map(lambda x: x[0][0]).values,
        "RejectReason": rejects._rej.map(lambda x: x[0][1]).values,
        # the row exactly as it arrived, so it can be fixed at the source and re-submitted
        "RawRecord": rejects.apply(lambda r: json.dumps({c: r[c] for c in CONTRACT}, ensure_ascii=False),
                                   axis=1).values,
    }).sort_values(["SourceFile", "SourceLine"]).reset_index(drop=True)
    reject_log["RejectID"] = range(1, len(reject_log) + 1)

    # --- dedupe the loadable rows on the CLEANED ShipmentID (trim + case first) ---
    loadable = s[~s.IsReject].copy()
    dup_mask = loadable.duplicated("ShipmentID_clean", keep="first")
    dups = loadable[dup_mask].copy()
    first_line = loadable[~dup_mask].set_index("ShipmentID_clean")[["SourceFile", "SourceLine"]]
    kept_raw = loadable[~dup_mask].set_index("ShipmentID_clean")
    dedup_log = pd.DataFrame({
        "ShipmentID": dups.ShipmentID_clean.values,
        "RemovedFile": dups.SourceFile.values, "RemovedLine": dups.SourceLine.values,
        "KeptFile": first_line.loc[dups.ShipmentID_clean, "SourceFile"].values,
        "KeptLine": first_line.loc[dups.ShipmentID_clean, "SourceLine"].values,
        # compare the two raw records field by field: identical = byte-identical copy,
        # otherwise the only thing that differs is whitespace on the ShipmentID
        "Kind": [
            "byte-identical" if all(rem[c] == kept_raw.loc[rem.ShipmentID_clean, c] for c in CONTRACT)
            else "trailing space"
            for _, rem in dups.iterrows()],
    })
    loaded = loadable[~dup_mask].copy()

    # --- conform: lookups that fail go to -1, they do not disappear ---
    loaded["OriginCityKey"] = loaded.OriginCityKey.fillna(-1).astype(int)
    loaded["DestCityKey"] = loaded.DestCityKey.fillna(-1).astype(int)
    loaded["StatusKey"] = loaded.StatusKey.fillna(-1).astype(int)
    route_key = {(o, d): k for k, o, d in zip(dim_route.RouteKey, dim_route.OriginCityKey, dim_route.DestCityKey)}
    loaded["RouteKey"] = [route_key.get((o, d), -1) for o, d in zip(loaded.OriginCityKey, loaded.DestCityKey)]
    mode_key = dict(zip(dim_mode.ModeName, dim_mode.ModeKey))
    loaded["ModeKey"] = loaded.Mode.map(mode_key)
    loaded["DateKey"] = loaded.Date_parsed.map(lambda d: int(d.strftime("%Y%m%d")))
    loaded["CustomerKey"] = loaded.CustomerKey.astype(int)
    assert set(loaded.DateKey) <= set(dim_date.DateKey), "fact date missing from DimDate"

    fact = pd.DataFrame({
        "ShipmentID": loaded.ShipmentID_clean, "DateKey": loaded.DateKey,
        "OriginCityKey": loaded.OriginCityKey, "DestCityKey": loaded.DestCityKey,
        "RouteKey": loaded.RouteKey, "ModeKey": loaded.ModeKey,
        "StatusKey": loaded.StatusKey, "CustomerKey": loaded.CustomerKey,
        "ShipmentCount": 1,
        "WeightKG": loaded.WeightKG_clean.round(2),
        "FreightCostPKR": loaded.Cost_num,
    }).sort_values(["DateKey", "ShipmentID"]).reset_index(drop=True)
    # whole kilograms / rupees where the data is whole, so the CSV does not carry .0
    for c in ("WeightKG", "FreightCostPKR"):
        if (fact[c] % 1 == 0).all():
            fact[c] = fact[c].astype(int)

    res = dict(staging=staging, scored=s, fact=fact, reject_log=reject_log, dedup_log=dedup_log,
               dim_customer=dim_customer, dim_date=dim_date, dim_city=dim_city, profile=prof,
               credit_notes=credit_notes, registry=registry, loadable=loadable,
               stale_date=stale_date, alias_map=alias_map, status_map=status_map,
               cust_id_to_key=cust_id_to_key, dim_route=dim_route)

    res["ladder"] = ladder(res)
    checks = ten_checks(res)
    res["checks"] = checks
    if verbose:
        print_report(res)
    if write:
        fact.to_csv(OUT / "FactShipment_March.csv", index=False)
        reject_log.to_csv(OUT / "RejectLog.csv", index=False)
        dim_customer.to_csv(OUT / "DimCustomer.csv", index=False)
        dim_date.to_csv(OUT / "DimDate.csv", index=False)
        dedup_log.to_csv(OUT / "DedupLog.csv", index=False)
        pd.DataFrame(res["ladder"]).to_csv(OUT / "Audit_Reconciliation.csv", index=False)
        if verbose:
            print(f"\n[write] files written to {OUT}")
    return res


# ----------------------------------------------------------------------------
# 6. PROVE -- the ladder and the ten checks
# ----------------------------------------------------------------------------
def _sum_numeric_like_excel(series):
    """SUM over a raw column the way a spreadsheet does it: text is silently skipped."""
    # same strict rule as the pipeline: '1.2e4' is text in a staging layer, so it is skipped too.
    # (the road TOTAL footer, 4,487,200, only reconciles if it is skipped)
    tot = 0.0
    for v in series:
        v = str(v).strip()
        if PLAIN_NUMBER.match(v):
            tot += float(v)
    return tot


def ladder(res):
    st = res["staging"]
    steps = []
    for label, mode in (("marine_march.csv, as extracted", "Marine"),
                        ("rail_march.xlsx, as extracted", "Rail"),
                        ("road_march.csv, as extracted", "Road")):
        d = st[st.Mode == mode]
        steps.append(dict(Stage=label, Rows=len(d),
                          SumWeight=_sum_numeric_like_excel(d.WeightKG),
                          SumCost=_sum_numeric_like_excel(d.FreightCostPKR)))
    steps.append(dict(Stage="staging, all three appended", Rows=len(st), SumWeight=None, SumCost=None))
    steps.append(dict(Stage="rejected", Rows=len(res["reject_log"]), SumWeight=None, SumCost=None))
    steps.append(dict(Stage="removed as duplicate", Rows=len(res["dedup_log"]), SumWeight=None, SumCost=None))
    f = res["fact"]
    steps.append(dict(Stage="loaded into FactShipment_March", Rows=len(f),
                      SumWeight=float(f.WeightKG.sum()), SumCost=float(f.FreightCostPKR.sum())))
    return steps


def ten_checks(res):
    f, dc, dd = res["fact"], res["dim_customer"], res["dim_date"]
    return [
        ("Rows extracted into staging", len(res["staging"]), 1284),
        ("Rows in RejectLog", len(res["reject_log"]), 24),
        ("Rows removed as duplicates", len(res["dedup_log"]), 60),
        ("Rows in FactShipment_March", len(f), 1200),
        ("SUM(WeightKG)", float(f.WeightKG.sum()), 17542050),
        ("SUM(FreightCostPKR)", float(f.FreightCostPKR.sum()), 147037000),
        ("Rows on Unknown city member (-1)", int((f.OriginCityKey == -1).sum()), 14),
        ("Rows on Unknown status member (-1)", int((f.StatusKey == -1).sum()), 7),
        ("Rows in DimCustomer, excluding Unknown", int((dc.CustomerKey != -1).sum()), 40),
        ("Rows in DimDate", len(dd), 90),
    ]


def print_report(res):
    print("\n=== THE LADDER ===")
    for s in res["ladder"]:
        w = "" if s["SumWeight"] is None else f"{s['SumWeight']:>16,.2f} kg"
        c = "" if s["SumCost"] is None else f"{s['SumCost']:>16,.0f} PKR"
        print(f"{s['Stage']:<36}{s['Rows']:>6,} {w} {c}")
    st, ld, rj, dp = (len(res["staging"]), len(res["fact"]),
                      len(res["reject_log"]), len(res["dedup_log"]))
    print(f"\nidentity: staging - loaded - rejected - removed = {st} - {ld} - {rj} - {dp} = {st - ld - rj - dp}")
    assert st - ld - rj - dp == 0, "rows left the pipeline unaccounted for"

    print("\n=== THE TEN CHECKS (T7) ===")
    for i, (name, got, exp) in enumerate(res["checks"], 1):
        ok = got == exp
        print(f"{i:>2}. {name:<42}{got:>16,.2f} (expected {exp:,})  {'pass' if ok else 'FIX'}")
        assert ok, f"check {i} failed: {name} = {got}, expected {exp}"
    print("\nall ten checks pass")

    f = res["fact"]
    cn = res["credit_notes"]
    print(f"credit notes loaded as negatives: {len(cn)}  ({cn.ShipmentID_clean.tolist()})")
    print(f"avg cost per kg (sum/sum): PKR {f.FreightCostPKR.sum() / f.WeightKG.sum():.2f}")


if __name__ == "__main__":
    run()
