"""Turn the NASA/IMS bearing run-to-failure archives into per-snapshot features.

Each archive holds one test: a shaft driven by an AC motor at 2000 rpm with four
bearings, run until a bearing failed. Every ~10 minutes the rig recorded a
1-second, 20 kHz vibration snapshot. This script extracts one test at a time
(the full extraction is ~6.5 GB), reduces every snapshot to RMS/kurtosis per
bearing, caches that test's features, and deletes the extracted text before
moving on. Re-running resumes from the cached tests.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = BACKEND_DIR / "data" / "interim" / "ims_bearings" / "extracted"
WORK_DIR = BACKEND_DIR / "data" / "interim" / "ims_bearings" / "work"
CACHE_DIR = BACKEND_DIR / "data" / "interim" / "ims_bearings" / "features"
OUTPUT = BACKEND_DIR / "data" / "processed" / "ims_bearings" / "ims_features.csv"
REPLAY_FILE = BACKEND_DIR / "data" / "replay" / "motor_failure_episodes.csv"

# Per the IMS readme. Test 1 logs two accelerometers per bearing; use the first
# (x-axis) so every test contributes one channel per bearing.
TESTS = {
    "1st_test.rar": {"test_id": "ims-test-1", "snapshots": 2156, "bearing_columns": [0, 2, 4, 6], "failed": "bearing 3 inner race, bearing 4 roller"},
    "2nd_test.rar": {"test_id": "ims-test-2", "snapshots": 984, "bearing_columns": [0, 1, 2, 3], "failed": "bearing 1 outer race"},
    "3rd_test.rar": {"test_id": "ims-test-3", "snapshots": 6324, "bearing_columns": [0, 1, 2, 3], "failed": "bearing 3 outer race"},
}


def find_7zip() -> str:
    candidate = shutil.which("7z") or shutil.which("7za")
    default = Path("C:/Program Files/7-Zip/7z.exe")
    if candidate:
        return candidate
    if default.exists():
        return str(default)
    sys.exit("7-Zip is required to extract the IMS .rar archives (https://www.7-zip.org).")


def remove_tree(path: Path) -> None:
    """Delete an extraction directory; the archives unpack as read-only files on Windows."""

    def make_writable_and_retry(function, target, _error) -> None:
        os.chmod(target, stat.S_IWRITE)
        function(target)

    shutil.rmtree(path, onexc=make_writable_and_retry)


def snapshot_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file() and path.name[:4].isdigit())


def snapshot_features(path: Path, columns: list[int]) -> dict[str, float]:
    values = pd.read_csv(path, sep="\t", header=None, usecols=columns, dtype=np.float64).to_numpy()
    centered = values - values.mean(axis=0)
    rms = np.sqrt((centered**2).mean(axis=0))
    kurtosis = (centered**4).mean(axis=0) / np.maximum(rms**4, 1e-12)
    features: dict[str, float] = {}
    for bearing, (bearing_rms, bearing_kurtosis) in enumerate(zip(rms, kurtosis, strict=True), start=1):
        features[f"bearing_{bearing}_rms"] = round(float(bearing_rms), 5)
        features[f"bearing_{bearing}_kurtosis"] = round(float(bearing_kurtosis), 3)
    return features


def process_archive(seven_zip: str, archive: Path, spec: dict) -> pd.DataFrame:
    """Features for one test, cached so an interrupted run never loses finished tests."""
    cache = CACHE_DIR / f"{spec['test_id']}.csv"
    if cache.exists():
        print(f"{spec['test_id']}: using cached features", flush=True)
        return pd.read_csv(cache)

    target = WORK_DIR / spec["test_id"]
    if target.exists() and len(snapshot_files(target)) == spec["snapshots"]:
        print(f"{spec['test_id']}: reusing already-extracted snapshots", flush=True)
    else:
        if target.exists():
            remove_tree(target)
        target.mkdir(parents=True)
        print(f"Extracting {archive.name} ...", flush=True)
        subprocess.run([seven_zip, "x", str(archive), f"-o{target}", "-y", "-bso0", "-bsp0"], check=True)

    snapshots = snapshot_files(target)
    rows = []
    for index, snapshot in enumerate(snapshots):
        recorded = datetime.strptime(snapshot.name, "%Y.%m.%d.%H.%M.%S")
        rows.append(
            {
                "test_id": spec["test_id"],
                "source_timestamp": recorded.strftime("%Y-%m-%d %H:%M:%S"),
                **snapshot_features(snapshot, spec["bearing_columns"]),
            }
        )
        if index % 500 == 0:
            print(f"  {spec['test_id']}: {index}/{len(snapshots)} snapshots", flush=True)

    features = pd.DataFrame(rows)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    features.to_csv(cache, index=False)
    remove_tree(target)
    return features


def build_motor_replay(features_path: Path, lead_hours: float) -> dict[str, object]:
    """Keep the final days of each test, where the bearing wears out, for live replay."""
    frame = pd.read_csv(features_path)
    rms_columns = [column for column in frame.columns if column.endswith("_rms")]
    frame["max_bearing_rms"] = frame[rms_columns].max(axis=1)
    times = pd.to_datetime(frame["source_timestamp"])
    end = times.groupby(frame["test_id"]).transform("max")
    keep = times >= end - pd.Timedelta(hours=lead_hours)
    window = frame[keep].copy()
    window["machine_status"] = np.where(times[keep] == end[keep], "FAILED", "NORMAL")
    window = window.rename(columns={"test_id": "episode_id"})
    window = window[["episode_id", "source_timestamp", "machine_status", *rms_columns, "max_bearing_rms"]]
    REPLAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    window.to_csv(REPLAY_FILE, index=False)
    return {"replay": str(REPLAY_FILE), "replay_rows": int(len(window))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replay-lead-hours", type=float, default=120.0)
    parser.add_argument("--replay-only", action="store_true", help="Rebuild the replay file from existing features.")
    args = parser.parse_args()
    if args.replay_only:
        print(json.dumps(build_motor_replay(args.output, args.replay_lead_hours), indent=2))
        return

    seven_zip = find_7zip()
    frame = pd.concat(
        [process_archive(seven_zip, ARCHIVE_DIR / name, spec) for name, spec in TESTS.items()],
        ignore_index=True,
    )
    if WORK_DIR.exists() and not any(WORK_DIR.iterdir()):
        WORK_DIR.rmdir()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)

    summary = {
        spec["test_id"]: {
            "snapshots": int((frame["test_id"] == spec["test_id"]).sum()),
            "start": frame.loc[frame["test_id"] == spec["test_id"], "source_timestamp"].min(),
            "failure_at": frame.loc[frame["test_id"] == spec["test_id"], "source_timestamp"].max(),
            "failed": spec["failed"],
        }
        for spec in TESTS.values()
    }
    replay = build_motor_replay(args.output, args.replay_lead_hours)
    print(json.dumps({"output": str(args.output), "rows": len(frame), "tests": summary, **replay}, indent=2))


if __name__ == "__main__":
    main()
