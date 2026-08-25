from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from urllib import request
import json


API_URL = "http://127.0.0.1:8000/api/v1/telemetry/ingest"
ASSETS = ["compressor-17", "motor-08", "pump-04"]


def build_metrics(asset_id: str, step: int) -> dict[str, float | None]:
    baseline = {
        "compressor-17": {
            "temperature_c": 72.0,
            "vibration_rms": 0.38,
            "pressure_bar": 5.0,
            "current_a": 10.2,
        },
        "motor-08": {
            "temperature_c": 68.0,
            "vibration_rms": 0.22,
            "pressure_bar": None,
            "current_a": 8.5,
        },
        "pump-04": {
            "temperature_c": 64.0,
            "vibration_rms": 0.31,
            "pressure_bar": 4.2,
            "current_a": 9.1,
        },
    }[asset_id].copy()

    for key, value in list(baseline.items()):
        if value is None:
            continue
        jitter = random.uniform(-0.25, 0.25) if key == "vibration_rms" else random.uniform(-1.5, 1.5)
        baseline[key] = value + jitter

    if asset_id == "compressor-17" and step > 10:
        baseline["temperature_c"] += step * 0.7
        baseline["vibration_rms"] += step * 0.015
    if asset_id == "motor-08" and step > 14:
        baseline["current_a"] += step * 0.18
        baseline["temperature_c"] += step * 0.25
    if asset_id == "pump-04" and step > 12:
        swing = 1.0 if step % 2 == 0 else -1.0
        baseline["pressure_bar"] += swing * 1.1

    baseline["vibration_rms"] = max(0.05, round(baseline["vibration_rms"], 3))
    baseline["temperature_c"] = round(baseline["temperature_c"], 2)
    baseline["current_a"] = round(baseline["current_a"], 2)
    if baseline["pressure_bar"] is not None:
        baseline["pressure_bar"] = round(baseline["pressure_bar"], 2)
    return baseline


def send_payload(payload: dict[str, object]) -> None:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=5) as response:
        print(f"{payload['asset_id']}: {response.status}")


def main() -> None:
    print("Starting telemetry simulator. Press Ctrl+C to stop.")
    step = 0
    while True:
        for asset_id in ASSETS:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "asset_id": asset_id,
                "metrics": build_metrics(asset_id, step),
            }
            send_payload(payload)
        step += 1
        time.sleep(3)


if __name__ == "__main__":
    main()
