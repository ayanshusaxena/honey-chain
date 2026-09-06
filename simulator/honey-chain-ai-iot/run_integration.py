#!/usr/bin/env python3
"""Honey Chain C3 Integration Entrypoint.

Provides a clean, repeatable, operator-facing way to execute the already-proven
AI/IoT -> FastAPI integration pipeline without modifying backend contracts,
PostgreSQL schemas, or AI algorithms.

Pipeline:
    Deterministic Simulator
              |
         C3 Adapter
        /          \
AI Observation   FastAPI Telemetry
                        |
               exact telemetry_id
                        |
             Backend Risk Evaluation
                        |
             Structured Runtime Result
"""

import argparse
import json
import os
import sys
import uuid
from typing import Any, Dict, Optional

# Ensure package root is in python path
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from adapter import HoneyChainAdapter
from simulator.simulator import generate, SCENARIOS


def is_valid_uuid(val: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(str(val).strip())
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def resolve_hive_uuid(hive_id: str, explicit_uuid: Optional[str] = None) -> Optional[str]:
    """Resolve backend Hive UUID from explicit argument or environment variables."""
    if explicit_uuid and is_valid_uuid(explicit_uuid):
        return explicit_uuid.strip()

    # If hive_id itself is a valid UUID, use it directly
    if is_valid_uuid(hive_id):
        return hive_id.strip()

    # Check environment variables: HIVE_UUID, or {HIVE_ID}_UUID (e.g. HIVE_001_UUID)
    env_exact = os.getenv(f"{hive_id.upper()}_UUID", "").strip()
    if env_exact and is_valid_uuid(env_exact):
        return env_exact

    env_generic = os.getenv("HIVE_UUID", "").strip()
    if env_generic and is_valid_uuid(env_generic):
        return env_generic

    return None


def format_presentation(
    hive_id: str,
    hive_uuid: Optional[str],
    scenario: str,
    step: int,
    seed: int,
    telemetry: Dict[str, Any],
    result: Dict[str, Any],
) -> str:
    """Format structured, human-readable terminal output for C3 integration run."""
    lines = []
    lines.append("=" * 80)
    lines.append("HONEY CHAIN C3 INTEGRATION RUN")
    lines.append("=" * 80)

    # Simulator Input Section
    lines.append("Simulator Input:")
    lines.append(f"  Hive ID:            {hive_id}")
    lines.append(f"  Hive UUID:          {hive_uuid or 'NONE (Local/AI-Only)'}")
    lines.append(f"  Scenario:           {scenario}")
    lines.append(f"  Step / Seed:        {step} / {seed}")
    lines.append(f"  Timestamp:          {telemetry.get('device_timestamp')}")
    lines.append(
        f"  Telemetry Signals:  Temp={telemetry.get('temperature_c')}°C, "
        f"Humidity={telemetry.get('humidity_pct')}%, "
        f"Weight={telemetry.get('weight_kg')}kg, "
        f"Quality={telemetry.get('quality')}"
    )
    lines.append("-" * 80)

    # 1. AI Observation Section
    ai_info = result.get("ai", {})
    ai_status = ai_info.get("status", "NOT_ATTEMPTED")
    ai_obs = ai_info.get("observation") or {}

    lines.append("1. AI OBSERVATION (Companion Microservice)")
    lines.append(f"  Status:             {ai_status}")
    if ai_obs:
        features = ai_obs.get("features") or {}
        lines.append(f"  Model Version:      {ai_obs.get('model_version', 'N/A')}")
        lines.append(f"  Baseline State:     {features.get('baseline_state', 'N/A')}")
        lines.append(f"  Risk Score:         {ai_obs.get('risk_score', 'N/A')}")
        lines.append(f"  Risk Level:         {ai_obs.get('risk_level', 'N/A')}")
        lines.append(f"  Recommended Action: {ai_obs.get('recommended_action', 'N/A')}")
        reasons = ai_obs.get("risk_reasons", [])
        if reasons:
            lines.append("  Risk Reasons:")
            for r in reasons:
                lines.append(f"    - {r}")
    lines.append("-" * 80)

    # 2. Backend Telemetry Section
    telem_info = result.get("backend_telemetry", {})
    telem_status = telem_info.get("status", "NOT_ATTEMPTED")
    telem_http = telem_info.get("http_status")
    http_str = f" (HTTP {telem_http})" if telem_http is not None else ""
    telem_id = result.get("telemetry_id")

    lines.append("2. BACKEND TELEMETRY INGESTION (FastAPI)")
    lines.append(f"  Status:             {telem_status}{http_str}")
    lines.append(f"  Telemetry ID:       {telem_id or 'NONE'}")
    lines.append("-" * 80)

    # 3. Backend Operational Risk Section
    risk_info = result.get("backend_risk", {})
    risk_status = risk_info.get("status", "NOT_ATTEMPTED")
    risk_http = risk_info.get("http_status")
    r_http_str = f" (HTTP {risk_http})" if risk_http is not None else ""

    lines.append("3. BACKEND OPERATIONAL RISK EVALUATION (FastAPI Rule Engine)")
    lines.append(f"  Status:             {risk_status}{r_http_str}")
    if telem_id and risk_status == "SUCCESS":
        lines.append(f"  Evaluated Record:   {telem_id}")
    lines.append("  Semantic Rule:      Backend Operational Risk is evaluated independently")
    lines.append("                      by the sealed Rule Engine and is NOT generated by AI.")
    lines.append("-" * 80)

    # Error & Overall Section
    err = result.get("error")
    if err:
        lines.append("Error:")
        lines.append(f"  Code:               {err.get('code')}")
        lines.append(f"  Detail:             {err.get('detail')}")
        lines.append("-" * 80)

    overall = result.get("overall_status", "FAILED")
    lines.append(f"OVERALL EXECUTION STATUS: {overall}")
    lines.append("=" * 80)

    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Honey Chain C3 Integration Pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="NORMAL",
        help=f"Simulator scenario to execute: {', '.join(SCENARIOS)}",
    )
    parser.add_argument(
        "--hive-id",
        default="HIVE_001",
        help="Simulator hive identifier or UUID",
    )
    parser.add_argument(
        "--hive-uuid",
        default=None,
        help="Explicit backend hive UUID (overrides HIVE_UUID env vars)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic random seed",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=0,
        help="Simulation time step index",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Fixed ISO 8601 device timestamp (defaults to current UTC time)",
    )
    parser.add_argument(
        "--backend-url",
        default=None,
        help="FastAPI backend URL (overrides HONEY_CHAIN_BACKEND_URL)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer access token (overrides HONEY_CHAIN_TOKEN)",
    )
    parser.add_argument(
        "--ai-url",
        default=None,
        help="Flask AI service URL (overrides HONEY_CHAIN_AI_URL)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP request timeout in seconds",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI observation microservice dispatch",
    )
    parser.add_argument(
        "--no-backend",
        action="store_true",
        help="Skip backend telemetry and risk ingestion dispatch",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON result to stdout",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    call_backend = not args.no_backend
    call_ai = not args.no_ai

    hive_uuid = resolve_hive_uuid(args.hive_id, args.hive_uuid)

    if call_backend and not hive_uuid:
        sys.stderr.write(
            "ERROR: A valid hive UUID is required when dispatching to the backend.\n"
            "Provide --hive-uuid <UUID>, set HIVE_UUID or {HIVE_ID}_UUID in environment, "
            "or pass a UUID to --hive-id.\n"
        )
        sys.exit(2)

    # 1. Deterministic simulation generation
    telemetry = generate(
        hive_id=args.hive_id,
        scenario=args.scenario,
        step=args.step,
        seed=args.seed,
        timestamp=args.timestamp,
    )

    # 2. Instantiate HoneyChainAdapter with runtime configuration
    adapter = HoneyChainAdapter(
        backend_url=args.backend_url,
        bearer_token=args.token,
        ai_service_url=args.ai_url,
        timeout_seconds=args.timeout,
    )

    # 3. Dispatch through C3 integration pipeline
    target_uuid = hive_uuid or "00000000-0000-0000-0000-000000000000"
    result = adapter.dispatch(
        hive_uuid=target_uuid,
        telemetry=telemetry,
        call_ai=call_ai,
        call_backend=call_backend,
    )

    # 4. Presentation
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        output_str = format_presentation(
            hive_id=args.hive_id,
            hive_uuid=hive_uuid,
            scenario=args.scenario,
            step=args.step,
            seed=args.seed,
            telemetry=telemetry,
            result=result,
        )
        print(output_str)

    # Exit code contract
    overall = result.get("overall_status")
    if overall == "SUCCESS":
        sys.exit(0)
    elif overall == "PARTIAL":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()

