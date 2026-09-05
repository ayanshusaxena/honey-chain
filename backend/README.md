# Honey Chain Backend

## Local setup

From the repository root, activate the backend virtual environment:

```bash
source backend/.venv/bin/activate
```

Install the application and development dependencies:

```bash
pip install -e "backend[dev]"
```

Optionally copy the example configuration for local overrides:

```bash
cp backend/.env.example backend/.env
```

## PostgreSQL configuration

Set `HONEY_CHAIN_DATABASE_URL` in `backend/.env`. Use SQLAlchemy's PostgreSQL
URL format:

```text
postgresql+psycopg://honey_chain_app:YOUR_PASSWORD@127.0.0.1:5432/honey_chain
```

For the local Homebrew PostgreSQL setup, start the service if needed:

```bash
brew services start postgresql@18
```

An administrator can create the dedicated local application role and empty
database once:

```bash
psql -d postgres -c "CREATE ROLE honey_chain_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;"
psql -d postgres -c "CREATE DATABASE honey_chain OWNER honey_chain_app;"
```

The default Homebrew local setup may use `trust` authentication. In that case,
the local URL can omit the password segment:

```text
postgresql+psycopg://honey_chain_app@127.0.0.1:5432/honey_chain
```

Use password authentication for non-local deployments; never commit real
connection credentials.

SQLAlchemy 2.x provides ORM/database access, and Alembic manages future schema
migrations. The approved Honey Chain schema is represented by SQLAlchemy models
under `app/models`; schema changes must be created and applied through Alembic.

Verify the configured connection without creating tables:

```bash
cd backend
HONEY_CHAIN_DATABASE_URL='postgresql+psycopg://honey_chain_app@127.0.0.1:5432/honey_chain' .venv/bin/python -m pytest tests/test_database.py -q
```

Run all tests with:

```bash
cd backend
.venv/bin/python -m pytest -q
```

Verify Alembic can load the configured metadata and database connection:

```bash
cd backend
HONEY_CHAIN_DATABASE_URL='postgresql+psycopg://honey_chain_app@127.0.0.1:5432/honey_chain' .venv/bin/alembic check
```

After the initial migration is applied, the command should report no new upgrade operations.

Apply the committed migration:

```bash
cd backend
HONEY_CHAIN_DATABASE_URL='postgresql+psycopg://honey_chain_app@127.0.0.1:5432/honey_chain' .venv/bin/alembic upgrade head
```

Verify the database matches the ORM metadata:

```bash
cd backend
HONEY_CHAIN_DATABASE_URL='postgresql+psycopg://honey_chain_app@127.0.0.1:5432/honey_chain' .venv/bin/alembic check
```

## Authentication

Authentication uses Argon2id password hashing and signed JWT access tokens.
Set these local-only values in `backend/.env` before using login or the seed
command:

```text
HONEY_CHAIN_JWT_SECRET=replace-with-a-high-entropy-local-secret
HONEY_CHAIN_JWT_ALGORITHM=HS256
HONEY_CHAIN_ACCESS_TOKEN_EXPIRE_MINUTES=30
HONEY_CHAIN_DEMO_PASSWORD=replace-with-a-local-demo-password
```

The access-token expiration defaults to 30 minutes and is configured by
`HONEY_CHAIN_ACCESS_TOKEN_EXPIRE_MINUTES`. Do not commit real secret values.

Create the three local demo users explicitly; FastAPI does not seed them on
startup:

```bash
cd backend
.venv/bin/python -m app.auth.seed
```

The command creates missing `ADMIN`, `BEEKEEPER`, and `PROCESSOR` demo users
only. It does not overwrite existing accounts or print their passwords. These
accounts are for local MVP/demo use only, never production.

Obtain an access token using form data. OAuth2 uses the `username` field for
the email address:

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=demo.admin@honeychain.local&password=YOUR_LOCAL_DEMO_PASSWORD'
```

Successful responses contain only `access_token` and `token_type`.

## Run the API

```bash
cd backend
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

## Health check

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","service":"Honey Chain API"}
```

## Hive Management

Hive management endpoints provide CRUD and operational status tracking for apiaries under `/hives`.

### Endpoints & Role Authorization

| Method | Endpoint | Allowed Roles | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/hives` | `ADMIN`, `BEEKEEPER` | Create hive. `BEEKEEPER` creates own hive; `ADMIN` must assign an active beekeeper via `beekeeper_id`. |
| `GET` | `/hives` | `ADMIN`, `BEEKEEPER`, `PROCESSOR` | List hives. `BEEKEEPER` sees own hives; `ADMIN` and `PROCESSOR` see all. |
| `GET` | `/hives/{hive_id}` | `ADMIN`, `BEEKEEPER`, `PROCESSOR` | View hive details. `BEEKEEPER` can only access own hives. |
| `PATCH` | `/hives/{hive_id}` | `ADMIN`, `BEEKEEPER` | Update region, operational status, or active flag. `BEEKEEPER` manages own hives. |

*Note: `PROCESSOR` has read-only visibility for operational traceability and cannot create, modify, or deactivate hives.*

### HTTP Status Codes

- `200 OK`: Successful retrieval or update.
- `201 Created`: Successful hive registration.
- `401 Unauthorized`: Missing or invalid bearer token.
- `403 Forbidden`: Authenticated user lacks permission or does not own the hive.
- `404 Not Found`: Target hive or assigned beekeeper does not exist.
- `409 Conflict`: `hive_code` already exists.
- `422 Unprocessable Entity`: Invalid request payload or blank required fields.

### Example: Create a Hive

```bash
curl -X POST http://127.0.0.1:8000/hives \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hive_code": "HIVE-KSH-001",
    "location_region": "Kashmir Valley"
  }'
```

### Example: Update / Deactivate a Hive

```bash
curl -X PATCH http://127.0.0.1:8000/hives/YOUR_HIVE_UUID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "MAINTENANCE",
    "is_active": false
  }'
```

## Telemetry Ingestion & Querying

Telemetry endpoints provide append-only ingestion and retrieval of IoT hive sensor metrics under `/telemetry` and `/hives/{hive_id}/telemetry`.

### Endpoints & Role Authorization

| Method | Endpoint | Allowed Roles | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/telemetry` | `ADMIN`, `BEEKEEPER` | Ingest telemetry specifying `hive_id` in request body. `BEEKEEPER` can only submit to own hives. |
| `POST` | `/hives/{hive_id}/telemetry` | `ADMIN`, `BEEKEEPER` | Ingest telemetry directly for the specified hive. `BEEKEEPER` can only submit to own hives. |
| `GET` | `/telemetry` | `ADMIN`, `BEEKEEPER`, `PROCESSOR` | List telemetry. `BEEKEEPER` sees own hives; `ADMIN` and `PROCESSOR` see all. Optional `?hive_id=` filter. |
| `GET` | `/hives/{hive_id}/telemetry` | `ADMIN`, `BEEKEEPER`, `PROCESSOR` | List all telemetry records for the specified hive. |
| `GET` | `/telemetry/{telemetry_id}` | `ADMIN`, `BEEKEEPER`, `PROCESSOR` | Retrieve a single telemetry record. |

*Note: Telemetry is strictly **append-only** (no update or delete endpoints). `received_at` is generated automatically by the backend in UTC. `PROCESSOR` is read-only.*

### HTTP Status Codes

- `200 OK`: Successful retrieval.
- `201 Created`: Successful telemetry ingestion.
- `401 Unauthorized`: Missing or invalid bearer token.
- `403 Forbidden`: Authenticated user lacks permission or does not own the target hive.
- `404 Not Found`: Target hive or telemetry record does not exist.
- `422 Unprocessable Entity`: Malformed request, negative weight, out-of-range humidity (0–100), or invalid quality enum.

### Example: Submit Telemetry

```bash
curl -X POST http://127.0.0.1:8000/hives/YOUR_HIVE_UUID/telemetry \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_timestamp": "2026-09-04T12:00:00Z",
    "weight_kg": 28.5,
    "temperature_c": 35.2,
    "humidity_pct": 52.0,
    "quality": "VALID"
  }'
```

### Example: Query Hive Telemetry

```bash
curl http://127.0.0.1:8000/hives/YOUR_HIVE_UUID/telemetry \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```
