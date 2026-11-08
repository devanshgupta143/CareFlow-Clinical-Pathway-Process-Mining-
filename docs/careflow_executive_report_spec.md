# CareFlow Power BI implementation specification

This is the implementation contract for the two-page CareFlow PBIP report. It
uses the canonical source files under `data\`, not the older four-column
`mock_hospital_logs` model or the smaller root-level CSV sample.

## 1. Source data and VS Code workflow

The canonical files are:

- `data\clinical_events.csv`: one row per event, including hospital,
  department, patient type, diagnosis, stage, event time, wait, and process
  time.
- `data\case_metadata.csv`: one row per encounter, including length of stay,
  total process time, readmission, satisfaction, and delayed-discharge reason.

The repository's 12,482-case `data\` cohort is synthetic demonstration data.
Do not present its results as real hospital outcomes.

The source contains an encounter identifier, not a persistent person ID.
Therefore **Total Patients** is a distinct encounter/case count until the
hospital provides a privacy-approved stable person identifier. The source has
patient names but no age/sex fields; names are deliberately omitted from all
Power BI exports.

Build the normalized import tables from the repository root in the VS Code
terminal:

```powershell
python -m pip install -r requirements.txt
python scripts\build_powerbi_dataset.py
```

Optional paths:

```powershell
python scripts\build_powerbi_dataset.py `
  --events data\clinical_events.csv `
  --case-metadata data\case_metadata.csv `
  --output-dir data\processed
```

The script validates event metadata joins, one-row-per-case keys, required
fields, non-negative durations, percentages, readmission values, and
case-constant demographics. It writes one CSV per table to `data\processed\`.
It does not invent a target or map missing outcomes to zero.

```text
CareFlow-Clinical-Pathway-Process-Mining/
├── careflow_clinical_pathway_process_mining.pbip
├── careflow_clinical_pathway_process_mining.Report/
├── careflow_clinical_pathway_process_mining.SemanticModel/
├── data/
│   ├── clinical_events.csv
│   ├── case_metadata.csv
│   └── processed/                 # generated Power BI import tables
├── dax/
│   └── careflow_dashboard_measures.dax
├── powerbi/
│   └── careflow_theme.json
├── scripts/
│   └── build_powerbi_dataset.py
└── docs/
    └── careflow_executive_report_spec.md
```

Open the PBIP in Power BI Desktop, load the generated CSVs from
`data\processed\`, add the relationships below, add the measures in
`dax\careflow_dashboard_measures.dax`, and import
`powerbi\careflow_theme.json` from **View → Themes → Browse for themes**.
Desktop owns the version-specific visual JSON; use Desktop to create and save
the visuals instead of hand-authoring opaque visual query payloads.

### Exported table grain

| Table | Grain | Fields used by report |
|---|---|---|
| `DimCase` | One row per encounter | `CaseID`, `Hospital`, `Department`, `PatientType`, `Diagnosis`, `CaseStartDate`, `VariantID` |
| `FactCases` | One row per encounter | `CaseID`, `CycleTimeHours`, `TotalLengthOfStayDays`, `TotalProcessTimeHours`, `IsReadmitted`, `PatientSatisfactionPct`, `IsDelayed`, `DelayedDischargeReason` |
| `FactEvents` | One row per event | `EventID`, `CaseID`, `EventTimestamp`, `EventDate`, `DayOfWeekName`, `DayOfWeekNumber`, `StageKey`, `StageOrder`, `WaitTimeHours`, `ProcessTimeHours` |
| `FactTransitions` | One row per consecutive event pair | `CaseID`, `FromStageKey`, `ToStageKey`, `ElapsedHours`, `WaitTimeHours` |
| `DimHospital`, `DimDepartment`, `DimPatientType`, `DimDiagnosis` | One row per label | Slicer and grouping labels |
| `DimStage` | One row per approved stage | `StageKey`, `StageName`, `StageOrder` |
| `DimDate` | One row per date | `Date`, `Year`, `MonthNumber`, `MonthName`, `YearMonth`, `YearMonthKey`, weekday fields |
| `DimVariant` | One row per ordered stage path | `VariantID`, `Variant`, `CaseCount`, `StageCount` |

`CycleTimeHours` is elapsed time from the first event start to the last event
end (event time plus event process duration). It is distinct from the metadata
`TotalProcessTimeHours`; label those metrics clearly in visuals.

## 2. Semantic model

Use one-way filtering from dimensions to `DimCase`, `FactEvents`, or
`FactTransitions`; keep case facts at encounter grain. Create these active
relationships:

| One side | Many side | Cardinality / direction |
|---|---|---|
| `DimHospital[Hospital]` | `DimCase[Hospital]` | 1:*; single direction |
| `DimDepartment[Department]` | `DimCase[Department]` | 1:*; single direction |
| `DimPatientType[PatientType]` | `DimCase[PatientType]` | 1:*; single direction |
| `DimDiagnosis[Diagnosis]` | `DimCase[Diagnosis]` | 1:*; single direction |
| `DimDate[Date]` | `DimCase[CaseStartDate]` | 1:*; single direction |
| `DimCase[CaseID]` | `FactCases[CaseID]` | 1:1; single direction |
| `DimCase[CaseID]` | `FactEvents[CaseID]` | 1:*; single direction |
| `DimCase[CaseID]` | `FactTransitions[CaseID]` | 1:*; single direction |
| `DimStage[StageKey]` | `FactEvents[StageKey]` | 1:*; single direction |
| `DimStage[StageKey]` | `FactTransitions[ToStageKey]` | 1:*; single direction |
| `DimVariant[VariantID]` | `DimCase[VariantID]` | 1:*; single direction |

Mark `DimDate` as the date table. Sort `MonthName` by `MonthNumber`,
`YearMonth` by `YearMonthKey`,
`DayOfWeekName` by `DayOfWeekNumber`, and `StageName` by `StageOrder`.
`DimDate` filters by encounter start date; use an additional role-playing event
date dimension only if the business needs the global date slicer to mean event
date instead.

Create two governed input tables; do not seed them with illustrative numbers:

- `Targets`: `TargetDate`, `Metric`, `TargetValue`, plus optional `Hospital`,
  `Department`, and `StageKey`. Store readmission and satisfaction targets as
  fractions (8% = `0.08`) and use labels such as `Avg LOS Days`, `Avg Process
  Time Hours`, and `Stage Duration Hours`. Ensure the row grain matches the
  visual's filter context.
- `WaitThresholds`: `StageKey`, `MediumHours`, `HighHours`, plus optional
  `Department`. The clinical/operations owner must approve these thresholds
  before a High/Medium/Low badge is shown.

When the matching keys are populated, relate `DimDate[Date]` to
`Targets[TargetDate]`, `DimStage[StageKey]` to `Targets[StageKey]`,
`DimDepartment[Department]` to `Targets[Department]`, and
`DimHospital[Hospital]` to `Targets[Hospital]`. Relate `DimStage` and
`DimDepartment` to the corresponding `WaitThresholds` columns. Keep these
single-direction relationships from dimension to target/threshold. Never use
bidirectional relationships to compensate for a missing key.

## 3. Theme and UI styling

Import `powerbi\careflow_theme.json`. Apply these tokens consistently:

| Token | Value | Use |
|---|---|---|
| Sidebar | `#0F1E36` | Persistent navigation rail |
| Canvas | `#F8FAFC` | Page background |
| Card | `#FFFFFF` | Visual backgrounds |
| Teal | `#00B4D8` | Primary actuals and selected state |
| Purple | `#7209B7` | Secondary/ideal series and alternate flow |
| Success | `#4BB543` | Favorable status |
| Warning | `#F72585` | Unfavorable/high-risk status |
| Text | `#0F1E36` | Headings and KPI values |
| Muted text | `#64748B` | Labels and supporting text |
| Border | `#E2E8F0` | Card outlines and dividers |

Use a 1920 × 1080 `FitToPage` canvas on both pages, Segoe UI, 8 px card
corners, subtle shadows, 16 px card padding, and 16 px gutters. Keep labels and
status text in addition to color for accessibility.

The 220 px left rail uses the dark blue token and active-page highlight in teal.
Place the four synced slicers in a top header filter bar on both pages:
Hospital, Department, Patient Type, and Date Period. Date Period is a relative
or between-date slicer on `DimDate[Date]`; use the same synced slicer state on
both pages.

On the 1920 × 1080 canvas, place the title at x=244, y=28, w=700, h=64.
Place four 220 × 56 px slicers at y=44 with x positions 980, 1212, 1444, and
1676. Divide the 1652 px KPI row into five 317.6 px cards with 16 px gutters:
x=244, 577.6, 911.2, 1244.8, and 1578.4; y=140, h=124.

### Page 1 — Executive Dashboard

| Container | x | y | w | h | Visual/content |
|---|---:|---:|---:|---:|---|
| Header and filter bar | 244 | 20 | 1652 | 104 | Title, subtitle, four synced slicers, refresh date |
| KPI cards 1–5 | 244 | 140 | 1652 | 124 | Total Patients + YoY; Avg LOS + previous period; Total Process Time + target context; Readmission Rate + 8% benchmark; Patient Satisfaction |
| Patient flow | 244 | 280 | 700 | 246 | Admission → Diagnosis → Treatment → Discharge; stage patients and conversion |
| ALOS trend | 960 | 280 | 480 | 246 | Monthly actual and approved target line, sorted Jan–Sep when available |
| Department volume | 1456 | 280 | 440 | 246 | Donut by department, encounter count and percent |
| Process performance | 244 | 542 | 560 | 298 | Stage, avg duration, variance vs target, monthly sparkline |
| Top diagnoses | 820 | 542 | 520 | 298 | Horizontal bar, Top N = 5, encounter count |
| Patient journey heatmap | 1356 | 542 | 540 | 298 | Weekday × stage matrix, average wait hours or event count |

Use `DimStage[StageOrder]` for the flow ordering and `[Stage Patients]` /
`[Stage Conversion (%)]` for stage cards. The ALOS chart uses `DimDate[YearMonth]`,
`[Avg Length of Stay (Days)]`, and `[Avg LOS Target (Days)]`. Use built-in
table sparklines where supported; otherwise align a small line visual beside
the process table.

The heatmap uses `FactEvents[DayOfWeekName]` and `DimStage[StageName]`, sorted
Monday through Sunday and by `StageOrder`; use `[Avg Stage Wait (Hours)]` as
the default value with a clearly labeled scale. Department volume includes
the six values present in the source, including Others.

### Page 2 — Process Mining & Patient Flow Analysis

| Container | x | y | w | h | Visual/content |
|---|---:|---:|---:|---:|---|
| Header and filter bar | 244 | 20 | 1652 | 104 | Page title, subtitle, synced slicers, refresh date |
| Actual vs ideal flow | 244 | 140 | 540 | 360 | Four ordered stage cards; actual avg hours vs approved target |
| Bottleneck analysis | 800 | 140 | 560 | 360 | Stage, avg wait, share of elapsed process time, approved risk status |
| Cycle-time histogram | 1376 | 140 | 520 | 360 | Encounter counts by 0–6h, 6–12h, 12–18h, 18–24h, 24–30h, >30h |
| Pathway variations | 244 | 516 | 920 | 500 | Sankey from `FactTransitions[FromStageKey]` to `[ToStageKey]`, weighted by `[Flow Cases]` |
| Delayed discharge | 1180 | 516 | 340 | 500 | Delayed case count, rate among known statuses, ranked reasons |
| Recommendations | 1536 | 516 | 360 | 500 | Numbered rule-based actions with triggering measure and evidence |

Use `[Avg Transition Wait (Hours)]`,
`[Transition Wait Share of Process and Wait (%)]`, and `[Bottleneck Status]`
in the bottleneck table. The share denominator is the sum of event process
duration and transition wait across the selected cohort; the transition wait
measure excludes the first event, which has no preceding stage. Use
`[Bottleneck Status]` only after approved thresholds have been loaded.
Power BI's native visuals do not provide a Sankey; use a tenant-reviewed custom
visual or replace it with a native transition matrix/table. The Sankey is a
stage transition flow, not a department-to-discharge pathway.

The supplied reason field supports Waiting for test results, Bed availability,
Medication delay, and other source values. Null reason values remain unknown;
the explicit `None`/no-delay value means a known non-delayed encounter.
Recommendation cards should be rule-based and evidence-linked unless an
approved Copilot/AI capability is actually connected. Do not present an
illustrative “reduce by 20%” as a model-generated finding.

## 4. DAX and metric semantics

The complete measure set is in
[`dax\careflow_dashboard_measures.dax`](../dax/careflow_dashboard_measures.dax).
It includes the five requested KPIs, YoY/previous-period calculations, stage
duration variance, target comparisons, flow, wait, delayed discharge, and
cycle-time bands.

Important semantics:

- Readmission uses only cases with a known outcome; if none are known, it
  returns blank. The benchmark is the requested 8%, not a claim about a
  regulatory or clinical standard.
- Satisfaction source values are 0–100; the measure converts to a 0–1 fraction
  for percentage formatting.
- Total process time is the sum of case-level metadata values. The KPI's
  target comparison should use the average per encounter unless an approved
  target is explicitly defined for the selected cohort total.
- Stage duration variance is actual average event `ProcessTimeHours` minus
  approved stage target hours. Positive means above target.
- The source spans 2025 only. YoY measures will correctly show blank until
  matching prior-year records are loaded.
- No stage targets or risk thresholds are included in source data. Target and
  status visuals remain blank/“No approved threshold” until they are supplied.

Format case counts as `#,##0`, LOS as `0.0` days, duration as `#,##0.0` hours,
rates as `0.0%`, and signed target variances as `+0.0%;-0.0%;0.0%` or the
corresponding signed hour format. The DAX benchmark returns a fraction, so set
its model format to percentage.

## 5. Build and verification checklist

1. Run the exporter and review its validation output. Do not use the older root
   `clinical_events.csv` / `case_metadata.csv` sample for the report.
2. Load all exported CSVs into the active PBIP semantic model and set identifiers
   and labels to text, hours/days to decimal, date fields to date, timestamps to
   datetime, and outcome flags to true/false.
3. Configure the single-direction relationships and date sorting above. Ensure
   each `DimCase[CaseID]` appears once and each `FactCases[CaseID]` appears
   once.
4. Add DAX measures, apply formats, and sort cycle-time bands by
   `Cycle Time Band Sort`.
5. Add only owner-approved target and wait-threshold rows. Confirm their grain
   matches the chart dimensions before enabling variance/status visuals.
6. Configure both pages and sync the four slicers. Test that hospital,
   department, patient type, date, and diagnosis filters affect case, event,
   transition, and delayed-discharge visuals consistently.
7. Check totals against source row/case counts; confirm no names were exported,
   unknown readmission/delay values remain excluded from known-outcome
   denominators, and out-of-scope or unmatched case IDs fail the Python build.
8. Save the PBIP from Power BI Desktop. Keep `data\processed\` generated and
   out of source control unless repository data policy explicitly approves
   committing generated encounter-level data.
