"""Turn the MetroPT-3 metro air-compressor recording into 5-minute telemetry.

Source: UCI Machine Learning Repository, dataset 791 (CC BY 4.0), Davari et al.
The raw file holds 1.5M readings at ~10 s intervals from Feb-Sep 2020. The
compressor constantly cycles between off, offloaded and loaded, so single
readings are not meaningful on their own; 5-minute averages are what an edge
gateway would report. Failure windows come from the operator's report in the
dataset description (four air leaks).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_FILE = BACKEND_DIR / "data" / "raw" / "MetroPT3" / "MetroPT3(AirCompressor).csv"
PROCESSED_FILE = BACKEND_DIR / "data" / "processed" / "metropt3" / "metropt3_5min.csv"
REPLAY_FILE = BACKEND_DIR / "data" / "replay" / "compressor_failure_episodes.csv"

AIR_LEAKS = [
    ("2020-04-18 00:00", "2020-04-18 23:59"),
    ("2020-05-29 23:30", "2020-05-30 06:00"),
    ("2020-06-05 10:00", "2020-06-07 14:30"),
    ("2020-07-15 14:30", "2020-07-15 19:00"),
]
AGGREGATES = {
    "Oil_temperature": ("oil_temperature_c", "mean"),
    "TP3": ("tp3_bar", "mean"),
    "Motor_current": ("motor_current_a", "mean"),
    "Reservoirs": ("reservoirs_min_bar", "min"),
    "DV_eletric": ("loaded_fraction", "mean"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=RAW_FILE)
    parser.add_argument("--lead-hours", type=float, default=48.0, help="Normal operation kept before each leak.")
    parser.add_argument("--tail-hours", type=float, default=12.0, help="Operation kept after each leak.")
    return parser.parse_args()


def build(args: argparse.Namespace) -> dict[str, object]:
    raw = pd.read_csv(args.input, usecols=["timestamp", *AGGREGATES], parse_dates=["timestamp"])
    frame = (
        raw.set_index("timestamp")
        .resample("5min")
        .agg({column: how for column, (_, how) in AGGREGATES.items()})
        .rename(columns={column: name for column, (name, _) in AGGREGATES.items()})
        .dropna()
        .round(4)
    )
    frame["machine_status"] = "NORMAL"
    for start, end in AIR_LEAKS:
        frame.loc[start:end, "machine_status"] = "AIR_LEAK"
    frame.index.name = "source_timestamp"
    frame = frame.reset_index()
    frame["source_timestamp"] = frame["source_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(PROCESSED_FILE, index=False)

    timestamps = pd.to_datetime(frame["source_timestamp"])
    episodes = []
    for start, end in AIR_LEAKS:
        window = (timestamps >= pd.Timestamp(start) - pd.Timedelta(hours=args.lead_hours)) & (
            timestamps <= pd.Timestamp(end) + pd.Timedelta(hours=args.tail_hours)
        )
        episodes.append(frame[window].assign(episode_id=f"compressor-{start[:10]}"))
    replay = pd.concat(episodes)
    replay = replay[["episode_id", "source_timestamp", "machine_status", *[name for name, _ in AGGREGATES.values()]]]
    REPLAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    replay.to_csv(REPLAY_FILE, index=False)

    return {
        "processed": str(PROCESSED_FILE),
        "processed_rows": int(len(frame)),
        "replay": str(REPLAY_FILE),
        "replay_rows": int(len(replay)),
        "air_leak_rows": int((frame["machine_status"] == "AIR_LEAK").sum()),
    }


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2))
