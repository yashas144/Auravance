from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.models.schemas import TelemetryRecord
from app.services.anomaly import anomaly_model_service
from app.services.scoring import score_asset


class TrainedAnomalyModelTests(unittest.TestCase):
    def _record(
        self,
        temperature: float,
        vibration: float,
        pressure: float,
        current: float,
    ) -> TelemetryRecord:
        return TelemetryRecord(
            asset_id="pump-04",
            timestamp=datetime.now(timezone.utc),
            temperature_c=temperature,
            vibration_rms=vibration,
            pressure_bar=pressure,
            current_a=current,
        )

    def test_model_artifact_loads(self) -> None:
        status = anomaly_model_service.status()
        self.assertTrue(status.loaded, status.detail)
        self.assertFalse(status.fallback_active)
        self.assertEqual(status.algorithm, "IsolationForest")

    def test_degraded_profile_scores_above_normal_profile(self) -> None:
        normal = score_asset("pump-04", [self._record(65.0, 0.31, 4.2, 9.1)])
        degraded = score_asset("pump-04", [self._record(96.0, 1.40, 2.8, 17.0)])

        self.assertEqual(normal.anomaly_label, "normal")
        self.assertGreater(degraded.anomaly_score, normal.anomaly_score)
        self.assertIn(degraded.anomaly_label, {"warning", "high-risk"})
        self.assertEqual(degraded.model_version, "isolation-forest-pump-v1.0.0")


if __name__ == "__main__":
    unittest.main()
