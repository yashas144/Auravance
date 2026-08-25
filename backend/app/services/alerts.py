from __future__ import annotations

from contextlib import closing

from app.core.db import get_connection
from app.models.schemas import AlertResponse


class AlertsService:
    def list_alerts(self) -> list[AlertResponse]:
        with closing(get_connection()) as connection:
            rows = connection.execute(
                """
                SELECT alert_id, asset_id, severity, message, status, created_at
                FROM alerts
                ORDER BY created_at DESC
                LIMIT 100
                """
            ).fetchall()
        return [AlertResponse(**dict(row)) for row in rows]


alerts_service = AlertsService()
