# Power BI DAX Measures

> **Current CareFlow dashboard:** use the canonical model export in
> `scripts/build_powerbi_dataset.py` and measures in
> [`dax/careflow_dashboard_measures.dax`](dax/careflow_dashboard_measures.dax).
> For the requested `Fact_Clinical_Events` enterprise schema, use
> [`dax/dax_measures.dax`](dax/dax_measures.dax).
> The examples below document earlier `mock_hospital_logs` and PM4Py models;
> their table names are not interchangeable with the current dashboard model.

The legacy `Clinical_Pathway_Analytics` model imports `mock_hospital_logs`
with `Case_ID`, `Activity_Name`, `Timestamp`, and `Department`. Measures in the
model use these actual columns.

## Executive Metrics

```DAX
Total Cases =
    DISTINCTCOUNT('mock_hospital_logs'[Case_ID])

Avg Pathway Duration =
    AVERAGEX(
        VALUES('mock_hospital_logs'[Case_ID]),
        CALCULATE(MAX('mock_hospital_logs'[Timestamp]))
            - CALCULATE(MIN('mock_hospital_logs'[Timestamp]))
    )

Adherence Rate =
    DIVIDE(
        CALCULATE([Total Cases], 'mock_hospital_logs'[IsStandardPath] = TRUE()),
        [Total Cases]
    )
```

`Avg Pathway Duration` is the elapsed time between the first and last event in
each case, averaged as fractional days. The adherence measure above is a
deployment template only: `IsStandardPath` is not present in the imported event
log. The separate baseline metadata also uses case IDs that do not match the
loaded event log, so adherence must not be reported until those inputs are
reconciled and the standard-path rule is defined.

## Process Measures

- `Avg Staging Time Hours` measures the average interval from the preceding event
  to the current event within each case; by activity, it represents wait before
  that activity.
- `Rework Cases` counts cases with repeated activity names.
- `Rework Rate` is `DIVIDE([Rework Cases], [Total Cases], 0)`.
- `Pathway Variant Cases` is the distinct case count for each calculated ordered
  activity sequence.

The event-log table has no clinical service-line column. Add and validate that
dimension before configuring a service-line slicer.

## PM4Py Pipeline Measures

The Power BI-ready output table schema, relationships, and full executive and
process-analysis measure set are documented in
[docs/power_bi_integration.md](docs/power_bi_integration.md). The measures below
use those exported table names:

The CareFlow-specific measure pack (including prior-month comparisons,
target variances, variant share, heatmap support, and data-readiness notes) is
in [dax/careflow_executive_measures.dax](dax/careflow_executive_measures.dax)
and the complete layout/model contract is in
[docs/careflow_executive_report_spec.md](docs/careflow_executive_report_spec.md).

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
    IF(KnownOutcomes = 0, BLANK(), DIVIDE(Readmissions, KnownOutcomes))

Patient Satisfaction (%) =
    AVERAGE(Cases[PatientSatisfactionPct])

Avg Stage Duration (Hours) =
    AVERAGE(Events[ActivityDurationHours])

Avg Stage Wait (Hours) =
    AVERAGE(Events[WaitHours])

Avg Transition Elapsed (Hours) =
    AVERAGE(Transitions[ElapsedHours])

Avg Bottleneck Wait (Hours) =
    AVERAGE(Transitions[WaitHours])
```

Readmission, satisfaction, and LOS-target measures depend on sourced,
case-matched outcomes or approved targets; they are blank or unavailable in the
current sample until that data is provided.
