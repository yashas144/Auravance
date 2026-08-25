from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.anomaly import FEATURE_NAMES, RUNTIME_PROFILE  # noqa: E402


SOURCE_COLUMNS = [
    "process_temperature_k",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]
TARGET = "machine_failure"
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the AI4I failure classifier.")
    parser.add_argument(
        "--input",
        type=Path,
        default=BACKEND_DIR / "data" / "processed" / "ai4i" / "ai4i2020_processed.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "artifacts" / "models" / "failure_gradient_boosting.joblib",
    )
    return parser.parse_args()


def train(args: argparse.Namespace) -> dict[str, object]:
    frame = pd.read_csv(args.input, usecols=[*SOURCE_COLUMNS, TARGET]).dropna()
    train_frame, test_frame = train_test_split(
        frame, test_size=0.2, random_state=RANDOM_STATE, stratify=frame[TARGET]
    )
    healthy = train_frame[train_frame[TARGET] == 0]
    medians = healthy[SOURCE_COLUMNS].median()
    scales = (healthy[SOURCE_COLUMNS].quantile(0.75) - healthy[SOURCE_COLUMNS].quantile(0.25)).replace(0, 1.0)

    def transform(rows: pd.DataFrame) -> np.ndarray:
        return ((rows[SOURCE_COLUMNS] - medians) / scales).to_numpy(dtype=np.float64)

    estimator = HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_iter=300,
        max_leaf_nodes=31,
        l2_regularization=0.2,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )
    estimator.fit(transform(train_frame), train_frame[TARGET].to_numpy())
    probabilities = estimator.predict_proba(transform(test_frame))[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        test_frame[TARGET], predictions, average="binary", zero_division=0
    )
    metrics = {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(test_frame[TARGET], probabilities)), 4),
        "average_precision": round(float(average_precision_score(test_frame[TARGET], probabilities)), 4),
        "evaluation_rows": float(len(test_frame)),
    }
    artifact: dict[str, object] = {
        "artifact_schema_version": 1,
        "task": "failure_classification",
        "model_version": "failure-hgb-ai4i-v1.0.0",
        "algorithm": "HistGradientBoostingClassifier",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "ai4i/ai4i2020_processed.csv",
        "feature_names": FEATURE_NAMES,
        "source_columns": SOURCE_COLUMNS,
        "source_transform": {"medians": medians.to_dict(), "iqr_scales": scales.to_dict()},
        "runtime_profile": RUNTIME_PROFILE,
        "metrics": metrics,
        "training_rows": int(len(train_frame)),
        "failure_rows": int(frame[TARGET].sum()),
        "estimator": estimator,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    metadata = {key: value for key, value in artifact.items() if key != "estimator"}
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"artifact": str(args.output), **metadata}


if __name__ == "__main__":
    print(json.dumps(train(parse_args()), indent=2))
