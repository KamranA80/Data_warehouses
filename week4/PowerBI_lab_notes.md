# PakFreight W4 lab notes (Power BI)

The `.pbix` has to be built in Power BI Desktop (or Power BI Service on macOS/Linux; say which in the submission). These notes
are the build order and the DAX for the model registered in T4. `PowerBI_Lab_Guide.md` was not in the upload, so check the measure
list against it.

## Build order
1. `File > Options > Current File > Data Load`: turn off relationship autodetect and type detection that rewrites keys.
2. Import the six files from `data/star/`. Every key column is Whole Number. Dimension keys must be unique and non-blank
   (`partD_reconcile.py` asserts this on the CSVs).
3. Create the six relationships through Manage relationships, not by dragging. Many to one, Single, all six:

| One side | Many side | Active |
|---|---|---|
| DimDate[DateKey] | FactShipment[DateKey] | Yes |
| DimCity[CityKey] | FactShipment[OriginCityKey] | Yes |
| DimCity[CityKey] | FactShipment[DestCityKey] | No |
| DimRoute[RouteKey] | FactShipment[RouteKey] | Yes |
| DimMode[ModeKey] | FactShipment[ModeKey] | Yes |
| DimStatus[StatusKey] | FactShipment[StatusKey] | Yes |

4. Mark DimDate as a date table on `FullDate`. Sort `MonthName` by `MonthNumber`.
5. Hide every key column from Report view. Leave `ShipmentID` visible.

## Measures
```dax
Total Weight KG = SUM ( FactShipment[WeightKG] )
Total Freight PKR = SUM ( FactShipment[FreightCostPKR] )
Cost per KG = DIVIDE ( [Total Freight PKR], [Total Weight KG] )
Shipments = COUNTROWS ( FactShipment )
Weight by Destination KG =
    CALCULATE (
        [Total Weight KG],
        USERELATIONSHIP ( FactShipment[DestCityKey], DimCity[CityKey] )
    )
```

## Matrix and slicer
Rows: `DimCity[Province]`, then `DimDate[MonthName]`. Values: `[Total Weight KG]`. Slicer: `DimMode[ModeName]`.
Province is a column on DimCity, so the matrix needs one relationship and no extra join.

## What to read off for T7
Card visuals for rows, weight and cost; `DISTINCTCOUNT ( DimCity[Province] )` for check 10 (reads 4 on the origin path);
the matrix for Sindh 484,350, Punjab 44,100, Balochistan 44,100. Workbook values were computed in `partD_reconcile.py`
from the same CSVs; the model has to reproduce them on screen.

## T4 part B text for the report page or model description
One DimCity with two relationships to FactShipment. OriginCityKey is active and DestCityKey is inactive. Destination questions use
`Weight by Destination KG`, which switches the path with USERELATIONSHIP. This keeps one 15-row dimension to maintain and gives
6 relationships, 5 active, 1 inactive.
