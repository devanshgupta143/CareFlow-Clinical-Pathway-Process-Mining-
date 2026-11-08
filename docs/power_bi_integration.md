# Power BI integration

The canonical CareFlow PBIP implementation, source schema, export command,
model relationships, theme, exact page layouts, DAX measures, and validation
steps are documented in
[careflow_executive_report_spec.md](./careflow_executive_report_spec.md).

Use this Python exporter for the dashboard's clinical source data:

```powershell
python scripts\build_powerbi_dataset.py
```

It reads `data\clinical_events.csv` and `data\case_metadata.csv` and writes the
model-ready CSVs to `data\processed\`. Import those tables into the PBIP
semantic model; the current `mock_hospital_logs` table and the separate
PM4Py-only export are not substitutes because they do not carry every field
needed for the Hospital, Patient Type, stage, and delayed-discharge visuals.

The generic PM4Py pipeline remains available for process-mining work on other
event logs:

```powershell
python src\process_mining.py --input data\raw\event_log.csv `
  --case-metadata data\metadata\case_metadata.csv `
  --output-dir data\pm4py_processed
```

That pipeline's output schema and measures are distinct from the dashboard
export; do not combine duplicate event/case tables from both paths in one
semantic model without an explicit key/grain design.
