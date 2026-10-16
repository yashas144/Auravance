"""Train anomaly, failure and RUL models for one equipment profile.

Profiles (real datasets, real units, no rescaling):
  compressor - MetroPT-3 metro air compressor, 5-minute averages, 4 air leaks
  motor      - NASA/IMS motor-driven bearing rig, 3 run-to-failure tests

Every profile follows the pump models' method: an Isolation Forest fitted on
healthy operation, plus failure/RUL gradient-boosting models evaluated
leave-one-failure-out. The fold models are stored too, so replayed historical
readings are always scored by a model that never saw that failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, IsolationForest
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.anomaly import TELEMETRY_FIELDS  # noqa: E402
from app.services.ml_estimators import SuddenFailureClassifier, SuddenFailureLifeRegressor  # noqa: E402
from app.services.model_profiles import PROFILE_DATASETS, artifact_paths  # noqa: E402


FAILURE_HORIZON_HOURS = 72.0
RUL_CAP_HOURS = 240.0
RANDOM_STATE = 42


@dataclass(slots=True)
class LabeledData:
    feature_names: list[str]
    values: np.ndarray  # real units, one column per feature
    timestamps: np.ndarray  # "YYYY-MM-DD HH:MM:SS"
    down: np.ndarray
    hours_to_failure: np.ndarray
    known: np.ndarray  # label is defined (not censored by the end of the recording)
    group: np.ndarray  # failure cycle
    failure_times: list[str]
    source_dataset: str


def _cycle_labels(times: pd.Series, down: np.ndarray, failure_starts: list[pd.Timestamp], end: pd.Timestamp):
    starts = np.array(failure_starts, dtype="datetime64[ns]")
    stamps = times.to_numpy(dtype="datetime64[ns]")
    next_index = np.searchsorted(starts, stamps, side="left")
    hours = np.full(len(times), np.inf)
    has_next = next_index < len(starts)
    hours[has_next] = (starts[next_index[has_next]] - stamps[has_next]) / np.timedelta64(1, "h")
    hours[down] = 0.0
    group = next_index.copy()
    # Rows during a failure belong to the failure that is in progress.
    group[down] = np.searchsorted(starts, stamps[down], side="right") - 1
    hours_to_end = (np.datetime64(end) - stamps) / np.timedelta64(1, "h")
    known = has_next | down | (hours_to_end >= RUL_CAP_HOURS)
    return hours, group, known


def load_compressor() -> LabeledData:
    frame = pd.read_csv(BACKEND_DIR / "data" / "processed" / "metropt3" / "metropt3_5min.csv")
    times = pd.to_datetime(frame["source_timestamp"])
    down = (frame["machine_status"] == "AIR_LEAK").to_numpy()
    leak_starts = times[down & ~np.roll(down, 1)].tolist()
    hours, group, known = _cycle_labels(times, down, leak_starts, times.max())
    return LabeledData(
        feature_names=["temperature", "pressure", "current"],
        values=frame[["oil_temperature_c", "tp3_bar", "motor_current_a"]].to_numpy(dtype=np.float64),
        timestamps=frame["source_timestamp"].to_numpy(),
        down=down,
        hours_to_failure=hours,
        known=known,
        group=group,
        failure_times=[str(start) for start in leak_starts],
        source_dataset="metropt3/metropt3_5min.csv",
    )


def load_motor() -> LabeledData:
    frame = pd.read_csv(BACKEND_DIR / "data" / "processed" / "ims_bearings" / "ims_features.csv")
    frame["max_bearing_rms"] = frame.filter(regex=r"bearing_\d_rms").max(axis=1)
    times = pd.to_datetime(frame["source_timestamp"])
    test_end = times.groupby(frame["test_id"]).transform("max")
    hours = ((test_end - times).dt.total_seconds() / 3600).to_numpy()
    down = hours == 0  # the final snapshot of each run-to-failure test
    return LabeledData(
        feature_names=["vibration"],
        values=frame[["max_bearing_rms"]].to_numpy(dtype=np.float64),
        timestamps=frame["source_timestamp"].to_numpy(),
        down=down,
        hours_to_failure=hours,
        known=np.ones(len(frame), dtype=bool),
        group=pd.factorize(frame["test_id"])[0],
        failure_times=sorted(frame.loc[down, "source_timestamp"].tolist()),
        source_dataset="ims_bearings/ims_features.csv",
    )


LOADERS = {"compressor": load_compressor, "motor": load_motor}
# "sudden": failures start without a measurable precursor (MetroPT-3 air leaks), so
#   the models learn "failure in progress" and add the empirical base rate.
# "degradation": the signal drifts towards failure (IMS bearing wear), so the
#   models learn the 72 h / hours-to-failure targets directly.
FAILURE_STRATEGY = {"compressor": "sudden", "motor": "degradation"}


def runtime_profile(data: LabeledData, healthy: np.ndarray) -> dict[str, dict[str, float]]:
    profile = {}
    for column, name in enumerate(data.feature_names):
        values = data.values[healthy, column]
        median = float(np.median(values))
        iqr = float(np.quantile(values, 0.75) - np.quantile(values, 0.25))
        profile[name] = {"center": round(median, 6), "scale": round(iqr if iqr > 1e-9 else 1.0, 6)}
    return profile


def standardise(data: LabeledData, profile: dict) -> np.ndarray:
    centers = np.array([profile[name]["center"] for name in data.feature_names])
    scales = np.array([profile[name]["scale"] for name in data.feature_names])
    return (data.values - centers) / scales


def buckets(data: LabeledData) -> dict[str, np.ndarray]:
    up = ~data.down
    hours = data.hours_to_failure
    return {
        "down": data.down,
        "under_24h": up & (hours < 24),
        "24_to_72h": up & (hours >= 24) & (hours < 72),
        "over_72h": up & (hours >= 72),
    }


def save(path: Path, artifact: dict, extra_metadata: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    metadata = {key: value for key, value in artifact.items() if key not in {"estimator", "fold_models"}}
    if "fold_models" in artifact:
        metadata["fold_held_out_ranges"] = [[f["held_out_start"], f["held_out_end"]] for f in artifact["fold_models"]]
    metadata.update(extra_metadata or {})
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def train(profile_name: str) -> dict[str, object]:
    data = LOADERS[profile_name]()
    dataset = PROFILE_DATASETS[profile_name]
    paths = artifact_paths(profile_name)
    trained_at = datetime.now(timezone.utc).isoformat()
    healthy = ~data.down & (data.hours_to_failure > FAILURE_HORIZON_HOURS)
    profile = runtime_profile(data, healthy)
    features = standardise(data, profile)
    common = {
        "artifact_schema_version": 1,
        "profile": profile_name,
        "trained_at": trained_at,
        "source_dataset": data.source_dataset,
        "feature_names": data.feature_names,
        "telemetry_fields": [TELEMETRY_FIELDS[name] for name in data.feature_names],
        "runtime_profile": profile,
        "failures": data.failure_times,
        "fold_dataset": dataset,
    }
    # Small trees with large leaves so the few failures can't simply be memorised;
    # leaves must still be smaller than one failure's worth of rows.
    leaf = max(20, min(int(data.known.sum()) // 50, int(data.down.sum()) // 4))
    params = {"learning_rate": 0.05, "max_iter": 100, "max_leaf_nodes": 8, "min_samples_leaf": leaf, "random_state": RANDOM_STATE}

    # Anomaly: Isolation Forest on healthy operation only.
    forest = IsolationForest(n_estimators=250, contamination="auto", random_state=RANDOM_STATE, n_jobs=-1)
    forest.fit(features[healthy])
    scores = -forest.decision_function(features)
    healthy_scores = scores[healthy]
    warning, high = float(np.quantile(healthy_scores, 0.99)), float(np.quantile(healthy_scores, 0.999))
    anomaly_metrics = {
        "down_vs_healthy_roc_auc": round(float(roc_auc_score(data.down[healthy | data.down], scores[healthy | data.down])), 4),
        "healthy_flag_rate": round(float((healthy_scores >= warning).mean()), 4),
        "down_flag_rate": round(float((scores[data.down] >= warning).mean()), 4),
    }
    save(
        paths["anomaly"],
        {
            **common,
            "model_version": f"isolation-forest-{profile_name}-v1.0.0",
            "algorithm": "IsolationForest",
            "thresholds": {"warning": warning, "high": max(high, warning + 1e-6)},
            "score_calibration": {
                "healthy_center": float(np.median(healthy_scores)),
                "observed_max": float(max(np.quantile(scores, 0.999), high + 1e-6)),
            },
            "metrics": anomaly_metrics,
            "estimator": forest,
        },
    )

    target = (data.down | (data.hours_to_failure < FAILURE_HORIZON_HOURS)).astype(int)
    rul = np.minimum(data.hours_to_failure, RUL_CAP_HOURS)
    strategy = FAILURE_STRATEGY[profile_name]

    if strategy == "sudden":
        def make_classifier(train: np.ndarray):
            in_failure = HistGradientBoostingClassifier(**params).fit(features[train], data.down[train].astype(int))
            up = train & ~data.down & data.known
            return SuddenFailureClassifier(in_failure, base_rate=target[up].mean())

        def make_regressor(train: np.ndarray):
            in_failure = HistGradientBoostingClassifier(**params).fit(features[train], data.down[train].astype(int))
            up = train & ~data.down & data.known
            return SuddenFailureLifeRegressor(in_failure, mean_healthy_hours=rul[up].mean())
    else:
        def make_classifier(train: np.ndarray):
            return HistGradientBoostingClassifier(**params).fit(features[train], target[train])

        def make_regressor(train: np.ndarray):
            return HistGradientBoostingRegressor(**params).fit(features[train], rul[train])

    def cross_fit_models(make, predict):
        out_of_fold = np.full(len(features), np.nan)
        folds = []
        for group in np.unique(data.group):
            held_out = data.group == group
            estimator = make(~held_out & data.known)
            out_of_fold[held_out] = predict(estimator, features[held_out])
            times = data.timestamps[held_out]
            folds.append({"held_out_start": str(times.min()), "held_out_end": str(times.max()), "estimator": estimator})
        return out_of_fold, folds

    probabilities, folds = cross_fit_models(make_classifier, lambda e, x: e.predict_proba(x)[:, 1])
    scored = data.known & ~np.isnan(probabilities)
    failure_metrics = {
        "loo_roc_auc": round(float(roc_auc_score(target[scored], probabilities[scored])), 4),
        "loo_average_precision": round(float(average_precision_score(target[scored], probabilities[scored])), 4),
        "loo_failure_in_progress_roc_auc": round(float(roc_auc_score(data.down[scored], probabilities[scored])), 4),
        "positive_rate": round(float(target[scored].mean()), 4),
        **{f"loo_mean_probability_{name}": round(float(np.nanmean(probabilities[mask & scored])), 4) for name, mask in buckets(data).items() if (mask & scored).any()},
    }
    save(
        paths["failure"],
        {
            **common,
            "task": "failure_classification",
            "model_version": f"failure-hgb-{profile_name}-v1.0.0",
            "algorithm": "HistGradientBoostingClassifier",
            "strategy": strategy,
            "target": f"failure in progress now or within {FAILURE_HORIZON_HOURS:.0f}h",
            "evaluation": "leave-one-failure-out",
            "metrics": failure_metrics,
            "estimator": make_classifier(data.known.copy()),
            "fold_models": folds,
        },
    )

    predictions, folds = cross_fit_models(make_regressor, lambda e, x: e.predict(x))
    scored = data.known & ~np.isnan(predictions)
    clipped = np.clip(predictions, 0, RUL_CAP_HOURS)
    rul_metrics = {
        "loo_mae_hours": round(float(mean_absolute_error(rul[scored], clipped[scored])), 2),
        "constant_baseline_mae_hours": round(float(mean_absolute_error(rul[scored], np.full(scored.sum(), rul[scored].mean()))), 2),
        **{f"loo_mean_prediction_hours_{name}": round(float(clipped[mask & scored].mean()), 1) for name, mask in buckets(data).items() if (mask & scored).any()},
    }
    save(
        paths["rul"],
        {
            **common,
            "task": "rul_regression",
            "model_version": f"rul-hgb-{profile_name}-v1.0.0",
            "algorithm": "HistGradientBoostingRegressor" if strategy == "degradation" else "HistGradientBoostingClassifier",
            "strategy": strategy,
            "target": f"hours until the next failure, capped at {RUL_CAP_HOURS:.0f}h; 0 during a failure",
            "target_unit": "hours",
            "rul_cap_hours": RUL_CAP_HOURS,
            "evaluation": "leave-one-failure-out",
            "metrics": rul_metrics,
            "estimator": make_regressor(data.known.copy()),
            "fold_models": folds,
        },
    )
    return {
        "profile": profile_name,
        "rows": int(len(data.values)),
        "failures": data.failure_times,
        "runtime_profile": profile,
        "anomaly": anomaly_metrics,
        "strategy": strategy,
        "failure": failure_metrics,
        "rul": rul_metrics,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("profile", choices=sorted(LOADERS))
    print(json.dumps(train(parser.parse_args().profile), indent=2))
