from __future__ import annotations

import pandas as pd
import pytest

from src.generate_dummy_data import (
    DEPARTMENTS,
    DIAGNOSES,
    EVENT_COLUMNS,
    METADATA_COLUMNS,
    STAGES,
    generate_data,
)


def test_generated_dataset_schema_benchmarks_and_timeline(tmp_path):
    events, metadata = generate_data(num_cases=2500, seed=7, output_dir=tmp_path)

    assert len(metadata) == 2500
    assert len(events) == 2500 * len(STAGES)
    assert events.columns.tolist() == EVENT_COLUMNS
    assert metadata.columns.tolist() == METADATA_COLUMNS
    assert metadata["case_id"].is_unique
    assert not events.isna().any().any()
    assert not metadata.isna().any().any()

    assert metadata["total_length_of_stay_days"].mean() == pytest.approx(4.2)
    assert metadata["total_process_time_hours"].mean() == pytest.approx(18.6)
    assert metadata["is_readmitted"].mean() == pytest.approx(0.063, abs=0.001)
    assert metadata["patient_satisfaction_pct"].mean() == pytest.approx(92.0)
    assert events["department"].isin(DEPARTMENTS).all()
    assert set(events["primary_diagnosis"]).issubset(set(DIAGNOSES))
    assert events.groupby("case_id", sort=False)["stage"].apply(list).map(
        lambda stages: stages == STAGES
    ).all()

    timestamps = pd.to_datetime(events["event_time"])
    assert timestamps.min() >= pd.Timestamp("2025-01-01")
    assert timestamps.max() <= pd.Timestamp("2025-09-30 23:59:59")
    for path in ("clinical_events.csv", "case_metadata.csv"):
        assert (tmp_path / path).is_file()


def test_generated_delay_reasons_have_none_and_ranked_reasons(tmp_path):
    _, metadata = generate_data(num_cases=2500, seed=11, output_dir=tmp_path)

    reasons = metadata["delayed_discharge_reason"]
    assert reasons.eq("None").any()
    assert reasons.ne("None").sum() == round(2500 * 0.087)
    assert set(reasons) == {
        "None",
        "Waiting for test results",
        "Bed availability",
        "Medication delay",
        "Patient refusal",
        "Others",
    }
