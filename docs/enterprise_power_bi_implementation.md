# CareFlow enterprise Power BI implementation

## 1. What the current sources can support

The canonical source files are `data\clinical_events.csv` and
`data\case_metadata.csv`. They contain case IDs, timestamps, stage, hospital,
department, patient type, diagnosis, event process duration, stay duration,
readmission, satisfaction, and delayed-discharge reason. They do **not** contain
a stable person ID, age, gender, risk score, cost, or cost center. The sample
data is synthetic.

Never infer `Patient_ID` from a patient name or a case/encounter ID. A person
may have multiple encounters, and names are sensitive and non-unique. Until an
approved case-to-patient crosswalk is provided, `Patient_ID` and
`Dim_Patients` remain empty, patient-level KPIs return zero/blank as
appropriate, and visuals should be labeled as encounter-level.

## 2. Workspace structure

```text
CareFlow-Clinical-Pathway-Process-Mining/
├── careflow_clinical_pathway_process_mining.pbip
├── careflow_clinical_pathway_process_mining.Report/
├── careflow_clinical_pathway_process_mining.SemanticModel/
├── data/
│   ├── clinical_events.csv
│   ├── case_metadata.csv
│   └── enterprise_processed/      # generated; git-ignored
├── dax/
│   └── dax_measures.dax
├── powerquery/
│   └── transform_scripts.pq
├── scripts/
│   └── build_enterprise_model.py
├── tests/
│   └── test_enterprise_model.py
└── docs/
    └── enterprise_power_bi_implementation.md
```

Build and test from the VS Code PowerShell terminal:

```powershell
python scripts\build_enterprise_model.py
python -m pytest tests\test_enterprise_model.py -q
```

To supply identity/demographic enrichment, provide a CSV with one row per
`Case_ID` and columns `Patient_ID`, `Age`, `Gender`, and `Risk_Score`.
`Satisfaction_Score` is optional; when absent, the exporter averages the
case-level `patient_satisfaction_pct` values for mapped cases. Each patient
attribute must be consistent across encounters for that patient.

```powershell
python scripts\build_enterprise_model.py `
  --patient-data data\approved_case_patient_map.csv `
  --output-dir data\enterprise_processed
```

The patient mapping file must be access-controlled, approved for this use, and
excluded from source control. The exporter never emits source `patient_name`.
Absent `Cost` and `Cost_Center` values are blank; connect validated cost data
before using financial measures.

## 3. Output schema and grain

The exporter writes four CSVs. `Fact_Clinical_Events` is one row per event;
`Length_of_Stay_Hours` and `Is_Readmission` are case-level values repeated on
each event. Always aggregate those fields at `Case_ID` grain in DAX.

| Table | Columns | Grain / notes |
|---|---|---|
| `Fact_Clinical_Events` | `Case_ID`, `Patient_ID`, `Event_Name`, `Timestamp`, `Date`, `DateKey`, `Department_ID`, `Department`, `Hospital`, `Patient_Type`, `Diagnosis`, `Cost`, `Length_of_Stay_Hours`, `Is_Readmission`, `Wait_Time_Hours`, `Stage_Duration_Hours`, `Cycle_Time_Hours`, `Cycle_Time_Buckets`, `Day_Name`, `Hour_of_Day` | Event grain; outcome, stay, and cycle-time fields are repeated case attributes. Department ID joins to dimension; direct labels are retained for requested slicers and tooltips. |
| `Dim_Patients` | `Patient_ID`, `Age`, `Gender`, `Risk_Score`, `Satisfaction_Score` | One row per sourced stable person ID. Empty with headers until a case-to-person map exists. Scores use source 0–100 units. |
| `Dim_Departments` | `Department_ID`, `Department`, `Cost_Center` | One row per department. `Department_ID` is a deterministic hash of normalized department text; cost center blank until supplied. |
| `Dim_Date` | `Date`, `DateKey`, `Year`, `Quarter`, `Month`, `MonthNumber`, `Weekday`, `WeekdayNumber`, `Is_Weekend` | One row per date from minimum through maximum event date. `DateKey` is integer `YYYYMMDD`; Monday=1, Sunday=7. |

`Cycle_Time_Hours` is elapsed time from the first event start to the latest
event end (`Timestamp + Stage_Duration_Hours`) in a case. Its bucket is
right-closed: `<=6`, `>6–12`, `>12–18`, `>18–24`, `>24–30`, `>30`. For
histograms, count distinct `Case_ID`, not event rows.

`Diagnosis` remains on the event fact because the requested architecture does
not include a diagnosis dimension. In diagnosis charts, count distinct
`Case_ID`; never count diagnosis-bearing event rows as patients.

The requested fact layout lists `Patient_ID` and patient attributes but has no
identity source. Department is the only requested dimension that can be keyed
from current source data. Hospital and patient type can filter the fact
directly. If this report grows, add `Dim_Hospitals` and `Dim_Patient_Types`
rather than creating ambiguous labels in the fact.

## 4. Star-schema relationships

In Power BI Model view, create active, one-to-many, single-direction
relationships:

| Dimension (one side) | Fact (many side) | Join |
|---|---|---|
| `Dim_Patients[Patient_ID]` | `Fact_Clinical_Events[Patient_ID]` | Person identity; empty until mapped |
| `Dim_Departments[Department_ID]` | `Fact_Clinical_Events[Department_ID]` | Department surrogate key |
| `Dim_Date[DateKey]` | `Fact_Clinical_Events[DateKey]` | Event date |

Mark `Dim_Date` as the date table using `[Date]`. Sort `Month` by `MonthNumber`
and `Weekday` by `WeekdayNumber`. Do not enable bidirectional relationships.
Add `Targets` as a governed table with a unique row per target date and target
scope; replace the placeholder `[Target Process Time]` measure with a measure
over `Targets[Target_Process_Time_Hours]` after the target table is loaded.
Targets are not part of the current supplied data.

### Mapping from source

| Output | Source / derivation |
|---|---|
| `Case_ID` | `case_id` |
| `Patient_ID` | Approved patient map only; otherwise blank |
| `Event_Name` | Validated `stage` value (`Admission`, `Diagnosis`, `Treatment`, `Discharge`) |
| `Diagnosis` | `primary_diagnosis` |
| `Timestamp` | `event_time`, parsed as UTC |
| `Department`, `Hospital`, `Patient_Type` | Event source attributes; values must be case-consistent |
| `Length_of_Stay_Hours` | `total_length_of_stay_days * 24` from case metadata |
| `Is_Readmission` | Nullable boolean from case metadata |
| `Stage_Duration_Hours` | `process_time_hours` |
| `Wait_Time_Hours` | `wait_time_hours` |
| `Cycle_Time_Hours` | Last event end minus first event start |
| `Cost`, `Cost_Center`, `Age`, `Gender`, `Risk_Score` | Not supplied; leave blank pending validated enrichment |

## 5. DAX measure file

Import measures from [`../dax/dax_measures.dax`](../dax/dax_measures.dax)
into a dedicated measures table. Important behavior:

- `Total Patients` counts nonblank stable `Patient_ID`s. It returns zero until
  an approved patient map is connected. Use `Total Cases` for the available
  encounter KPI in the meantime.
- Length of stay and readmission are computed once per case because their
  columns repeat on the event fact. Summing raw event rows would multiply
  results by events per case.
- `Readmission Rate %` follows the requested denominator (all known
  `Patient_ID`s) and returns zero for an empty denominator. Unknown outcomes
  are therefore treated as non-readmitted in this exact measure. Prefer
  `Readmission Rate Known Outcomes %` for operational reporting; it returns
  blank when no patient outcomes are known. If adopting a strictly case-based
  definition, use distinct `Case_ID` for both numerator and denominator.
- `Patient Satisfaction Avg` needs a valid patient mapping and scores. The
  measure uses scoped `CROSSFILTER` to let fact filters (e.g. department/date)
  affect the patient-dimension average without making the model relationship
  bidirectional.
- `Stage Duration Variance` returns blank when the approved target is absent.
  `[Target Process Time]` is a compile-safe blank placeholder; replace it with
  `SELECTEDVALUE(Targets[Target_Process_Time_Hours])` (or an aggregation that
  matches the target grain) when a governed target table is added.
- Bottleneck measures use `Wait_Time_Hours`; the medium and high threshold
  measures are blank placeholders until approved local threshold values or a
  governed threshold table are connected.

The requested formula labels Total Process Time as a sum of case LOS hours.
These are not equivalent clinical concepts. The file follows the requested
definition while aggregating by case; label it “total case LOS hours” unless
the business owner confirms it is the intended process-time KPI.

## 6. Power Query M

`powerquery\transform_scripts.pq` defines `fxTransformClinicalEvents(Raw)`.
In Desktop, create a blank query named `fxTransformClinicalEvents`, paste the
file contents, then create a raw CSV query and invoke the function. Example
queries (set `pEventCsvPath` as a Power Query text parameter):

```powerquery
let
    Raw = Csv.Document(
        File.Contents(pEventCsvPath),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Result = fxTransformClinicalEvents(Raw)
in
    Result[Transformed_Events]
```

Create separate reference queries for the two rejected-row outputs. The
function returns a record:

- `[Transformed_Events]`: valid-timestamp events with trimmed fields,
  canonical event names, date key, weekday/hour, and cycle-time bucket.
- `[Dim_Departments]` and `[Dim_Date]`: the source-derived department and
  calendar dimensions.
- `[Rejected_Event_Rows]`: rows with null/invalid timestamps and a
  `Timestamp_Quality` reason. Review this table during refresh; they are not
  silently discarded without an audit trail.
- `[Rejected_Duration_Rows]`: timestamp-valid events with missing, invalid,
  or negative process durations.

The M function is event-log preprocessing; use the Python exporter for the
complete multi-source `Fact_Clinical_Events` output, including case metadata
joins and controlled patient enrichment. Do not load both outputs as duplicate
event facts.

## 7. Two-page report layout

See [`../DASHBOARD_LAYOUT.md`](../DASHBOARD_LAYOUT.md) for the concise page
blueprint. Use synced Hospital, Department, Patient Type, and Date Period
slicers. Keep the date slicer connected to `Dim_Date[Date]`.

The current dataset does not provide costs, targets, a patient identity map,
or demographic enrichment. Do not invent these fields or show fabricated
target comparisons, risk segmentation, or individual patient counts. The
current sample values are synthetic and are not hospital performance results.
