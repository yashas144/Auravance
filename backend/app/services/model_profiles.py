"""Which trained model set (profile) scores which kind of asset.

Each profile is trained on a real dataset recorded from that kind of machine:
  pump       - Kaggle pump-sensor recording (7 breakdowns)
  compressor - MetroPT-3 metro air compressor (4 air leaks)
  motor      - NASA/IMS motor-driven bearing rig (3 run-to-failure tests)
Drives and conveyors are motor-driven, so they use the motor profile; cooling
skids are pump loops, so they use the pump profile.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from app.core.config import settings
from app.core.db import get_connection


DEFAULT_PROFILE = "pump"
PROFILES = ("pump", "compressor", "motor")
PROFILE_DATASETS = {
    "pump": "kaggle-pump-sensor",
    "compressor": "metropt-3",
    "motor": "ims-bearings",
}
ASSET_TYPE_PROFILES = {
    "pump": "pump",
    "cooling-system": "pump",
    "compressor": "compressor",
    "motor": "motor",
    "drive": "motor",
    "conveyor": "motor",
}


def profile_for_asset_type(asset_type: str | None) -> str:
    return ASSET_TYPE_PROFILES.get((asset_type or "").strip().lower(), DEFAULT_PROFILE)


def profile_for_asset(asset_id: str) -> str:
    try:
        with closing(get_connection()) as connection:
            row = connection.execute("SELECT asset_type FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    except sqlite3.Error:
        return DEFAULT_PROFILE
    return profile_for_asset_type(row["asset_type"] if row else None)


def artifact_paths(profile: str) -> dict[str, Path]:
    if profile == "pump":
        return {
            "anomaly": Path(settings.anomaly_model_path),
            "failure": Path(settings.failure_model_path),
            "rul": Path(settings.rul_model_path),
        }
    registry = Path(settings.model_registry_path)
    return {
        "anomaly": registry / f"{profile}_anomaly_isolation_forest.joblib",
        "failure": registry / f"{profile}_failure_gradient_boosting.joblib",
        "rul": registry / f"{profile}_rul_gradient_boosting.joblib",
    }
