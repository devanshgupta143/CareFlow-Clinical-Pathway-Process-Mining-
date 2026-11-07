# Clinical Pathway Analytics: PM4Py and PBIP Integration

## Run the processing pipeline

Generate the dashboard-ready synthetic inputs from the repository root:

```powershell
python generate_data.py
```

By default this writes `data\clinical_events.csv` and
`data\case_metadata.csv` for 12,482 synthetic cases. The case duration,
process-time, readmission, and satisfaction averages are calibrated to the
requested dashboard benchmarks. Override the population, seed, or output
location with `--cases`, `--seed`, or `--output-dir`. These records are
synthetic test data and must not be presented as real hospital outcomes.

Run the PM4Py exporter directly on those generated files:

```powershell
python src\process_mining.py --input data\clinical_events.csv --case-metadata data\case_metadata.csv --output-dir data\processed
```

The script accepts CSV and PM4Py-readable XES/XES.GZ event logs. It accepts the
CareFlow export (`Case_ID`, `Activity_Name`,
`Start_Timestamp`, `End_Timestamp`) and common XES/CSV field names. Required
event fields are case ID, activity, and a start/event timestamp. An end timestamp
is optional; when absent, the event timestamp is used as both endpoints.
When `ProcessTimeHours`/`process_time_hours` is present without an end timestamp,
the exporter derives the event end from its start and process duration.
Timestamps are parsed as UTC.

From the repository root:

```powershell
python -m pip install -r requirements.txt
python src\process_mining.py --input data\raw\event_log.csv --case-metadata data\metadata\case_metadata.csv --output-dir data\processed
```

The default writes one CSV per table. Parquet is opt-in and requires `pyarrow`:

```powershell
python -m pip install pyarrow
python src\process_mining.py --format both
```

The pipeline calculates case duration from the earliest event start through the
latest event end, activity duration from each activity interval, and wait time
from the previous event's end to the next event's start. Overlapping events
receive zero sequential wait; they are not treated as negative waiting time.
PM4Py converts the normalized event frame to an event log and extracts activity
variants. The script checks PM4Py's variant frequencies against the normalized
case sequences before exporting.

`--risk-threshold-hours` defaults to 1 hour only as an operational flagging
threshold. Set it to a locally approved value; it is not a clinical guideline.
Input readmission and satisfaction columns are optional and remain null when
absent. The current sample logs have no targets, diagnosis, readmission, or
satisfaction values; those dashboard metrics cannot be populated truthfully
until those data are sourced and joined.

## Output tables and grain

| Table | Grain | Key fields and purpose |
|---|---|---|
| `Cases` | One row per case | `CaseID`, `CaseStart`, `CaseEnd`, `CaseStartDate`, `DurationHours`, `DurationDays`, `TotalActivityHours`, `TotalWaitHours`, `Department`, `Diagnosis`, `ResourceCount`, `VariantID`, `IsReadmitted`, `PatientSatisfactionPct`. |
| `Events` | One row per activity event | `EventID`, `CaseID`, `EventSequence`, `Activity`, `StartTimestamp`, `EndTimestamp`, `EventDate`, `DayOfWeekNumber`, `DayOfWeekName`, `Resource`, `Department`, `Diagnosis`, `ActivityDurationHours`, `WaitHours`. Use for stage, calendar and heatmap visuals. |
| `Transitions` | One row per consecutive event pair | `CaseID`, `TransitionSequence`, `FromActivity`, `ToActivity`, timestamps, `ElapsedHours`, `WaitHours`, `IsDiagnosticWait`, `Department`, `Diagnosis`. |
| `StageMetrics` | Activity and department | `EventCount`, `AvgDurationHours`, `AvgWaitHours`, `TotalWaitHours`. Aggregated stage-performance table. |
| `Bottlenecks` | Destination activity and wait category | `WaitCategory` (`Diagnostics/Lab` or `Other`), `TransitionCount`, `AvgWaitHours`, `TotalWaitHours`, `DiagnosticWaitCount`, `PctOfTotalCaseTime`, `RiskStatus`. `PctOfTotalCaseTime` is total wait before that step/category divided by summed case elapsed time. |
| `DimVariant` | One row per ordered path | `VariantID`, `Variant`, `StageCount`. |
| `VariantFrequency` | One row per ordered path | `VariantID`, `Variant`, `CaseCount`, `FrequencyPct`, `StageCount`. |
| `VariantFlows` | Variant and directed edge | `VariantID`, `Variant`, `Source`, `Target`, `StageOrder`, `FlowCount`. Includes `Start` and `End` sentinel edges for Sankey visuals. |
| `DimDate` | One row per calendar date | Date, year/month fields, weekday number and name. |
| `DimActivity` | One row per activity | `Activity`, `StageOrder`. |
| `DimDepartment`, `DimDiagnosis`, `DimResource` | One row per label | Unique department, diagnosis and resource values. |

`IsReadmitted` is a nullable boolean and `PatientSatisfactionPct` is nullable
numeric percentage (0–100). The optional metadata file must have a unique case
ID per row. Null outcomes are intentionally excluded from their respective KPI
denominators.

## Recommended semantic model

Import all output CSVs from `data\processed` into the PBIP semantic model as
separate tables. Use single-direction, one-to-many relationships:

| One side | Many side | Active |
|---|---|---|
| `DimDate[Date]` | `Cases[CaseStartDate]` | Yes |
| `Cases[CaseID]` | `Events[CaseID]` | Yes |
| `Cases[CaseID]` | `Transitions[CaseID]` | Yes |
| `DimDepartment[Department]` | `Cases[Department]` | Yes |
| `DimDiagnosis[Diagnosis]` | `Cases[Diagnosis]` | Yes |
| `DimResource[Resource]` | `Events[Resource]` | Yes |
| `DimActivity[Activity]` | `Events[Activity]` | Yes |
| `DimActivity[Activity]` | `StageMetrics[Activity]` | Yes |
| `DimActivity[Activity]` | `Transitions[ToActivity]` | Yes |
| `DimActivity[Activity]` | `Bottlenecks[ProcessStep]` | Yes |
| `DimDepartment[Department]` | `StageMetrics[Department]` | Yes |
| `DimVariant[VariantID]` | `Cases[VariantID]` | Yes |
| `DimVariant[VariantID]` | `VariantFrequency[VariantID]` | Yes |
| `DimVariant[VariantID]` | `VariantFlows[VariantID]` | Yes |

The case table is the case-grain fact and the filter hub for events/transitions;
do not add direct department or diagnosis relationships to those child facts as
that would create multiple filter paths. Date filtering is by case arrival
(`CaseStartDate`). For event-date filtering, create a second role-playing date
dimension and relate it to `Events[EventDate]` instead of activating a second
path through `Cases`. Sort `DimDate[MonthName]` by `DimDate[MonthNumber]`,
`DimDate[DayOfWeekName]` by `DimDate[DayOfWeekNumber]`, and
`DimActivity[Activity]` by `DimActivity[StageOrder]`.

For a monthly actual-versus-target line chart, add an organization-approved
`Targets` table with one row per target date, metric and optional activity or
department. Include `TargetDate` (month start), `Metric`, `TargetValue`, and
the matching dimension keys. No target is inferred or generated by this
pipeline. Configure a one-to-many `DimDate[Date]` to `Targets[TargetDate]`
relationship; add an activity relationship only if activity-specific targets
exist. For trend sparklines, use `DimDate[YearMonth]` and the relevant
duration/wait measure.

## DAX measures

Create these measures in the semantic model (or a dedicated measures table):

```DAX
Total Patients =
    DISTINCTCOUNT(Events[CaseID])

Avg Length of Stay (Days) =
    AVERAGE(Cases[DurationDays])

Total Process Time (Hours) =
    SUM(Cases[DurationHours])

Readmission Rate (%) =
    DIVIDE(
        CALCULATE(COUNT(Cases[CaseID]), Cases[IsReadmitted] = TRUE()),
        COUNT(Cases[CaseID])
    )

Readmission Rate (Known Outcomes Only) =
VAR KnownOutcomes =
    CALCULATE(
        COUNTROWS(Cases),
        FILTER(Cases, NOT ISBLANK(Cases[IsReadmitted]))
    )
VAR Readmissions =
    CALCULATE(COUNTROWS(Cases), Cases[IsReadmitted] = TRUE())
RETURN
    IF(
        KnownOutcomes = 0,
        BLANK(),
        DIVIDE(Readmissions, KnownOutcomes)
    )

Patient Satisfaction (%) =
    AVERAGE(Cases[PatientSatisfactionPct])

Avg Stage Duration (Hours) =
    AVERAGE(Events[ActivityDurationHours])

Avg Stage Wait (Hours) =
    AVERAGE(Events[WaitHours])

Avg Stage Duration Target (Hours) =
    CALCULATE(
        AVERAGE(Targets[TargetValue]),
        Targets[Metric] = "Stage Duration Hours"
    )

Stage Duration vs Target (%) =
    DIVIDE(
        [Avg Stage Duration (Hours)] - [Avg Stage Duration Target (Hours)],
        [Avg Stage Duration Target (Hours)]
    )

Total Stage Wait (Hours) =
    SUM(Events[WaitHours])

Avg Transition Elapsed (Hours) =
    AVERAGE(Transitions[ElapsedHours])

Avg Bottleneck Wait (Hours) =
    AVERAGE(Transitions[WaitHours])

Wait as % of Total Case Time =
    DIVIDE(
        [Total Stage Wait (Hours)],
        CALCULATE(SUM(Cases[DurationHours]), REMOVEFILTERS(DimActivity)),
        0
    )

Variant Cases =
    SUM(VariantFrequency[CaseCount])

Avg LOS Target (Days) =
    CALCULATE(
        AVERAGE(Targets[TargetValue]),
        Targets[Metric] = "Avg LOS Days"
    )

LOS vs Target (%) =
    DIVIDE(
        [Avg Length of Stay (Days)] - [Avg LOS Target (Days)],
        [Avg LOS Target (Days)]
    )
```

Format readmission rate, satisfaction and variance as percentages. The
user-specified `Readmission Rate (%)` denominator counts every case and returns
0% when all outcome values are missing. Use `Readmission Rate (Known Outcomes
Only)` for the dashboard while outcomes are nullable; it returns blank when no
outcomes are known and calculates the rate only over known outcomes.
`Total Process Time (Hours)` sums each case's elapsed start-to-end pathway time;
it is not the sum of staff treatment minutes. Use `TotalActivityHours` when
activity time rather than elapsed throughput is the intended KPI. The two
dashboard measures “Avg Stage Wait” and “Avg Bottleneck Wait” use different
grains; use `Transitions` for wait specifically before a destination activity.

## PBIP report integration steps

1. Run the script and confirm that all expected files exist in
   `data\processed`. Keep this generated directory stable for Power BI refresh.
2. Open `Clinical_Pathway_Analytics.pbip` in Power BI Desktop. In **Transform
   data → New Source → Text/CSV**, load each table CSV. Set IDs and labels to
   text, numeric hours/days/percentages to decimal numbers, date columns to
   date, timestamps to datetime, and `IsReadmitted` to true/false.
3. If using the existing `mock_hospital_logs` query, either replace its source
   with `Events.csv` and rename its columns to the output schema, or keep it
   separate; do not load both versions as competing event facts.
4. In Model view, create the relationships in the table above. Verify
   cardinality, active status, and single-direction filtering. Disable or delete
   auto date hierarchies where they add duplicate date paths.
5. Add the measures above. For LOS actual-vs-target, create/import `Targets`
   only after the hospital provides approved values. Add `DimDate[YearMonth]`
   to the line-chart axis and the actual and target measures to values.
6. Bind the report page visuals:
   - Executive Overview: patient and LOS measures; monthly LOS actual/target;
     `Cases[Department]`/`DimDepartment` patient counts; `Cases[Diagnosis]` top
     five; `Events[DayOfWeekName]` × `DimActivity[Activity]` wait/count matrix;
     `DimActivity[Activity]`, stage duration, wait and target variance table.
   - Process Mining: `DimActivity[StageOrder]` with stage duration and targets;
     bottleneck wait table; `Cases[DurationHours]` binned into a histogram;
     `VariantFlows[Source]`, `[Target]`, and `[FlowCount]` in the selected
     Sankey custom visual. Filter the Sankey by `DimVariant[Variant]` as needed.
7. For the Sankey AppSource visual, map Source=`VariantFlows[Source]`,
   Destination=`VariantFlows[Target]`, Weight=`VariantFlows[FlowCount]`.
   Review the visual's publisher, permissions, and certification status before
   deployment; custom visuals are not required for the native charts/tables.
8. Save the PBIP and refresh it after each pipeline export. Keep the existing
   report definition and semantic model changes under source control, and avoid
   committing generated patient-level exports unless repository data policy
   explicitly permits it.

## Data readiness limitations

The current `data/raw/event_log.csv` contains case, activity, start and end
timestamps only. It does not contain diagnosis, resource, department,
readmission, or satisfaction fields. Its adjacent metadata contains baseline
pathway/incomplete-visit fields, not readmission or satisfaction. Consequently:

- Department and diagnosis visuals show `Unknown` until a validated source is
  added to the event log.
- Readmission and satisfaction measures are blank until a case-level source is
  provided and matched by `CaseID`.
- Targets must come from operational/clinical owners.
- Patient IDs represent encounters/cases in this output. If “Total Patients”
  must deduplicate people across multiple admissions, provide a stable patient
  identifier separate from `CaseID` and use that key for the KPI.
