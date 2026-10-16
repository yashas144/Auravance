from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.replay import DATASETS, load_pump_mappings  # noqa: E402


STATUS_COLUMN = "machine_status"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract real pump failure episodes into a compact replay file."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=BACKEND_DIR / "data" / "processed" / "pump_sensor" / "sensor_processed.csv",
    )
    parser.add_argument("--output", type=Path, default=DATASETS["pump"].replay_path)
    parser.add_argument("--lead-hours", type=float, default=36.0, help="Normal operation kept before each failure.")
    parser.add_argument(
        "--max-recovery-hours",
        type=float,
        default=12.0,
        help="Cap on RECOVERING minutes kept per episode (one outage lasts ~6 days).",
    )
    parser.add_argument("--tail-hours", type=float, default=6.0, help="Normal operation kept after recovery.")
    return parser.parse_args()


def build(args: argparse.Namespace) -> dict[str, object]:
    sensor_columns = [mapping.source_column for mapping in load_pump_mappings()]
    frame = pd.read_csv(args.input, usecols=["timestamp", *sensor_columns, STATUS_COLUMN])
    frame[STATUS_COLUMN] = frame[STATUS_COLUMN].str.strip().str.upper()

    lead = int(args.lead_hours * 60)
    max_recovery = int(args.max_recovery_hours * 60)
    tail = int(args.tail_hours * 60)
    is_normal = (frame[STATUS_COLUMN] == "NORMAL").to_numpy()

    episodes: list[pd.DataFrame] = []
    summary: list[dict[str, object]] = []
    previous_end = -1
    for break_index in frame.index[frame[STATUS_COLUMN] == "BROKEN"]:
        recovered_index = break_index + 1
        while recovered_index < len(frame) and not is_normal[recovered_index]:
            recovered_index += 1
        recovery_minutes = recovered_index - break_index - 1

        start = max(previous_end + 1, break_index - lead)
        if recovery_minutes > max_recovery:
            # Skip the middle of very long outages but still show the return to normal.
            parts = [
                frame.iloc[start : break_index + 1 + max_recovery // 2],
                frame.iloc[recovered_index - max_recovery // 2 : min(len(frame), recovered_index + tail)],
            ]
        else:
            parts = [frame.iloc[start : min(len(frame), recovered_index + tail)]]
        episode = pd.concat(parts)
        previous_end = int(episode.index[-1])

        episode_id = f"pump-{frame.at[break_index, 'timestamp'][:10]}"
        episodes.append(episode.assign(episode_id=episode_id))
        summary.append(
            {
                "episode_id": episode_id,
                "failure_at": frame.at[break_index, "timestamp"],
                "rows": int(len(episode)),
                "recovery_minutes_in_source": int(recovery_minutes),
            }
        )

    if not episodes:
        raise ValueError("No BROKEN rows found; cannot build failure episodes.")

    output = pd.concat(episodes).rename(columns={"timestamp": "source_timestamp"})
    output = output[["episode_id", "source_timestamp", STATUS_COLUMN, *sensor_columns]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, float_format="%.6g")
    return {"output": str(args.output), "rows": int(len(output)), "episodes": summary}


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), indent=2))
