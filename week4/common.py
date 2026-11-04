"""Shared paths, lookups and the relationship register for the PakFreight W4 lab.

Run every script from the project root (the folder that contains ./data).
"""
from pathlib import Path
import sys

DATA_DIR = Path("./data")
STAR_DIR = DATA_DIR / "star"
SNOW_DIR = DATA_DIR / "snowflake"
OUTPUT_DIR = Path("./outputs")

for _d in (DATA_DIR, STAR_DIR, SNOW_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SHIPMENTS_CSV = DATA_DIR / "Shipments_Unified.csv"
WORKBOOK_IN = DATA_DIR / "PakFreight_W4_SchemaLab_STUDENT.xlsx"
WORKBOOK_OUT = OUTPUT_DIR / "W4_Schema_TEAM.xlsx"   # rename to W4_Schema_<team number>.xlsx before upload

for _f in (SHIPMENTS_CSV, WORKBOOK_IN):
    if not _f.exists():
        sys.exit(f"Missing input file: {_f}. Copy it into ./data and rerun.")

EXPECTED_ROWS = 34
EXPECTED_KG = 578_650
EXPECTED_PKR = 4_808_000

# The six relationships: (one side, many side, active). Single cross-filter, many-to-one, for all six.
REGISTER = [
    ("DimDate[DateKey]",     "FactShipment[DateKey]",       True),
    ("DimCity[CityKey]",     "FactShipment[OriginCityKey]", True),
    ("DimCity[CityKey]",     "FactShipment[DestCityKey]",   False),
    ("DimRoute[RouteKey]",   "FactShipment[RouteKey]",      True),
    ("DimMode[ModeKey]",     "FactShipment[ModeKey]",       True),
    ("DimStatus[StatusKey]", "FactShipment[StatusKey]",     True),
]
