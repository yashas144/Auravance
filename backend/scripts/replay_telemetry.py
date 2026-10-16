"""Stream real recorded failure episodes into the Auravance ingest API.

By default every registered asset gets a live stream from the real dataset that
matches its equipment profile:
  pump, cooling-system        -> Kaggle pump-sensor recording (7 breakdowns)
  compressor                  -> MetroPT-3 metro air compressor (4 air leaks)
  motor, drive, conveyor      -> NASA/IMS motor-driven bearing rig (3 run-to-failure tests)
Assets sharing a dataset start at evenly spaced points in it, so the plant shows
machines in different states at once. Every tick sends one batch with the next
reading for each asset, stamped with the current time. The original timestamp,
raw readings and the dataset's ground-truth status travel in source_context.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.replay import (  # noqa: E402
    DATASETS,
    ChannelMapping,
    ReplayDataset,
    ReplayRow,
    build_payload,
    build_timeline,
    group_episodes,
    read_replay_rows,
    staggered_start,
    stream_from,
    stride_for,
)


MAX_BACKOFF_SECONDS = 30.0
# Retrying these cannot succeed; they mean the command line or server config is wrong.
FATAL_STATUSES = {400, 401, 403, 404, 422}


class FatalIngestError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay real pump failure episodes as live telemetry.")
    parser.add_argument(
        "--api-url",
        default=os.getenv("AURAVANCE_API_URL", "http://127.0.0.1:8000/api/v1"),
        help="Base API URL (env AURAVANCE_API_URL).",
    )
    parser.add_argument(
        "--ingest-key",
        default=os.getenv("AURAVANCE_INGEST_API_KEY", ""),
        help="Sent as X-Ingest-Key (env AURAVANCE_INGEST_API_KEY).",
    )
    parser.add_argument(
        "--assets",
        default="all",
        help="'all' (default) streams to every registered asset and picks up new ones; "
        "or a comma-separated list of asset ids.",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between ticks.")
    parser.add_argument(
        "--minutes-per-tick",
        type=float,
        default=5.0,
        help="Recorded minutes advanced per tick (rounded to each dataset's sampling: "
        "pump 1 min, compressor 5 min, motor 10 min).",
    )
    parser.add_argument(
        "--episodes",
        default="",
        help="Comma-separated episode ids (default: all). Datasets with no matching episode are skipped.",
    )
    parser.add_argument(
        "--refresh-seconds",
        type=float,
        default=60.0,
        help="With --assets all, how often to re-check the asset list.",
    )
    parser.add_argument("--ticks", type=int, default=0, help="Stop after this many ticks (default: run forever).")
    return parser.parse_args()


def _request(url: str, ingest_key: str, payload: dict | None = None) -> object:
    headers = {"Content-Type": "application/json"}
    if ingest_key:
        headers["X-Ingest-Key"] = ingest_key
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    http_request = request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with request.urlopen(http_request, timeout=15) as response:
            # Always drain the body: on Windows, closing a socket with unread data
            # sends a TCP reset, which the server logs as ConnectionResetError.
            return json.loads(response.read() or b"null")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code in FATAL_STATUSES:
            raise FatalIngestError(exc.code, f"HTTP {exc.code} from {url}: {detail}") from exc
        raise


def request_with_retry(url: str, ingest_key: str, payload: dict | None = None) -> object:
    """Retry transient failures (server down, 5xx, timeouts) with capped backoff."""
    delay = 1.0
    while True:
        try:
            return _request(url, ingest_key, payload)
        except FatalIngestError:
            raise
        except (error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            print(
                f"  API unavailable at {url} ({exc}); retrying in {delay:.0f}s. "
                "Is the backend running? (uvicorn app.main:app --app-dir backend)",
                flush=True,
            )
            time.sleep(delay)
            delay = min(MAX_BACKOFF_SECONDS, delay * 2)


@dataclass(slots=True)
class LoadedDataset:
    spec: ReplayDataset
    mappings: list[ChannelMapping]
    timeline: list[ReplayRow]


def load_datasets(minutes_per_tick: float, episode_filter: set[str]) -> dict[str, LoadedDataset]:
    loaded: dict[str, LoadedDataset] = {}
    for profile, spec in DATASETS.items():
        if not spec.replay_path.exists():
            print(f"  Skipping {profile}: replay file not found ({spec.replay_path}).", flush=True)
            continue
        episodes = group_episodes(read_replay_rows(spec.replay_path))
        if episode_filter:
            episodes = [episode for episode in episodes if episode[0].episode_id in episode_filter]
            if not episodes:
                continue
        timeline = build_timeline(episodes, stride_for(spec, minutes_per_tick))
        loaded[profile] = LoadedDataset(spec, spec.load_mappings(), timeline)
        print(f"  {profile:10s} {spec.label}: {len(episodes)} episode(s), {len(timeline)} readings per loop", flush=True)
    return loaded


class AssetStreams:
    """One replay stream per asset, from the dataset matching its profile."""

    def __init__(self, datasets: dict[str, LoadedDataset]) -> None:
        self._datasets = datasets
        self._streams: dict[str, tuple[LoadedDataset, Iterator[ReplayRow]]] = {}

    @property
    def asset_ids(self) -> list[str]:
        return list(self._streams)

    def sync(self, targets: list[dict]) -> None:
        wanted = {t["asset_id"]: t["profile"] for t in targets if t["profile"] in self._datasets}
        removed = [asset_id for asset_id in self._streams if asset_id not in wanted]
        for asset_id in removed:
            del self._streams[asset_id]
        added = [asset_id for asset_id in wanted if asset_id not in self._streams]
        for asset_id in added:
            profile = wanted[asset_id]
            dataset = self._datasets[profile]
            peers = [other for other, other_profile in wanted.items() if other_profile == profile]
            start = staggered_start(asset_id, peers, len(dataset.timeline))
            self._streams[asset_id] = (dataset, stream_from(dataset.timeline, start))
        if added or removed:
            by_profile = Counter(dataset.spec.profile for dataset, _ in self._streams.values())
            message = f"Streaming to {len(self._streams)} asset(s) (" + ", ".join(
                f"{count} {profile}" for profile, count in sorted(by_profile.items())
            ) + ")"
            if added:
                message += f"; added {', '.join(added)}"
            if removed:
                message += f"; removed {', '.join(removed)}"
            print(message, flush=True)

    def next_payloads(self, timestamp: str) -> list[tuple[dict, ReplayRow]]:
        payloads = []
        for asset_id, (dataset, stream) in self._streams.items():
            row = next(stream)
            payloads.append((build_payload(row, asset_id, timestamp, dataset.mappings, dataset.spec), row))
        return payloads


def main() -> None:
    args = parse_args()
    api_url = args.api_url.rstrip("/")
    discover_assets = args.assets.strip().lower() == "all"
    fixed_assets = [] if discover_assets else [a.strip() for a in args.assets.split(",") if a.strip()]
    if not discover_assets and not fixed_assets:
        sys.exit("--assets needs 'all' or at least one asset id.")

    print("Loading real datasets:", flush=True)
    episode_filter = {episode.strip() for episode in args.episodes.split(",") if episode.strip()}
    datasets = load_datasets(args.minutes_per_tick, episode_filter)
    if not datasets:
        sys.exit("No replay datasets available; see backend/README.md (Real-Data Replay).")
    streams = AssetStreams(datasets)
    print(
        f"Replaying to {'every registered asset' if discover_assets else ', '.join(fixed_assets)}: "
        f"{args.minutes_per_tick:g} recorded minute(s) every {args.interval}s. Ctrl+C to stop.",
        flush=True,
    )

    def refresh_assets() -> None:
        targets = list(request_with_retry(f"{api_url}/telemetry/ingest/targets", args.ingest_key))
        if not discover_assets:
            known = {target["asset_id"] for target in targets}
            missing = [asset_id for asset_id in fixed_assets if asset_id not in known]
            if missing:
                raise FatalIngestError(404, f"Unknown asset(s): {', '.join(missing)}")
            targets = [target for target in targets if target["asset_id"] in fixed_assets]
        streams.sync(targets)

    batch_url = f"{api_url}/telemetry/ingest/batch"
    try:
        refresh_assets()
        last_refresh = time.monotonic()
        tick = 0
        while args.ticks <= 0 or tick < args.ticks:
            if discover_assets and time.monotonic() - last_refresh >= args.refresh_seconds:
                refresh_assets()
                last_refresh = time.monotonic()
            if not streams.asset_ids:
                print("No assets to stream yet; checking again shortly.", flush=True)
                time.sleep(max(args.interval, 5.0))
                refresh_assets()
                continue

            payloads = streams.next_payloads(datetime.now(timezone.utc).isoformat())
            try:
                request_with_retry(batch_url, args.ingest_key, {"readings": [payload for payload, _ in payloads]})
            except FatalIngestError as exc:
                if exc.status == 404 and discover_assets:
                    # An asset was deleted since the last refresh; resync and carry on.
                    print(f"  {exc}; refreshing asset list.", flush=True)
                    refresh_assets()
                    last_refresh = time.monotonic()
                    continue
                raise

            tick += 1
            states = Counter(row.machine_status for _, row in payloads)
            summary = ", ".join(f"{count} {state}" for state, count in sorted(states.items()))
            print(f"tick {tick}: {len(payloads)} readings ({summary})", flush=True)
            time.sleep(args.interval)
    except FatalIngestError as exc:
        sys.exit(f"Stopping: {exc}")
    except KeyboardInterrupt:
        print("Replay stopped.")


if __name__ == "__main__":
    main()
