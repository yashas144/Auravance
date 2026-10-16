from __future__ import annotations

from statistics import mean

from app.models.schemas import PredictionResponse, TelemetryRecord
from app.services.model_profiles import profile_for_asset
from app.services.model_registry import models_for


def _normalize(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 0.0
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _trend_bonus(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    rising_steps = sum(1 for left, right in zip(values, values[1:]) if right > left)
    return min(0.2, rising_steps / max(1, len(values) - 1) * 0.2)


def score_asset(asset_id: str, telemetry: list[TelemetryRecord], profile: str | None = None) -> PredictionResponse:
    models = models_for(profile or profile_for_asset(asset_id))
    latest = telemetry[-1]
    temp_score = _normalize(latest.temperature_c, 70.0, 95.0)
    vibration_score = _normalize(latest.vibration_rms, 0.45, 1.2)
    pressure_score = _normalize(abs((latest.pressure_bar or 0.0) - 5.0), 0.4, 2.0)
    current_score = _normalize(latest.current_a, 9.0, 16.0)

    rules_anomaly_score = min(
        1.0,
        temp_score * 0.3 + vibration_score * 0.35 + pressure_score * 0.15 + current_score * 0.2,
    )
    model_inference = models.anomaly.predict(telemetry)
    anomaly_score = model_inference.score if model_inference else rules_anomaly_score
    temp_trend = _trend_bonus([point.temperature_c for point in telemetry if point.temperature_c is not None])
    vibration_trend = _trend_bonus(
        [point.vibration_rms for point in telemetry if point.vibration_rms is not None]
    )
    rules_failure_probability = min(
        0.98, 0.1 + anomaly_score * 0.7 + temp_trend + vibration_trend
    )
    failure_inference = models.failure.predict(telemetry)
    failure_probability = (
        failure_inference.probability if failure_inference else rules_failure_probability
    )
    rules_rul_hours = max(12.0, round(240.0 * (1.0 - failure_probability), 1))
    rul_inference = models.rul.predict(telemetry)
    estimated_rul_hours = rul_inference.hours if rul_inference else rules_rul_hours

    dominant_signal = max(
        {
            "temperature": temp_score,
            "vibration": vibration_score,
            "pressure": pressure_score,
            "current": current_score,
        }.items(),
        key=lambda item: item[1],
    )[0]

    model_version = "demo-rules-0.1.0"
    if model_inference:
        anomaly_label = model_inference.label
        dominant_signal = model_inference.dominant_signal
        model_version = model_inference.model_version
    elif anomaly_score >= 0.75:
        anomaly_label = "high-risk"
    elif anomaly_score >= 0.45:
        anomaly_label = "warning"
    else:
        anomaly_label = "normal"

    recent_pressure = [point.pressure_bar for point in telemetry if point.pressure_bar is not None]
    if not model_inference and len(recent_pressure) >= 3 and max(recent_pressure) - min(recent_pressure) > 1.2:
        dominant_signal = "pressure_instability"

    if not model_inference and len(telemetry) >= 3:
        recent_temp_avg = mean([point.temperature_c or 0.0 for point in telemetry[-3:]])
        if recent_temp_avg > 85.0 and vibration_score > 0.55:
            dominant_signal = "bearing_pattern"

    return PredictionResponse(
        asset_id=asset_id,
        anomaly_score=round(anomaly_score, 2),
        anomaly_label=anomaly_label,
        failure_probability_72h=round(failure_probability, 2),
        estimated_rul_hours=estimated_rul_hours,
        model_version=model_version,
        dominant_signal=dominant_signal,
        anomaly_model_version=model_version,
        failure_model_version=(failure_inference.model_version if failure_inference else None),
        rul_model_version=(rul_inference.model_version if rul_inference else None),
    )
