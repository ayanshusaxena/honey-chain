# Integration note

The public Honey Chain repository currently documents FastAPI endpoints for telemetry and risk evaluation.

This package intentionally does not overwrite the team's backend because the exact ORM/router source is not included in this download.

Recommended next step after copying this folder into the team's repository:
1. Keep the existing FastAPI backend.
2. Import `ai.feature_engine` and `ai.risk_engine` from this module.
3. Pass the latest valid telemetry into `evaluate(...)`.
4. Store the resulting risk score, level, reasons, and model version in the existing risk-event flow.
5. Keep the existing PostgreSQL/Alembic schema as the source of truth.
