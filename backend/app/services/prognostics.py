from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import settings
from app.models.schemas import AnomalyModelStatusResponse, TelemetryRecord
from app.services.anomaly import FEATURE_NAMES, RUNTIME_PROFILE, TELEMETRY_FIELDS


@dataclass(slots=True)
class FailureInference:
    probability: float
    model_version: str


@dataclass(slots=True)
class RulInference:
    hours: float
    model_version: str


def _runtime_features(
    latest: TelemetryRecord,
    runtime_profile: dict[str, dict[str, float]],
) -> list[float]:
    values: list[float] = []
    for feature_name in FEATURE_NAMES:
        config = runtime_profile[feature_name]
        raw_value = getattr(latest, TELEMETRY_FIELDS[feature_name])
        value = float(config["center"]) if raw_value is None else float(raw_value)
        values.append(
            (value - float(config["center"])) / max(float(config["scale"]), 1e-9)
        )
    return values


class _ArtifactService:
    def __init__(self, artifact_path: str, expected_task: str, fallback_version: str) -> None:
        self._path = Path(artifact_path)
        self._expected_task = expected_task
        self._fallback_version = fallback_version
        self._artifact: dict[str, Any] | None = None
        self._load_error: str | None = None
        self._loaded_path: Path | None = None
        self._lock = Lock()

    def _load(self) -> dict[str, Any] | None:
        if self._loaded_path == self._path and (
            self._artifact is not None or self._load_error is not None
        ):
            return self._artifact

        with self._lock:
            if self._loaded_path == self._path and (
                self._artifact is not None or self._load_error is not None
            ):
                return self._artifact
            self._loaded_path = self._path
            self._artifact = None
            self._load_error = None
            if not self._path.exists():
                self._load_error = f"Model artifact not found: {self._path.name}"
                return None
            try:
                import joblib

                artifact = joblib.load(self._path)
                if artifact.get("artifact_schema_version") != 1:
                    raise ValueError("Unsupported model artifact schema.")
                if artifact.get("task") != self._expected_task:
                    raise ValueError("Model task does not match the inference service.")
                if artifact.get("feature_names") != FEATURE_NAMES:
                    raise ValueError("Model feature contract does not match live telemetry.")
                self._artifact = artifact
            except Exception as exc:  # Keep the API available when an artifact is invalid.
                self._load_error = f"Unable to load model artifact: {exc}"
            return self._artifact

    def status(self) -> AnomalyModelStatusResponse:
        artifact = self._load()
        if artifact is None:
            return AnomalyModelStatusResponse(
                loaded=False,
                artifact_exists=self._path.exists(),
                model_version=self._fallback_version,
                algorithm="rules-fallback",
                fallback_active=True,
                detail=self._load_error or "Trained model is unavailable.",
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
            detail="Trained model loaded and serving predictions.",
        )


class FailureModelService(_ArtifactService):
    def __init__(self) -> None:
        super().__init__(settings.failure_model_path, "failure_classification", "rules-failure-v1")

    def predict(self, telemetry: list[TelemetryRecord]) -> FailureInference | None:
        artifact = self._load()
        if artifact is None:
            return None
        features = _runtime_features(
            telemetry[-1], artifact.get("runtime_profile", RUNTIME_PROFILE)
        )
        probability = float(artifact["estimator"].predict_proba([features])[0, 1])
        return FailureInference(
            probability=round(min(0.99, max(0.01, probability)), 4),
            model_version=str(artifact["model_version"]),
        )


class RulModelService(_ArtifactService):
    def __init__(self) -> None:
        super().__init__(settings.rul_model_path, "rul_regression", "rules-rul-v1")

    def predict(self, telemetry: list[TelemetryRecord]) -> RulInference | None:
        artifact = self._load()
        if artifact is None:
            return None
        features = _runtime_features(
            telemetry[-1], artifact.get("runtime_profile", RUNTIME_PROFILE)
        )
        cycles = float(artifact["estimator"].predict([features])[0])
        hours_per_cycle = float(artifact.get("hours_per_cycle", 2.0))
        raw_hours = cycles * hours_per_cycle
        # Constrain only out-of-domain extrapolation between C-MAPSS and the demo
        # telemetry contract; ordinary model estimates remain unchanged.
        severity = max(abs(value) for value in features)
        safety_envelope_hours = 250.0 / (1.0 + 0.8 * severity)
        hours = min(500.0, max(6.0, min(raw_hours, safety_envelope_hours)))
        return RulInference(hours=round(hours, 1), model_version=str(artifact["model_version"]))


failure_model_service = FailureModelService()
rul_model_service = RulModelService()
