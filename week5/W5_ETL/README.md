# PakFreight W5 - ETL lab (Python track)

Kamran Khan Hussain · BSDS030 · BSDS (Data Science) 7A · Data Warehousing & Business Intelligence

```
W5_BSDS030.py                      the pipeline (named STEPS, 8 checks, -1 count, refresh test)
W5_BSDS030_traps.py                companion: breaks each ordering on purpose to measure the wrong totals
fill_workbook.py                   fills the cream cells of the workbook (T1-T7)
make_refresh_png.py                before / after picture of the refresh test
PakFreight_W5_ETLLab_STUDENT.xlsx  the given workbook, untouched
alias_lookup.csv                   given, used only to cross-check my own alias map
TASKS.md, PowerQuery_Lab_Guide.md  the brief + guide, with my submission notes appended at the end
dims/                              the five Week 4 dimensions (imported, not rebuilt)
source/            night one       marine, rail, road - unmodified
source/night2/                     the refresh-test files - unmodified
outputs/                           workbook answers, FactShipment, logs, run report, picture
```

```
pip install pandas openpyxl pillow
python W5_BSDS030.py          # night one + refresh test; writes outputs/
python W5_BSDS030_traps.py    # the wrong-order numbers
```

Both scripts change into their own folder first, so the relative `Path("source")` / `Path("dims")` resolve wherever
they are launched from.
