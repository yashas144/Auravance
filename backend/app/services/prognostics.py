from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import settings
from app.models.schemas import AnomalyModelStatusResponse, TelemetryRecord
from app.services.anomaly import FEATURE_NAMES, RUNTIME_PROFILE, TELEMETRY_FIELDS, valid_feature_names


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
    feature_names: list[str] = FEATURE_NAMES,
) -> list[float]:
    values: list[float] = []
    for feature_name in feature_names:
        config = runtime_profile[feature_name]
        raw_value = getattr(latest, TELEMETRY_FIELDS[feature_name])
        value = float(config["center"]) if raw_value is None else float(raw_value)
        values.append(
            (value - float(config["center"])) / max(float(config["scale"]), 1e-9)
        )
    return values


def _select_estimator(artifact: dict[str, Any], latest: TelemetryRecord) -> tuple[Any, str]:
    """Pick the model that never saw this reading.

    A replayed reading from the training recording is scored by the fold model
    that held out its failure cycle, so the replay shows honest held-out
    behaviour. Everything else (genuinely new data) uses the full model.
    """
    version = str(artifact["model_version"])
    context = latest.source_context
    recorded_at = context.get("source_timestamp")
    if context.get("dataset") == artifact.get("fold_dataset") and isinstance(recorded_at, str):
        for index, fold in enumerate(artifact.get("fold_models", [])):
            if fold["held_out_start"] <= recorded_at <= fold["held_out_end"]:
                return fold["estimator"], f"{version}+heldout-{index}"
    return artifact["estimator"], version


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
                if not valid_feature_names(artifact.get("feature_names")):
                    raise ValueError("Model feature contract does not match live telemetry.")
                if self._expected_task == "rul_regression" and artifact.get("target_unit") != "hours":
                    raise ValueError("RUL artifact predates v2 (cycles); retrain with scripts/train_rul_model.py.")
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
    def __init__(self, artifact_path: Path | str | None = None) -> None:
        super().__init__(artifact_path or settings.failure_model_path, "failure_classification", "rules-failure-v1")

    def predict(self, telemetry: list[TelemetryRecord]) -> FailureInference | None:
        artifact = self._load()
        if artifact is None:
            return None
        features = _runtime_features(
            telemetry[-1], artifact.get("runtime_profile", RUNTIME_PROFILE), artifact["feature_names"]
        )
        estimator, model_version = _select_estimator(artifact, telemetry[-1])
        probability = float(estimator.predict_proba([features])[0, 1])
        return FailureInference(
            probability=round(min(0.99, max(0.01, probability)), 4),
            model_version=model_version,
        )


class RulModelService(_ArtifactService):
    def __init__(self, artifact_path: Path | str | None = None) -> None:
        super().__init__(artifact_path or settings.rul_model_path, "rul_regression", "rules-rul-v1")

    def predict(self, telemetry: list[TelemetryRecord]) -> RulInference | None:
        artifact = self._load()
        if artifact is None:
            return None
        features = _runtime_features(
            telemetry[-1], artifact.get("runtime_profile", RUNTIME_PROFILE), artifact["feature_names"]
        )
        estimator, model_version = _select_estimator(artifact, telemetry[-1])
        hours = float(estimator.predict([features])[0])
        # The model predicts 0h while the pump is down; the API contract needs a
        # positive value, so report at least 0.1h.
        hours = min(float(artifact["rul_cap_hours"]), max(0.1, hours))
        return RulInference(hours=round(hours, 1), model_version=model_version)


failure_model_service = FailureModelService()
rul_model_service = RulModelService()
