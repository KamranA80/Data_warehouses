# Week 6 — one page

**Kamran Khan Hussain · BSDS030 · BSDS 7A · Data Warehousing & BI**

1,284 rows came in. 1,200 are in `FactShipment_March`, 24 are in `RejectLog`, 60 were removed as duplicates, and 1,284 − 1,200 − 24 − 60 is exactly zero. The fact table carries 17,542,050 kg and PKR 147,037,000 (PKR 8.38 per kg, which is a sensible number next to February's 8.31).

## What I rejected, and why no transform gets it back

I rejected 24 rows, and each of them is missing something the fact table cannot do without.

- **9 text weights** (`approx 7000`, `n/a`, `TBC`, `--`, `see note`, `unknown` and `1.2e4`). There is no weight in them to recover. `1.2e4` is the sneaky one: it casts cleanly to 12,000 kg, but that is a road truck whose class tops out around 8 tonnes, so I did not trust it.
- **6 dates that do not parse** (`00/00/0000`, `32/03/2026`, `31/02/2026`, `2026/13/04`, `Mar-2026`). With no date there is no `DateKey`, and `DimDate` has no Unknown member to hide it behind.
- **5 negative weights.** A truck cannot carry minus 7,200 kg.
- **4 blank ShipmentIDs.** No ID means no grain: I could not dedupe the row or ever tell it apart from a replay.

Each reject goes into `RejectLog` with the file, the line, the failed column, the reason and the whole raw record, so someone can fix the source and push it back through.

The three negative *costs* are **not** rejects. They are credit notes (−283,000 PKR in total) and they load as negatives. Rejecting them is how you end up with 27.

## What I routed to Unknown, and why that is a different decision

21 rows load against the `-1` member. Their weight, cost, date and ID are all fine, so the shipment really happened; only a descriptive lookup failed. A reject says "this row's facts cannot be trusted". A route says "the facts are good, I just cannot label them yet". If I had rejected these 21, real freight would have disappeared from March and the dashboard would still have looked green.

## The −1 counts

- **14 rows on the Unknown city** (195,150 kg, PKR 1,649,500). Six spellings are behind them: Keti Bandar Jetty (3), Kotri Junction (3), Wagah Border (2), Taftan Crossing (2), Torkham Gate (2) and Chaman Border (2).
- **7 rows on the Unknown status** (92,950 kg): RTO (2), Hold (1) and held at customs (4).

No row is in both lists. Deleting the 14 would have given 1,186 rows and 17,346,900 kg and a tidy zero, and I would have lost freight that was actually moved.

## Two things that were not in the March files

`dims/DimDate.csv` was February's 28 rows, so every March row would have failed to join while the weights still added up. I rebuilt it for Q1 2026 (90 days, gapless). And the registry's 46 customers are really **40**: six businesses are in it twice under a second ID and another spelling (CU-101 and CU-901, and so on). That is a dimension problem, so fixing it moved no weight or cost totals at all.

## The index I would build

`DateKey` first, with `CustomerKey` as a second if the dashboard needs it. `DateKey` has 31 values at about 39 rows each, every page filters on it, and the fact grows by date so new rows append at the end. I would skip `ShipmentID` (perfectly selective, never filtered) and `ModeKey` (3 values, and road alone is 660 rows).

**Cost on every load:** one extra index entry per row, so 1,200 extra writes for a March-sized load with a `DateKey` index, and 2,400 with both. Before adding either, I would check that the fact has no descriptive text, that the relationships are single-direction, and that cost per kg is a ratio of sums and not recomputed per row.
