# DATAFORGE PIPELINE

DATAFORGE PIPELINE is a production-style Python data ingestion system that monitors a folder for CSV and XLSX files, validates row-level data, stores results in PostgreSQL (including JSONB row payloads), and exposes pipeline monitoring APIs through FastAPI.

## Architecture

Pipeline flow:

Incoming Files -> File Detection -> Parse CSV/XLSX -> Validation -> Store Raw Rows -> Track Pipeline Run -> Store Errors -> Move File

Core modules:

- `app/ingestion`: file watcher, parser, file orchestration
- `app/validation`: row validation rules
- `app/transform`: row normalization/sanitization
- `app/load`: database write layer
- `app/database`: SQLAlchemy engine and models
- `app/api`: monitoring and reprocess endpoints
- `app/logging`: Loguru logger configuration

Storage lifecycle:

- `storage/incoming`: new files
- `storage/processing`: in-progress files
- `storage/processed`: completed files
- `storage/failed`: failed files

## Database Schema

Tables managed by Alembic migrations:

- `source_files`
  - `id` (UUID, PK)
  - `file_name`, `file_type`, `file_size_bytes`, `source_path`, `checksum`
  - `status`, `uploaded_at`, `processed_at`
- `pipeline_runs`
  - `id` (UUID, PK)
  - `file_id` (UUID, FK -> source_files.id)
  - `start_time`, `end_time`, `rows_total`, `rows_valid`, `rows_failed`, `status`, `error_message`
- `raw_records`
  - `id` (BIGSERIAL, PK)
  - `file_id` (UUID, FK)
  - `row_number`, `row_data` (JSONB), `ingested_at`
- `validation_errors`
  - `id` (BIGSERIAL, PK)
  - `file_id` (UUID, FK)
  - `row_number`, `error_type`, `error_message`, `failed_data` (JSONB), `created_at`

## Validation Rules

Current baseline rules:

- Row must not be empty
- Row must contain at least one column
- Null values are allowed, but logged as warnings

Valid rows are inserted into `raw_records`.
Invalid rows are inserted into `validation_errors`.

## Environment Variables

Use `.env` (copy from `.env.example`):

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/dataforge_db
PIPELINE_SCAN_INTERVAL=5
```

## Local Setup

1. Create virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

2. Create `.env` from example and update values.

3. Run migrations:

```bash
alembic upgrade head
```

4. Start ingestion watcher:

```bash
python scripts/start_pipeline.py
```

5. Start API server:

```bash
uvicorn app.api.main:app --reload
```

## API Endpoints

- `GET /health`
- `GET /pipeline/runs`
- `GET /files`
- `GET /errors`
- `POST /pipeline/reprocess`

Reprocess payload:

```json
{ "file_name": "sample_customers.csv" }
```

If `file_name` is omitted, all files in `storage/failed` are reprocessed.

## Logging

Structured logs are written to:

- `logs/pipeline.log`

Log coverage includes:

- File detection
- Rows processed (total, valid, failed)
- Errors
- Execution time

## Docker Usage

From the `docker` folder:

```bash
docker compose up --build
```

Services:

- `postgres` (PostgreSQL 16)
- `pipeline` (watcher process)
- `api` (FastAPI)

## Sample Data

Sample files are preloaded in `storage/incoming`:

- `sample_customers.csv`
- `sample_inventory.xlsx`

## Reprocessing Failed Files

Run script to reprocess all failed files:

```bash
python scripts/reprocess_failed.py
```
