from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.ingestion.replay import (
    DATASETS,
    build_payload,
    build_timeline,
    downsample,
    group_episodes,
    read_replay_rows,
    staggered_start,
    stream_from,
)
from app.models.schemas import TelemetryIngestRequest, TelemetryRecord
from app.services.anomaly import anomaly_model_service


class PumpReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mappings = DATASETS["pump"].load_mappings()
        cls.rows = read_replay_rows(DATASETS["pump"].replay_path)

    def test_mapping_preserves_training_feature_space(self) -> None:
        for mapping in self.mappings:
            raw = mapping.median + 2.5 * mapping.iqr_scale
            contract = mapping.to_contract(raw)
            self.assertAlmostEqual((contract - mapping.center) / mapping.scale, 2.5, places=3)
        self.assertIsNone(self.mappings[0].to_contract(None))

    def test_downsample_keeps_single_minute_failures(self) -> None:
        for episode in group_episodes(self.rows):
            sampled = downsample(episode, stride=7)
            self.assertIn("BROKEN", {row.machine_status for row in sampled})
            self.assertLess(len(sampled), len(episode))

    def test_assets_start_at_distinct_points_in_the_timeline(self) -> None:
        timeline = build_timeline(group_episodes(self.rows), stride=5)
        assets = [f"asset-{index:02d}" for index in range(10)]
        starts = {staggered_start(asset, assets, len(timeline)) for asset in assets}
        self.assertEqual(len(starts), len(assets))
        first = {next(stream_from(timeline, start)).source_timestamp for start in starts}
        self.assertEqual(len(first), len(assets))

    def test_payload_is_valid_ingest_request(self) -> None:
        payload = build_payload(self.rows[0], "pump-04", datetime.now(timezone.utc).isoformat(), self.mappings, DATASETS["pump"])
        request = TelemetryIngestRequest.model_validate(payload)
        self.assertEqual(request.source, "dataset-replay")
        self.assertEqual(request.source_context["dataset"], "kaggle-pump-sensor")
        self.assertEqual(request.source_context["machine_status"], self.rows[0].machine_status)

    def test_model_separates_recorded_failures_from_normal_operation(self) -> None:
        # Only NORMAL rows before each failure count as healthy: the dataset flips
        # back to NORMAL while the pump is still idle (sensors 20-47 IQR below
        # baseline), and the model rightly keeps flagging that stretch.
        flagged = {"healthy": [], "RECOVERING": []}
        for episode in group_episodes(self.rows):
            seen_failure = False
            for row in downsample(episode, stride=10):
                seen_failure = seen_failure or row.machine_status == "BROKEN"
                if row.machine_status == "RECOVERING":
                    bucket = "RECOVERING"
                elif row.machine_status == "NORMAL" and not seen_failure:
                    bucket = "healthy"
                else:
                    continue
                metrics = build_payload(row, "pump-04", "", self.mappings, DATASETS["pump"])["metrics"]
                record = TelemetryRecord(asset_id="pump-04", timestamp=datetime.now(timezone.utc), **metrics)
                inference = anomaly_model_service.predict([record])
                self.assertIsNotNone(inference)
                flagged[bucket].append(inference.label != "normal")

        recovering_rate = sum(flagged["RECOVERING"]) / len(flagged["RECOVERING"])
        healthy_rate = sum(flagged["healthy"]) / len(flagged["healthy"])
        self.assertGreater(recovering_rate, 0.8)
        self.assertLess(healthy_rate, 0.15)


if __name__ == "__main__":
    unittest.main()
