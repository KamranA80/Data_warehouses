"""Part B - split DimCity into DimCity -> DimProvince -> DimCountry.

Region is NOT a function of Province in this data (see region_conflicts below), so DimProvince.RegionName
needs a rule. Rule used: the region held by most of the province's cities; ties go to the lowest CityKey.
Writes ./data/snowflake/{DimProvince,DimCountry,DimCity_normalized}.csv and ./outputs/region_conflicts.csv
"""
import pandas as pd
from common import *

city = pd.read_csv(STAR_DIR / "DimCity.csv")
real = city[city.CityKey > 0]

# --- Region vs Province: which provinces carry more than one region? ---------------------------
reg_per_prov = real.groupby("Province").Region.nunique()
conflicts = real[real.Province.isin(reg_per_prov[reg_per_prov > 1].index)].sort_values(["Province", "CityKey"])
print("Provinces with >1 region:", reg_per_prov[reg_per_prov > 1].to_dict())

def pick_region(g):
    counts = g.Region.value_counts()
    top = counts[counts == counts.max()].index
    return g[g.Region.isin(top)].sort_values("CityKey").Region.iloc[0]

# --- DimProvince: keys minted in order of first appearance in DimCity --------------------------
order = list(dict.fromkeys(real.Province))
prov = pd.DataFrame({"ProvinceKey": range(1, len(order) + 1), "ProvinceName": order})
prov["RegionName"] = prov.ProvinceName.map(real.groupby("Province").apply(pick_region, include_groups=False))
prov["CountryKey"] = 1
prov.loc[len(prov)] = [-1, "Unknown", "Unknown", -1]

# --- DimCountry --------------------------------------------------------------------------------
country = pd.DataFrame({"CountryKey": [1, -1], "CountryName": ["Pakistan", "Unknown"], "RegionGroup": ["South Asia", "Unknown"]})

# --- DimCity, normalized -----------------------------------------------------------------------
pkey = dict(zip(prov.ProvinceName, prov.ProvinceKey))
city_n = city.assign(ProvinceKey=city.Province.map(pkey))[["CityKey", "CityName", "ProvinceKey", "IsPortCity", "FacilityType"]]
assert city_n.ProvinceKey.notna().all() and len(city_n) == 15

# --- Region changes caused by moving Region up to DimProvince ----------------------------------
chk = city.merge(prov[["ProvinceName", "RegionName"]], left_on="Province", right_on="ProvinceName")
changed = chk[(chk.Region != chk.RegionName)][["CityKey", "CityName", "Province", "Region", "RegionName"]]
changed.columns = ["CityKey", "CityName", "Province", "RegionInDimCity", "RegionInDimProvince"]

prov.to_csv(SNOW_DIR / "DimProvince.csv", index=False)
country.to_csv(SNOW_DIR / "DimCountry.csv", index=False)
city_n.to_csv(SNOW_DIR / "DimCity_normalized.csv", index=False)
changed.to_csv(OUTPUT_DIR / "region_conflicts.csv", index=False)
print(prov.to_string(index=False)); print(country.to_string(index=False))
print(f"DimProvince {len(prov)} rows (5 + Unknown), DimCountry {len(country)} rows (1 + Unknown)")
print(f"Cities whose Region changes when Region moves to DimProvince: {len(changed)} of {len(real)}")
print(changed.to_string(index=False))
