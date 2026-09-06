# Honey Chain — AI + IoT MVP Module

This folder contains the AI + simulated-IoT part designed to fit the Honey Chain backend.

## What is included

- Simulated telemetry for 3 hives
- Normal + abnormal scenario
- Telemetry validation
- Feature generation:
  - weight rolling mean
  - weight change rate
  - temperature deviation from recent baseline
  - humidity deviation from recent baseline
- Isolation Forest anomaly detection
- Explainable rule + ML combined risk
- LOW / MEDIUM / HIGH risk
- Reasons and recommended action
- Model/baseline version
- Optional POST to the team's existing Honey Chain API

## Important scope

This is an anomaly / health-risk flagging prototype.
It does NOT diagnose bee disease and does NOT claim disease detection.

The included CSV is SYNTHETIC DEMO TRAINING DATA so the package can run immediately.
For the SIH report, replace/retrain it using the public honey-bee telemetry dataset described below.

## Public dataset recommended for retraining

Weight, Temperature and Humidity Sensor Data of Honey Bee Colonies in Germany, 2019–2022:
https://zenodo.org/records/10407693

It contains sensor data from 78 colonies and includes temperature, humidity and hive weight.
The full publication/raw archives are large, so do not blindly download the multi-GB raw archive on a laptop.

## Setup (Windows / VS Code)

Open PowerShell in this folder:

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

If the model file is missing:

    python train_model.py

Then test the AI service:

    python service\ai_service.py

Open:

    http://127.0.0.1:5050/health

Run simulator in another terminal:

    python simulator\simulator.py

## Connect to the team's existing backend

The repository's current backend uses:

    POST /telemetry
    POST /hives/{hive_id}/telemetry
    POST /hives/{hive_id}/risk/evaluate

The simulator is configured for the hive-specific telemetry endpoint.
Set these environment variables before running it:

    $env:HONEY_CHAIN_BACKEND_URL="http://127.0.0.1:8000"
    $env:HONEY_CHAIN_TOKEN="YOUR_ACCESS_TOKEN"
    $env:HIVE_001_UUID="YOUR_HIVE_UUID"
    $env:HIVE_002_UUID="YOUR_HIVE_UUID"
    $env:HIVE_003_UUID="YOUR_HIVE_UUID"

Then:

    python simulator\simulator.py

The current Honey Chain backend requires authenticated roles for telemetry/risk endpoints.
The AI module therefore keeps its local evaluation independent and makes backend posting optional.

## Recommended integration architecture

IoT Simulator
    -> telemetry
    -> validation
    -> feature generation
    -> Isolation Forest + rules
    -> risk score / reasons
    -> Honey Chain API
    -> PostgreSQL
    -> dashboard

## C3 Integration Runner (Step 6 / 7)

`run_integration.py` provides a clean, repeatable, operator-facing entrypoint for executing the complete simulation, AI observation, and FastAPI backend ingestion pipeline against the running Honey Chain stack.

> [!NOTE]
> **Data Nature**: All sensor telemetry produced by this simulator is **SYNTHETIC DEMO DATA** for prototype demonstration. It does NOT represent biological or veterinary diagnostic standards.

### 1. Installation
In an isolated environment (e.g. a dedicated virtualenv):
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
*(Note: Do not install ML dependencies into the core backend venv).*

### 2. Service Startup
Start the components in separate terminals:
- **PostgreSQL**: Ensure the Honey Chain database is running locally on port `5432`.
- **FastAPI Backend**:
  ```powershell
  cd backend
  .venv\Scripts\uvicorn app.main:app --port 8000
  ```
- **AI Companion Microservice**:
  ```powershell
  cd simulator\honey-chain-ai-iot
  python service\ai_service.py
  ```

### 3. Runtime Configuration
Set the following environment variables (or supply them directly as CLI flags):
```powershell
$env:HONEY_CHAIN_BACKEND_URL="http://127.0.0.1:8000"
$env:HONEY_CHAIN_AI_URL="http://127.0.0.1:5050"
$env:HONEY_CHAIN_TOKEN="<BEARER_JWT_TOKEN>"
$env:HIVE_UUID="<TARGET_BACKEND_HIVE_UUID>"
```
*Hive UUID Mapping*: You can also map specific hives via `$env:HIVE_001_UUID`, `$env:HIVE_002_UUID`, or pass `--hive-uuid <UUID>` directly on the command line.

### 4. Demo Commands

**Normal Scenario (Nominal Baseline):**
```powershell
python run_integration.py --scenario NORMAL --hive-uuid <TARGET_BACKEND_HIVE_UUID>
```

**Combined Anomaly Scenario:**
```powershell
python run_integration.py --scenario COMBINED --hive-id HIVE_003 --step 1 --hive-uuid <TARGET_BACKEND_HIVE_UUID>
```

**Fully Reproducible Deterministic Execution:**
To guarantee byte-for-byte reproducibility across independent runs, specify the seed, step, and an explicit timestamp:
```powershell
python run_integration.py `
  --scenario COMBINED `
  --hive-id HIVE_003 `
  --hive-uuid <TARGET_BACKEND_HIVE_UUID> `
  --seed 42 `
  --step 1 `
  --timestamp "2026-09-06T12:00:00+00:00"
```

### 5. Semantic Separation: AI Observation vs. Backend Operational Risk
- **AI Observation (Advisory)**: Generated by the companion microservice (`isolation-forest-v1` + feature engine). Returns advisory anomaly metrics (`risk_score`, `risk_level`, `reasons`).
- **Backend Operational Risk (Authoritative)**: Evaluated independently by the sealed FastAPI backend Rule Engine and committed to PostgreSQL table `risk_events`.
- **Business State Governance**: **AI DOES NOT CONTROL BUSINESS STATE.** Anomaly scores generated by AI never trigger lot quarantine (`HOLD`), product `RECALL`, or blockchain notarization. The adapter is strictly an orchestrator.

### 6. Failure Behavior (Operator Reference)
- **AI Service Unavailable**: Ingestion and backend risk evaluation proceed normally. Telemetry is saved, operational risk is recorded, and the overall result reports `PARTIAL`.
- **Backend Unavailable**: AI observation completes successfully; telemetry submission fails with `BACKEND_UNAVAILABLE`; risk evaluation is not attempted (`overall_status = PARTIAL`).
- **Auth / Schema Errors (HTTP 401, 403, 422)**: Telemetry is rejected, and the adapter aborts before calling risk evaluation (`backend_risk = NOT_ATTEMPTED`).

## Demo

1. Start the AI service.
2. Start the simulator.
3. Keep ANOMALY_MODE=True.
4. HIVE_003 should show abnormal temperature/humidity/weight and a higher risk.
5. Change ANOMALY_MODE=False and run again for a normal scenario.

## SIH wording

Say:
"AI-based anomaly and hive health-risk flagging using sensor telemetry."

Do not say:
"AI detects bee disease."
