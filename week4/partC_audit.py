"""Part C - T1 hop counts and T3 storage arithmetic, both computed rather than typed.

T1: a join = one dimension reached beyond FactShipment. In the snowflake, reading Province adds 1 (DimProvince),
    reading Country adds 2 (DimProvince, DimCountry).
T3: 2 bytes per character, 4 bytes per integer key; province and region information only. Nothing is rounded.
Writes ./outputs/t1_hops.csv, ./outputs/t3_storage.csv, ./outputs/t3_context.csv
"""
from fractions import Fraction
import pandas as pd
from common import *

# ---------------- T1 ----------------
# (question, dimensions touched, extra snowflake hops for province/country reads)
Q = [
    ("Total weight by month",                  ["DimDate"],                             0),
    ("Total weight by origin city",            ["DimCity"],                             0),
    ("Total weight by province",               ["DimCity"],                             1),
    ("Total weight by country",                ["DimCity"],                             2),
    ("Total cost by province, by month",       ["DimCity", "DimDate"],                  1),
    ("Total weight by mode and status",        ["DimMode", "DimStatus"],                0),
    ("Cost per kg by corridor",                ["DimRoute"],                            0),
    ("Weight by destination province, by mode", ["DimCity", "DimMode"],                 1),
]
t1 = pd.DataFrame([{"Q": i + 1, "Question": q, "Dims": ", ".join(d), "StarJoins": len(d),
                    "SnowJoins": len(d) + extra} for i, (q, d, extra) in enumerate(Q)])
t1["Changed"] = t1.StarJoins != t1.SnowJoins
assert t1.StarJoins.sum() == 11 and t1.SnowJoins.sum() == 16 and t1.Changed.sum() == 4
t1.to_csv(OUTPUT_DIR / "t1_hops.csv", index=False)
print(t1.to_string(index=False), "\nextra joins:", t1.SnowJoins.sum() - t1.StarJoins.sum())

# ---------------- T3 ----------------
city = pd.read_csv(STAR_DIR / "DimCity.csv")               # 15 rows incl. Unknown
prov_n = pd.read_csv(SNOW_DIR / "DimProvince.csv")         # 6 rows incl. Unknown
CHAR, KEY = 2, 4

raw15_chars = int((city.Province.str.len() + city.Region.str.len()).sum())     # chars written out on 15 rows
dict_prov = city.Province.drop_duplicates()                                    # 6 strings incl. Unknown
dict_reg = city.Region.drop_duplicates()                                       # 5 strings incl. Unknown
dict_chars = int(dict_prov.str.len().sum() + dict_reg.str.len().sum())
n_prov_rows = len(prov_n)                                                      # DimProvince rows incl. Unknown
dict_bytes = dict_chars * CHAR
dimprov_overhead = n_prov_rows * (2 * KEY + 2 * KEY)    # 2 pointers (name, region) + ProvinceKey + CountryKey per row
print(f"\nraw chars on 15 rows: {raw15_chars}; dictionary chars: {dict_chars} "
      f"({len(dict_prov)} province strings, {len(dict_reg)} region strings); DimProvince rows: {n_prov_rows}; "
      f"DimProvince key+pointer bytes: {dimprov_overhead}")

def models(n):
    raw = Fraction(raw15_chars * CHAR * n, 15)          # per-row average of the 15 real rows, scaled
    enc = dict_bytes + 2 * KEY * n
    snow = KEY * n + dict_bytes + dimprov_overhead
    return raw, enc, snow

rows = []
for n in (15, 1_000, 100_000, 5_000_000, 50_000_000):
    raw, enc, snow = models(n)
    rows.append({"DimCityRows": n, "FlatRaw": float(raw), "FlatEncoded": enc, "Snowflaked": snow, "Saving": enc - snow})
t3 = pd.DataFrame(rows)
assert t3.Saving[0] < 0 and (t3.Saving[1:] > 0).all()
assert all(t3.Saving == [4 * n - dimprov_overhead for n in t3.DimCityRows])      # saving = 4 bytes/row - DimProvince overhead
t3.to_csv(OUTPUT_DIR / "t3_storage.csv", index=False)
print(t3.to_string(index=False))

ctx = []
for n in (15, 50_000_000):
    saving = 4 * n - dimprov_overhead
    fact_bytes = n * 100 * 40
    ctx.append({"DimCityRows": n, "SavingBytes": saving, "FactBytes": fact_bytes, "SavingPctOfFact": 100 * saving / fact_bytes})
pd.DataFrame(ctx).to_csv(OUTPUT_DIR / "t3_context.csv", index=False)
print(pd.DataFrame(ctx).to_string(index=False))
print("break-even rows: saving > 0 when 4n >", dimprov_overhead, "-> n >", dimprov_overhead // 4)
