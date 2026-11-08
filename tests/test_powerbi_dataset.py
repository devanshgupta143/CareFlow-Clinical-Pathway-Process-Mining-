from __future__ import annotations

import pandas as pd
import pytest

from scripts.build_powerbi_dataset import build_tables


def _write_inputs(tmp_path, metadata_case_ids=("C1", "C2")):
    events = pd.DataFrame(
        [
            ["C1", "Private Name", "Hospital A", "General Medicine", "Inpatient", "Diabetes", "Admission", "2025-01-01 08:00:00", "Admission", 0.5, 1.0],
            ["C1", "Private Name", "Hospital A", "General Medicine", "Inpatient", "Diabetes", "Diagnosis", "2025-01-01 10:00:00", "Diagnosis", 1.0, 2.0],
            ["C2", "Other Name", "Hospital B", "Surgery", "Emergency", "Fracture", "Admission", "2025-01-02 08:00:00", "Admission", 0.0, 1.5],
            ["C2", "Other Name", "Hospital B", "Surgery", "Emergency", "Fracture", "Discharge", "2025-01-02 12:00:00", "Discharge", 2.0, 1.0],
        ],
        columns=[
            "case_id",
            "patient_name",
            "hospital",
            "department",
            "patient_type",
            "primary_diagnosis",
            "event_activity",
            "event_time",
            "stage",
            "wait_time_hours",
            "process_time_hours",
        ],
    )
    metadata = pd.DataFrame(
        [
            ["C1", 1.5, 3.0, "false", 85, "None"],
            ["C2", 2.0, 2.5, "true", 95, "Waiting for test results"],
        ],
        columns=[
            "case_id",
            "total_length_of_stay_days",
            "total_process_time_hours",
            "is_readmitted",
            "patient_satisfaction_pct",
            "delayed_discharge_reason",
        ],
    )
    metadata = metadata[metadata["case_id"].isin(metadata_case_ids)]
    event_path = tmp_path / "events.csv"
    metadata_path = tmp_path / "metadata.csv"
    events.to_csv(event_path, index=False)
    metadata.to_csv(metadata_path, index=False)
    return event_path, metadata_path


def test_build_tables_preserves_grains_and_excludes_patient_names(tmp_path):
    event_path, metadata_path = _write_inputs(tmp_path)

    tables = build_tables(event_path, metadata_path)

    assert len(tables["DimCase"]) == 2
    assert tables["DimCase"]["CaseID"].is_unique
    assert len(tables["FactEvents"]) == 4
    assert len(tables["FactTransitions"]) == 2
    assert "patient_name" not in set().union(*(set(frame.columns) for frame in tables.values()))
    assert tables["FactCases"]["IsDelayed"].tolist() == [False, True]
    assert tables["FactCases"]["DelayedDischargeReason"].isna().tolist() == [True, False]


def test_build_tables_rejects_unmatched_case_metadata(tmp_path):
    event_path, metadata_path = _write_inputs(tmp_path, metadata_case_ids=("C1",))

    with pytest.raises(ValueError, match="IDs do not match"):
        build_tables(event_path, metadata_path)
