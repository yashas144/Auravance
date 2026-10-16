from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

import pump_prognostics_data as pump


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the pump failure-risk classifier.")
    parser.add_argument("--input", type=Path, default=pump.DEFAULT_INPUT)
    parser.add_argument(
        "--output",
        type=Path,
        default=pump.BACKEND_DIR / "artifacts" / "models" / "failure_gradient_boosting.joblib",
    )
    return parser.parse_args()


def make_estimator() -> HistGradientBoostingClassifier:
    # No class weighting: the output should stay a calibrated probability.
    return HistGradientBoostingClassifier(**pump.MODEL_PARAMS)


def leave_one_failure_out(data: pump.PumpPrognosticsData) -> tuple[dict[str, float], list[dict]]:
    """Score every failure cycle with a model that never saw it."""
    known = data.failure_label_known
    probabilities, folds = pump.cross_fit(
        data,
        make_estimator,
        data.failure_label,
        known,
        lambda estimator, features: estimator.predict_proba(features)[:, 1],
    )

    scored = known & ~np.isnan(probabilities)
    labels = data.failure_label[scored]
    metrics = {
        "loo_roc_auc": round(float(roc_auc_score(labels, probabilities[scored])), 4),
        "loo_average_precision": round(float(average_precision_score(labels, probabilities[scored])), 4),
        "positive_rate": round(float(labels.mean()), 4),
    }
    for name, mask in pump.horizon_buckets(data).items():
        metrics[f"loo_mean_probability_{name}"] = round(float(np.nanmean(probabilities[mask & scored])), 4)
    return metrics, folds


def train(args: argparse.Namespace) -> dict[str, object]:
    data = pump.load(args.input)
    metrics, folds = leave_one_failure_out(data)
    known = data.failure_label_known
    estimator = make_estimator().fit(data.features[known], data.failure_label[known])

    artifact: dict[str, object] = {
        "artifact_schema_version": 1,
        "task": "failure_classification",
        "model_version": "failure-hgb-pump-v2.1.0",
        "algorithm": "HistGradientBoostingClassifier",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "pump_sensor/sensor_processed.csv",
        "target": f"pump is BROKEN/RECOVERING now or breaks within {pump.FAILURE_HORIZON_HOURS}h",
        "evaluation": "leave-one-failure-out: each failure cycle scored by a model trained without it",
        "feature_names": data.feature_names,
        "source_columns": data.source_columns,
        "source_transform": data.source_transform,
        "runtime_profile": data.runtime_profile,
        "metrics": metrics,
        "training_rows": int(known.sum()),
        "failures": data.failure_times,
        "estimator": estimator,
        "fold_dataset": "kaggle-pump-sensor",
        "fold_models": folds,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    metadata = {key: value for key, value in artifact.items() if key not in {"estimator", "fold_models"}}
    metadata["fold_held_out_ranges"] = [[fold["held_out_start"], fold["held_out_end"]] for fold in folds]
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"artifact": str(args.output), **metadata}


if __name__ == "__main__":
    print(json.dumps(train(parse_args()), indent=2))
