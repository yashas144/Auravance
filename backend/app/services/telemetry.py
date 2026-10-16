from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import settings
from app.core.db import get_connection
from app.models.schemas import (
    IngestTargetResponse,
    TelemetryBatchIngestRequest,
    TelemetryBatchIngestResponse,
    TelemetryIngestRequest,
    TelemetryIngestResponse,
    TelemetryRecord,
)
from app.services.model_profiles import profile_for_asset_type
from app.services.scoring import score_asset


TELEMETRY_COLUMNS = (
    "asset_id, timestamp, temperature_c, vibration_rms, pressure_bar, current_a, source, source_context_json"
)


def _row_to_record(row) -> TelemetryRecord:
    data = dict(row)
    data["source_context"] = json.loads(data.pop("source_context_json") or "{}")
    return TelemetryRecord(**data)


class TelemetryService:
    def ingest(self, payload: TelemetryIngestRequest) -> TelemetryIngestResponse:
        self._store([payload])
        self._maybe_create_alert(payload.asset_id)
        return TelemetryIngestResponse(
            status="accepted",
            asset_id=payload.asset_id,
            received_at=datetime.now(timezone.utc),
        )

    def ingest_batch(self, payload: TelemetryBatchIngestRequest) -> TelemetryBatchIngestResponse:
        self._store(payload.readings)
        asset_ids = list(dict.fromkeys(reading.asset_id for reading in payload.readings))
        for asset_id in asset_ids:
            self._maybe_create_alert(asset_id)
        return TelemetryBatchIngestResponse(
            status="accepted",
            accepted=len(payload.readings),
            asset_ids=asset_ids,
            received_at=datetime.now(timezone.utc),
        )

    def list_ingest_targets(self) -> list[IngestTargetResponse]:
        with closing(get_connection()) as connection:
            rows = connection.execute("SELECT asset_id, asset_type FROM assets ORDER BY asset_id").fetchall()
        return [
            IngestTargetResponse(
                asset_id=row["asset_id"],
                asset_type=row["asset_type"],
                profile=profile_for_asset_type(row["asset_type"]),
            )
            for row in rows
        ]

    def _store(self, readings: list[TelemetryIngestRequest]) -> None:
        """Insert readings in one transaction; reject the whole batch if any asset is unknown."""
        with closing(get_connection()) as connection:
            requested = {reading.asset_id for reading in readings}
            placeholders = ", ".join("?" for _ in requested)
            known = {
                row["asset_id"]
                for row in connection.execute(
                    f"SELECT asset_id FROM assets WHERE asset_id IN ({placeholders})",
                    tuple(requested),
                ).fetchall()
            }
            unknown = sorted(requested - known)
            if unknown:
                names = ", ".join(f"'{asset_id}'" for asset_id in unknown)
                raise HTTPException(status_code=404, detail=f"Unknown asset(s): {names}.")

            connection.executemany(
                """
                INSERT INTO telemetry (
                    asset_id, timestamp, temperature_c, vibration_rms, pressure_bar, current_a,
                    source, source_context_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        reading.asset_id,
                        reading.timestamp.isoformat(),
                        reading.metrics.temperature_c,
                        reading.metrics.vibration_rms,
                        reading.metrics.pressure_bar,
                        reading.metrics.current_a,
                        reading.source,
                        json.dumps(reading.source_context),
                    )
                    for reading in readings
                ],
            )
            connection.commit()

    def get_latest(self, asset_id: str) -> TelemetryRecord | None:
        with closing(get_connection()) as connection:
            row = connection.execute(
                f"""
                SELECT {TELEMETRY_COLUMNS}
                FROM telemetry
                WHERE asset_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def get_history(self, asset_id: str, limit: int = 50) -> list[TelemetryRecord]:
        with closing(get_connection()) as connection:
            rows = connection.execute(
                f"""
                SELECT {TELEMETRY_COLUMNS}
                FROM telemetry
                WHERE asset_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (asset_id, limit),
            ).fetchall()
        records = [_row_to_record(row) for row in rows]
        return list(reversed(records))

    def _maybe_create_alert(self, asset_id: str) -> None:
        history = self.get_history(asset_id, limit=8)
        if len(history) < 3:
            return

        prediction = score_asset(asset_id, history)
        if prediction.anomaly_label == "normal":
            return

        severity = "high" if prediction.anomaly_label == "high-risk" else "medium"
        message = (
            f"{prediction.anomaly_label} condition detected from "
            f"{prediction.dominant_signal}; failure probability is "
            f"{prediction.failure_probability_72h:.0%} in 72 hours."
        )
        now = datetime.now(timezone.utc)

        with closing(get_connection()) as connection:
            latest = connection.execute(
                """
                SELECT message, severity, created_at
                FROM alerts
                WHERE asset_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (asset_id,),
            ).fetchone()
            if latest:
                if latest["message"] == message:
                    return
                # A sustained condition re-scores on every reading; only re-alert
                # after the cooldown unless the severity changes.
                created_at = datetime.fromisoformat(latest["created_at"])
                within_cooldown = now - created_at < timedelta(seconds=settings.alert_cooldown_seconds)
                if latest["severity"] == severity and within_cooldown:
                    return

            connection.execute(
                """
                INSERT INTO alerts (alert_id, asset_id, severity, message, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"alert-{uuid4().hex[:10]}",
                    asset_id,
                    severity,
                    message,
                    "open",
                    now.isoformat(),
                ),
            )
            connection.commit()


telemetry_service = TelemetryService()
