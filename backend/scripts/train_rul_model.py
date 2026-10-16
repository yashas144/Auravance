from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

import pump_prognostics_data as pump


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the pump remaining-useful-life regressor.")
    parser.add_argument("--input", type=Path, default=pump.DEFAULT_INPUT)
    parser.add_argument(
        "--output",
        type=Path,
        default=pump.BACKEND_DIR / "artifacts" / "models" / "rul_gradient_boosting.joblib",
    )
    return parser.parse_args()


def make_estimator() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(**pump.MODEL_PARAMS)


def leave_one_failure_out(data: pump.PumpPrognosticsData) -> tuple[dict[str, float], list[dict]]:
    """Score every failure cycle with a model that never saw it."""
    known = data.rul_known
    predictions, folds = pump.cross_fit(
        data,
        make_estimator,
        data.rul_hours,
        known,
        lambda estimator, features: estimator.predict(features),
    )

    scored = known & ~np.isnan(predictions)
    actual = data.rul_hours[scored]
    predicted = np.clip(predictions[scored], 0.0, pump.RUL_CAP_HOURS)
    metrics = {
        "loo_mae_hours": round(float(mean_absolute_error(actual, predicted)), 2),
        "constant_baseline_mae_hours": round(float(mean_absolute_error(actual, np.full(len(actual), actual.mean()))), 2),
    }
    for name, mask in pump.horizon_buckets(data).items():
        bucket = mask & scored
        metrics[f"loo_mean_prediction_hours_{name}"] = round(float(np.clip(predictions[bucket], 0, None).mean()), 1)
        metrics[f"actual_mean_hours_{name}"] = round(float(data.rul_hours[bucket].mean()), 1)
    return metrics, folds


def train(args: argparse.Namespace) -> dict[str, object]:
    data = pump.load(args.input)
    metrics, folds = leave_one_failure_out(data)
    known = data.rul_known
    estimator = make_estimator().fit(data.features[known], data.rul_hours[known])

    artifact: dict[str, object] = {
        "artifact_schema_version": 1,
        "task": "rul_regression",
        "model_version": "rul-hgb-pump-v2.1.0",
        "algorithm": "HistGradientBoostingRegressor",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "pump_sensor/sensor_processed.csv",
        "target": f"hours until the next BROKEN event, capped at {pump.RUL_CAP_HOURS:.0f}h; 0 while down",
        "target_unit": "hours",
        "rul_cap_hours": pump.RUL_CAP_HOURS,
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
