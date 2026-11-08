# CareFlow-Clinical-Pathway-Process-Mining

End-to-end healthcare analytics and process mining repository tracking clinical pathways, patient flows, and operational insights.

## 📊 Project Overview
This project uses Process Mining techniques to analyze clinical event logs (hospital workflows). It identifies how patients move through the healthcare system, discovers bottlenecks, checks protocol compliance, and visualizes operational insights.

## 🛠️ Tech Stack
- **Python 3**
- **PM4Py** (Process Mining algorithms)
- **Pandas** (Data manipulation)
- **Matplotlib / Seaborn** (Visualization)
- **Graphviz** (Process model rendering)

## ⚙️ Setup & Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/jiyamulla1212-dev/CareFlow-Clinical-Pathway-Process-Mining.git
   cd CareFlow-Clinical-Pathway-Process-MiningUpdated Clinical Pathway Analytics project workspace, documentation, and data models for Power BI integration.
## Data Model Updates (Nov 3, 2026)
Configured process mining relationships and updated pathway stage tables.
Added new measure logic for average patient wait time across clinical stages.
Updated dashboard layout, report theme colors, and interactive slicer panel.
Refined report visual formatting, tooltips, and measure performance in Power BI.

## Process Mining and PBIP Integration

Build the enterprise star-schema tables for the two-page report with
`python scripts\build_enterprise_model.py`. The output schema, relationship
contract, DAX, and Power Query function are documented in
[docs/enterprise_power_bi_implementation.md](docs/enterprise_power_bi_implementation.md).

For the two-page CareFlow dashboard, run
`python scripts\build_powerbi_dataset.py` from the repository root. It builds
the normalized CSV tables under `data\processed`. See
[docs/careflow_executive_report_spec.md](docs/careflow_executive_report_spec.md)
for the model relationships, DAX measures, layout, and PBIP setup steps.

The generic PM4Py pipeline is also available for other event logs:
`python src\process_mining.py --output-dir data\pm4py_processed`.
## Updates (Nov 4, 2026)
Configured dataset schema mappings and validated event log structures.
Refined process mining script to output throughput times and bottleneck tables.
Added DAX measures for patient wait times and configured report tooltips.
Completed local setup, dependency checks, and daily project progress log.
## Update (Nov 5, 2026)
Documented pipeline execution steps and dashboard layout requirements.
Verified argument parsing for input logs and metadata paths.
Added integration notes for connecting PM4Py outputs to Power BI tables.
## Update (Nov 6, 2026)
Configured execution logging for PM4Py event log processing and exception handling.
Documented mandatory column schemas for case IDs, timestamps, and activity names.
Standardized throughput and wait time calculations for Power BI visual consumption.
Validated git commit history integrity and daily streak updates.
