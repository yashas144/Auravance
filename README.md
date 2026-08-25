# Auravance — AI-Powered Predictive Maintenance Platform

Auravance is an end-to-end industrial predictive maintenance platform that combines classical ML, deep learning, and LLM-based retrieval-augmented generation (RAG) to predict equipment failures, detect anomalies, and explain root causes in plain language.

Built as a portfolio-grade demonstration of production ML system design: model training pipelines, a typed FastAPI backend, a React monitoring dashboard, and a GPT-4o-powered diagnostic assistant grounded in internal maintenance knowledge.

---

## Why this exists

Unplanned equipment downtime is one of the costliest problems in industrial operations. Auravance simulates a realistic predictive maintenance stack — the kind used in manufacturing, energy, and heavy industry — covering the full loop:

**Sensor data → feature engineering → ML/DL models → anomaly & failure prediction → RAG-based root cause explanation → operator-facing dashboard.**

## Architecture

```
Auravance/
├── backend/          FastAPI service, ML pipelines, RAG engine
│   ├── app/
│   │   ├── api/routes/     REST endpoints (assets, telemetry, predictions, diagnostics, knowledge, alerts, auth)
│   │   ├── core/            Config, DB session, security
│   │   ├── models/          Pydantic schemas
│   │   └── services/        Business logic: anomaly detection, prognostics, RAG, scoring, telemetry
│   ├── scripts/              Dataset prep, knowledge base prep, model training
│   ├── artifacts/models/     Trained model binaries (Isolation Forest, Gradient Boosting)
│   ├── knowledge/            Domain knowledge base for RAG (maintenance playbooks, sensor guides)
│   └── data/                 Processed datasets (raw sources excluded — see Data section)
├── frontend/          React + Vite monitoring dashboard
└── docs/              Architecture notes
```

See [`docs/backend-architecture.md`](docs/backend-architecture.md) for a detailed system design writeup.

## Core capabilities

- **Failure prediction** — Gradient Boosting model trained on run-to-failure sensor data to estimate probability of equipment failure
- **Remaining Useful Life (RUL) estimation** — regression model trained on NASA C-MAPSS turbofan degradation data
- **Anomaly detection** — Isolation Forest for unsupervised detection of abnormal sensor behavior
- **RAG-based root cause analysis** — GPT-4o retrieves from a curated knowledge base (compressor, bearing, motor, and temperature guides) to generate grounded, human-readable explanations for detected issues, instead of relying on the LLM's unverified priors
- **Telemetry simulation** — synthetic real-time sensor stream generator for live dashboard demos
- **REST API** — endpoints for assets, telemetry ingestion, predictions, diagnostics, alerts, and knowledge queries
- **Monitoring dashboard** — React frontend for visualizing asset health, alerts, and diagnostic output

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python, SQLite |
| ML / DL | XGBoost, scikit-learn (Isolation Forest, Gradient Boosting), LSTM |
| LLM / RAG | GPT-4o, custom retrieval pipeline over chunked domain knowledge |
| Frontend | React, Vite |
| Data | NASA C-MAPSS (turbofan degradation), IMS Bearings, AI4I 2020, industrial pump sensor data |

## Datasets

Raw and intermediate dataset archives (multi-GB IMS bearing recordings, full sensor logs) are excluded from version control — see `.gitignore`. Processed, model-ready datasets are included under `backend/data/processed/` for reference.

To regenerate the full pipeline from raw sources:

```bash
python backend/scripts/prepare_datasets.py
python backend/scripts/prepare_knowledge.py
```

## Model training

```bash
python backend/scripts/train_anomaly_model.py
python backend/scripts/train_failure_model.py
python backend/scripts/train_rul_model.py
```

Trained artifacts are saved to `backend/artifacts/models/`.

## Running locally

**Backend**

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

**Environment variables**

The backend requires a `.env` file in `backend/` (not committed — see `backend/README.md` or `.env.example` for required keys, including your OpenAI API key for the RAG pipeline).

## Testing

```bash
cd backend
pytest tests/
```

## Roadmap / possible extensions

- Swap SQLite for a production-grade time-series store (TimescaleDB / InfluxDB) for telemetry at scale
- Add model monitoring/drift detection for the deployed prediction models
- Extend RAG knowledge base with additional equipment classes beyond compressors, bearings, and motors

## Author

Built by **Yashas Chandra Bathini** demonstrating full-stack ML system design — from data pipeline to deployed inference to LLM-grounded diagnostics.
