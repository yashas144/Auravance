from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.anomaly import FEATURE_NAMES, RUNTIME_PROFILE  # noqa: E402


SOURCE_COLUMNS = ["sensor_2", "sensor_4", "sensor_11", "sensor_15"]
RANDOM_STATE = 42
RUL_CAP_CYCLES = 125


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the NASA C-MAPSS RUL model.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=BACKEND_DIR / "data" / "processed" / "c_mapss",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "artifacts" / "models" / "rul_gradient_boosting.joblib",
    )
    return parser.parse_args()


def load_training_data(input_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for subset in ("fd001", "fd002", "fd003", "fd004"):
        path = input_dir / f"train_{subset}.csv"
        frame = pd.read_csv(path, usecols=["unit_id", "cycle", *SOURCE_COLUMNS])
        frame["subset"] = subset
        maximum_cycle = frame.groupby("unit_id")["cycle"].transform("max")
        frame["rul_cycles"] = (maximum_cycle - frame["cycle"]).clip(upper=RUL_CAP_CYCLES)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def train(args: argparse.Namespace) -> dict[str, object]:
    frame = load_training_data(args.input_dir)
    engines = frame[["subset", "unit_id"]].drop_duplicates().sample(frac=1, random_state=RANDOM_STATE)
    test_engines = engines.groupby("subset", group_keys=False).sample(frac=0.2, random_state=RANDOM_STATE)
    test_keys = set(map(tuple, test_engines[["subset", "unit_id"]].to_numpy()))
    test_mask = np.array([(subset, unit_id) in test_keys for subset, unit_id in frame[["subset", "unit_id"]].to_numpy()])
    train_frame = frame[~test_mask]
    test_frame = frame[test_mask]

    medians = train_frame[SOURCE_COLUMNS].median()
    scales = (train_frame[SOURCE_COLUMNS].quantile(0.75) - train_frame[SOURCE_COLUMNS].quantile(0.25)).replace(0, 1.0)

    def transform(rows: pd.DataFrame) -> np.ndarray:
        return ((rows[SOURCE_COLUMNS] - medians) / scales).to_numpy(dtype=np.float64)

    estimator = HistGradientBoostingRegressor(
        learning_rate=0.06,
        max_iter=350,
        max_leaf_nodes=31,
        l2_regularization=0.3,
        random_state=RANDOM_STATE,
    )
    estimator.fit(transform(train_frame), train_frame["rul_cycles"].to_numpy())
    predicted = estimator.predict(transform(test_frame))
    actual = test_frame["rul_cycles"].to_numpy()
    metrics = {
        "mae_cycles": round(float(mean_absolute_error(actual, predicted)), 4),
        "rmse_cycles": round(float(mean_squared_error(actual, predicted) ** 0.5), 4),
        "r2": round(float(r2_score(actual, predicted)), 4),
        "evaluation_rows": float(len(test_frame)),
        "evaluation_engines": float(len(test_engines)),
    }
    artifact: dict[str, object] = {
        "artifact_schema_version": 1,
        "task": "rul_regression",
        "model_version": "rul-hgb-cmapss-v1.0.0",
        "algorithm": "HistGradientBoostingRegressor",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "c_mapss/train_fd001-fd004.csv",
        "feature_names": FEATURE_NAMES,
        "source_columns": SOURCE_COLUMNS,
        "source_transform": {"medians": medians.to_dict(), "iqr_scales": scales.to_dict()},
        "runtime_profile": RUNTIME_PROFILE,
        "rul_cap_cycles": RUL_CAP_CYCLES,
        "hours_per_cycle": 2.0,
        "deployment_safety_envelope": "min(model_hours, 250 / (1 + 0.8 * max_abs_runtime_z))",
        "metrics": metrics,
        "training_rows": int(len(train_frame)),
        "training_engines": int(len(engines) - len(test_engines)),
        "estimator": estimator,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, args.output)
    metadata = {key: value for key, value in artifact.items() if key != "estimator"}
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"artifact": str(args.output), **metadata}


if __name__ == "__main__":
    print(json.dumps(train(parse_args()), indent=2))
