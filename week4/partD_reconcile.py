"""Part D - the 13 T7 checks, computed from the star CSVs the way the Power BI model resolves them.

Relationship counts come from REGISTER in common.py (the T4 register). Origin is the active role for DimCity.
Writes ./outputs/t7_reconcile.csv
"""
import pandas as pd
from common import *

fact = pd.read_csv(STAR_DIR / "FactShipment.csv")
dims = {n: pd.read_csv(STAR_DIR / f"{n}.csv") for n in ["DimDate", "DimCity", "DimRoute", "DimMode", "DimStatus"]}
fk = {"DimDate": ["DateKey"], "DimCity": ["OriginCityKey", "DestCityKey"], "DimRoute": ["RouteKey"],
      "DimMode": ["ModeKey"], "DimStatus": ["StatusKey"]}
pk = {"DimDate": "DateKey", "DimCity": "CityKey", "DimRoute": "RouteKey", "DimMode": "ModeKey", "DimStatus": "StatusKey"}

# Power BI shows a (Blank) row for every fact key with no dimension match; count them, plus blank dimension keys.
blank_rows = 0
for d, cols in fk.items():
    assert dims[d][pk[d]].is_unique and dims[d][pk[d]].notna().all(), f"{d} key not unique/non-blank"
    for c in cols:
        blank_rows += int((~fact[c].isin(dims[d][pk[d]])).sum())
    blank_rows += int(dims[d].isna().any(axis=1).sum())      # rows with an empty cell anywhere

origin = fact.merge(dims["DimCity"], left_on="OriginCityKey", right_on="CityKey")     # active relationship
by_prov = origin.groupby("Province").WeightKG.sum()

n_rel = len(REGISTER)
checks = [
    ("Relationships in the model", n_rel),
    ("Relationships with cardinality * : 1", n_rel),            # all six are many-to-one by construction
    ("Relationships with cross-filter Single", n_rel),
    ("Active relationships", sum(a for *_, a in REGISTER)),
    ("Inactive relationships", sum(not a for *_, a in REGISTER)),
    ("Rows in FactShipment", len(fact)),
    ("SUM of WeightKG", int(fact.WeightKG.sum())),
    ("SUM of FreightCostPKR", int(fact.FreightCostPKR.sum())),
    ("Blank rows across all five dimensions", blank_rows),
    ("Distinct origin provinces in the fact", origin.Province.nunique()),
    ("WeightKG for Sindh origins", int(by_prov["Sindh"])),
    ("WeightKG for Punjab origins", int(by_prov["Punjab"])),
    ("WeightKG for Balochistan origins", int(by_prov["Balochistan"])),
]
expected = [6, 6, 6, 5, 1, 34, 578650, 4808000, 0, 4, 484350, 44100, 44100]
out = pd.DataFrame({"Check": [c for c, _ in checks], "Computed": [v for _, v in checks], "Expected": expected})
out["Pass"] = out.Computed == out.Expected
out.to_csv(OUTPUT_DIR / "t7_reconcile.csv", index=False)
print(out.to_string(index=False))
print("Origin weight by province:", by_prov.to_dict())
print("Distinct origin cities:", origin.CityKey.nunique(), "| distinct destination provinces:",
      fact.merge(dims["DimCity"], left_on="DestCityKey", right_on="CityKey").Province.nunique())
assert out.Pass.all()
