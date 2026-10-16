from __future__ import annotations

import unittest
from datetime import datetime, timezone
from statistics import mean

from app.ingestion.replay import DATASETS, build_payload, group_episodes, read_replay_rows
from app.models.schemas import TelemetryRecord
from app.services.model_profiles import profile_for_asset_type
from app.services.model_registry import models_for


def replayed_records(profile: str) -> list[list[tuple[str, TelemetryRecord]]]:
    """Every replay episode of a profile as (ground-truth status, record) pairs."""
    dataset = DATASETS[profile]
    mappings = dataset.load_mappings()
    episodes = []
    for episode in group_episodes(read_replay_rows(dataset.replay_path)):
        records = []
        for row in episode:
            payload = build_payload(row, f"{profile}-test", "", mappings, dataset)
            records.append(
                (
                    row.machine_status,
                    TelemetryRecord(
                        asset_id=f"{profile}-test",
                        timestamp=datetime.now(timezone.utc),
                        source_context=payload["source_context"],
                        **payload["metrics"],
                    ),
                )
            )
        episodes.append(records)
    return episodes


class AssetTypeProfileTests(unittest.TestCase):
    def test_asset_types_map_to_matching_datasets(self) -> None:
        self.assertEqual(profile_for_asset_type("compressor"), "compressor")
        self.assertEqual(profile_for_asset_type("motor"), "motor")
        self.assertEqual(profile_for_asset_type("drive"), "motor")
        self.assertEqual(profile_for_asset_type("conveyor"), "motor")
        self.assertEqual(profile_for_asset_type("pump"), "pump")
        self.assertEqual(profile_for_asset_type("cooling-system"), "pump")
        self.assertEqual(profile_for_asset_type("unknown-kind"), "pump")

    def test_every_profile_has_trained_models(self) -> None:
        for profile in ("pump", "compressor", "motor"):
            models = models_for(profile)
            for service in (models.anomaly, models.failure, models.rul):
                self.assertTrue(service.status().loaded, f"{profile}: {service.status().detail}")


class CompressorModelTests(unittest.TestCase):
    """MetroPT-3 air leaks, scored by models that never saw the leak in question."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.models = models_for("compressor")
        cls.episodes = replayed_records("compressor")

    def test_replay_uses_real_units(self) -> None:
        _, record = self.episodes[0][0]
        self.assertEqual(record.source_context["units"], "real")
        self.assertGreater(record.temperature_c, 30.0)  # oil temperature in degC
        self.assertIsNone(record.vibration_rms)  # MetroPT-3 has no vibration sensor

    def test_air_leaks_raise_failure_probability(self) -> None:
        for episode in self.episodes:
            leak = [self.models.failure.predict([r]).probability for s, r in episode if s == "AIR_LEAK"]
            healthy = [self.models.failure.predict([r]).probability for s, r in episode if s == "NORMAL"]
            self.assertIn("+heldout-", self.models.failure.predict([episode[0][1]]).model_version)
            self.assertGreater(mean(leak), mean(healthy))
        all_leak = [self.models.failure.predict([r]).probability for e in self.episodes for s, r in e if s == "AIR_LEAK"]
        self.assertGreater(mean(all_leak), 0.2)

    def test_anomaly_model_flags_leaks_far_more_than_normal_running(self) -> None:
        def flag_rate(status: str) -> float:
            labels = [self.models.anomaly.predict([r]).label for e in self.episodes for s, r in e if s == status]
            return sum(label != "normal" for label in labels) / len(labels)

        self.assertGreater(flag_rate("AIR_LEAK"), 0.3)
        self.assertLess(flag_rate("NORMAL"), 0.1)


if __name__ == "__main__":
    unittest.main()


class MotorModelTests(unittest.TestCase):
    """NASA/IMS bearing run-to-failure tests, scored by models that never saw the test."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.models = models_for("motor")
        cls.episodes = replayed_records("motor")

    def test_replay_uses_real_vibration_units(self) -> None:
        _, record = self.episodes[0][0]
        self.assertEqual(record.source_context["vibration_rms_unit"], "g")
        self.assertIsNone(record.temperature_c)  # the IMS rig only measured vibration
        self.assertGreater(record.vibration_rms, 0.0)

    def test_risk_rises_and_life_falls_as_bearings_wear_out(self) -> None:
        def hours_left(episode, index):
            end = datetime.fromisoformat(episode[-1][1].source_context["source_timestamp"])
            now = datetime.fromisoformat(episode[index][1].source_context["source_timestamp"])
            return (end - now).total_seconds() / 3600

        early_p, late_p, early_rul, late_rul = [], [], [], []
        for episode in self.episodes:
            for index, (_, record) in enumerate(episode):
                hours = hours_left(episode, index)
                if hours > 72:
                    early_p.append(self.models.failure.predict([record]).probability)
                    early_rul.append(self.models.rul.predict([record]).hours)
                elif hours < 24:
                    late_p.append(self.models.failure.predict([record]).probability)
                    late_rul.append(self.models.rul.predict([record]).hours)
        self.assertGreater(mean(late_p), mean(early_p) + 0.3)
        self.assertLess(mean(late_rul), mean(early_rul) - 80)
