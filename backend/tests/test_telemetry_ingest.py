from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _payload(asset_id: str = "pump-04", **extra) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_id": asset_id,
        "metrics": {"temperature_c": 70.0, "vibration_rms": 0.3, "pressure_bar": 5.0, "current_a": 9.0},
        **extra,
    }


class TelemetryIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._original = (settings.demo_db_path, settings.ingest_api_key)
        settings.demo_db_path = str(Path(self._tmp.name) / "test.db")
        settings.ingest_api_key = ""

    def tearDown(self) -> None:
        settings.demo_db_path, settings.ingest_api_key = self._original
        self._tmp.cleanup()

    def _login(self, client: TestClient) -> dict:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "yashas@auravance.demo", "password": "Auravance@123"},
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_unknown_asset_is_rejected(self) -> None:
        with TestClient(app) as client:
            response = client.post("/api/v1/telemetry/ingest", json=_payload("no-such-asset"))
        self.assertEqual(response.status_code, 404)

    def test_ingest_key_enforced_when_configured(self) -> None:
        settings.ingest_api_key = "test-key"
        with TestClient(app) as client:
            missing = client.post("/api/v1/telemetry/ingest", json=_payload())
            wrong = client.post("/api/v1/telemetry/ingest", json=_payload(), headers={"X-Ingest-Key": "nope"})
            ok = client.post("/api/v1/telemetry/ingest", json=_payload(), headers={"X-Ingest-Key": "test-key"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(ok.status_code, 200)

    def test_source_context_round_trips(self) -> None:
        context = {"machine_status": "RECOVERING", "sensor_04": 412.5}
        with TestClient(app) as client:
            client.post("/api/v1/telemetry/ingest", json=_payload(source="pump-replay", source_context=context))
            latest = client.get("/api/v1/telemetry/assets/pump-04/latest", headers=self._login(client)).json()
        self.assertEqual(latest["source"], "pump-replay")
        self.assertEqual(latest["source_context"], context)

    def test_batch_ingest_stores_every_asset(self) -> None:
        with TestClient(app) as client:
            targets = [target["asset_id"] for target in client.get("/api/v1/telemetry/ingest/targets").json()]
            response = client.post(
                "/api/v1/telemetry/ingest/batch",
                json={"readings": [_payload(asset_id) for asset_id in targets]},
            )
            headers = self._login(client)
            latest = {
                asset_id: client.get(f"/api/v1/telemetry/assets/{asset_id}/latest", headers=headers).status_code
                for asset_id in targets
            }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["accepted"], len(targets))
        self.assertGreaterEqual(len(targets), 10)
        self.assertEqual(set(latest.values()), {200})

    def test_batch_with_unknown_asset_is_rejected_atomically(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/telemetry/ingest/batch",
                json={"readings": [_payload("pump-04"), _payload("ghost-asset")]},
            )
            stored = client.get("/api/v1/telemetry/assets/pump-04/latest", headers=self._login(client))
        self.assertEqual(response.status_code, 404)
        self.assertIn("ghost-asset", response.json()["detail"])
        self.assertEqual(stored.status_code, 404)

    def test_ingest_targets_require_key_when_configured(self) -> None:
        settings.ingest_api_key = "test-key"
        with TestClient(app) as client:
            missing = client.get("/api/v1/telemetry/ingest/targets")
            ok = client.get("/api/v1/telemetry/ingest/targets", headers={"X-Ingest-Key": "test-key"})
        self.assertEqual(missing.status_code, 401)
        profiles = {target["asset_id"]: target["profile"] for target in ok.json()}
        self.assertEqual(profiles["pump-04"], "pump")
        self.assertEqual(profiles["compressor-17"], "compressor")
        self.assertEqual(profiles["motor-08"], "motor")
        self.assertEqual(profiles["drive-21"], "motor")

    def test_sustained_condition_does_not_flood_alerts(self) -> None:
        degraded = {"temperature_c": 96.0, "vibration_rms": 1.4, "pressure_bar": 2.8, "current_a": 17.0}
        with TestClient(app) as client:
            for _ in range(10):
                client.post("/api/v1/telemetry/ingest", json={**_payload(), "metrics": degraded})
            alerts = client.get("/api/v1/alerts", headers=self._login(client)).json()
        self.assertGreaterEqual(len(alerts), 1)
        self.assertLessEqual(len(alerts), 2)


if __name__ == "__main__":
    unittest.main()
