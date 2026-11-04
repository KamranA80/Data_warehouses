# Week 6 - Query Optimization & Data Quality

Kamran Khan Hussain | BSDS030 | BSDS (Data Science) 7A | Data Warehousing & BI

Dual-route load for the PakFreight March files, built in pandas.

## Run it
    pip install pandas openpyxl
    python W6_BSDS030.py

It reads `data/` and writes `output/`. It prints the reconciliation ladder
(1,284 = 1,200 + 24 + 60) and asserts all ten T7 checks.

## What is here
| Path | What it is |
|---|---|
| `W6_Quality_BSDS030.xlsx` | Workbook, T1 to T7 (T7 reads 10 / 10) |
| `W6_BSDS030.py` | The pipeline |
| `W6_OnePage_BSDS030.md` | One-page write-up |
| `W6_Pipeline_Steps_BSDS030.md` | Every transform step, named |
| `output/FactShipment_March.csv` | 1,200 rows |
| `output/RejectLog.csv` | 24 rows |
| `output/DimCustomer.csv`, `output/DimDate.csv` | 40 + Unknown, 90 rows |
| `output/DedupLog.csv`, `output/Audit_Reconciliation.csv` | The 60 removed rows, and the ladder |
| `data/` | Course input files, unchanged |
