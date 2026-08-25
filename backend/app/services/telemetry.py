from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from app.core.db import get_connection
from app.models.schemas import TelemetryIngestRequest, TelemetryIngestResponse, TelemetryRecord
from app.services.scoring import score_asset


class TelemetryService:
    def ingest(self, payload: TelemetryIngestRequest) -> TelemetryIngestResponse:
        with closing(get_connection()) as connection:
            connection.execute(
                """
                INSERT INTO telemetry (
                    asset_id, timestamp, temperature_c, vibration_rms, pressure_bar, current_a
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.asset_id,
                    payload.timestamp.isoformat(),
                    payload.metrics.temperature_c,
                    payload.metrics.vibration_rms,
                    payload.metrics.pressure_bar,
                    payload.metrics.current_a,
                ),
            )
            connection.commit()

        self._maybe_create_alert(payload.asset_id)
        return TelemetryIngestResponse(
            status="accepted",
            asset_id=payload.asset_id,
            received_at=datetime.now(timezone.utc),
        )

    def get_latest(self, asset_id: str) -> TelemetryRecord | None:
        with closing(get_connection()) as connection:
            row = connection.execute(
                """
                SELECT asset_id, timestamp, temperature_c, vibration_rms, pressure_bar, current_a
                FROM telemetry
                WHERE asset_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return TelemetryRecord(**dict(row))

    def get_history(self, asset_id: str, limit: int = 50) -> list[TelemetryRecord]:
        with closing(get_connection()) as connection:
            rows = connection.execute(
                """
                SELECT asset_id, timestamp, temperature_c, vibration_rms, pressure_bar, current_a
                FROM telemetry
                WHERE asset_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (asset_id, limit),
            ).fetchall()
        records = [TelemetryRecord(**dict(row)) for row in rows]
        return list(reversed(records))

    def _maybe_create_alert(self, asset_id: str) -> None:
        history = self.get_history(asset_id, limit=8)
        if len(history) < 3:
            return

        prediction = score_asset(asset_id, history)
        if prediction.anomaly_label == "normal":
            return

        message = (
            f"{prediction.anomaly_label} condition detected from "
            f"{prediction.dominant_signal}; failure probability is "
            f"{prediction.failure_probability_72h:.0%} in 72 hours."
        )

        with closing(get_connection()) as connection:
            latest_similar = connection.execute(
                """
                SELECT message
                FROM alerts
                WHERE asset_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (asset_id,),
            ).fetchone()
            if latest_similar and latest_similar["message"] == message:
                return

            connection.execute(
                """
                INSERT INTO alerts (alert_id, asset_id, severity, message, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"alert-{uuid4().hex[:10]}",
                    asset_id,
                    "high" if prediction.anomaly_label == "high-risk" else "medium",
                    message,
                    "open",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()


telemetry_service = TelemetryService()
