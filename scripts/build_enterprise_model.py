"""Build the CareFlow enterprise star-schema CSVs from the clinical source files."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVENT_COLUMNS = {
    "case_id",
    "event_time",
    "stage",
    "department",
    "hospital",
    "patient_type",
    "primary_diagnosis",
    "wait_time_hours",
    "process_time_hours",
}
STAGES = {
    "admission": "Admission",
    "diagnosis": "Diagnosis",
    "treatment": "Treatment",
    "discharge": "Discharge",
}
PATIENT_COLUMNS = {
    "case_id",
    "patient_id",
    "age",
    "gender",
    "risk_score",
}


def _read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    if frame.empty:
        raise ValueError(f"{label} file is empty: {path}")
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    return frame


def _text(values: pd.Series) -> pd.Series:
    result = values.astype("string").str.strip()
    return result.mask(result.eq(""), pd.NA)


def _department_id(name: str) -> str:
    normalized = " ".join(name.casefold().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12].upper()
    return f"DEPT-{digest}"


def _cycle_bucket(hours: float | None) -> str | None:
    if pd.isna(hours):
        return None
    for upper_bound, label in (
        (6, "0-6h"),
        (12, "6-12h"),
        (18, "12-18h"),
        (24, "18-24h"),
        (30, "24-30h"),
    ):
        if hours <= upper_bound:
            return label
    return ">30h"


def _date_dimension(dates: pd.Series) -> pd.DataFrame:
    start = dates.min().normalize().tz_localize(None)
    end = dates.max().normalize().tz_localize(None)
    calendar = pd.DataFrame({"Date": pd.date_range(start, end, freq="D")})
    calendar["DateKey"] = (
        calendar["Date"].dt.year * 10000
        + calendar["Date"].dt.month * 100
        + calendar["Date"].dt.day
    ).astype("int64")
    calendar["Year"] = calendar["Date"].dt.year.astype("int64")
    calendar["Quarter"] = "Q" + calendar["Date"].dt.quarter.astype("string")
    calendar["Month"] = calendar["Date"].dt.month_name()
    calendar["MonthNumber"] = calendar["Date"].dt.month.astype("int64")
    calendar["Weekday"] = calendar["Date"].dt.day_name()
    calendar["WeekdayNumber"] = (calendar["Date"].dt.day_of_week + 1).astype("int64")
    calendar["Is_Weekend"] = calendar["Date"].dt.day_of_week.ge(5)
    return calendar


def build_model(
    event_path: Path,
    metadata_path: Path,
    patient_data_path: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Return fact and dimension tables; absent sensitive attributes stay null."""
    events = _read_csv(event_path, "Event log")
    metadata = _read_csv(metadata_path, "Case metadata")
    missing = EVENT_COLUMNS - set(events.columns)
    if missing:
        raise ValueError(f"Event log is missing columns: {', '.join(sorted(missing))}.")
    required_metadata = {
        "case_id",
        "total_length_of_stay_days",
        "is_readmitted",
    }
    missing = required_metadata - set(metadata.columns)
    if missing:
        raise ValueError(
            f"Case metadata is missing columns: {', '.join(sorted(missing))}."
        )

    events["Case_ID"] = _text(events["case_id"])
    events["Timestamp"] = pd.to_datetime(events["event_time"], errors="coerce", utc=True)
    if events["Case_ID"].isna().any():
        raise ValueError("Event log contains a blank case_id.")
    if events["Timestamp"].isna().any():
        raise ValueError("Event log contains a blank or invalid event_time.")

    normalized_stages = _text(events["stage"]).str.casefold()
    invalid_stages = normalized_stages.isna() | ~normalized_stages.isin(STAGES)
    if invalid_stages.any():
        raise ValueError(
            f"Unsupported or blank stage: {_text(events['stage'])[invalid_stages].iloc[0]!r}."
        )
    events["Event_Name"] = normalized_stages.map(STAGES)

    for column in ("department", "hospital", "patient_type"):
        events[column] = _text(events[column]).fillna("Unknown")
    events["primary_diagnosis"] = _text(events["primary_diagnosis"]).fillna("Unknown")

    for column, output_name in (
        ("wait_time_hours", "Wait_Time_Hours"),
        ("process_time_hours", "Stage_Duration_Hours"),
    ):
        numeric = pd.to_numeric(_text(events[column]), errors="coerce")
        if numeric.isna().any() or numeric.lt(0).any():
            raise ValueError(f"Event log {column} must contain non-negative numbers.")
        events[output_name] = numeric

    metadata["Case_ID"] = _text(metadata["case_id"])
    if metadata["Case_ID"].isna().any() or metadata["Case_ID"].duplicated().any():
        raise ValueError("Case metadata must have one non-blank row per case_id.")
    metadata["Length_of_Stay_Hours"] = (
        pd.to_numeric(_text(metadata["total_length_of_stay_days"]), errors="coerce") * 24
    )
    if metadata["Length_of_Stay_Hours"].isna().any() or metadata[
        "Length_of_Stay_Hours"
    ].lt(0).any():
        raise ValueError("Case metadata total_length_of_stay_days must be non-negative.")
    if "patient_satisfaction_pct" in metadata:
        raw_satisfaction = _text(metadata["patient_satisfaction_pct"])
        metadata["patient_satisfaction_pct"] = pd.to_numeric(
            raw_satisfaction, errors="coerce"
        )
        if (
            raw_satisfaction.notna() & metadata["patient_satisfaction_pct"].isna()
        ).any():
            raise ValueError("patient_satisfaction_pct must be numeric.")
        values = metadata["patient_satisfaction_pct"].dropna()
        if values.lt(0).any() or values.gt(100).any():
            raise ValueError("patient_satisfaction_pct must be from 0 to 100.")
    raw_readmission = _text(metadata["is_readmitted"]).str.casefold()
    bool_map = {
        "true": True,
        "1": True,
        "yes": True,
        "y": True,
        "false": False,
        "0": False,
        "no": False,
        "n": False,
    }
    missing_outcome = raw_readmission.isna() | raw_readmission.isin(
        {"none", "null", "n/a"}
    )
    invalid_outcome = ~missing_outcome & ~raw_readmission.isin(bool_map)
    if invalid_outcome.any():
        raise ValueError(
            f"Invalid is_readmitted value: {raw_readmission[invalid_outcome].iloc[0]!r}."
        )
    metadata["Is_Readmission"] = raw_readmission.map(bool_map).astype("boolean")

    event_ids = set(events["Case_ID"])
    metadata_ids = set(metadata["Case_ID"])
    if event_ids != metadata_ids:
        missing_meta = sorted(event_ids - metadata_ids)[:5]
        extra_meta = sorted(metadata_ids - event_ids)[:5]
        raise ValueError(
            "Event and case metadata IDs do not match. "
            f"Missing metadata: {missing_meta}; unmatched metadata: {extra_meta}."
        )

    if patient_data_path is None:
        case_keys = events["Case_ID"].drop_duplicates().reset_index(drop=True)
        patient_map = pd.DataFrame(
            {
                "Case_ID": case_keys,
                "Patient_ID": pd.Series([pd.NA] * len(case_keys), dtype="string"),
            }
        )
        patient_attributes = pd.DataFrame(
            columns=["Patient_ID", "Age", "Gender", "Risk_Score", "Satisfaction_Score"]
        )
    else:
        patient_source = _read_csv(patient_data_path, "Patient enrichment")
        missing = PATIENT_COLUMNS - set(patient_source.columns)
        if missing:
            raise ValueError(
                f"Patient enrichment is missing columns: {', '.join(sorted(missing))}."
            )
        patient_source["Case_ID"] = _text(patient_source["case_id"])
        patient_source["Patient_ID"] = _text(patient_source["patient_id"])
        if patient_source["Case_ID"].isna().any() or patient_source[
            "Case_ID"
        ].duplicated().any():
            raise ValueError("Patient enrichment must have one non-blank row per Case_ID.")
        if patient_source["Patient_ID"].isna().any():
            raise ValueError("Patient enrichment contains a blank Patient_ID.")
        if set(patient_source["Case_ID"]) != event_ids:
            raise ValueError("Patient enrichment Case_ID values must exactly match event cases.")

        for column in ("age", "risk_score"):
            raw_values = _text(patient_source[column])
            patient_source[column] = pd.to_numeric(raw_values, errors="coerce")
            if (raw_values.notna() & patient_source[column].isna()).any():
                raise ValueError(f"Patient enrichment {column} must be numeric.")
        patient_source["gender"] = _text(patient_source["gender"])
        patient_map = patient_source[["Case_ID", "Patient_ID"]].copy()
        patient_attributes = (
            patient_source.groupby("Patient_ID", as_index=False, dropna=False)
            .agg(
                Age=("age", "first"),
                Gender=("gender", "first"),
                Risk_Score=("risk_score", "first"),
            )
        )
        for attribute in ("age", "gender", "risk_score"):
            distinct_counts = patient_source.groupby("Patient_ID")[attribute].nunique(
                dropna=True
            )
            if distinct_counts.gt(1).any():
                raise ValueError(
                    f"Patient enrichment {attribute} must be constant per Patient_ID."
                )
        if "satisfaction_score" in patient_source:
            patient_source["satisfaction_score"] = pd.to_numeric(
                _text(patient_source["satisfaction_score"]), errors="coerce"
            )
            provided = patient_source["satisfaction_score"].dropna()
            if provided.lt(0).any() or provided.gt(100).any():
                raise ValueError("satisfaction_score must be from 0 to 100.")
            satisfaction = patient_source.groupby("Patient_ID")[
                "satisfaction_score"
            ].mean()
            patient_attributes["Satisfaction_Score"] = patient_attributes[
                "Patient_ID"
            ].map(satisfaction)
        else:
            if "patient_satisfaction_pct" in metadata:
                mapped_scores = patient_source[["Case_ID", "Patient_ID"]].merge(
                    metadata[["Case_ID", "patient_satisfaction_pct"]],
                    on="Case_ID",
                    how="left",
                    validate="one_to_one",
                )
                satisfaction = mapped_scores.groupby("Patient_ID")[
                    "patient_satisfaction_pct"
                ].mean()
                patient_attributes["Satisfaction_Score"] = patient_attributes[
                    "Patient_ID"
                ].map(satisfaction)
            else:
                patient_attributes["Satisfaction_Score"] = pd.NA

    if patient_data_path is None:
        patient_map["Patient_ID"] = pd.NA
    patient_map = patient_map.drop_duplicates("Case_ID")
    metadata_columns = metadata[
        ["Case_ID", "Length_of_Stay_Hours", "Is_Readmission"]
    ]
    case_attributes = (
        events.groupby("Case_ID", as_index=False)
        .agg(
            Department=("department", "first"),
            Hospital=("hospital", "first"),
            Patient_Type=("patient_type", "first"),
            Diagnosis=("primary_diagnosis", "first"),
        )
    )
    for column in ("Department", "Hospital", "Patient_Type", "Diagnosis"):
        source_column = (
            "primary_diagnosis" if column == "Diagnosis" else column.lower()
        )
        inconsistent = events.groupby("Case_ID")[source_column].nunique(dropna=False).gt(1)
        if inconsistent.any():
            raise ValueError(f"Event log has inconsistent {column} values within a case.")

    facts = (
        events.merge(patient_map, on="Case_ID", how="left", validate="many_to_one")
        .merge(metadata_columns, on="Case_ID", how="left", validate="many_to_one")
        .merge(case_attributes, on="Case_ID", validate="many_to_one")
    )
    facts["Department_ID"] = facts["Department"].map(_department_id)
    facts["Cost"] = pd.NA
    facts["Date"] = facts["Timestamp"].dt.normalize().dt.tz_localize(None)
    facts["DateKey"] = (
        facts["Date"].dt.year * 10000
        + facts["Date"].dt.month * 100
        + facts["Date"].dt.day
    ).astype("int64")
    facts["Day_Name"] = facts["Timestamp"].dt.day_name()
    facts["Hour_of_Day"] = facts["Timestamp"].dt.hour.astype("int64")
    case_start = facts.groupby("Case_ID")["Timestamp"].transform("min")
    case_end = (
        facts["Timestamp"] + pd.to_timedelta(facts["Stage_Duration_Hours"], unit="h")
    ).groupby(facts["Case_ID"]).transform("max")
    facts["Cycle_Time_Hours"] = (case_end - case_start).dt.total_seconds() / 3600
    facts["Cycle_Time_Buckets"] = facts["Cycle_Time_Hours"].map(_cycle_bucket)

    fact_columns = [
        "Case_ID",
        "Patient_ID",
        "Event_Name",
        "Timestamp",
        "Date",
        "DateKey",
        "Department_ID",
        "Department",
        "Hospital",
        "Patient_Type",
        "Diagnosis",
        "Cost",
        "Length_of_Stay_Hours",
        "Is_Readmission",
        "Wait_Time_Hours",
        "Stage_Duration_Hours",
        "Cycle_Time_Hours",
        "Cycle_Time_Buckets",
        "Day_Name",
        "Hour_of_Day",
    ]
    fact = facts[fact_columns].sort_values(
        ["Case_ID", "Timestamp", "Event_Name"], kind="stable"
    )
    departments = (
        facts[["Department_ID", "Department"]]
        .drop_duplicates()
        .sort_values("Department")
        .reset_index(drop=True)
    )
    departments["Cost_Center"] = pd.NA

    if not patient_attributes.empty:
        patient_attributes = patient_attributes[
            ["Patient_ID", "Age", "Gender", "Risk_Score", "Satisfaction_Score"]
        ].drop_duplicates("Patient_ID")
    date_dimension = _date_dimension(facts["Date"])
    return {
        "Fact_Clinical_Events": fact.reset_index(drop=True),
        "Dim_Patients": patient_attributes.reset_index(drop=True),
        "Dim_Departments": departments,
        "Dim_Date": date_dimension,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build CareFlow's enterprise Power BI star-schema CSVs."
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=ROOT / "data" / "clinical_events.csv",
        help="Clinical event log CSV.",
    )
    parser.add_argument(
        "--case-metadata",
        type=Path,
        default=ROOT / "data" / "case_metadata.csv",
        help="One-row-per-case metadata CSV.",
    )
    parser.add_argument(
        "--patient-data",
        type=Path,
        help="Optional one-row-per-case patient mapping/enrichment CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "enterprise_processed",
        help="Output directory for the four model tables.",
    )
    args = parser.parse_args()

    tables = build_model(args.events, args.case_metadata, args.patient_data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for table_name, frame in tables.items():
        frame.to_csv(
            args.output_dir / f"{table_name}.csv",
            index=False,
        )
        print(f"{table_name}: {len(frame):,} rows")
    if args.patient_data is None:
        print(
            "WARNING: no stable Patient_ID source provided; Patient_ID and "
            "patient attributes remain unavailable."
        )
    print(
        "WARNING: Cost and Cost_Center are not present in the source files; "
        "those fields remain blank."
    )
    print(f"Output directory: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
