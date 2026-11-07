"""Build Power BI-ready clinical pathway tables from an event log."""

from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path

import pandas as pd
import pm4py
from pm4py.statistics.variants.log import get as variants_get


INPUT_ALIASES = {
    "CaseID": ("CaseID", "Case_ID", "Case ID", "PatientID", "case:concept:name"),
    "Activity": (
        "Activity",
        "Activity_Name",
        "Activity Name",
        "Action",
        "event_activity",
        "concept:name",
    ),
    "StartTimestamp": (
        "StartTimestamp",
        "Start_Timestamp",
        "Start Timestamp",
        "Timestamp",
        "Time",
        "event_time",
        "time:timestamp",
    ),
    "EndTimestamp": ("EndTimestamp", "End_Timestamp", "End Timestamp"),
    "ProcessTimeHours": ("ProcessTimeHours", "Process_Time_Hours"),
    "Resource": ("Resource", "Resource_Name", "org:resource"),
    "Department": ("Department", "Ward"),
    "Diagnosis": ("Diagnosis", "Diagnosis_Name", "primary_diagnosis"),
}

CASE_ALIASES = {
    "CaseID": INPUT_ALIASES["CaseID"],
    "IsReadmitted": ("IsReadmitted", "Is_Readmitted", "Readmitted"),
    "PatientSatisfactionPct": (
        "PatientSatisfactionPct",
        "Patient_Satisfaction_Pct",
        "SatisfactionPct",
    ),
}

OUTPUT_TABLES = (
    "Events",
    "Cases",
    "Transitions",
    "StageMetrics",
    "Bottlenecks",
    "DimVariant",
    "VariantFrequency",
    "VariantFlows",
    "DimDate",
    "DimActivity",
    "DimDepartment",
    "DimDiagnosis",
    "DimResource",
)


def _column_name(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    columns = {str(column).strip().lower(): str(column) for column in frame.columns}
    for alias in aliases:
        found = columns.get(alias.lower())
        if found is not None:
            return found
    return None


def _require_column(frame: pd.DataFrame, aliases: tuple[str, ...], label: str) -> str:
    column = _column_name(frame, aliases)
    if column is None:
        raise ValueError(f"Input is missing required {label} column (accepted names: {aliases}).")
    return column


def _clean_text(values: pd.Series) -> pd.Series:
    cleaned = values.astype("string").str.strip()
    return cleaned.mask(cleaned.eq(""), pd.NA)


def load_events(path: str | Path) -> pd.DataFrame:
    """Load common clinical CSV schemas and normalize event fields."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Event log not found: {path}")

    if path.name.lower().endswith((".xes", ".xes.gz")):
        raw = pm4py.convert_to_dataframe(pm4py.read_xes(str(path)))
    else:
        raw = pd.read_csv(path, dtype="string")
    if raw.empty:
        raise ValueError(f"Event log is empty: {path}")
    case_column = _require_column(raw, INPUT_ALIASES["CaseID"], "case ID")
    activity_column = _require_column(raw, INPUT_ALIASES["Activity"], "activity")
    start_column = _require_column(raw, INPUT_ALIASES["StartTimestamp"], "timestamp")
    end_column = _column_name(raw, INPUT_ALIASES["EndTimestamp"])
    process_time_column = _column_name(raw, INPUT_ALIASES["ProcessTimeHours"])
    start_times = pd.to_datetime(raw[start_column], errors="coerce", utc=True)
    if end_column:
        end_times = pd.to_datetime(raw[end_column], errors="coerce", utc=True)
    elif process_time_column:
        process_hours = pd.to_numeric(raw[process_time_column], errors="coerce")
        end_times = start_times + pd.to_timedelta(process_hours, unit="h")
    else:
        end_times = start_times

    events = pd.DataFrame(
        {
            "CaseID": _clean_text(raw[case_column]),
            "Activity": _clean_text(raw[activity_column]),
            "StartTimestamp": start_times,
            "EndTimestamp": end_times,
        }
    )
    for field in ("Resource", "Department", "Diagnosis"):
        column = _column_name(raw, INPUT_ALIASES[field])
        events[field] = (
            _clean_text(raw[column]).fillna("Unknown")
            if column
            else "Unknown"
        )

    invalid = (
        events["CaseID"].isna()
        | events["Activity"].isna()
        | events["StartTimestamp"].isna()
        | events["EndTimestamp"].isna()
        | (events["EndTimestamp"] < events["StartTimestamp"])
    )
    if invalid.any():
        rows = (events.index[invalid] + 2).tolist()[:10]
        raise ValueError(
            f"Found {int(invalid.sum())} invalid event row(s); CSV line(s): {rows}."
        )

    return (
        events.sort_values(
            ["CaseID", "StartTimestamp", "EndTimestamp", "Activity"],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def _read_case_metadata(path: str | Path | None, events: pd.DataFrame) -> pd.DataFrame:
    """Load optional case-level outcome fields; absent fields remain null."""
    base = pd.DataFrame({"CaseID": events["CaseID"].drop_duplicates()})
    base["IsReadmitted"] = pd.NA
    base["PatientSatisfactionPct"] = pd.NA
    if path is None:
        return base
    if not Path(path).is_file():
        raise FileNotFoundError(f"Case metadata file not found: {path}")

    raw = pd.read_csv(path, dtype="string")
    case_column = _require_column(raw, CASE_ALIASES["CaseID"], "case ID in case metadata")
    metadata = pd.DataFrame({"CaseID": _clean_text(raw[case_column])})
    for field in ("IsReadmitted", "PatientSatisfactionPct"):
        column = _column_name(raw, CASE_ALIASES[field])
        metadata[field] = raw[column] if column else pd.NA
    metadata = metadata.dropna(subset=["CaseID"])
    if metadata["CaseID"].duplicated().any():
        duplicate = metadata.loc[metadata["CaseID"].duplicated(), "CaseID"].iloc[0]
        raise ValueError(f"Case metadata contains duplicate CaseID {duplicate!r}.")
    unmatched = set(metadata["CaseID"]) - set(base["CaseID"])
    if unmatched:
        examples = sorted(unmatched)[:5]
        raise ValueError(
            f"Case metadata has {len(unmatched)} CaseID value(s) not found in the event log: "
            f"{examples}."
        )

    readmitted = metadata["IsReadmitted"].astype("string").str.strip().str.lower()
    bool_values = {
        "true": True,
        "1": True,
        "yes": True,
        "y": True,
        "false": False,
        "0": False,
        "no": False,
        "n": False,
    }
    invalid_bool = readmitted.notna() & ~readmitted.isin(bool_values)
    if invalid_bool.any():
        invalid_value = readmitted[invalid_bool].iloc[0]
        raise ValueError(f"Invalid IsReadmitted value {invalid_value!r}; use true/false or leave blank.")
    metadata["IsReadmitted"] = readmitted.map(bool_values).astype("boolean")

    satisfaction = pd.to_numeric(metadata["PatientSatisfactionPct"], errors="coerce")
    provided_satisfaction = metadata["PatientSatisfactionPct"].notna()
    invalid_satisfaction = provided_satisfaction & (
        satisfaction.isna() | satisfaction.lt(0) | satisfaction.gt(100)
    )
    if invalid_satisfaction.any():
        raise ValueError("PatientSatisfactionPct values must be numeric percentages from 0 to 100.")
    metadata["PatientSatisfactionPct"] = satisfaction

    return base.drop(columns=["IsReadmitted", "PatientSatisfactionPct"]).merge(
        metadata, on="CaseID", how="left", validate="one_to_one"
    )


def _pm4py_variant_counts(events: pd.DataFrame) -> Counter[tuple[str, ...]]:
    pm_events = events.rename(
        columns={
            "CaseID": "case:concept:name",
            "Activity": "concept:name",
            "StartTimestamp": "time:timestamp",
            "Resource": "org:resource",
            "Department": "case:Department",
            "Diagnosis": "case:Diagnosis",
        }
    )
    event_log = pm4py.convert_to_event_log(pm_events)
    variants = variants_get.get_variants_as_tuples(event_log)
    return Counter({tuple(map(str, path)): len(traces) for path, traces in variants.items()})


def _event_tables(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = events.copy()
    result["EventSequence"] = result.groupby("CaseID", sort=False).cumcount() + 1
    result["EventID"] = result["CaseID"] + "-" + result["EventSequence"].astype(str)
    result["PreviousActivity"] = result.groupby("CaseID", sort=False)["Activity"].shift()
    result["PreviousStart"] = result.groupby("CaseID", sort=False)["StartTimestamp"].shift()
    result["PreviousEnd"] = result.groupby("CaseID", sort=False)["EndTimestamp"].shift()
    result["ActivityDurationHours"] = (
        (result["EndTimestamp"] - result["StartTimestamp"]).dt.total_seconds() / 3600
    )
    result["WaitHours"] = (
        (result["StartTimestamp"] - result["PreviousEnd"]).dt.total_seconds() / 3600
    ).clip(lower=0).fillna(0)
    result["EventDate"] = result["StartTimestamp"].dt.date
    result["DayOfWeekNumber"] = result["StartTimestamp"].dt.dayofweek + 1
    result["DayOfWeekName"] = result["StartTimestamp"].dt.day_name()

    transitions = result.loc[result["PreviousActivity"].notna()].copy()
    transitions["TransitionSequence"] = transitions["EventSequence"]
    transitions["FromActivity"] = transitions["PreviousActivity"]
    transitions["ToActivity"] = transitions["Activity"]
    transitions["ElapsedHours"] = (
        (transitions["StartTimestamp"] - transitions["PreviousStart"])
        .dt.total_seconds()
        / 3600
    )
    transitions["IsDiagnosticWait"] = transitions["ToActivity"].str.contains(
        r"lab|diagn|test|imaging|scan|radiology", case=False, regex=True
    )
    transitions["WaitCategory"] = transitions["IsDiagnosticWait"].map(
        {True: "Diagnostics/Lab", False: "Other"}
    )

    event_columns = [
        "EventID",
        "CaseID",
        "EventSequence",
        "Activity",
        "StartTimestamp",
        "EndTimestamp",
        "EventDate",
        "DayOfWeekNumber",
        "DayOfWeekName",
        "Resource",
        "Department",
        "Diagnosis",
        "ActivityDurationHours",
        "WaitHours",
    ]
    transition_columns = [
        "CaseID",
        "TransitionSequence",
        "FromActivity",
        "ToActivity",
        "PreviousStart",
        "PreviousEnd",
        "StartTimestamp",
        "ElapsedHours",
        "WaitHours",
        "IsDiagnosticWait",
        "WaitCategory",
        "Department",
        "Diagnosis",
    ]
    return result[event_columns], transitions[transition_columns].reset_index(drop=True)


def _case_table(events: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    cases = (
        events.groupby("CaseID", sort=False)
        .agg(
            CaseStart=("StartTimestamp", "min"),
            CaseEnd=("EndTimestamp", "max"),
            Department=("Department", "first"),
            Diagnosis=("Diagnosis", "first"),
            ResourceCount=("Resource", "nunique"),
        )
        .reset_index()
    )
    event_totals = events.groupby("CaseID").agg(
        TotalActivityHours=("ActivityDurationHours", "sum"),
        TotalWaitHours=("WaitHours", "sum"),
    )
    cases = cases.merge(event_totals, on="CaseID", validate="one_to_one")
    cases["DurationHours"] = (
        (cases["CaseEnd"] - cases["CaseStart"]).dt.total_seconds() / 3600
    )
    cases["DurationDays"] = cases["DurationHours"] / 24
    cases["CaseStartDate"] = cases["CaseStart"].dt.date
    cases = cases.merge(metadata, on="CaseID", how="left", validate="one_to_one")
    return cases[
        [
            "CaseID",
            "CaseStart",
            "CaseEnd",
            "CaseStartDate",
            "DurationHours",
            "DurationDays",
            "TotalActivityHours",
            "TotalWaitHours",
            "Department",
            "Diagnosis",
            "ResourceCount",
            "IsReadmitted",
            "PatientSatisfactionPct",
        ]
    ]


def _variant_tables(
    events: pd.DataFrame, transitions: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]:
    case_paths = (
        events.groupby("CaseID", sort=False)["Activity"]
        .agg(tuple)
        .rename("Path")
        .reset_index()
    )
    path_counts = Counter(case_paths["Path"])
    pm4py_counts = _pm4py_variant_counts(events)
    if path_counts != pm4py_counts:
        raise RuntimeError(
            "PM4Py variant counts differ from normalized event order; "
            "check timestamp ordering and duplicate event timestamps."
        )

    paths = sorted(path_counts, key=lambda path: (-path_counts[path], path))
    path_to_id = {path: f"V{index:04d}" for index, path in enumerate(paths, start=1)}
    frequency = pd.DataFrame(
        [
            {
                "VariantID": path_to_id[path],
                "Variant": " > ".join(path),
                "CaseCount": path_counts[path],
                "FrequencyPct": path_counts[path] / len(case_paths) * 100,
                "StageCount": len(path),
            }
            for path in paths
        ]
    )
    variant_dimension = frequency[["VariantID", "Variant", "StageCount"]].copy()

    case_paths["VariantID"] = case_paths["Path"].map(path_to_id)
    case_lookup = case_paths.set_index("CaseID")["VariantID"]
    flow_source = transitions.copy()
    flow_source["VariantID"] = flow_source["CaseID"].map(case_lookup)
    case_variant_ids = dict(zip(case_paths["CaseID"], case_paths["VariantID"]))
    path_start = pd.DataFrame(
        {
            "CaseID": case_paths["CaseID"],
            "FromActivity": "Start",
            "ToActivity": case_paths["Path"].map(lambda path: path[0]),
            "TransitionSequence": 0,
            "VariantID": case_paths["VariantID"],
        }
    )
    path_end = pd.DataFrame(
        {
            "CaseID": case_paths["CaseID"],
            "FromActivity": case_paths["Path"].map(lambda path: path[-1]),
            "ToActivity": "End",
            "TransitionSequence": case_paths["Path"].map(len),
            "VariantID": case_paths["VariantID"],
        }
    )
    flow_source = pd.concat(
        [
            flow_source[
                ["CaseID", "FromActivity", "ToActivity", "TransitionSequence", "VariantID"]
            ],
            path_start,
            path_end,
        ],
        ignore_index=True,
    )
    flows = (
        flow_source.groupby(
            ["VariantID", "FromActivity", "ToActivity", "TransitionSequence"],
            as_index=False,
        )
        .agg(FlowCount=("CaseID", "nunique"))
        .rename(
            columns={
                "FromActivity": "Source",
                "ToActivity": "Target",
                "TransitionSequence": "StageOrder",
            }
        )
    )
    flows["Variant"] = flows["VariantID"].map(
        frequency.set_index("VariantID")["Variant"]
    )
    return frequency, flows, variant_dimension, case_variant_ids


def _summary_tables(
    events: pd.DataFrame, cases: pd.DataFrame, transitions: pd.DataFrame, risk_threshold: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stage = (
        events.groupby(["Activity", "Department"], as_index=False)
        .agg(
            EventCount=("EventID", "count"),
            AvgDurationHours=("ActivityDurationHours", "mean"),
            AvgWaitHours=("WaitHours", "mean"),
            TotalWaitHours=("WaitHours", "sum"),
        )
        .sort_values(["Activity", "Department"])
    )
    total_case_time = cases["DurationHours"].sum()
    bottlenecks = (
        transitions.groupby(["ToActivity", "WaitCategory"], as_index=False)
        .agg(
            TransitionCount=("CaseID", "count"),
            AvgWaitHours=("WaitHours", "mean"),
            TotalWaitHours=("WaitHours", "sum"),
            DiagnosticWaitCount=("IsDiagnosticWait", "sum"),
        )
        .rename(columns={"ToActivity": "ProcessStep"})
    )
    bottlenecks["PctOfTotalCaseTime"] = (
        bottlenecks["TotalWaitHours"] / total_case_time * 100
        if total_case_time
        else 0
    )
    bottlenecks["RiskStatus"] = bottlenecks["AvgWaitHours"].map(
        lambda value: "High" if value >= risk_threshold else "Review"
    )
    bottlenecks.loc[bottlenecks["AvgWaitHours"] == 0, "RiskStatus"] = "Low"
    return stage.reset_index(drop=True), bottlenecks.sort_values(
        "AvgWaitHours", ascending=False
    ).reset_index(drop=True)


def _dimension_tables(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    activities = (
        events[["Activity", "EventSequence"]]
        .groupby("Activity", as_index=False)["EventSequence"]
        .min()
        .sort_values(["EventSequence", "Activity"])
        .reset_index(drop=True)
        .rename(columns={"EventSequence": "StageOrder"})
    )
    dates = pd.Series(events["StartTimestamp"].dt.date.unique()).sort_values()
    date_range = pd.date_range(min(dates), max(dates), freq="D")
    calendar = pd.DataFrame({"Date": date_range.date})
    calendar["Year"] = date_range.year
    calendar["MonthNumber"] = date_range.month
    calendar["MonthName"] = date_range.strftime("%B")
    calendar["YearMonth"] = date_range.strftime("%Y-%m")
    calendar["DayOfWeekNumber"] = date_range.dayofweek + 1
    calendar["DayOfWeekName"] = date_range.day_name()
    calendar["WeekdayName"] = calendar["DayOfWeekName"]

    def dim_name(field: str) -> pd.DataFrame:
        return (
            events[[field]]
            .drop_duplicates()
            .sort_values(field)
            .reset_index(drop=True)
        )

    return {
        "DimDate": calendar,
        "DimActivity": activities[["Activity", "StageOrder"]],
        "DimDepartment": dim_name("Department"),
        "DimDiagnosis": dim_name("Diagnosis"),
        "DimResource": dim_name("Resource"),
    }


def build_tables(
    event_path: str | Path,
    case_metadata_path: str | Path | None = None,
    risk_threshold_hours: float = 1.0,
) -> dict[str, pd.DataFrame]:
    """Return all normalized fact and dimension tables."""
    if not math.isfinite(risk_threshold_hours) or risk_threshold_hours < 0:
        raise ValueError("Risk threshold must be a finite number zero or greater.")

    events = load_events(event_path)
    metadata = _read_case_metadata(case_metadata_path, events)
    fact_events, transitions = _event_tables(events)
    cases = _case_table(events, metadata)
    variants, flows, variant_dimension, case_variant_ids = _variant_tables(
        events, transitions
    )
    cases["VariantID"] = cases["CaseID"].map(case_variant_ids)
    stage_metrics, bottlenecks = _summary_tables(
        fact_events, cases, transitions, risk_threshold_hours
    )
    tables = {
        "Events": fact_events,
        "Cases": cases,
        "Transitions": transitions,
        "StageMetrics": stage_metrics,
        "Bottlenecks": bottlenecks,
        "DimVariant": variant_dimension,
        "VariantFrequency": variants,
        "VariantFlows": flows,
        **_dimension_tables(events),
    }
    return {name: tables[name] for name in OUTPUT_TABLES}


def export_tables(
    tables: dict[str, pd.DataFrame], output_dir: str | Path, file_format: str = "csv"
) -> list[Path]:
    """Export all tables in CSV, Parquet, or both formats."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if file_format in {"parquet", "both"}:
        try:
            import pyarrow  # noqa: F401
        except ImportError as error:
            raise RuntimeError(
                "Parquet output requires pyarrow; install it with "
                "`python -m pip install pyarrow` or use --format csv."
            ) from error

    output_paths: list[Path] = []
    formats = ("csv", "parquet") if file_format == "both" else (file_format,)
    for name, table in tables.items():
        for extension in formats:
            path = output_dir / f"{name}.{extension}"
            if extension == "csv":
                table.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
            else:
                table.to_parquet(path, index=False)
            output_paths.append(path)
    return output_paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/event_log.csv", help="Raw event-log CSV.")
    parser.add_argument(
        "--case-metadata",
        default=None,
        help="Optional case-level metadata CSV.",
    )
    parser.add_argument("--output-dir", default="data/processed", help="Output directory.")
    parser.add_argument(
        "--format", choices=("csv", "parquet", "both"), default="csv"
    )
    parser.add_argument(
        "--risk-threshold-hours",
        type=float,
        default=1.0,
        help="Operational reporting threshold; set locally, not a clinical guideline.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tables = build_tables(
        args.input,
        case_metadata_path=args.case_metadata,
        risk_threshold_hours=args.risk_threshold_hours,
    )
    paths = export_tables(tables, args.output_dir, args.format)
    print(f"Processed {len(tables['Events']):,} events across {len(tables['Cases']):,} cases.")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
