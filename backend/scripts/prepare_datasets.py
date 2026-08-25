from __future__ import annotations

import csv
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

try:
    import py7zr
except ImportError:  # pragma: no cover - depends on local install state
    py7zr = None


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.db import init_db, upsert_dataset


RAW_ROOT = Path(settings.raw_data_root)
INTERIM_ROOT = Path(settings.interim_data_root)
PROCESSED_ROOT = Path(settings.processed_data_root)
FEATURE_ROOT = Path(settings.feature_data_root)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def normalize_column_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def ensure_data_directories() -> None:
    for directory in (RAW_ROOT, INTERIM_ROOT, PROCESSED_ROOT, FEATURE_ROOT):
        directory.mkdir(parents=True, exist_ok=True)


def cmapss_column_names() -> list[str]:
    return ["unit_id", "cycle", "setting_1", "setting_2", "setting_3"] + [f"sensor_{index}" for index in range(1, 22)]


def extract_zip_if_needed(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        return destination

    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination)
    return destination


def extract_7z_if_needed(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        return destination

    if py7zr is None:
        raise RuntimeError(
            "py7zr is required to extract IMS.7z. Install dependencies with `pip install -e .` in backend."
        )

    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        archive.extractall(path=destination)
    return destination


def prepare_ai4i() -> tuple[dict, list[dict]]:
    raw_dir = RAW_ROOT / "AI4I_2020_Predictive_Maintenance"
    raw_file = raw_dir / "ai4i2020.csv"
    processed_dir = PROCESSED_ROOT / "ai4i"
    processed_dir.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_csv(raw_file)
    dataframe.columns = [normalize_column_name(column) for column in dataframe.columns]
    processed_file = processed_dir / "ai4i2020_processed.csv"
    dataframe.to_csv(processed_file, index=False)

    dataset = {
        "dataset_id": "ai4i_2020",
        "name": "AI4I 2020 Predictive Maintenance",
        "source": "UCI / AI4I 2020",
        "raw_path": str(raw_dir),
        "processed_path": str(processed_dir),
        "status": "processed",
        "record_count": int(len(dataframe)),
        "notes": "Tabular predictive maintenance baseline for supervised classification.",
        "last_synced_at": utc_now_iso(),
    }
    artifacts = [
        {
            "artifact_type": "processed_csv",
            "file_path": str(processed_file),
            "row_count": int(len(dataframe)),
            "metadata": {"columns": dataframe.columns.tolist()},
        }
    ]
    return dataset, artifacts


def prepare_pump_sensor() -> tuple[dict, list[dict]]:
    raw_dir = RAW_ROOT / "Sensor_pump_data"
    raw_file = raw_dir / "sensor.csv"
    processed_dir = PROCESSED_ROOT / "pump_sensor"
    processed_dir.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_csv(raw_file)
    dataframe.columns = [normalize_column_name(column) for column in dataframe.columns]
    dataframe = dataframe.loc[:, ~dataframe.columns.str.startswith("unnamed_")]
    processed_file = processed_dir / "sensor_processed.csv"
    dataframe.to_csv(processed_file, index=False)

    dataset = {
        "dataset_id": "pump_sensor",
        "name": "Sensor Pump Data",
        "source": "Kaggle / nphantawee pump sensor data",
        "raw_path": str(raw_dir),
        "processed_path": str(processed_dir),
        "status": "processed",
        "record_count": int(len(dataframe)),
        "notes": "High-volume multivariate sensor dataset for anomaly detection and time-series feature engineering.",
        "last_synced_at": utc_now_iso(),
    }
    artifacts = [
        {
            "artifact_type": "processed_csv",
            "file_path": str(processed_file),
            "row_count": int(len(dataframe)),
            "metadata": {"columns": dataframe.columns.tolist()},
        }
    ]
    return dataset, artifacts


def prepare_cmapss() -> tuple[dict, list[dict]]:
    raw_dir = RAW_ROOT / "NASA_C_MAPPS_Turbofan_Engine_Degradation_Simulation"
    archive_path = next(raw_dir.rglob("CMAPSSData.zip"))
    extracted_dir = INTERIM_ROOT / "c_mapss" / "extracted"
    processed_dir = PROCESSED_ROOT / "c_mapss"
    processed_dir.mkdir(parents=True, exist_ok=True)

    extract_zip_if_needed(archive_path, extracted_dir)

    artifacts: list[dict] = []
    total_rows = 0

    for source_file in sorted(extracted_dir.rglob("*.txt")):
        name = source_file.stem.lower()
        if name.startswith(("train_fd", "test_fd")):
            dataframe = pd.read_csv(source_file, sep=r"\s+", header=None, engine="python")
            dataframe.columns = cmapss_column_names()
        elif name.startswith("rul_fd"):
            dataframe = pd.read_csv(source_file, sep=r"\s+", header=None, engine="python")
            dataframe.columns = ["rul"]
        else:
            continue

        output_file = processed_dir / f"{name}.csv"
        dataframe.to_csv(output_file, index=False)
        total_rows += int(len(dataframe))
        artifacts.append(
            {
                "artifact_type": "processed_csv",
                "file_path": str(output_file),
                "row_count": int(len(dataframe)),
                "metadata": {"source_file": str(source_file), "columns": dataframe.columns.tolist()},
            }
        )

    dataset = {
        "dataset_id": "nasa_cmapss",
        "name": "NASA C-MAPSS Turbofan Engine Degradation Simulation",
        "source": "NASA PCoE",
        "raw_path": str(raw_dir),
        "extracted_path": str(extracted_dir),
        "processed_path": str(processed_dir),
        "status": "processed",
        "record_count": total_rows,
        "notes": "Run-to-failure engine dataset for RUL modeling and sequence learning.",
        "last_synced_at": utc_now_iso(),
    }
    return dataset, artifacts


def prepare_ims_bearings() -> tuple[dict, list[dict]]:
    raw_dir = RAW_ROOT / "IMS_Bearings"
    archive_path = next(raw_dir.rglob("IMS.7z"))
    extracted_dir = INTERIM_ROOT / "ims_bearings" / "extracted"
    processed_dir = PROCESSED_ROOT / "ims_bearings"
    processed_dir.mkdir(parents=True, exist_ok=True)

    extract_7z_if_needed(archive_path, extracted_dir)

    manifest_file = processed_dir / "ims_file_manifest.csv"
    records = []
    file_paths = sorted(path for path in extracted_dir.rglob("*") if path.is_file())
    nested_archives = [path for path in file_paths if path.suffix.lower() == ".rar"]
    extracted_data_files = [path for path in file_paths if path.suffix.lower() not in {".rar", ".pdf"}]

    for file_path in file_paths:
        relative_path = file_path.relative_to(extracted_dir)
        test_group = relative_path.parts[0] if relative_path.parts else "unknown"
        records.append(
            {
                "test_group": test_group,
                "relative_path": str(relative_path),
                "size_bytes": file_path.stat().st_size,
                "file_type": file_path.suffix.lower().lstrip(".") or "no_extension",
            }
        )

    with manifest_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["test_group", "relative_path", "size_bytes", "file_type"])
        writer.writeheader()
        writer.writerows(records)

    if nested_archives and not extracted_data_files:
        status = "nested_archives_detected"
        notes = (
            "IMS top-level archive extracted, but nested .rar files still need manual extraction "
            "into data/interim/ims_bearings/extracted before vibration files can be processed."
        )
        record_count = len(nested_archives)
    else:
        status = "indexed"
        notes = "Bearing run-to-failure archive indexed for downstream vibration feature extraction."
        record_count = len(extracted_data_files)

    dataset = {
        "dataset_id": "ims_bearings",
        "name": "IMS Bearings Dataset",
        "source": "NASA PCoE / IMS",
        "raw_path": str(raw_dir),
        "extracted_path": str(extracted_dir),
        "processed_path": str(processed_dir),
        "status": status,
        "record_count": record_count,
        "notes": notes,
        "last_synced_at": utc_now_iso(),
    }
    artifacts = [
        {
            "artifact_type": "manifest_csv",
            "file_path": str(manifest_file),
            "row_count": len(records),
            "metadata": {
                "archive_path": str(archive_path),
                "nested_rar_count": len(nested_archives),
                "extracted_data_file_count": len(extracted_data_files),
            },
        }
    ]
    return dataset, artifacts


def main() -> None:
    ensure_data_directories()
    init_db()

    preparations = [
        prepare_ai4i,
        prepare_pump_sensor,
        prepare_cmapss,
        prepare_ims_bearings,
    ]

    for prepare in preparations:
        dataset, artifacts = prepare()
        upsert_dataset(dataset, artifacts)
        print(f"Prepared {dataset['dataset_id']} -> {dataset['status']} ({dataset['record_count']} records)")


if __name__ == "__main__":
    main()
