"""Shared labelling for the pump-trained failure and RUL models.

Both models use the anomaly model's feature transform, so all three see the same
z-scored features that live telemetry produces at serving time.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.anomaly import FEATURE_NAMES, RUNTIME_PROFILE  # noqa: E402


DEFAULT_INPUT = BACKEND_DIR / "data" / "processed" / "pump_sensor" / "sensor_processed.csv"
ANOMALY_METADATA = BACKEND_DIR / "artifacts" / "models" / "anomaly_isolation_forest.json"
FAILURE_HORIZON_HOURS = 72
RUL_CAP_HOURS = 240.0
RANDOM_STATE = 42


@dataclass(slots=True)
class PumpPrognosticsData:
    features: np.ndarray
    down: np.ndarray  # BROKEN or RECOVERING
    hours_to_failure: np.ndarray  # inf when no later failure is recorded
    failure_label: np.ndarray
    failure_label_known: np.ndarray
    rul_hours: np.ndarray
    rul_known: np.ndarray
    group: np.ndarray  # index of the next failure; rows after the last failure form their own group
    timestamps: np.ndarray
    failure_times: list[str]
    source_columns: list[str]
    source_transform: dict[str, dict[str, float]]

    @property
    def runtime_profile(self) -> dict:
        return RUNTIME_PROFILE

    @property
    def feature_names(self) -> list[str]:
        return FEATURE_NAMES


def load(path: Path = DEFAULT_INPUT) -> PumpPrognosticsData:
    metadata = json.loads(ANOMALY_METADATA.read_text(encoding="utf-8"))
    columns = metadata["source_columns"]
    medians = pd.Series(metadata["source_transform"]["medians"])
    scales = pd.Series(metadata["source_transform"]["iqr_scales"])

    frame = pd.read_csv(path, usecols=["timestamp", *columns, "machine_status"])
    status = frame["machine_status"].str.strip().str.upper().to_numpy()
    features = ((frame[columns].fillna(medians) - medians) / scales).to_numpy(dtype=np.float64)

    rows = len(frame)
    positions = np.arange(rows)
    failures = np.flatnonzero(status == "BROKEN")
    next_failure = np.full(rows, -1)
    upcoming = -1
    for index in range(rows - 1, -1, -1):
        if status[index] == "BROKEN":
            upcoming = index
        next_failure[index] = upcoming

    down = status != "NORMAL"
    hours_to_failure = np.where(next_failure >= 0, (next_failure - positions) / 60.0, np.inf)
    hours_to_end = (rows - 1 - positions) / 60.0

    # Target: the pump is down now or breaks within the horizon. Rows near the end
    # of the recording with no later failure are censored and left out.
    failure_label = (down | (hours_to_failure < FAILURE_HORIZON_HOURS)).astype(int)
    failure_label_known = (next_failure >= 0) | (hours_to_end >= FAILURE_HORIZON_HOURS) | down

    rul_hours = np.minimum(hours_to_failure, RUL_CAP_HOURS)
    rul_hours[down] = 0.0
    rul_known = (next_failure >= 0) | (hours_to_end >= RUL_CAP_HOURS) | down

    # Group by failure cycle; BROKEN/RECOVERING minutes belong to the failure they follow.
    group = np.searchsorted(failures, positions)
    group[down] = np.searchsorted(failures, positions[down], side="right") - 1

    return PumpPrognosticsData(
        features=features,
        down=down,
        hours_to_failure=hours_to_failure,
        failure_label=failure_label,
        failure_label_known=failure_label_known,
        rul_hours=rul_hours,
        rul_known=rul_known,
        group=group,
        timestamps=frame["timestamp"].to_numpy(),
        failure_times=frame["timestamp"].iloc[failures].tolist(),
        source_columns=columns,
        source_transform={"medians": medians.to_dict(), "iqr_scales": scales.to_dict()},
    )


MODEL_PARAMS = {
    # Small trees with large leaves: 7 failures are too few for deeper models,
    # which memorise each pre-failure period instead of learning a pattern.
    "learning_rate": 0.05,
    "max_iter": 100,
    "max_leaf_nodes": 8,
    "min_samples_leaf": 2000,
    "random_state": RANDOM_STATE,
}


def cross_fit(data: PumpPrognosticsData, make_estimator, target: np.ndarray, known: np.ndarray, predict):
    """Fit one model per failure cycle, each trained without that cycle.

    Returns out-of-fold predictions for every row, plus the fold models with the
    recorded time range they were held out on. The API serves replayed historical
    readings with the matching fold model, so the replay never shows a model
    scoring data it was trained on.
    """
    out_of_fold = np.full(len(data.features), np.nan)
    folds: list[dict] = []
    for group in np.unique(data.group):
        held_out = data.group == group
        train = ~held_out & known
        estimator = make_estimator().fit(data.features[train], target[train])
        out_of_fold[held_out] = predict(estimator, data.features[held_out])
        held_out_times = data.timestamps[held_out]
        folds.append(
            {
                "held_out_start": str(held_out_times[0]),
                "held_out_end": str(held_out_times[-1]),
                "estimator": estimator,
            }
        )
    return out_of_fold, folds


def horizon_buckets(data: PumpPrognosticsData) -> dict[str, np.ndarray]:
    up = ~data.down
    hours = data.hours_to_failure
    return {
        "down": data.down,
        "under_24h": up & (hours < 24),
        "24_to_72h": up & (hours >= 24) & (hours < 72),
        "3_to_7d": up & (hours >= 72) & (hours < 168),
        "over_7d": up & (hours >= 168),
    }
