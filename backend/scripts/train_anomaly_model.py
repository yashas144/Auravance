from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.anomaly import FEATURE_NAMES, RUNTIME_PROFILE  # noqa: E402


SOURCE_COLUMNS = ["sensor_04", "sensor_00", "sensor_01", "sensor_02"]
STATUS_COLUMN = "machine_status"
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the Auravance Isolation Forest baseline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=BACKEND_DIR / "data" / "processed" / "pump_sensor" / "sensor_processed.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "artifacts" / "models" / "anomaly_isolation_forest.joblib",
    )
    parser.add_argument("--max-normal-rows", type=int, default=100_000)
    parser.add_argument("--estimators", type=int, default=250)
    return parser.parse_args()


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Processed pump dataset not found: {path}")
    frame = pd.read_csv(path, usecols=[*SOURCE_COLUMNS, STATUS_COLUMN])
    frame[STATUS_COLUMN] = frame[STATUS_COLUMN].str.strip().str.upper()
    return frame


def robust_transform(frame: pd.DataFrame, medians: pd.Series, scales: pd.Series) -> np.ndarray:
    numeric = frame[SOURCE_COLUMNS].fillna(medians)
    return ((numeric - medians) / scales).to_numpy(dtype=np.float64)


def train(args: argparse.Namespace) -> dict[str, object]:
    frame = load_dataset(args.input)
    normal = frame[frame[STATUS_COLUMN] == "NORMAL"]
    abnormal = frame[frame[STATUS_COLUMN] != "NORMAL"]
    if normal.empty or abnormal.empty:
        raise ValueError("Training requires both NORMAL and non-NORMAL pump records.")

    normal_train = normal.sample(
        n=min(args.max_normal_rows, len(normal)),
        random_state=RANDOM_STATE,
    )
    normal_evaluation = normal.drop(normal_train.index).sample(
        n=min(25_000, max(1, len(normal) - len(normal_train))),
        random_state=RANDOM_STATE,
    )

    medians = normal_train[SOURCE_COLUMNS].median()
    lower_quartile = normal_train[SOURCE_COLUMNS].quantile(0.25)
    upper_quartile = normal_train[SOURCE_COLUMNS].quantile(0.75)
    scales = (upper_quartile - lower_quartile).replace(0, 1.0)

    train_features = robust_transform(normal_train, medians, scales)
    # The source labels contain shutdown-transition spikes marked NORMAL. Keep the
    # robust healthy envelope so those points do not teach the forest that extreme
    # deployment readings are ordinary operation.
    healthy_mask = (np.abs(train_features) <= 4.0).all(axis=1)
    train_features = train_features[healthy_mask]
    estimator = IsolationForest(
        n_estimators=args.estimators,
        max_samples="auto",
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    estimator.fit(train_features)

    normal_scores = -estimator.decision_function(train_features)
    evaluation_frame = pd.concat([normal_evaluation, abnormal], ignore_index=True)
    evaluation_features = robust_transform(evaluation_frame, medians, scales)
    evaluation_scores = -estimator.decision_function(evaluation_features)
    labels = (evaluation_frame[STATUS_COLUMN] != "NORMAL").astype(int).to_numpy()

    warning_threshold = float(np.quantile(normal_scores, 0.99))
    high_threshold = float(max(warning_threshold + 1e-6, np.quantile(normal_scores, 0.999)))
    predictions = (evaluation_scores >= warning_threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels,
        predictions,
        average="binary",
        zero_division=0,
    )
    metrics = {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(labels, evaluation_scores)), 4),
        "evaluation_rows": float(len(evaluation_frame)),
    }

    artifact: dict[str, object] = {
        "artifact_schema_version": 1,
        "model_version": "isolation-forest-pump-v1.0.0",
        "algorithm": "IsolationForest",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "pump_sensor/sensor_processed.csv",
        "feature_names": FEATURE_NAMES,
        "source_columns": SOURCE_COLUMNS,
        "source_transform": {
            "medians": medians.to_dict(),
            "iqr_scales": scales.to_dict(),
        },
        "runtime_profile": RUNTIME_PROFILE,
        "thresholds": {
            "warning": warning_threshold,
            "high": high_threshold,
        },
        "score_calibration": {
            "healthy_center": float(np.median(normal_scores)),
            "observed_max": float(max(np.quantile(evaluation_scores, 0.999), high_threshold + 1e-6)),
        },
        "metrics": metrics,
        "training_rows": int(len(train_features)),
        "normal_rows_excluded_as_transition_outliers": int((~healthy_mask).sum()),
        "status_counts": {key: int(value) for key, value in frame[STATUS_COLUMN].value_counts().items()},
        "estimator": estimator,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    metadata_path = args.output.with_suffix(".json")
    metadata = {key: value for key, value in artifact.items() if key != "estimator"}
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"artifact": str(args.output), "metadata": str(metadata_path), **metadata}


def main() -> None:
    result = train(parse_args())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
