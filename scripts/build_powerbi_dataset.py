"""Prepare validated, privacy-minimized CareFlow tables for Power BI."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE_ORDER = {
    "admission": ("Admission", 1),
    "diagnosis": ("Diagnosis", 2),
    "treatment": ("Treatment", 3),
    "discharge": ("Discharge", 4),
}
CASE_ATTRIBUTES = {
    "hospital": "Hospital",
    "department": "Department",
    "patient_type": "PatientType",
    "primary_diagnosis": "Diagnosis",
}


def _read_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    if frame.empty:
        raise ValueError(f"{label} file is empty: {path}")
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    return frame


def _require_columns(frame: pd.DataFrame, names: set[str], label: str) -> None:
    missing = sorted(names - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required column(s): {', '.join(missing)}.")


def _clean_text(values: pd.Series) -> pd.Series:
    cleaned = values.astype("string").str.strip()
    return cleaned.mask(cleaned.eq(""), pd.NA)


def _numeric_column(frame: pd.DataFrame, name: str, label: str) -> pd.Series:
    raw = _clean_text(frame[name])
    values = pd.to_numeric(raw, errors="coerce")
    invalid = raw.notna() & values.isna()
    if invalid.any():
        raise ValueError(f"{label}.{name} contains a non-numeric value.")
    if values.isna().any():
        raise ValueError(f"{label}.{name} contains a blank value.")
    if (values < 0).any():
        raise ValueError(f"{label}.{name} contains a negative value.")
    return values


def _boolean_column(values: pd.Series, label: str) -> pd.Series:
    normalized = _clean_text(values).str.lower()
    mapping = {
        "true": True,
        "1": True,
        "yes": True,
        "y": True,
        "false": False,
        "0": False,
        "no": False,
        "n": False,
    }
    missing = normalized.isna() | normalized.isin({"none", "null", "n/a"})
    invalid = ~missing & ~normalized.isin(mapping)
    if invalid.any():
        raise ValueError(f"{label} contains an invalid boolean value: {normalized[invalid].iloc[0]!r}.")
    return normalized.map(mapping).astype("boolean")


def build_tables(event_path: Path, metadata_path: Path) -> dict[str, pd.DataFrame]:
    """Load the source CSVs and return validated, model-ready tables."""
    events = _read_csv(event_path, "Event log")
    metadata = _read_csv(metadata_path, "Case metadata")

    required_events = {
        "case_id",
        "event_activity",
        "event_time",
        "stage",
        "wait_time_hours",
        "process_time_hours",
        *CASE_ATTRIBUTES,
    }
    _require_columns(events, required_events, "Event log")
    _require_columns(
        metadata,
        {"case_id", "total_length_of_stay_days", "total_process_time_hours"},
        "Case metadata",
    )

    events["CaseID"] = _clean_text(events["case_id"])
    events["EventTimestamp"] = pd.to_datetime(events["event_time"], errors="coerce", utc=True)
    if events["CaseID"].isna().any() or events["EventTimestamp"].isna().any():
        raise ValueError("Event log contains a blank CaseID or an invalid event_time.")

    for source, target in CASE_ATTRIBUTES.items():
        events[target] = _clean_text(events[source]).fillna("Unknown")
        conflicting = events.groupby("CaseID", sort=False)[target].nunique(dropna=False).gt(1)
        if conflicting.any():
            case_id = conflicting[conflicting].index[0]
            raise ValueError(f"Event log has inconsistent {target} values for CaseID {case_id!r}.")

    stage_values = _clean_text(events["stage"])
    if stage_values.isna().any():
        raise ValueError("Event log contains a blank stage.")
    normalized_stages = stage_values.str.lower()
    invalid_stages = ~normalized_stages.isin(STAGE_ORDER)
    if invalid_stages.any():
        raise ValueError(f"Unsupported clinical stage: {stage_values[invalid_stages].iloc[0]!r}.")
    events["StageKey"] = normalized_stages.map(
        {key: value[0] for key, value in STAGE_ORDER.items()}
    )
    events["StageOrder"] = normalized_stages.map(
        {key: value[1] for key, value in STAGE_ORDER.items()}
    ).astype("int64")
    events["WaitTimeHours"] = _numeric_column(events, "wait_time_hours", "Event log")
    events["ProcessTimeHours"] = _numeric_column(events, "process_time_hours", "Event log")
    events["EventEndTimestamp"] = events["EventTimestamp"] + pd.to_timedelta(
        events["ProcessTimeHours"], unit="h"
    )
    events = events.sort_values(
        ["CaseID", "EventTimestamp", "StageOrder"], kind="stable"
    ).reset_index(drop=True)
    events["EventSequence"] = events.groupby("CaseID", sort=False).cumcount() + 1
    events["EventID"] = (
        events["CaseID"].astype("string")
        + "-"
        + events["EventSequence"].astype("string").str.zfill(3)
    )

    metadata["CaseID"] = _clean_text(metadata["case_id"])
    if metadata["CaseID"].isna().any():
        raise ValueError("Case metadata contains a blank CaseID.")
    if metadata["CaseID"].duplicated().any():
        duplicate = metadata.loc[metadata["CaseID"].duplicated(), "CaseID"].iloc[0]
        raise ValueError(f"Case metadata contains duplicate CaseID {duplicate!r}.")
    event_ids = set(events["CaseID"])
    metadata_ids = set(metadata["CaseID"])
    if event_ids != metadata_ids:
        missing = sorted(event_ids - metadata_ids)[:5]
        extra = sorted(metadata_ids - event_ids)[:5]
        raise ValueError(
            "Event and case metadata IDs do not match. "
            f"Missing metadata IDs: {missing}; unmatched metadata IDs: {extra}."
        )

    metadata["TotalLengthOfStayDays"] = _numeric_column(
        metadata, "total_length_of_stay_days", "Case metadata"
    )
    metadata["TotalProcessTimeHours"] = _numeric_column(
        metadata, "total_process_time_hours", "Case metadata"
    )
    if "is_readmitted" in metadata:
        metadata["IsReadmitted"] = _boolean_column(
            metadata["is_readmitted"], "Case metadata.is_readmitted"
        )
    else:
        metadata["IsReadmitted"] = pd.Series(pd.NA, index=metadata.index, dtype="boolean")

    if "patient_satisfaction_pct" in metadata:
        satisfaction = pd.to_numeric(
            _clean_text(metadata["patient_satisfaction_pct"]), errors="coerce"
        )
        provided = _clean_text(metadata["patient_satisfaction_pct"]).notna()
        if (provided & satisfaction.isna()).any() or (
            satisfaction.dropna().lt(0) | satisfaction.dropna().gt(100)
        ).any():
            raise ValueError(
                "Case metadata.patient_satisfaction_pct must be a percentage from 0 to 100."
            )
        metadata["PatientSatisfactionPct"] = satisfaction
    else:
        metadata["PatientSatisfactionPct"] = pd.NA

    if "delayed_discharge_reason" in metadata:
        raw_reasons = _clean_text(metadata["delayed_discharge_reason"])
        normalized_reasons = raw_reasons.str.lower()
        no_delay = normalized_reasons.isin({"none", "no delay", "not delayed", "n/a"})
        metadata["IsDelayed"] = pd.Series(pd.NA, index=metadata.index, dtype="boolean")
        known_reason = raw_reasons.notna()
        metadata.loc[known_reason, "IsDelayed"] = ~no_delay[known_reason]
        metadata["DelayedDischargeReason"] = raw_reasons.mask(no_delay, pd.NA)
    else:
        metadata["IsDelayed"] = pd.Series(pd.NA, index=metadata.index, dtype="boolean")
        metadata["DelayedDischargeReason"] = pd.NA

    events["EventDate"] = events["EventTimestamp"].dt.strftime("%Y-%m-%d")
    events["DayOfWeekNumber"] = events["EventTimestamp"].dt.day_of_week + 1
    events["DayOfWeekName"] = events["EventTimestamp"].dt.day_name()

    case_paths = events.groupby("CaseID", sort=False)["StageKey"].agg(tuple)
    unique_paths = sorted(
        set(case_paths),
        key=lambda path: tuple(STAGE_ORDER[stage.lower()][1] for stage in path),
    )
    variant_ids = {path: f"V{index:04d}" for index, path in enumerate(unique_paths, 1)}
    case_variant = case_paths.map(variant_ids).rename("VariantID")

    cases = (
        events.groupby("CaseID", sort=False)
        .agg(
            Hospital=("Hospital", "first"),
            Department=("Department", "first"),
            PatientType=("PatientType", "first"),
            Diagnosis=("Diagnosis", "first"),
            CaseStart=("EventTimestamp", "min"),
            CaseEnd=("EventEndTimestamp", "max"),
        )
        .join(case_variant)
        .reset_index()
    )
    cases["CaseStartDate"] = cases["CaseStart"].dt.strftime("%Y-%m-%d")
    cases["CycleTimeHours"] = (
        (cases["CaseEnd"] - cases["CaseStart"]).dt.total_seconds() / 3600
    )
    case_dimensions = cases[
        [
            "CaseID",
            "Hospital",
            "Department",
            "PatientType",
            "Diagnosis",
            "CaseStartDate",
            "VariantID",
        ]
    ].copy()

    fact_cases = cases[["CaseID", "CycleTimeHours"]].merge(
        metadata[
            [
                "CaseID",
                "TotalLengthOfStayDays",
                "TotalProcessTimeHours",
                "IsReadmitted",
                "PatientSatisfactionPct",
                "IsDelayed",
                "DelayedDischargeReason",
            ]
        ],
        on="CaseID",
        how="left",
        validate="one_to_one",
    )

    event_columns = [
        "EventID",
        "CaseID",
        "EventSequence",
        "EventTimestamp",
        "EventDate",
        "DayOfWeekNumber",
        "DayOfWeekName",
        "StageKey",
        "StageOrder",
        "WaitTimeHours",
        "ProcessTimeHours",
    ]
    fact_events = events[event_columns].copy()

    transitions = events[["CaseID", "EventSequence", "EventTimestamp", "StageKey"]].copy()
    grouped = transitions.groupby("CaseID", sort=False)
    transitions["FromStageKey"] = grouped["StageKey"].shift()
    transitions["PreviousTimestamp"] = grouped["EventTimestamp"].shift()
    transitions = transitions[transitions["FromStageKey"].notna()].copy()
    transitions["ElapsedHours"] = (
        (transitions["EventTimestamp"] - transitions["PreviousTimestamp"])
        .dt.total_seconds()
        / 3600
    )
    transition_waits = events.set_index(["CaseID", "EventSequence"])["WaitTimeHours"]
    transitions["WaitTimeHours"] = [
        transition_waits.loc[(row.CaseID, row.EventSequence)]
        for row in transitions.itertuples()
    ]
    fact_transitions = transitions[
        [
            "CaseID",
            "EventSequence",
            "FromStageKey",
            "StageKey",
            "ElapsedHours",
            "WaitTimeHours",
        ]
    ].rename(
        columns={
            "EventSequence": "TransitionSequence",
            "StageKey": "ToStageKey",
        }
    )

    variant_table = (
        case_dimensions.groupby("VariantID", as_index=False)
        .agg(CaseCount=("CaseID", "nunique"))
        .sort_values("VariantID")
    )
    variant_table["Variant"] = variant_table["VariantID"].map(
        {
            variant_id: " > ".join(path)
            for path, variant_id in variant_ids.items()
        }
    )
    variant_table["StageCount"] = variant_table["Variant"].str.count(" > ") + 1

    stage_table = pd.DataFrame(
        [
            {"StageKey": name, "StageName": name, "StageOrder": order}
            for name, order in STAGE_ORDER.values()
        ]
    )
    date_range = pd.date_range(
        cases["CaseStart"].min().normalize(),
        cases["CaseEnd"].max().normalize(),
        freq="D",
        tz="UTC",
    )
    date_table = pd.DataFrame({"Date": date_range.strftime("%Y-%m-%d")})
    parsed_dates = pd.to_datetime(date_table["Date"], utc=True)
    date_table["Year"] = parsed_dates.dt.year
    date_table["MonthNumber"] = parsed_dates.dt.month
    date_table["MonthName"] = parsed_dates.dt.strftime("%b")
    date_table["YearMonth"] = parsed_dates.dt.strftime("%Y-%m")
    date_table["YearMonthKey"] = parsed_dates.dt.year * 100 + parsed_dates.dt.month
    date_table["DayOfWeekNumber"] = parsed_dates.dt.day_of_week + 1
    date_table["DayOfWeekName"] = parsed_dates.dt.day_name()

    tables = {
        "DimCase": case_dimensions,
        "FactCases": fact_cases,
        "FactEvents": fact_events,
        "FactTransitions": fact_transitions,
        "DimHospital": pd.DataFrame({"Hospital": sorted(case_dimensions["Hospital"].unique())}),
        "DimDepartment": pd.DataFrame(
            {"Department": sorted(case_dimensions["Department"].unique())}
        ),
        "DimPatientType": pd.DataFrame(
            {"PatientType": sorted(case_dimensions["PatientType"].unique())}
        ),
        "DimDiagnosis": pd.DataFrame({"Diagnosis": sorted(case_dimensions["Diagnosis"].unique())}),
        "DimStage": stage_table,
        "DimDate": date_table,
        "DimVariant": variant_table,
    }
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build validated CSV tables for the CareFlow Power BI model."
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
        help="One-row-per-case outcome and duration CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "processed",
        help="Directory for Power BI import CSVs.",
    )
    args = parser.parse_args()

    tables = build_tables(args.events, args.case_metadata)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(args.output_dir / f"{name}.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
        print(f"{name}: {len(frame):,} rows")
    print(f"Power BI tables written to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
