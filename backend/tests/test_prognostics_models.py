from __future__ import annotations

import unittest
from datetime import datetime, timezone
from statistics import mean

from app.ingestion.replay import (
    DATASETS,
    build_payload,
    downsample,
    group_episodes,
    read_replay_rows,
)
from app.models.schemas import TelemetryRecord
from app.services.prognostics import failure_model_service, rul_model_service


class PrognosticsModelTests(unittest.TestCase):
    """Behaviour on the recorded pump episodes that the replay streams live."""

    @classmethod
    def setUpClass(cls) -> None:
        mappings = DATASETS["pump"].load_mappings()
        cls.episodes: list[dict[str, list[TelemetryRecord]]] = []
        for episode in group_episodes(read_replay_rows(DATASETS["pump"].replay_path)):
            phases: dict[str, list[TelemetryRecord]] = {"healthy": [], "down": []}
            cls.episodes.append(phases)
            seen_failure = False
            for row in downsample(episode, stride=15):
                seen_failure = seen_failure or row.machine_status == "BROKEN"
                if row.machine_status == "NORMAL" and not seen_failure:
                    phase = "healthy"
                elif row.machine_status in {"BROKEN", "RECOVERING"}:
                    phase = "down"
                else:
                    continue
                payload = build_payload(row, "pump-04", "", mappings, DATASETS["pump"])
                phases[phase].append(
                    TelemetryRecord(
                        asset_id="pump-04",
                        timestamp=datetime.now(timezone.utc),
                        source_context=payload["source_context"],
                        **payload["metrics"],
                    )
                )

    def test_models_are_pump_trained(self) -> None:
        for service in (failure_model_service, rul_model_service):
            status = service.status()
            self.assertTrue(status.loaded, status.detail)
            self.assertEqual(status.source_dataset, "pump_sensor/sensor_processed.csv")

    def test_replayed_readings_are_scored_by_held_out_models(self) -> None:
        record = self.episodes[0]["down"][0]
        self.assertIn("+heldout-", failure_model_service.predict([record]).model_version)

        live = record.model_copy(update={"source_context": {}})
        self.assertNotIn("+heldout-", failure_model_service.predict([live]).model_version)

    def _phase_means(self, predict) -> list[tuple[float, float]]:
        return [
            (mean(predict(record) for record in phases["healthy"]), mean(predict(record) for record in phases["down"]))
            for phases in self.episodes
        ]

    def test_failure_probability_tracks_pump_state(self) -> None:
        # Held-out scores, per recorded failure: higher while the pump is broken or
        # recovering than while it runs normally beforehand.
        per_episode = self._phase_means(lambda record: failure_model_service.predict([record]).probability)
        for healthy, down in per_episode:
            self.assertGreater(down, healthy + 0.25)
        self.assertGreater(mean(down for _, down in per_episode), 0.6)
        self.assertLess(mean(healthy for healthy, _ in per_episode), 0.25)

    def test_remaining_life_collapses_when_pump_is_down(self) -> None:
        per_episode = self._phase_means(lambda record: rul_model_service.predict([record]).hours)
        for healthy, down in per_episode:
            self.assertLess(down, healthy - 40.0)
        self.assertGreater(mean(healthy for healthy, _ in per_episode), 120.0)
        self.assertLess(mean(down for _, down in per_episode), 80.0)


if __name__ == "__main__":
    unittest.main()
