# Evidelta

Evidelta is an evidence-first change intelligence platform for tracking real product and platform signals across GitHub, docs, forums, status pages, and probe-style checks. The core idea is simple: collect noisy signals, normalize them into evidence, classify the product and dimension, cluster related reports, and present only the change records that are actually supported by usable evidence.

This repository contains the working backend and a minimal Next.js dashboard that surface the evidence feed, incident summary, and detailed provenance behind each signal.

## Why this project exists

Many product and platform regressions are not announced in a clean release note. They appear as scattered issues, docs updates, forum complaints, status-page notices, and probe output. Evidelta turns that noise into a compact change feed with:

- product and dimension classification
- time-window grouping
- evidence provenance
- conservative status grading
- citation-friendly detail view

The design is intentionally honest: weak or ambiguous evidence stays in a candidate state instead of being exaggerated into a measured or acknowledged incident.

## Product goals

The system is designed to answer questions like:

- Did a product or platform change recently?
- What dimension changed: latency, rate limits, structured output, availability, or another signal?
- Which source families support the claim?
- How much independent evidence exists?
- What exact records were used to build the conclusion?

## Current implementation

The project currently includes:

- FastAPI backend with API routes for ingestion, change detection, synthesis, evaluation, and UI data
- SQLAlchemy persistence for raw snapshots and evidence records
- evidence normalization and deduplication
- conservative clustering and signal grading logic
- minimal Next.js frontend for product selection, change feed, summary, and evidence drill-down
- local SQLite default database for development
- tests covering ingestion and evidence-grade logic

## Tech stack

- Python 3.9+
- FastAPI
- SQLAlchemy 2.x
- Pydantic + settings
- SQLite for local development
- PostgreSQL-ready schema and configuration for production deployment
- Next.js 14 for the dashboard frontend
- pytest for backend validation

## Repository layout

```text
.
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── change_detection.py
│   │       ├── extraction.py
│   │       ├── ingestion.py
│   │       ├── ui.py
│   │       └── ...
│   ├── db/
│   │   ├── base.py
│   │   └── __init__.py
│   ├── models/
│   │   ├── evidence.py
│   │   └── __init__.py
│   ├── services/
│   │   ├── change_detection.py
│   │   ├── evidence_pipeline.py
│   │   ├── extraction.py
│   │   ├── ingestion.py
│   │   ├── llm.py
│   │   ├── synthesis.py
│   │   └── ...
│   ├── config.py
│   ├── main.py
│   └── __init__.py
├── frontend/
│   ├── app/
│   ├── package.json
│   └── next.config.mjs
├── tests/
│   ├── test_change_detection.py
│   ├── test_ingestion.py
│   └── ...
├── .env.example
├── .gitignore
├── Evidelta.md
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── alembic/
└── requirements or generated local files
```

## Local development setup

1. Clone the repo.

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install -e .[dev]
   ```

3. Copy the environment file and adjust values if needed:

   ```bash
   cp .env.example .env
   ```

4. Start the backend:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. Start the frontend in a separate terminal:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

6. Open the app in a browser:

   - Backend API docs: http://localhost:8000/docs
   - Frontend UI: http://localhost:3000

## API flow

The backend supports a simple evidence lifecycle:

1. Ingest raw source data
2. Normalize and deduplicate by content hash
3. Store the raw snapshot and provenance metadata
4. Classify product and dimension from text
5. Cluster related evidence by product + dimension + time window
6. Grade the cluster conservatively
7. Surface a candidate change feed with audit-friendly evidence details

## Example ingestion

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "github",
    "source_url": "https://example.com/issues/123",
    "observed_at": "2026-10-10T12:00:00+00:00",
    "raw_content": {
      "title": "Structured output is failing for tool calls",
      "body": "Users report OpenAI chat-completions structured output is returning malformed payloads after the rollout.",
      "source": "github"
    },
    "author_id": "manual-test-user"
  }'
```

## Testing

Run the backend regression tests with:

```bash
source .venv/bin/activate
pytest -q
```

Or for the targeted checks used during development:

```bash
pytest tests/test_change_detection.py tests/test_ingestion.py -q
```

## Environment configuration

The main configuration lives in [app/config.py](app/config.py) and the environment template in [.env.example](.env.example). The default local setup uses SQLite for development; Postgres configuration is also prepared for production-ready deployment.

## Notes

This repository is intentionally focused on a conservative, evidence-backed workflow rather than speculative automation. The app is designed to show what is supported by real signals and to avoid falsely escalating weak signal data into stronger claims.

The design document in [Evidelta.md](Evidelta.md) remains the main product/reference document for the broader architecture and system intent.
