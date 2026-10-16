"""Replay of real recorded datasets as live telemetry, one dataset per equipment profile.

  pump       - Kaggle pump-sensor recording. Its channels are anonymized (unknown
               units), so the four modelled channels are rescaled into the anomaly
               model's feature space: value = center + (raw - median) / IQR * scale.
  compressor - MetroPT-3 metro air compressor, 5-minute averages in real units
               (oil temperature degC, panel pressure bar, motor current A).
  motor      - NASA/IMS motor-driven bearing rig, worst-bearing vibration RMS in g.

Raw readings, the original timestamp and the dataset's ground truth travel in
source_context next to the contract metrics.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.services.anomaly import FEATURE_NAMES, TELEMETRY_FIELDS
from app.services.model_profiles import PROFILE_DATASETS


SOURCE_NAME = "dataset-replay"
REPLAY_DIR = Path(__file__).resolve().parents[2] / "data" / "replay"
META_COLUMNS = {"episode_id", "source_timestamp", "machine_status"}


@dataclass(frozen=True, slots=True)
class ChannelMapping:
    source_column: str
    telemetry_field: str
    median: float = 0.0
    iqr_scale: float = 1.0
    center: float = 0.0
    scale: float = 1.0
    unit: str = ""  # real-unit datasets only; anonymized channels have none

    def to_contract(self, raw: float | None) -> float | None:
        if raw is None or math.isnan(raw):
            return None
        z = (raw - self.median) / self.iqr_scale
        return round(self.center + z * self.scale, 4)


@dataclass(frozen=True, slots=True)
class ReplayRow:
    episode_id: str
    source_timestamp: str
    machine_status: str
    raw: dict[str, float | None]


@dataclass(frozen=True, slots=True)
class ReplayDataset:
    profile: str
    label: str
    replay_path: Path
    units: str  # "real" or "anonymized"
    minutes_per_row: float
    load_mappings: Callable[[], list[ChannelMapping]]

    @property
    def dataset_id(self) -> str:
        return PROFILE_DATASETS[self.profile]


def load_pump_mappings(metadata_path: Path | None = None) -> list[ChannelMapping]:
    path = metadata_path or Path(settings.anomaly_model_path).with_suffix(".json")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("feature_names") != FEATURE_NAMES:
        raise ValueError("Anomaly model metadata does not match the telemetry feature contract.")
    medians = metadata["source_transform"]["medians"]
    scales = metadata["source_transform"]["iqr_scales"]
    profile = metadata["runtime_profile"]
    return [
        ChannelMapping(
            source_column=column,
            telemetry_field=TELEMETRY_FIELDS[feature],
            median=float(medians[column]),
            iqr_scale=float(scales[column]),
            center=float(profile[feature]["center"]),
            scale=float(profile[feature]["scale"]),
        )
        for feature, column in zip(FEATURE_NAMES, metadata["source_columns"], strict=True)
    ]


DATASETS: dict[str, ReplayDataset] = {
    "pump": ReplayDataset(
        profile="pump",
        label="Kaggle pump sensor dataset",
        replay_path=REPLAY_DIR / "pump_failure_episodes.csv",
        units="anonymized",
        minutes_per_row=1.0,
        load_mappings=load_pump_mappings,
    ),
    "compressor": ReplayDataset(
        profile="compressor",
        label="MetroPT-3 metro air compressor (UCI, CC BY 4.0)",
        replay_path=REPLAY_DIR / "compressor_failure_episodes.csv",
        units="real",
        minutes_per_row=5.0,
        load_mappings=lambda: [
            ChannelMapping("oil_temperature_c", "temperature_c", unit="°C"),
            ChannelMapping("tp3_bar", "pressure_bar", unit="bar"),
            ChannelMapping("motor_current_a", "current_a", unit="A"),
        ],
    ),
    "motor": ReplayDataset(
        profile="motor",
        label="NASA IMS bearing run-to-failure (motor-driven shaft)",
        replay_path=REPLAY_DIR / "motor_failure_episodes.csv",
        units="real",
        minutes_per_row=10.0,
        load_mappings=lambda: [ChannelMapping("max_bearing_rms", "vibration_rms", unit="g")],
    ),
}


def _parse_float(value: str) -> float | None:
    if value == "":
        return None
    parsed = float(value)
    return None if math.isnan(parsed) else parsed


def read_replay_rows(path: Path) -> list[ReplayRow]:
    rows: list[ReplayRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        value_columns = [name for name in reader.fieldnames or [] if name not in META_COLUMNS]
        for record in reader:
            rows.append(
                ReplayRow(
                    episode_id=record["episode_id"],
                    source_timestamp=record["source_timestamp"],
                    machine_status=record["machine_status"],
                    raw={column: _parse_float(record[column]) for column in value_columns},
                )
            )
    if not rows:
        raise ValueError(f"Replay file has no rows: {path}")
    return rows


def group_episodes(rows: list[ReplayRow]) -> list[list[ReplayRow]]:
    episodes: dict[str, list[ReplayRow]] = {}
    for row in rows:
        episodes.setdefault(row.episode_id, []).append(row)
    return list(episodes.values())


def downsample(episode: list[ReplayRow], stride: int) -> list[ReplayRow]:
    """Keep every `stride`-th row, plus every row where machine_status changes.

    Some failures last a single recorded row (pump BROKEN, final IMS snapshot),
    so plain striding would skip them.
    """
    if stride <= 1:
        return list(episode)
    kept: list[ReplayRow] = []
    previous_status: str | None = None
    for index, row in enumerate(episode):
        if index % stride == 0 or row.machine_status != previous_status:
            kept.append(row)
        previous_status = row.machine_status
    return kept


def build_timeline(episodes: list[list[ReplayRow]], stride: int) -> list[ReplayRow]:
    """Concatenate the downsampled episodes into one loop."""
    return [row for episode in episodes for row in downsample(episode, stride)]


def stride_for(dataset: ReplayDataset, minutes_per_tick: float) -> int:
    return max(1, round(minutes_per_tick / dataset.minutes_per_row))


def stream_from(timeline: list[ReplayRow], start: int) -> Iterator[ReplayRow]:
    index = start % len(timeline)
    while True:
        yield timeline[index]
        index = (index + 1) % len(timeline)


def staggered_start(asset_id: str, asset_ids: list[str], timeline_length: int) -> int:
    """Spread assets evenly over the timeline so no two show the same moment.

    Positions depend only on the sorted asset list, so a restart resumes the same layout.
    """
    ordered = sorted(asset_ids)
    return ordered.index(asset_id) * timeline_length // len(ordered)


def build_payload(
    row: ReplayRow,
    asset_id: str,
    timestamp: str,
    mappings: list[ChannelMapping],
    dataset: ReplayDataset,
) -> dict:
    metrics = {mapping.telemetry_field: mapping.to_contract(row.raw.get(mapping.source_column)) for mapping in mappings}
    context: dict[str, str | float | None] = {
        "dataset": dataset.dataset_id,
        "dataset_label": dataset.label,
        "units": dataset.units,
        "episode_id": row.episode_id,
        "source_timestamp": row.source_timestamp,
        "machine_status": row.machine_status,
        **row.raw,
    }
    for mapping in mappings:
        context[f"{mapping.telemetry_field}_source"] = mapping.source_column
        if mapping.unit:
            context[f"{mapping.telemetry_field}_unit"] = mapping.unit
    return {
        "timestamp": timestamp,
        "asset_id": asset_id,
        "metrics": metrics,
        "source": SOURCE_NAME,
        "source_context": context,
    }
