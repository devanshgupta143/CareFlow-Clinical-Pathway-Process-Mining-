from __future__ import annotations

import pandas as pd
import pytest

from scripts.build_enterprise_model import build_model


def _inputs(tmp_path, include_patient_data=False):
    events = pd.DataFrame(
        [
            ["C1", "Hospital A", "General Medicine", "Inpatient", "Diabetes", "Admission", "2025-01-03 08:00:00", 0.5, 1.0],
            ["C1", "Hospital A", "General Medicine", "Inpatient", "Diabetes", "Diagnosis", "2025-01-03 10:00:00", 1.0, 2.0],
            ["C2", "Hospital B", "Surgery", "Emergency", "Fracture", "Admission", "2025-01-04 23:00:00", 0.0, 1.0],
            ["C2", "Hospital B", "Surgery", "Emergency", "Fracture", "Discharge", "2025-01-05 01:00:00", 2.0, 1.0],
        ],
        columns=[
            "case_id",
            "hospital",
            "department",
            "patient_type",
            "primary_diagnosis",
            "stage",
            "event_time",
            "wait_time_hours",
            "process_time_hours",
        ],
    )
    metadata = pd.DataFrame(
        [
            ["C1", 2.0, False],
            ["C2", 1.0, True],
        ],
        columns=["case_id", "total_length_of_stay_days", "is_readmitted"],
    )
    event_path = tmp_path / "events.csv"
    metadata_path = tmp_path / "metadata.csv"
    events.to_csv(event_path, index=False)
    metadata.to_csv(metadata_path, index=False)
    patient_path = None
    if include_patient_data:
        patient_data = pd.DataFrame(
            [
                ["C1", "P1", 45, "F", 0.4, 90],
                ["C2", "P2", 60, "M", 0.7, 80],
            ],
            columns=[
                "case_id",
                "patient_id",
                "age",
                "gender",
                "risk_score",
                "satisfaction_score",
            ],
        )
        patient_path = tmp_path / "patient_data.csv"
        patient_data.to_csv(patient_path, index=False)
    return event_path, metadata_path, patient_path


def test_model_keeps_unknown_patient_data_blank_and_case_metrics_non_additive(tmp_path):
    event_path, metadata_path, _ = _inputs(tmp_path)
    tables = build_model(event_path, metadata_path)
    fact = tables["Fact_Clinical_Events"]

    assert len(fact) == 4
    assert fact["Case_ID"].nunique() == 2
    assert fact["Patient_ID"].isna().all()
    assert fact["Cost"].isna().all()
    assert "patient_name" not in {column.lower() for column in fact.columns}
    assert set(fact["Length_of_Stay_Hours"]) == {24.0, 48.0}
    assert set(fact["Cycle_Time_Buckets"]) == {"0-6h"}
    assert set(fact["Department_ID"]) == set(tables["Dim_Departments"]["Department_ID"])
    assert fact["Diagnosis"].notna().all()
    assert tables["Dim_Patients"].empty
    assert tables["Dim_Date"]["DateKey"].is_unique


def test_model_uses_supplied_patient_map_and_calendar_attributes(tmp_path):
    event_path, metadata_path, patient_path = _inputs(tmp_path, include_patient_data=True)
    tables = build_model(event_path, metadata_path, patient_path)

    assert tables["Dim_Patients"]["Patient_ID"].tolist() == ["P1", "P2"]
    assert tables["Dim_Patients"]["Satisfaction_Score"].tolist() == [90, 80]
    assert set(tables["Fact_Clinical_Events"]["Patient_ID"]) == {"P1", "P2"}
    assert tables["Dim_Date"]["Is_Weekend"].tolist() == [False, True, True]


def test_model_rejects_mismatched_metadata_keys(tmp_path):
    event_path, metadata_path, _ = _inputs(tmp_path)
    metadata = pd.read_csv(metadata_path)
    metadata.loc[0, "case_id"] = "NOT-A-CASE"
    metadata.to_csv(metadata_path, index=False)

    with pytest.raises(ValueError, match="IDs do not match"):
        build_model(event_path, metadata_path)
