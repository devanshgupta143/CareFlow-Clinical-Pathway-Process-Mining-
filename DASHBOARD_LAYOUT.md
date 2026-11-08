# CareFlow report blueprint

The enterprise model schema, actual source availability, Power BI relationships,
DAX measures, Power Query, and build commands are documented in
[docs/enterprise_power_bi_implementation.md](docs/enterprise_power_bi_implementation.md).

## Shared design

- Canvas: 1920 × 1080, `FitToPage`; 220 px left navigation rail.
- Sidebar: `#0F1E36`; canvas: `#F8FAFC`; cards: white.
- Accents: Teal `#00B4D8`, Purple `#7209B7`, Success `#4BB543`,
  Warning `#F72585`.
- Header slicers on both pages: Hospital, Department, Patient Type, Date Period.
  Sync slicers across pages and validate all cross-filter interactions.
- Shared header: x=244, y=20, w=1652, h=104; left navigation rail: x=0,
  y=0, w=220, h=1080.

## Page 1 — Executive Dashboard

| Row | Visuals |
|---|---|
| Header | Page title, subtitle, Hospital / Department / Patient Type / Date Period slicers |
| KPI row (x=244, y=140, w=1652, h=124) | Five equal cards: Total Patients (YoY), Avg Length of Stay, Total Process Time, Readmission Rate, Patient Satisfaction |
| Flow / trend / mix (y=280, h=246) | Patient Flow cards x=244,w=700; monthly ALOS actual vs approved target line x=960,w=480; Department Volume donut x=1456,w=440 |
| Operations / diagnosis / journey (y=542, h=298) | Process Performance matrix x=244,w=560; Top 5 Diagnoses horizontal bar x=820,w=520; weekday × stage heatmap x=1356,w=540 |

Use the encounter count when `Patient_ID` is not available; do not label cases
as unique patients. Keep LOS and process-duration definitions distinct.

## Page 2 — Process Mining & Bottleneck Analysis

| Row | Visuals |
|---|---|
| Flow / bottlenecks / distribution (y=140, h=360) | Actual vs ideal ordered stage nodes x=244,w=540; process-step wait table with High / Medium / Low thresholds x=800,w=560; cycle-time histogram x=1376,w=520 |
| Pathways / actions (y=516, h=500) | Patient pathway variations (Sankey or matrix fallback) x=244,w=920; delayed discharge case study x=1180,w=340; actionable recommendations card x=1536,w=360 |

Only display ideal/target times and bottleneck statuses when governed target and
threshold tables are supplied. A Sankey requires an approved custom visual;
use a native transition matrix as the fallback.
