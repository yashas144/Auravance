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

Train the supervised AI4I failure classifier and NASA C-MAPSS RUL regressor from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\scripts\train_failure_model.py
.\.venv\Scripts\python.exe backend\scripts\train_rul_model.py
```

Restart the API after training. Check all active prediction models at:

```text
GET /api/v1/predictions/models/status
```

The failure output is a demo operating-window probability mapped to the dashboard's 72-hour field.
The RUL model predicts capped C-MAPSS cycles and converts them to demo hours using two hours per cycle.
Both adapters must be recalibrated when real equipment sensor semantics and duty-cycle history are available.

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
