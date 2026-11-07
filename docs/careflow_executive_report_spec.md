# CareFlow: Clinical Pathway Process Mining

## Purpose and current PBIP state

This specification defines the requested two-page executive/process-mining
report, its semantic-model contract, DAX, and report layout for
`Clinical_Pathway_Analytics.pbip`.

The current PBIP imports `mock_hospital_logs` with only `Case_ID`,
`Activity_Name`, `Timestamp`, and `Department`. The PM4Py pipeline described in
[power_bi_integration.md](./power_bi_integration.md) can export case/event
durations, waits, variants, and optional case outcomes. The current sample does
not provide diagnosis, patient satisfaction, readmission, delayed-discharge
reasons, approved targets, patient type, or a separately identified patient.
Accordingly:

- The figures in the requested design (for example 12,482 patients and 92%
  satisfaction) are **design examples**, not results calculated from this
  repository's current model. Do not hard-code them into visuals.
- "Patients" currently means distinct encounters (`CaseID`). Use a stable
  person identifier if the KPI is intended to deduplicate people across
  encounters.
- Measures depending on absent data or targets are blank until a validated
  source is joined. Do not convert missing outcomes to zero.
- Process stage names such as Admission and Discharge require an approved
  activity-to-stage mapping; do not infer them from arbitrary activity labels.

## Theme and canvas

| Token | Value | Use |
|---|---|---|
| Canvas | `#F8FAFC` | Page background |
| Sidebar | `#0F172A` | Navigation and period filter |
| Card | `#FFFFFF` | Visual containers |
| Primary | `#0284C7` | Actuals, selected states, primary actions |
| Accent | `#38BDF8` | Secondary series and highlights |
| Positive | `#10B981` | Favorable change/status |
| Alert | `#EF4444` | Unfavorable change/high risk |
| Caution | `#F59E0B` | Medium risk |
| Heading | `#0F172A` | Titles and KPI values |
| Muted text | `#64748B` | Subtitles, labels, supporting text |
| Border | `#E2E8F0` | Card edge and dividers |

Use Segoe UI (or Inter where installed), white cards with 8 px corner radius,
subtle shadow, 16 px internal padding, consistent 16 px gutters, and clear
contrast. Use a fixed 220 px left rail on both pages. Navigation labels:
Overview, Patient Flow, Process Mining, Department Analysis, Performance
Metrics, Reports. Highlight the active page with a teal/blue strip and use a
date-range slicer in a sidebar card at x=16, y=844, w=188, h=212. Space the
six navigation labels evenly between y=150 and y=510. Avoid using color alone to
convey status; include a label/icon.

## Page 1 — Executive Dashboard

Set page size to 1920 × 1080, `FitToPage`. The coordinates below are in report
pixels and assume the 220 px sidebar. Cards should be aligned to the same grid.

| Container | x | y | w | h | Contents |
|---|---:|---:|---:|---:|---|
| Header | 244 | 20 | 1652 | 104 | Executive Dashboard title, subtitle, Hospital/Department/Patient Type slicers and refresh time |
| KPI 1–5 | 244 | 140 | 1652 | 124 | Five equal-width cards: Total Patients, Avg LOS, Total Process Time, Readmission Rate, Patient Satisfaction |
| Pathway flow | 244 | 280 | 700 | 246 | Admission → Diagnosis → Treatment → Discharge; distinct case count and percent at each stage |
| LOS trend | 960 | 280 | 480 | 246 | Monthly actual and target line series, Jan–Sep when that date range exists |
| Department mix | 1456 | 280 | 440 | 246 | Department donut with total case count in center and percentage legend |
| Stage performance | 244 | 542 | 560 | 298 | Stage, average time, variance/status badge, and monthly sparkline |
| Diagnosis mix | 820 | 542 | 520 | 298 | Top five diagnosis horizontal bar chart, descending |
| Journey heatmap | 1356 | 542 | 540 | 298 | Weekday rows × approved stage columns; event/case count or wait measure |
| Insight cards 1–4 | 244 | 856 | 1652 | 172 | Four compact, filter-responsive takeaways with icon, label, and measure |

The requested five KPI examples are presentation references only. Bind cards to
`Total Patients`, `Avg Length of Stay (Days)`, `Total Process Time (Hours)`,
`Readmission Rate (%)`, and `Patient Satisfaction (%)`. Put the relevant
previous-month measure under each KPI. Color favorable direction by metric
semantics: a decrease is favorable for LOS, process time, and readmissions; an
increase is favorable for patients and satisfaction. The subtitle should say
“previous month” if using the supplied previous-month measures.

The flow visual can be built with four native card/shape groups and connectors.
Use stage-completion measures and a validated stage mapping. Use a native
donut, line chart, bar chart, table/matrix, and conditional formatting where
possible. Power BI native visuals do not provide a general-purpose sparkline
inside every table layout; use the table's built-in sparkline if supported by
the Desktop version, otherwise place a small line visual alongside the table.

For the heatmap, set weekday sort by `DayOfWeekNumber`; columns use `StageOrder`.
Apply a sequential blue conditional-format scale, with a neutral/light color for
low values and blue for higher intensity. Add a legend/tooltip so intensity is
interpretable.

## Page 2 — Process Mining & Patient Flow Analysis

Use the same page size, rail, header, card styling, and global slicer
behavior. Header title: “Process Mining & Patient Flow Analysis”; subtitle:
“Visualizing actual vs. ideal process, bottlenecks and opportunities for
improvement”.

| Container | x | y | w | h | Contents |
|---|---:|---:|---:|---:|---|
| Header | 244 | 20 | 1652 | 104 | Title/subtitle, same global slicers and refresh time |
| Stage comparison | 244 | 140 | 540 | 360 | Four ordered stage cards, actual hours and approved ideal/target hours |
| Bottleneck table | 800 | 140 | 560 | 360 | Process step, average wait, share of total time, risk label |
| Cycle-time histogram | 1376 | 140 | 520 | 360 | Case counts in `0–6`, `6–12`, `12–18`, `18–24`, `24–30`, `>30` hour bins |
| Pathway variations | 244 | 516 | 920 | 500 | Variant flow from start through department/stage nodes to discharge |
| Delayed discharge | 1180 | 516 | 340 | 500 | Delayed case count/rate and ranked reason percentages |
| Recommendations | 1536 | 516 | 360 | 500 | Four numbered, actionable insights |

The stage comparison's requested actual/ideal values (2.1/2.5, 4.3/6.0,
7.8/9.5, 4.4/5.0 hours) and the displayed discharge/department counts must be
bound to sourced measures, not entered as permanent labels. The case study
reason percentages and recommendation text require local operational
validation. No delayed discharge flag or reason field currently exists.

For the pathway variations visual, use `VariantFlows[Source]`,
`VariantFlows[Target]`, and `VariantFlows[FlowCount]` in a reviewed Sankey
custom visual. It is optional and may require tenant approval; provide a native
matrix/table fallback. The `VariantFlows` export models path sequence edges,
not necessarily department transitions, unless the event activity/department
mapping is configured for that meaning.

## Model and relationships

The PM4Py names can be used as-is or renamed to the requested fact/dimension
names. The mapping below keeps the pipeline's existing names explicit:

| Report/model name | PM4Py export | Grain / use |
|---|---|---|
| `FactEvents` | `Events` (rename in model) | One row per activity event |
| `FactCases` | `Cases` (rename in model) | One row per encounter; duration and outcome measures |
| `DimCases` | Derived from `Cases` | One row per CaseID; case/person attributes only |
| `DimDepartments` | `DimDepartment` | One row per department |
| `DimStages` | `DimActivity` plus approved stage mapping | One row per stage/activity, with `StageOrder` |
| `DimDate` | `DimDate` | One row per date |
| `DimEventDate` | `DimDate` (role-playing copy) | One row per event date |
| `DimVariants` | `DimVariant` | One row per ordered path |

Recommended active relationships; filtering flows in one direction from
dimension to fact or case attributes:

| Dimension/key | Fact/key | Cardinality | Notes |
|---|---|---|---|
| `DimCases[CaseID]` | `FactEvents[CaseID]` | 1:* | Case context filters event rows |
| `DimCases[CaseID]` | `FactCases[CaseID]` | 1:1 | Dimension filters the one-row-per-case fact |
| `DimCases[CaseID]` | `Transitions[CaseID]` | 1:* | Case context filters transitions |
| `DimDepartments[Department]` | `DimCases[Department]` | 1:* | Case-level department filtering; this filters both facts via DimCases |
| `DimStages[StageKey]` | `FactEvents[StageKey]` | 1:* | Derive StageKey from a validated mapping; `Activity` may be the key if unique |
| `DimStages[StageKey]` | `StageMetrics[StageKey]` | 1:* | If the aggregated PM4Py table is loaded |
| `DimStages[StageKey]` | `Transitions[ToActivity]` | 1:* | Map destination activity to the stage key |
| `DimDate[Date]` | `DimCases[CaseStartDate]` | 1:* | Encounter-arrival date role; case attributes filter both facts |
| `DimEventDate[Date]` | `FactEvents[EventDate]` | 1:* | Separate role-playing event date dimension |
| `DimVariants[VariantID]` | `DimCases[VariantID]` | 1:* | Enables case-level variant measures |
| `DimVariants[VariantID]` | `VariantFlows[VariantID]` | 1:* | Filters exported flow edges |
| `DimDate[Date]` | `Targets[TargetDate]` | 1:* | Month-start target grain |
| `DimDepartments[Department]` | `Targets[Department]` | 1:* | Only when targets are department-specific |
| `DimStages[StageKey]` | `Targets[StageKey]` | 1:* | Only when targets are stage-specific |

Do not add direct `DimDepartments` relationships to both fact tables when it
already filters through `DimCases`; that creates duplicate filter paths. Avoid
bidirectional filtering. `DimCases` should contain unique case attributes and
keys, not duration/outcome values; `FactCases` holds the PM4Py `Cases` rows and
case-grain metrics. Put `CaseStartDate` on `DimCases` so the arrival-date
filter flows through to both facts. Use a separate `DimEventDate` for direct
event-date filtering. The current four-column
`mock_hospital_logs` table is not this model: use the PM4Py output or build
validated dimensions/facts before using these bindings.

Build `DimCases` as one unique row per `CaseID` from case attributes; keep
duration, nullable outcomes, and numeric case metrics in `FactCases`. In the
model, configure their unique `CaseID` relationship as one-to-one and single
direction from `DimCases`. Derive `DimStages[StageKey]` in Power Query using
the approved activity mapping, and ensure the key remains stable across event
and stage-metric tables.

### Targets

Create `Targets` only from approved operational targets. Minimum fields:
`TargetDate` (month start), `Metric`, `TargetValue`, and optional
`DepartmentKey`/`StageKey`. Use a unique target grain. Relate `DimDate[Date]`
to `Targets[TargetDate]` and connect department/stage dimensions only where
target rows carry matching keys. The DAX expects metric
labels `Avg LOS Days`, `Total Process Time Hours`, `Stage Duration Hours`, and
`Readmission Rate`, and optionally `Patient Satisfaction`. Store percentage
targets as fractions (for example 0.08 for 8%). Add target fields at the same
grain as visual filter context; otherwise the target measures can return
misleading repeated values. Do not create implied targets from the examples.

The cycle-time bands use `<=6`, `>6–12`, `>12–18`, `>18–24`, `>24–30`, and
`>30` hour boundaries to avoid overlap at exact cutoffs. The DAX file includes
optional `FactCases` calculated columns for these bins; sort the label by
`Cycle Time Band Sort`.

## Measures, formatting, and status

The complete reusable DAX is in
[careflow_executive_measures.dax](../dax/careflow_executive_measures.dax).
It includes executive KPIs, known-outcome readmission logic, previous-month
comparison, stage and variant calculations, target variance, and supporting
flow/heatmap measures, plus target-status labels. The delayed-discharge card has
no measure yet because neither an approved delayed-case flag nor reason field
exists in the source.

| Measure | Format |
|---|---|
| Total Patients, Variant Cases, Stage Patients, Stage Event Count | `#,##0` |
| Avg Length of Stay (Days) | `0.0` |
| Total Process Time (Hours), stage/wait hours | `#,##0.0` |
| Readmission Rate, Patient Satisfaction, Variant Share, Stage Completion | `0.0%` |
| Relative variance (`LOS vs Target (%)`, `Stage Duration vs Target (%)`) | `+0.0%;-0.0%;0.0%` |
| Percentage-point differences (`Readmission vs Previous Month (pp)`) | `+0.0%;-0.0%;0.0%` |

For target status, compare actual to target and show a text badge:
`Favorable` when actual is at or below target for duration/readmission metrics,
`Above target` otherwise, and `No target` when the target is blank. Satisfaction
uses the inverse favorable direction. For prior-month comparisons, use the
metric-specific direction noted above. Apply green/red colors as conditional
formatting and preserve textual badges for accessibility.

The previous-month calculations assume a contiguous, marked `DimDate` and
report filter context that includes the comparison month. If the requirement is
to compare two arbitrary selected ranges rather than calendar months, implement
a disconnected period selector and a matched-period calculation instead of
labeling month-over-month values “previous period”.

## PBIP implementation steps

1. Process validated logs and load the PM4Py outputs described in
   [power_bi_integration.md](./power_bi_integration.md). Set keys/labels to
   text, numeric measures to decimal, timestamps to datetime, dates to date,
   and outcome flags to true/false.
2. Create/validate the `DimCases`, `DimDepartments`, `DimStages`, `DimDate`,
   `DimVariants`, and fact tables. Populate stage and department keys from
   validated source mappings. Add source fields before designing dependent
   visuals.
3. Configure relationships as above, mark `DimDate` as the date table, and
   sort month and weekday labels by numeric sort columns.
4. Add the measures from the DAX file. Confirm known-outcome denominators and
   blank behavior with test records before deployment.
5. In Power BI Desktop, set page canvas to 1920 × 1080 and place containers
   using the coordinate tables. Build the sidebar as page-level shapes/text
   and duplicate it consistently across pages. Use synced slicers for shared
   filters; only show Hospital/Patient Type after those dimensions exist.
6. Bind the visuals to measures and dimensions. Configure Top N = 5 for
   diagnoses, conditional formatting for the matrix and status table, and
   tooltips with counts/definitions. Use a native visual when a custom visual
   has not passed security, certification, accessibility, and tenant review.
7. Set report page names and navigation in Desktop, then save the `.pbip`.
   Power BI Desktop should write the final version-specific visual JSON under
   `Clinical_Pathway_Analytics.Report\definition\pages`; do not hand-author
   opaque `query`/`visual` payloads for all visuals.
8. Refresh and verify slicer cross-filtering, totals at case grain, date roles,
   missing outcome behavior, sort order, labels, and contrast at Fit-to-Page
   and actual presentation size.

### Page definition metadata example

Power BI Desktop manages the versioned report-definition schemas. This
illustrative page metadata shows the expected sizing and display-name shape;
retain generated names/IDs and let Desktop maintain the actual schema fields.

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
  "name": "<desktop-generated-page-id>",
  "displayName": "Executive Dashboard",
  "displayOption": "FitToPage",
  "height": 1080,
  "width": 1920
}
```

The report's current page IDs and visual definitions remain Power BI-owned.
Use the grid above as the build specification; the supplied design examples
are not a replacement for validated, refreshed model results.
