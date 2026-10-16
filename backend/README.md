# Auravance Backend

Demo-first backend scaffold for the Auravance predictive maintenance platform.

## Run

```bash
pip install -e backend
```

Then start the API:

```bash
uvicorn app.main:app --app-dir backend --reload
```

## Demo Flow

1. Start the API server.
2. Run the simulator to generate fake sensor telemetry.
3. Query assets, telemetry, predictions, alerts, and diagnostics from the API.

## Simulator

```bash
python backend/scripts/simulate_telemetry.py
```

## Real-Data Replay

Streams real recorded machine data into the ingest API, as if the machines were
live. Every registered asset gets the dataset that matches its type:

| Asset types | Dataset | Real failures | Units |
|---|---|---|---|
| pump, cooling-system | Kaggle pump-sensor recording, 1-min readings | 7 breakdowns | anonymized |
| compressor | [MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset) metro-train air compressor (UCI, CC BY 4.0), 5-min averages | 4 air leaks (operator report) | real: oil temperature degC, panel pressure bar, motor current A |
| motor, drive, conveyor | NASA/IMS bearing run-to-failure rig (shaft driven by an AC motor at 2000 rpm), a 1-s vibration snapshot every 10 min | 3 bearing failures | real: worst-bearing vibration RMS in g |

```bash
python backend/scripts/replay_telemetry.py
```

- **Every registered asset streams by default** (`--assets all`). The replay reads
  `GET /telemetry/ingest/targets` (asset id, type and profile) and re-checks it
  every `--refresh-seconds` (default 60), so new or deleted assets are picked up
  without a restart. Pass `--assets pump-04,compressor-17` to stream to specific assets.
- Assets that share a dataset start at evenly spaced points in it, so the plant
  shows machines in different real states at once.
- Each tick sends one `POST /telemetry/ingest/batch` with a reading for every asset,
  saved in a single transaction. By default it advances 5 recorded minutes every
  2 s (rounded to each dataset's sampling: 1, 5 and 10 minutes). Tune with
  `--minutes-per-tick`, `--interval`, `--episodes`, `--ticks`.
- Readings are stamped with the current time. The original timestamp, raw values,
  the dataset's ground-truth status (`NORMAL`, `BROKEN`, `RECOVERING`, `AIR_LEAK`,
  `FAILED`), units and dataset name travel in `source_context`, and the dashboard
  shows them next to the model output.
- The replay waits for the API and retries with backoff if it goes down. It exits
  only on errors a retry cannot fix (bad ingest key, unknown asset).

### Preparing the datasets

Replay files in `data/replay/` and the processed training files are committed.
To rebuild them from the original sources:

```bash
# Pump: needs the Kaggle CSV processed by prepare_datasets.py
python backend/scripts/build_replay_dataset.py
# Compressor: download MetroPT-3 (208 MB zip) from UCI into data/raw/MetroPT3/
python backend/scripts/prepare_metropt.py
# Motor: the IMS .rar archives in data/interim/ims_bearings/extracted/, needs 7-Zip.
# Extracts one test at a time (6.5 GB unpacked in total), caches features per test.
python backend/scripts/prepare_ims.py
```

### Pump notes

The pump channels are anonymized, so their units are unknown. The four modelled
channels are rescaled with the transform saved in
`artifacts/models/anomaly_isolation_forest.json`, so the anomaly model sees exactly
the features it was trained on. The anomaly model flags about 95% of breakdown and
recovery minutes. After each recovery, several hours stay flagged. This is correct:
the dataset switches back to `NORMAL` while the pump is still idle.

### Ingest security

Set `AURAVANCE_INGEST_API_KEY` on the server to require a matching
`X-Ingest-Key` header on `POST /telemetry/ingest`, `POST /telemetry/ingest/batch`
and `GET /telemetry/ingest/targets`. The replay and simulator
scripts read the same environment variable. When it is unset, ingest stays open
for local development. Repeat alerts for a sustained condition are suppressed
for `AURAVANCE_ALERT_COOLDOWN_SECONDS` (default 300) unless the severity changes.

## Current Scope

- FastAPI application setup
- SQLite-backed assets, telemetry, and alerts
- SQLite-backed dataset catalog and artifact registry
- Trained Isolation Forest anomaly scoring with a safe rules fallback
- Diagnostics service with sample knowledge references
- Simulated telemetry generator for asset demo flows

## Dataset Preparation

Place raw datasets under:

```text
backend/data/raw/
  AI4I_2020_Predictive_Maintenance/
  NASA_C_MAPPS_Turbofan_Engine_Degradation_Simulation/
  IMS_Bearings/
  Sensor_pump_data/
```

Then install backend dependencies and prepare the datasets:

```bash
pip install -e .
python scripts/prepare_datasets.py
```

What the script does:

- validates the four raw dataset folders
- extracts `CMAPSSData.zip` into `data/interim/c_mapss/extracted`
- extracts `IMS.7z` into `data/interim/ims_bearings/extracted`
- writes normalized CSV outputs to `data/processed`
- registers dataset metadata in the SQLite database

You can inspect the dataset registry from the API:

```text
GET /api/v1/datasets
```

## Knowledge Preparation

The OpenAI-backed RAG pipeline expects the API key to be stored as an environment variable and never hardcoded in source.

If you already keep secrets in `backend/.env`, the backend now loads that file automatically at startup and during knowledge indexing.

On Windows PowerShell, set it like this for your current shell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

To persist it for your user profile:

```powershell
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "your_api_key_here", "User")
```

Optional model overrides:

```powershell
$env:AURAVANCE_RAG_RESPONSE_MODEL="gpt-4.1-mini"
$env:AURAVANCE_RAG_EMBEDDING_MODEL="text-embedding-3-small"
```

Place manuals under:

```text
backend/knowledge/raw/
  valeo/
    m1.pdf
    m2.pdf
    m3.pdf
```

Then prepare the knowledge index:

```bash
pip install -e .
python scripts/prepare_knowledge.py
```

What the script does:

- scans `knowledge/raw/**/*.pdf`
- scans built-in markdown guides under `backend/knowledge/*.md`
- extracts PDF text
- writes normalized text files to `knowledge/processed`
- writes JSONL chunks to `knowledge/chunks`
- builds TF-IDF-style chunk vectors across the full corpus
- requests OpenAI embeddings for each chunk when `OPENAI_API_KEY` is set
- stores document, chunk, and corpus-vector metadata in SQLite

You can inspect indexed manuals from the API:

```text
GET /api/v1/knowledge/documents
GET /api/v1/knowledge/search?q=bearing%20temperature
```

## Root Cause Analysis RAG Flow

The diagnostics service now uses a grounded retrieval flow:

1. fetch the latest prediction for an asset
2. build a retrieval query from the asset context, symptom summary, and dominant signal
3. generate a query embedding with OpenAI and retrieve the highest scoring manual chunks from the indexed knowledge base
4. send the prediction context plus retrieved evidence into the OpenAI Responses API
5. return structured root-cause analysis with grounded causes, actions, confidence, and evidence

Useful endpoints:

```text
GET /api/v1/diagnostics/status
GET /api/v1/diagnostics/retrieve?q=bearing%20temperature
POST /api/v1/diagnostics/root-cause
```

Example root-cause payload:

```json
{
  "asset_id": "compressor-17",
  "symptom_summary": "High vibration and bearing temperature on compressor 17 during line 1 production ramp.",
  "recent_alert_ids": []
}
```

Response fields now include:

- `grounded_summary`
- `likely_causes`
- `recommended_actions`
- `confidence`
- `generation_mode`
- `generation_model`
- `evidence_snippets`

Status endpoint behavior:

- `openai_api_key_loaded`: confirms the backend read the key without exposing it
- `knowledge_documents`: indexed manuals count
- `knowledge_chunks`: total chunk count
- `embedded_chunks`: chunks that already have OpenAI embeddings

## Train The Anomaly Model

The anomaly baseline trains on normal operating records from the processed pump dataset and evaluates
against `RECOVERING` and `BROKEN` records. It writes a versioned model plus readable metadata under
`backend/artifacts/models`.

From the repository root:

```powershell
.\.venv\Scripts\python.exe backend\scripts\train_anomaly_model.py
```

Restart the API after training. Authenticated users can verify the active model at:

```text
GET /api/v1/predictions/model/status
```

If the artifact or its Python dependencies are unavailable, the API stays operational and reports
`fallback_active: true` while using the original rules scorer.

## Train Failure Prediction And RUL Models

Both models are trained on the pump-sensor recording (7 real breakdowns), using the
anomaly model's feature transform, so all three models see the same features that
live telemetry produces. Train from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\scripts\train_failure_model.py
.\.venv\Scripts\python.exe backend\scripts\train_rul_model.py
```

Restart the API after training. Check all active prediction models at:

```text
GET /api/v1/predictions/models/status
```

- **Failure model** predicts P(pump is broken/recovering now, or breaks within 72 h).
- **RUL model** predicts hours until the next breakdown, capped at 240 h (0 while down).
- **Evaluation is leave-one-failure-out:** each failure cycle is scored by a model
  trained without it. The results are stored in each model's `.json` metadata.
  Failure model: AUC 0.66. RUL: MAE 64 h against 81 h for a constant guess.
- **Honest limits:** with 4 sensors and 7 failures, the models clearly track the
  pump's current state. Held-out P(fail) is about 0.89 when down and about 0.14 when
  healthy, and RUL falls from about 180 h to about 22 h. Forecasting days ahead is
  weak: the probability rises before only some failures (Jun 28, Jul 8, Jul 25)
  and stays near the base rate before the others. Using all 51 sensors performed
  worse (AUC 0.51), because the extra sensors drift between months.
- **Out-of-fold serving:** each model file also stores the 8 held-out fold models.
  Replayed readings (`source_context.dataset == "kaggle-pump-sensor"`) are scored
  by the fold model that never saw that failure, so the replay never shows
  memorised training data. These show as `...+heldout-N` in
  `failure_model_version` and `rul_model_version`. Any other telemetry uses the
  full model.

## Compressor And Motor Models

Each equipment profile has its own anomaly, failure and RUL models, trained on that
machine type's real dataset in real units. Scoring picks the set from the asset type
(`app/services/model_profiles.py`), and `GET /predictions/models/status` lists all of them.

```bash
python backend/scripts/train_profile_models.py compressor
python backend/scripts/train_profile_models.py motor
```

Held-out results (leave-one-failure-out, stored in each model's `.json`):

| | Compressor (MetroPT-3, 4 air leaks) | Motor (IMS, 3 bearing failures) |
|---|---|---|
| Anomaly: failure vs healthy AUC | 0.99 (1% false flags) | 0.98 (1% false flags) |
| P(fail) when healthy / 1-3 days before / last 24 h / during failure | 0.08 / 0.06 / 0.06 / 0.33 | 0.22 / 0.42 / 0.78 / - |
| RUL in the last 24 h | no warning (sudden) | 33 h (190 h when healthy) |

- **Compressor air leaks are sudden.** The hours before a leak look like normal
  running, so a 72 h forecast is not learnable from these sensors (AUC 0.45). The
  models learn "leak in progress" instead (AUC 0.96) and add the empirical base
  rate: P = P(leak now) + (1 - P(leak now)) x 6%, RUL = (1 - P(leak now)) x mean
  healthy hours. See `app/services/ml_estimators.py`.
- **Motor bearings degrade gradually.** Worst-bearing vibration climbs from about
  0.10 g to 0.2-0.5 g over the final day, so the models learn the 72 h and
  hours-to-failure targets directly.
- **Known limitation: absolute baselines differ between machines.** IMS test 1
  ran at about 0.11 g where tests 2 and 3 ran at about 0.08 g. A model that never
  saw test 1 therefore rates it as already worn days before failure. Per-asset
  baselines, learned from each machine's own healthy period, would fix this.

## New Master Data Endpoints

After starting the API, these read endpoints are available:

```text
GET /api/v1/plants
GET /api/v1/vendors
GET /api/v1/equipment
GET /api/v1/sensors
GET /api/v1/users
GET /api/v1/maintenance-schedules
GET /api/v1/work-orders
GET /api/v1/defects
```

## Next Build Targets

1. Add chart-friendly dashboard endpoints and summary KPIs.
2. Train the RUL model on NASA C-MAPSS and connect it to prediction responses.
3. Validate anomaly thresholds against real Auravance equipment telemetry.
4. Add model drift monitoring and scheduled retraining.
