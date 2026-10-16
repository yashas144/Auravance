from __future__ import annotations

from typing import NamedTuple

from app.services.anomaly import AnomalyModelService, anomaly_model_service
from app.services.model_profiles import DEFAULT_PROFILE, PROFILES, artifact_paths
from app.services.prognostics import FailureModelService, RulModelService, failure_model_service, rul_model_service


class ProfileModels(NamedTuple):
    anomaly: AnomalyModelService
    failure: FailureModelService
    rul: RulModelService


def _build() -> dict[str, ProfileModels]:
    models = {"pump": ProfileModels(anomaly_model_service, failure_model_service, rul_model_service)}
    for profile in PROFILES:
        if profile in models:
            continue
        paths = artifact_paths(profile)
        models[profile] = ProfileModels(
            AnomalyModelService(paths["anomaly"]),
            FailureModelService(paths["failure"]),
            RulModelService(paths["rul"]),
        )
    return models


MODELS = _build()


def models_for(profile: str) -> ProfileModels:
    return MODELS.get(profile, MODELS[DEFAULT_PROFILE])
