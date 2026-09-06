# Integration with Honey Chain Backend

This document details the architecture and operational contract connecting the AI/IoT module to the Honey Chain backend, as verified across Steps 4–8.

## 1. Architectural Roles & Separation of Concerns

The integration maintains a strict boundary between advisory machine learning anomaly detection and authoritative operational governance:

- **AI Observation is LOCAL and ADVISORY:**
  The AI companion microservice (`service/ai_service.py`) and underlying algorithms (`ai/anomaly_model.py`, `ai/feature_engine.py`, `ai/risk_engine.py`) generate advisory anomaly observations, risk scores, risk levels (`LOW`, `MEDIUM`, `HIGH`), recommended actions, and explainable feature evidence.
- **FastAPI Telemetry Ingestion:**
  The sealed backend telemetry endpoint (`POST /hives/{hive_id}/telemetry`) receives **raw sensor telemetry only**. Sanitized telemetry payloads match the backend schema strictly (`extra="forbid"`).
- **Authoritative Operational Risk Evaluation:**
  The backend risk endpoint (`POST /hives/{hive_id}/risk/evaluate`) evaluates operational risk independently via the sealed backend **Rule Engine**. This evaluation creates the authoritative `RiskEvent` stored in PostgreSQL.
- **No Client Injection of AI Risk:**
  Client-generated AI risk evaluations are **never** accepted, manufactured, or injected into PostgreSQL as the authoritative backend `RiskEvent`.
- **Exact Telemetry ID Chaining:**
  The adapter (`adapter.py`) and integration runner (`run_integration.py`) capture the exact UUID `telemetry_id` returned in the HTTP 201 response from the FastAPI telemetry ingestion endpoint, and supply that same `telemetry_id` to the backend risk evaluation endpoint to maintain end-to-end database relational integrity.

## 2. Integration Pipeline Flow

```text
Telemetry generated (IoT Simulator)
         ↓
AI observation service (Flask companion microservice)
         ↓
    C3 Adapter
         ├── AI observation remains advisory / local
         │
         └── FastAPI telemetry endpoint (POST /hives/{hive_id}/telemetry)
                  ↓
             returned telemetry_id (HTTP 201)
                  ↓
            FastAPI risk endpoint (POST /hives/{hive_id}/risk/evaluate)
                  ↓
            Backend Rule Engine (sealed domain logic)
                  ↓
           authoritative RiskEvent (PostgreSQL operational truth)
```

> [!IMPORTANT]
> **AI Observation ≠ Backend RiskEvent**
> AI anomaly detection and backend operational risk serve different roles:
> - **AI Observation**: Detects multi-dimensional statistical patterns and deviations (Isolation Forest + rolling feature baselines) to alert operators.
> - **Backend RiskEvent**: Evaluates the incoming telemetry using the sealed backend Rule Engine and records the resulting operational risk in PostgreSQL.
>
> Because they evaluate distinct criteria, AI risk scores/levels and backend operational risk scores/levels **may legitimately differ**. Differences between advisory AI scores and backend risk events represent distinct analytical domains, not system contradictions.

## 3. Governance Boundaries

The AI subsystem operates within explicit governance constraints:

- **Isolation Forest does NOT generate backend RiskEvents:**
  The Isolation Forest model is an anomaly-scoring component within the advisory AI observation service. Official backend `RiskEvent` records are generated exclusively by the backend Rule Engine with `source = "RULE_ENGINE"`.
- **Zero Business-State Control:**
  AI output does **NOT** trigger or control:
  - `HOLD` status
  - `RECALL` status
  - Final business/lot states
  - Packaging batch approvals
  - Blockchain cryptographic notarization or on-chain state
  - Final operational decisions

## 4. Execution Entrypoint

To run the complete verified pipeline against the running backend stack:

```powershell
# Execute complete pipeline (Simulator -> AI Observation -> Backend Telemetry -> Backend Risk)
python run_integration.py --scenario NORMAL --hive-uuid <TARGET_HIVE_UUID> --backend-url http://127.0.0.1:8000 --token <BEARER_TOKEN> --ai-url http://127.0.0.1:5050
```
