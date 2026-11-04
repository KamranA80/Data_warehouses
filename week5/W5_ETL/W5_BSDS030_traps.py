"""
PakFreight Week 5 - the forbidden orderings, measured (companion to W5_BSDS030.py)

Student : Kamran Khan Hussain | BSDS030 | BSDS 7A

Every wrong-order number I quote in the workbook (T3, T4 part B, T5) is produced here
by actually doing the wrong thing on purpose, so none of them is copied from the slides.
This file is NOT the pipeline; it imports the real one and then breaks it.

    python W5_BSDS030_traps.py        # writes outputs/forbidden_orderings.txt
"""
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))      # find W5_BSDS030.py next to this file
import W5_BSDS030 as etl
from W5_BSDS030 import CONTRACT, FILES, SOURCE, build_steps, run_pipeline, run_steps

LINES = []


def say(msg=""):
    print(msg)
    LINES.append(msg)


def forbidden_orderings(night1, night2):
    """The four numbers in T3/T4/T5, produced from the data instead of quoted."""
    say("The forbidden orderings, reproduced (not quoted)")

    # 1. append before rename -> 20 columns, no error
    promoted = []
    for n in ("marine", "rail", "road"):
        _, fr = run_steps(build_steps(n, night1["src"] / FILES[n]), stop_after="PromotedHeaders")
        promoted.append(fr["PromotedHeaders"])
    wide = pd.concat(promoted, ignore_index=True)
    say(f"  1. append before rename      -> {wide.shape[1]} columns, rows {len(wide)}, no error raised")
    assert wide.shape[1] == 20

    # 3. tons never converted -> 283,695.25
    fact = night1["fact"]
    tons = night1["frames"]["rail"]["TypedNumbers"].WeightTons.sum()
    wrong = fact[fact.ModeKey != 2].WeightKG.sum() + tons
    say(f"  3. tons left unconverted     -> SUM(WeightKG) = {wrong:,.2f}  (short by {fact.WeightKG.sum() - wrong:,.2f})")
    assert abs(wrong - 283_695.25) < 1e-6

    # 2. dedup before trim, on night two. whole-row compare on the untrimmed road rows
    road_raw = night2["frames"]["road"]["RemovedTotalRow"]
    whole_row = road_raw.drop_duplicates()
    leak = whole_row[whole_row.duplicated(subset=["ShipmentID"], keep="first")]
    n_rows = len(night2["fact"]) + len(leak)
    n_kg = night2["fact"].WeightKG.sum() + pd.to_numeric(leak.WeightKG).sum()
    say(f"  2. dedup before trim (night2) -> {n_rows} rows / {int(n_kg):,} kg instead of "
        f"{len(night2['fact'])} / {int(night2['fact'].WeightKG.sum()):,}")
    assert (n_rows, int(n_kg)) == (36, 591_550)
    # and on night one the two RD-505 rows are byte-identical, so the bad order still gives 34
    r1 = night1["frames"]["road"]["RemovedTotalRow"]
    say(f"     same wrong order on night1 -> road keeps {len(r1.drop_duplicates())} of {len(r1)} rows "
        f"(RD-505 is byte-identical), so the file can never tell you")

    # 4. the locale: marine text dates read month-first
    s = night1["frames"]["marine"]["UppercasedIDs"].ShipDate
    us = pd.to_datetime(s, format="%m/%d/%Y", errors="coerce")
    gb = pd.to_datetime(s, format="%d/%m/%Y")
    wrong_month = int(((us.dt.month != gb.dt.month) & us.notna()).sum())
    lucky = int(((us == gb) & us.notna()).sum())
    say(f"  4. en-US read of marine dates -> wrong month {wrong_month}, right by luck {lucky}, "
        f"error {int(us.isna().sum())}, distinct months {us.dt.month.nunique()}")
    assert (wrong_month, lucky, int(us.isna().sum()), us.dt.month.nunique()) == (10, 1, 1, 11)

    # the rest of the T4 part B gaps, each read from its own missing step
    base_rows, base_kg = len(fact), int(fact.WeightKG.sum())
    no_dedup = night1["frames"]["FactStaging"]["AppendedQueries"]
    say(f"  5. no dedup at all           -> {len(no_dedup)} rows, {int(no_dedup.WeightKG.sum()):,} kg "
        f"(+{int(no_dedup.WeightKG.sum()) - base_kg:,})")
    assert (len(no_dedup), int(no_dedup.WeightKG.sum())) == (35, 584_750)

    with_total = night1["frames"]["road"]["RemovedBlankRows"]
    total_kg = int(pd.to_numeric(with_total[with_total.ShipmentID.str.upper() == "TOTAL"].WeightKG).sum())
    say(f"  6. TOTAL footer left in      -> {base_rows + 1} rows, {base_kg + total_kg:,} kg (+{total_kg:,})")
    assert base_kg + total_kg == 661_650

    with_blank = night1["frames"]["road"]["RenamedToContract"]
    blank = with_blank[with_blank.ShipmentID.str.strip() == ""]
    blank_kg = int(pd.to_numeric(blank.WeightKG, errors="coerce").fillna(0).sum())
    say(f"  7. blank road row left in    -> {base_rows + len(blank)} rows, {base_kg + blank_kg:,} kg "
        f"(both totals still exact, COUNTROWS is the only thing that moves)")
    assert (base_rows + len(blank), blank_kg) == (35, 0)

    # 8. inner join instead of left outer, on night two
    stage = night2["frames"]["FactStaging"]["DedupedOnShipmentID"]
    al = night2["alias"]
    inner = (stage.merge(al.rename(columns={"RawSpelling": "OriginRaw", "CityKey": "OriginCityKey"}), on="OriginRaw", how="inner")
                  .merge(al.rename(columns={"RawSpelling": "DestRaw", "CityKey": "DestCityKey"}), on="DestRaw", how="inner"))
    say(f"  8. inner join on night2      -> {len(inner)} rows, {int(inner.WeightKG.sum()):,} kg, "
        f"PKR {int(inner.FreightCostPKR.sum()):,} (night one's totals to the unit, so it even looks reconciled)")
    assert (len(inner), int(inner.WeightKG.sum()), int(inner.FreightCostPKR.sum())) == (34, 578_650, 4_808_000)


def main():
    os.chdir(Path(__file__).resolve().parent)
    etl.DIMS = Path("dims")
    n1 = run_pipeline(SOURCE, "night1")
    n2 = run_pipeline(SOURCE / "night2", "night2")
    forbidden_orderings(n1, n2)
    Path("outputs").mkdir(exist_ok=True)
    Path("outputs/forbidden_orderings.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
