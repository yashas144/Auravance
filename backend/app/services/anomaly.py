from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import settings
from app.models.schemas import AnomalyModelStatusResponse, TelemetryRecord


FEATURE_NAMES = ["temperature", "vibration", "pressure", "current"]
RUNTIME_PROFILE = {
    "temperature": {"center": 70.0, "scale": 8.0},
    "vibration": {"center": 0.30, "scale": 0.20},
    "pressure": {"center": 5.0, "scale": 0.80},
    "current": {"center": 9.0, "scale": 2.50},
}
TELEMETRY_FIELDS = {
    "temperature": "temperature_c",
    "vibration": "vibration_rms",
    "pressure": "pressure_bar",
    "current": "current_a",
}


@dataclass(slots=True)
class AnomalyInference:
    score: float
    label: str
    dominant_signal: str
    model_version: str


def valid_feature_names(names: object) -> bool:
    """Profiles may use any non-empty subset of the telemetry contract's features."""
    return isinstance(names, list) and bool(names) and all(name in TELEMETRY_FIELDS for name in names)


class AnomalyModelService:
    def __init__(self, artifact_path: Path | None = None) -> None:
        self._artifact_path = artifact_path
        self._artifact: dict[str, Any] | None = None
        self._load_error: str | None = None
        self._loaded_path: Path | None = None
        self._lock = Lock()

    @property
    def artifact_path(self) -> Path:
        return self._artifact_path or Path(settings.anomaly_model_path)

    def _load(self) -> dict[str, Any] | None:
        path = self.artifact_path
        if self._loaded_path == path and (self._artifact is not None or self._load_error is not None):
            return self._artifact

        with self._lock:
            if self._loaded_path == path and (
                self._artifact is not None or self._load_error is not None
            ):
                return self._artifact

            self._loaded_path = path
            self._artifact = None
            self._load_error = None
            if not path.exists():
                self._load_error = "Model artifact not found. Run scripts/train_anomaly_model.py."
                return None

            try:
                import joblib

                artifact = joblib.load(path)
                if artifact.get("artifact_schema_version") != 1:
                    raise ValueError("Unsupported anomaly model artifact schema.")
                if not valid_feature_names(artifact.get("feature_names")):
                    raise ValueError("Model feature contract does not match the API feature contract.")
                self._artifact = artifact
            except Exception as exc:  # Model loading must not prevent API startup.
                self._load_error = f"Unable to load model artifact: {exc}"
            return self._artifact

    def reload(self) -> None:
        with self._lock:
            self._artifact = None
            self._load_error = None
            self._loaded_path = None

    def predict(self, telemetry: list[TelemetryRecord]) -> AnomalyInference | None:
        artifact = self._load()
        if artifact is None:
            return None

        latest = telemetry[-1]
        profile = artifact.get("runtime_profile", RUNTIME_PROFILE)
        transformed: list[float] = []
        deviations: dict[str, float] = {}
        for feature_name in artifact["feature_names"]:
            config = profile[feature_name]
            raw_value = getattr(latest, TELEMETRY_FIELDS[feature_name])
            value = config["center"] if raw_value is None else float(raw_value)
            deviation = (value - config["center"]) / max(float(config["scale"]), 1e-9)
            transformed.append(deviation)
            deviations[feature_name] = abs(deviation)

        estimator = artifact["estimator"]
        raw_score = float(-estimator.decision_function([transformed])[0])
        warning_threshold = float(artifact["thresholds"]["warning"])
        high_threshold = float(artifact["thresholds"]["high"])
        healthy_center = float(artifact["score_calibration"]["healthy_center"])
        observed_max = float(artifact["score_calibration"]["observed_max"])
        score = self._calibrate_score(
            raw_score,
            healthy_center,
            warning_threshold,
            high_threshold,
            observed_max,
        )

        if raw_score >= high_threshold:
            label = "high-risk"
        elif raw_score >= warning_threshold:
            label = "warning"
        else:
            label = "normal"

        dominant_signal = max(deviations.items(), key=lambda item: item[1])[0]
        if artifact.get("profile", "pump") == "pump":
            # Pattern rules tuned to the pump telemetry scale.
            recent_pressure = [point.pressure_bar for point in telemetry if point.pressure_bar is not None]
            if len(recent_pressure) >= 3 and max(recent_pressure) - min(recent_pressure) > 1.2:
                dominant_signal = "pressure_instability"
            elif (
                latest.temperature_c is not None
                and latest.temperature_c > 85.0
                and latest.vibration_rms is not None
                and latest.vibration_rms > 0.70
            ):
                dominant_signal = "bearing_pattern"

        return AnomalyInference(
            score=round(score, 3),
            label=label,
            dominant_signal=dominant_signal,
            model_version=str(artifact["model_version"]),
        )

    @staticmethod
    def _calibrate_score(
        raw_score: float,
        healthy_center: float,
        warning_threshold: float,
        high_threshold: float,
        observed_max: float,
    ) -> float:
        if raw_score <= healthy_center:
            return 0.0
        if raw_score < warning_threshold:
            width = max(warning_threshold - healthy_center, 1e-9)
            return min(0.44, 0.44 * (raw_score - healthy_center) / width)
        if raw_score < high_threshold:
            width = max(high_threshold - warning_threshold, 1e-9)
            return 0.45 + 0.29 * (raw_score - warning_threshold) / width
        width = max(observed_max - high_threshold, 1e-9)
        return min(1.0, 0.75 + 0.25 * (raw_score - high_threshold) / width)

    def status(self) -> AnomalyModelStatusResponse:
        artifact = self._load()
        if artifact is None:
            return AnomalyModelStatusResponse(
                loaded=False,
                artifact_exists=self.artifact_path.exists(),
                model_version="demo-rules-0.1.0",
                algorithm="rules-fallback",
                fallback_active=True,
                detail=self._load_error or "Trained anomaly model is unavailable.",
            )

        return AnomalyModelStatusResponse(
            loaded=True,
            artifact_exists=True,
            model_version=str(artifact["model_version"]),
            algorithm=str(artifact["algorithm"]),
            trained_at=artifact.get("trained_at"),
            source_dataset=artifact.get("source_dataset"),
            feature_names=list(artifact["feature_names"]),
            metrics={key: float(value) for key, value in artifact.get("metrics", {}).items()},
            fallback_active=False,
            detail="Trained anomaly model loaded and serving predictions.",
        )


anomaly_model_service = AnomalyModelService()
