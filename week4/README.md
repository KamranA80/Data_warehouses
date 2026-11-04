# PakFreight W4: dimensional modelling (T1-T7)

Run from this folder (paths are relative: `./data`, `./outputs`; missing folders are created on start).

```
pip install pandas openpyxl
python partA_build_star.py        # data/star/*.csv  (6 tables, 34 fact rows, 578,650 kg, PKR 4,808,000)
python partB_snowflake.py         # data/snowflake/*.csv  + outputs/region_conflicts.csv
python partC_audit.py             # outputs/t1_hops.csv, t3_storage.csv, t3_context.csv
python partD_reconcile.py         # outputs/t7_reconcile.csv (13 checks, asserts all pass)
python partE_fill_workbook.py     # outputs/W4_Schema_TEAM.xlsx
```

`common.py` holds the paths and the six-relationship register that T4 and T7 both read.

## Things to know before submitting
- `data/star` and `data/snowflake` were not in the upload, so partA/partB rebuild them from `Shipments_Unified.csv` and the DimCity block in the workbook.
  Use your repo's own `star/*.csv` for the Power BI lab if the keys differ. `DistanceBand` in DimRoute uses my approximate road distances.
- Region is not a function of Province here: Punjab (North, Central), Sindh (South, Central), Balochistan (South, West). DimProvince keeps the region held by
  most of the province's cities (ties: lowest CityKey). That changes the region of 4 of 14 cities (`outputs/region_conflicts.csv`). T2 part D uses this as an argument.
- T3 model: dictionary of 88 characters (6 province strings, 5 region strings, both incl. Unknown) = 176 bytes; DimProvince = 6 rows x (2 pointers + 2 keys) = 96 bytes.
  Saving = 4 x rows - 96, so the snowflake is bigger below 25 rows. Flat raw for rows above 15 scales the 15-row average (211 chars) without rounding.
- T7 values were computed with pandas from the star CSVs, not read from Power BI. Build the model and confirm them on screen before you submit.
- Rename `W4_Schema_TEAM.xlsx` to `W4_Schema_<team number>.xlsx`. The `.pbix` is not included; see `PowerBI_lab_notes.md`.
