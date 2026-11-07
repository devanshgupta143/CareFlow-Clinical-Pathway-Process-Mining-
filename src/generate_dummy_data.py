"""Generate deterministic synthetic clinical events and case outcomes."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


EVENT_COLUMNS = [
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
]

METADATA_COLUMNS = [
    "case_id",
    "total_length_of_stay_days",
    "total_process_time_hours",
    "is_readmitted",
    "patient_satisfaction_pct",
    "delayed_discharge_reason",
]

DEPARTMENTS = [
    "General Medicine",
    "Surgery",
    "Orthopedics",
    "Cardiology",
    "Gynecology",
    "Others",
]
DEPARTMENT_PROBABILITIES = [0.28, 0.22, 0.16, 0.12, 0.09, 0.13]

DIAGNOSES = [
    "Respiratory Infection",
    "Fracture",
    "Cardiovascular",
    "Diabetes",
    "Gastrointestinal",
    "Other",
]
DIAGNOSIS_PROBABILITIES = [0.18, 0.14, 0.12, 0.09, 0.07, 0.40]

STAGES = ["Admission", "Diagnosis", "Treatment", "Discharge"]
ACTIVITIES = [
    "Patient Admission",
    "Clinical Assessment",
    "Treatment",
    "Discharge",
]

DELAY_REASONS = [
    "Waiting for test results",
    "Bed availability",
    "Medication delay",
    "Patient refusal",
    "Others",
]
DELAY_REASON_PROBABILITIES = [0.32, 0.24, 0.18, 0.12, 0.14]

HOSPITALS = [
    "CareFlow Central Hospital",
    "CareFlow North Hospital",
    "CareFlow South Hospital",
]
HOSPITAL_PROBABILITIES = [0.50, 0.30, 0.20]

FIRST_NAMES = [
    "Avery", "Jordan", "Morgan", "Taylor", "Riley", "Casey", "Quinn",
    "Parker", "Rowan", "Cameron", "Dakota", "Reese", "Skyler", "Emerson",
    "Finley", "Hayden",
]
LAST_NAMES = [
    "Morgan", "Reed", "Parker", "Brooks", "Hayes", "Bennett", "Rivera",
    "Foster", "Ellis", "Carter", "Bailey", "Diaz", "Cole", "Murphy",
    "Turner", "Patel",
]

START_DATE = datetime(2025, 1, 1)
END_DATE = datetime(2025, 9, 30, 23, 59, 59)
TARGET_MEAN_LOS_DAYS = 4.2
TARGET_MEAN_PROCESS_HOURS = 18.6
TARGET_READMISSION_RATE = 0.063
TARGET_SATISFACTION_PCT = 92.0
TARGET_DELAY_RATE = 0.087


def _bounded_mean(
    values: np.ndarray,
    target: float,
    lower: float,
    upper: float,
) -> np.ndarray:
    """Shift and clip samples so their mean matches target within bounds."""
    low_shift = lower - float(np.max(values))
    high_shift = upper - float(np.min(values))
    for _ in range(80):
        shift = (low_shift + high_shift) / 2
        mean = float(np.clip(values + shift, lower, upper).mean())
        if mean < target:
            low_shift = shift
        else:
            high_shift = shift
    result = np.clip(values + (low_shift + high_shift) / 2, lower, upper)
    if not np.isclose(result.mean(), target, atol=1e-9):
        raise ValueError("Unable to calibrate generated values to the requested mean.")
    return result


def _allocate_counts(total: int, probabilities: list[float]) -> np.ndarray:
    expected = np.asarray(probabilities, dtype=float) * total
    counts = np.floor(expected).astype(int)
    remainder = total - int(counts.sum())
    if remainder:
        order = np.argsort(-(expected - counts))
        counts[order[:remainder]] += 1
    return counts


def _synthetic_names(count: int) -> list[str]:
    return [
        f"{FIRST_NAMES[index % len(FIRST_NAMES)]} "
        f"{LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]} "
        f"{index + 1:05d}"
        for index in range(count)
    ]


def generate_data(
    num_cases: int = 12_482,
    seed: int = 42,
    output_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate and write clinical_events.csv and case_metadata.csv.

    The default population is 12,482 synthetic encounters. Aggregate LOS,
    process time, readmission, and satisfaction values are calibrated to the
    requested dashboard benchmarks, while individual records remain varied.
    """
    if num_cases < 1:
        raise ValueError("num_cases must be at least 1.")

    rng = np.random.default_rng(seed)
    case_ids = [f"CF{index:06d}" for index in range(1, num_cases + 1)]

    los_samples = rng.normal(loc=4.2, scale=0.85, size=num_cases)
    los_samples += rng.gamma(shape=1.2, scale=0.20, size=num_cases) * (
        rng.random(num_cases) < TARGET_DELAY_RATE
    )
    los_days = _bounded_mean(los_samples, TARGET_MEAN_LOS_DAYS, 2.0, 8.0)

    process_samples = rng.gamma(shape=8.0, scale=2.3, size=num_cases)
    process_hours = _bounded_mean(
        process_samples,
        TARGET_MEAN_PROCESS_HOURS,
        6.0,
        36.0,
    )
    if np.any(process_hours >= los_days * 24):
        raise ValueError("Generated process time must be shorter than each case stay.")

    satisfaction_samples = rng.normal(
        loc=TARGET_SATISFACTION_PCT,
        scale=4.5,
        size=num_cases,
    )
    satisfaction = _bounded_mean(
        satisfaction_samples,
        TARGET_SATISFACTION_PCT,
        70.0,
        100.0,
    )

    readmitted = np.zeros(num_cases, dtype=bool)
    readmitted_count = round(num_cases * TARGET_READMISSION_RATE)
    readmitted[rng.choice(num_cases, size=readmitted_count, replace=False)] = True

    delayed = np.zeros(num_cases, dtype=bool)
    delayed_count = round(num_cases * TARGET_DELAY_RATE)
    delayed[rng.choice(num_cases, size=delayed_count, replace=False)] = True
    delayed_reasons = np.full(num_cases, "None", dtype=object)
    delayed_indexes = rng.permutation(np.flatnonzero(delayed))
    reason_counts = _allocate_counts(
        delayed_count,
        DELAY_REASON_PROBABILITIES,
    )
    offset = 0
    for reason, count in zip(DELAY_REASONS, reason_counts):
        selected = delayed_indexes[offset : offset + count]
        delayed_reasons[selected] = reason
        offset += count

    departments = rng.choice(
        DEPARTMENTS,
        size=num_cases,
        p=DEPARTMENT_PROBABILITIES,
    )
    diagnoses = rng.choice(
        DIAGNOSES,
        size=num_cases,
        p=DIAGNOSIS_PROBABILITIES,
    )
    hospitals = rng.choice(
        HOSPITALS,
        size=num_cases,
        p=HOSPITAL_PROBABILITIES,
    )
    patient_types = rng.choice(
        ["Emergency", "Elective"],
        size=num_cases,
        p=[0.58, 0.42],
    )
    names = _synthetic_names(num_cases)

    total_wait_hours = los_days * 24 - process_hours
    stage_process_shares = rng.dirichlet(
        alpha=np.array([1.5, 5.5, 22.0, 7.0]),
        size=num_cases,
    )
    normal_wait_shares = rng.dirichlet(
        alpha=np.array([3.0, 4.0, 6.0]),
        size=num_cases,
    )
    delayed_wait_shares = rng.dirichlet(
        alpha=np.array([1.5, 2.0, 10.0]),
        size=num_cases,
    )
    wait_shares = normal_wait_shares
    wait_shares[delayed] = delayed_wait_shares[delayed]
    stage_wait_hours = np.column_stack(
        [np.zeros(num_cases), total_wait_hours[:, None] * wait_shares]
    )
    stage_hours = process_hours[:, None] * stage_process_shares

    available_seconds = np.maximum(
        0,
        (END_DATE - START_DATE).total_seconds() - los_days * 24 * 3600,
    )
    start_offsets = (
        rng.random(num_cases) * np.asarray(available_seconds, dtype=float)
    ).astype(np.int64)
    case_starts = [
        START_DATE + timedelta(seconds=int(offset))
        for offset in start_offsets
    ]

    event_rows: list[dict[str, object]] = []
    for index, case_id in enumerate(case_ids):
        event_time = case_starts[index]
        for stage_index, (stage, activity) in enumerate(zip(STAGES, ACTIVITIES)):
            duration_hours = float(stage_hours[index, stage_index])
            wait_hours = float(stage_wait_hours[index, stage_index])
            event_rows.append(
                {
                    "case_id": case_id,
                    "patient_name": names[index],
                    "hospital": hospitals[index],
                    "department": departments[index],
                    "patient_type": patient_types[index],
                    "primary_diagnosis": diagnoses[index],
                    "event_activity": activity,
                    "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "stage": stage,
                    "wait_time_hours": wait_hours,
                    "process_time_hours": duration_hours,
                }
            )
            event_time += timedelta(hours=duration_hours + wait_hours)

    events = pd.DataFrame(event_rows, columns=EVENT_COLUMNS)
    metadata = pd.DataFrame(
        {
            "case_id": case_ids,
            "total_length_of_stay_days": los_days,
            "total_process_time_hours": process_hours,
            "is_readmitted": readmitted,
            "patient_satisfaction_pct": satisfaction,
            "delayed_discharge_reason": delayed_reasons,
        },
        columns=METADATA_COLUMNS,
    )

    destination = (
        Path(output_dir)
        if output_dir is not None
        else Path(__file__).resolve().parents[1] / "data"
    )
    destination.mkdir(parents=True, exist_ok=True)
    events.to_csv(
        destination / "clinical_events.csv",
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
        float_format="%.4f",
        encoding="utf-8",
    )
    metadata.to_csv(
        destination / "case_metadata.csv",
        index=False,
        float_format="%.4f",
        encoding="utf-8",
    )
    return events, metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic CareFlow event and case metadata CSVs."
    )
    parser.add_argument(
        "--cases",
        type=int,
        default=12_482,
        help="Number of encounters to generate (default: 12482).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible output (default: 42).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: repository data directory).",
    )
    args = parser.parse_args()
    events, metadata = generate_data(args.cases, args.seed, args.output_dir)
    output_dir = args.output_dir or Path(__file__).resolve().parents[1] / "data"
    print(f"Generated {len(metadata):,} cases and {len(events):,} events.")
    print(f"Events: {output_dir / 'clinical_events.csv'}")
    print(f"Metadata: {output_dir / 'case_metadata.csv'}")
    print(
        "Benchmarks: "
        f"LOS={metadata['total_length_of_stay_days'].mean():.2f} days, "
        f"process={metadata['total_process_time_hours'].mean():.2f} hours, "
        f"readmission={metadata['is_readmitted'].mean():.2%}, "
        f"satisfaction={metadata['patient_satisfaction_pct'].mean():.2f}%"
    )


if __name__ == "__main__":
    main()
