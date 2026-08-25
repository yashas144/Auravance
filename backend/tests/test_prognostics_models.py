from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.models.schemas import TelemetryRecord
from app.services.prognostics import failure_model_service, rul_model_service


class PrognosticsModelTests(unittest.TestCase):
    def _record(self, temperature: float, vibration: float, pressure: float, current: float) -> TelemetryRecord:
        return TelemetryRecord(
            asset_id="pump-04",
            timestamp=datetime.now(timezone.utc),
            temperature_c=temperature,
            vibration_rms=vibration,
            pressure_bar=pressure,
            current_a=current,
        )

    def test_failure_model_loads_and_ranks_degradation(self) -> None:
        self.assertTrue(failure_model_service.status().loaded)
        normal = failure_model_service.predict([self._record(68.0, 0.30, 5.0, 9.0)])
        degraded = failure_model_service.predict([self._record(96.0, 1.40, 2.8, 17.0)])
        self.assertIsNotNone(normal)
        self.assertIsNotNone(degraded)
        self.assertGreater(degraded.probability, normal.probability)

    def test_rul_model_loads_and_reduces_life_for_degradation(self) -> None:
        self.assertTrue(rul_model_service.status().loaded)
        normal = rul_model_service.predict([self._record(68.0, 0.30, 5.0, 9.0)])
        warning = rul_model_service.predict([self._record(84.0, 0.72, 4.0, 12.5)])
        degraded = rul_model_service.predict([self._record(96.0, 1.40, 2.8, 17.0)])
        self.assertIsNotNone(normal)
        self.assertIsNotNone(warning)
        self.assertIsNotNone(degraded)
        self.assertLess(warning.hours, normal.hours)
        self.assertLess(degraded.hours, warning.hours)


if __name__ == "__main__":
    unittest.main()
