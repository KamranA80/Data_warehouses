# W6 pipeline: every step named

Kamran Khan Hussain · BSDS030 · tool: pandas (`W6_BSDS030.py`). Row counts are from the run.

| # | Step name | What it does | Rows in → out |
|---|---|---|---|
| E1 | `Land_Marine` | read `marine_march.csv` as text, rename to the 8-column contract, tag file + line | 261 → 261 |
| E2 | `Land_Rail` | skip 2 title rows, header on row 3, tag Excel row; dates kept as ISO text | 315 → 315 |
| E3 | `Land_Road` | read as text, keep blank line so line numbers stay true | 710 lines |
| E4 | `Skip_StructuralLines` | drop the blank line and the TOTAL footer after checking the footer against the column (4,487,200 kg / PKR 32,259,500 tie exactly) | 710 → 708 |
| E5 | `Append_Staging` | append the three files, nothing corrected | 1,284 |
| P1 | `Profile_Raw` | blanks, distinct values, rule failures per column before any change (105 failures) | 1,284 |
| T1 | `Trim_Text` | trim every text field | 1,284 |
| T2 | `Conform_ShipmentID` | upper case, restore `RL-` on rail IDs | 1,284 |
| T3 | `Parse_Date` | `dd/MM/yyyy` for marine, ISO for road and rail; must be a real March 2026 date | 6 fail |
| T4 | `Type_Weight` | plain numbers only (`1.2e4` and text are not numbers); rail × 1,000 per row | 14 fail (9 text, 5 negative) |
| T5 | `Type_Cost` | numeric; a negative is a credit note and stays | 0 fail, 3 credit notes |
| R1 | `Route_Reject` | blank ID, bad date, text weight, negative weight → `RejectLog` with file, line, reason, raw record | 1,284 → 24 rejected, 1,260 loadable |
| D1 | `Remove_Duplicates` | on the cleaned `ShipmentID`, keep the first copy, log the rest in `DedupLog` (48 identical + 12 trailing space) | 1,260 → 1,200, 60 removed |
| C1 | `Conform_City` | `alias_lookup` for origin and destination; no match → `-1` | 14 rows on -1 |
| C2 | `Conform_Status` | trim + case against `DimStatus`; no match → `-1` | 7 rows on -1 |
| C3 | `Key_Route`, `Key_Mode`, `Key_Date` | route from `DimRoute` (`-1` if the city is unknown), mode from the file, `DateKey` yyyymmdd | 1,200 |
| C4 | `Conform_Customer` | normalise names, merge 6 duplicate businesses, keep second IDs as aliases | 46 IDs → 40 + Unknown |
| B1 | `Build_DimDate` | rebuilt for Q1 2026, gapless, same columns and conventions as Week 4 (February matches the old file exactly) | 90 |
| B2 | `Build_FactShipment_March` | 8 keys + `ShipmentCount`, `WeightKG`, `FreightCostPKR`; no descriptive text | 1,200 |
| V1 | `Prove` | print the ladder, assert 1,284 = 1,200 + 24 + 60, assert all ten checks | all pass |

Run it from the folder holding the data: `python W6_BSDS030.py`. It writes `output/`.
