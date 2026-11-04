"""Part A - rebuild the six star tables from Shipments_Unified.csv and the DimCity given in the workbook.

Writes ./data/star/{DimDate,DimCity,DimRoute,DimMode,DimStatus,FactShipment}.csv
"""
import pandas as pd
import openpyxl
from common import *

# ---- DimCity: read the grey 'The Model (given)' block (rows 6-20), do not retype it -------------
ws = openpyxl.load_workbook(WORKBOOK_IN, data_only=True)["The Model (given)"]
city_rows, raw_to_city = [], {}
for r in range(6, 21):
    key, name, prov, region, port, fac, raw = (ws.cell(r, c).value for c in range(1, 8))
    city_rows.append([key, name, prov, region, port, fac])
    for s in (raw or "").split("|"):
        if s.strip():
            raw_to_city[s.strip()] = key
dim_city = pd.DataFrame(city_rows, columns=["CityKey", "CityName", "Province", "Region", "IsPortCity", "FacilityType"])
assert len(dim_city) == 15 and dim_city.CityKey.is_unique

# ---- Staging ----------------------------------------------------------------------------------
s = pd.read_csv(SHIPMENTS_CSV, parse_dates=["ShipDate"])
assert len(s) == EXPECTED_ROWS
unmapped = set(s.Origin) | set(s.Destination)
unmapped -= set(raw_to_city)
assert not unmapped, f"raw strings with no city: {unmapped}"
s["OriginCityKey"] = s.Origin.map(raw_to_city)
s["DestCityKey"] = s.Destination.map(raw_to_city)
city_name = dim_city.set_index("CityKey").CityName
s["Corridor"] = s.OriginCityKey.map(city_name) + " > " + s.DestCityKey.map(city_name)

# ---- DimDate: gapless, 1-28 Feb 2026 (28 rows, no Unknown member) ------------------------------
days = pd.date_range("2026-02-01", "2026-02-28", freq="D")
dim_date = pd.DataFrame({
    "DateKey": days.strftime("%Y%m%d").astype(int),
    "FullDate": days.strftime("%Y-%m-%d"),
    "Year": days.year, "MonthNumber": days.month, "MonthName": days.strftime("%B"),
    "DayOfMonth": days.day, "DayName": days.strftime("%A"),
})
assert s.ShipDate.dt.strftime("%Y%m%d").astype(int).isin(dim_date.DateKey).all()

# ---- DimRoute: 20 corridors + Unknown. DistanceBand uses approximate road km (my estimates) -----
APPROX_KM = {
    "Faisalabad > Multan": 240, "Gwadar > Karachi": 630, "Gwadar > Quetta": 900, "Islamabad > Peshawar": 180,
    "Karachi > Faisalabad": 1100, "Karachi > Hyderabad": 160, "Karachi > Islamabad": 1400, "Karachi > Lahore": 1200,
    "Karachi > Multan": 900, "Karachi > Peshawar": 1550, "Karachi > Rawalpindi": 1400, "Karachi > Sialkot": 1250,
    "Karachi > Sukkur": 470, "Lahore > Faisalabad": 130, "Lahore > Gujranwala": 70, "Lahore > Islamabad": 380,
    "Lahore > Sialkot": 125, "Multan > Lahore": 340, "Quetta > Karachi": 690, "Rawalpindi > Abbottabad": 120,
}
band = lambda km: "Short (<300 km)" if km < 300 else ("Medium (300-800 km)" if km <= 800 else "Long (>800 km)")
corridors = list(dict.fromkeys(s.Corridor))           # order of first appearance
assert len(corridors) == 20 and set(corridors) == set(APPROX_KM)
dim_route = pd.DataFrame({"RouteKey": range(1, 21), "Corridor": corridors})
dim_route["DistanceBand"] = dim_route.Corridor.map(lambda c: band(APPROX_KM[c]))
dim_route.loc[len(dim_route)] = [-1, "Unknown", "Unknown"]
s["RouteKey"] = s.Corridor.map(dict(zip(dim_route.Corridor, dim_route.RouteKey)))

# ---- DimMode, DimStatus ------------------------------------------------------------------------
dim_mode = pd.DataFrame({"ModeKey": [1, 2, 3, -1], "ModeName": ["Marine", "Rail", "Road", "Unknown"]})
dim_status = pd.DataFrame({"StatusKey": [1, 2, 3, -1], "StatusName": ["Delivered", "In Transit", "Delayed", "Unknown"]})
s["ModeKey"] = s.SourceSystem.map(dict(zip(dim_mode.ModeName, dim_mode.ModeKey)))
s["StatusKey"] = s.Status.map(dict(zip(dim_status.StatusName, dim_status.StatusKey)))

# ---- FactShipment ------------------------------------------------------------------------------
fact = pd.DataFrame({
    "ShipmentID": s.ShipmentID, "DateKey": s.ShipDate.dt.strftime("%Y%m%d").astype(int),
    "OriginCityKey": s.OriginCityKey, "DestCityKey": s.DestCityKey, "RouteKey": s.RouteKey,
    "ModeKey": s.ModeKey, "StatusKey": s.StatusKey,
    "WeightKG": s.WeightKG, "FreightCostPKR": s.CostPKR, "ShipmentCount": 1,
})
assert fact.isna().sum().sum() == 0
assert len(fact) == EXPECTED_ROWS and fact.WeightKG.sum() == EXPECTED_KG and fact.FreightCostPKR.sum() == EXPECTED_PKR

for name, df in [("DimDate", dim_date), ("DimCity", dim_city), ("DimRoute", dim_route),
                 ("DimMode", dim_mode), ("DimStatus", dim_status), ("FactShipment", fact)]:
    df.to_csv(STAR_DIR / f"{name}.csv", index=False)
    print(f"{name:13s} {len(df):3d} rows -> {STAR_DIR / (name + '.csv')}")
print(f"FactShipment: {len(fact)} rows, {fact.WeightKG.sum():,} kg, PKR {fact.FreightCostPKR.sum():,}")
