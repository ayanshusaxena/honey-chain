"""C3 Minimal Backend Adapter.

Connects the IoT simulator to the sealed Honey Chain FastAPI backend and the
companion AI microservice without modifying backend contracts, database,
or business state.
"""

from typing import Any, Dict, Optional
import os
import requests

ALLOWED_TELEMETRY_FIELDS = {
    "device_timestamp",
    "weight_kg",
    "temperature_c",
    "humidity_pct",
    "quality",
}


class HoneyChainAdapter:
    """Orchestrates telemetry submission to the sealed backend and AI observation service."""

    def __init__(
        self,
        backend_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        ai_service_url: Optional[str] = None,
        timeout_seconds: float = 5.0,
    ):
        self.backend_url = (
            backend_url or os.getenv("HONEY_CHAIN_BACKEND_URL", "")
        ).rstrip("/")
        self.bearer_token = (
            bearer_token or os.getenv("HONEY_CHAIN_TOKEN", "")
        ).strip()
        self.ai_service_url = (
            ai_service_url or os.getenv("HONEY_CHAIN_AI_URL", "http://127.0.0.1:5050")
        ).rstrip("/")
        self.timeout = timeout_seconds

    def sanitize_telemetry(self, raw_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Strip internal simulation/AI keys to strictly match HiveTelemetryCreate (extra='forbid')."""
        sanitized = {}
        for k in ALLOWED_TELEMETRY_FIELDS:
            if k in raw_telemetry:
                sanitized[k] = raw_telemetry[k]
        if "quality" not in sanitized:
            sanitized["quality"] = "VALID"
        return sanitized

    def dispatch(
        self,
        hive_uuid: str,
        telemetry: Dict[str, Any],
        call_ai: bool = True,
        call_backend: bool = True,
    ) -> Dict[str, Any]:
        """Execute dispatch to AI service and sealed backend.

        Returns a structured dictionary strictly adhering to C3 Step 4 semantics.
        """
        result: Dict[str, Any] = {
            "hive_id": hive_uuid,
            "telemetry_id": None,
            "ai": {
                "status": "NOT_ATTEMPTED",
                "observation": None,
            },
            "backend_telemetry": {
                "status": "NOT_ATTEMPTED",
                "http_status": None,
            },
            "backend_risk": {
                "status": "NOT_ATTEMPTED",
                "http_status": None,
            },
            "error": None,
            "overall_status": "FAILED",
        }

        # 1. AI Observation Dispatch
        if call_ai:
            ai_status, ai_obs, ai_err = self._dispatch_ai(telemetry)
            result["ai"]["status"] = ai_status
            result["ai"]["observation"] = ai_obs
            if ai_err and not result["error"]:
                result["error"] = ai_err

        # If backend dispatch not requested, compute overall and return
        if not call_backend:
            if result["ai"]["status"] == "SUCCESS":
                result["overall_status"] = "SUCCESS"
            else:
                result["overall_status"] = "FAILED"
            return result

        # Pre-check backend configuration
        if not self.backend_url:
            result["backend_telemetry"]["status"] = "FAILED"
            result["error"] = {
                "code": "BACKEND_UNAVAILABLE",
                "detail": "HONEY_CHAIN_BACKEND_URL is not configured",
            }
            result["overall_status"] = (
                "PARTIAL" if result["ai"]["status"] == "SUCCESS" else "FAILED"
            )
            return result

        if not self.bearer_token:
            result["backend_telemetry"]["status"] = "FAILED"
            result["error"] = {
                "code": "AUTH_TOKEN_MISSING",
                "detail": "HONEY_CHAIN_TOKEN is not configured",
            }
            result["overall_status"] = (
                "PARTIAL" if result["ai"]["status"] == "SUCCESS" else "FAILED"
            )
            return result

        # 2. Telemetry Ingestion Dispatch
        sanitized_payload = self.sanitize_telemetry(telemetry)
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        telemetry_url = f"{self.backend_url}/hives/{hive_uuid}/telemetry"

        try:
            r_telem = requests.post(
                telemetry_url,
                json=sanitized_payload,
                headers=headers,
                timeout=self.timeout,
            )
            result["backend_telemetry"]["http_status"] = r_telem.status_code

            if r_telem.status_code == 201:
                telem_json = r_telem.json()
                telem_id = telem_json.get("id")
                result["telemetry_id"] = telem_id
                result["backend_telemetry"]["status"] = "SUCCESS"
            else:
                result["backend_telemetry"]["status"] = "FAILED"
                err_detail = "Backend rejected telemetry"
                try:
                    err_json = r_telem.json()
                    err_detail = err_json.get("detail", str(err_json))
                except Exception:
                    err_detail = r_telem.text or err_detail
                result["error"] = {
                    "code": f"HTTP_{r_telem.status_code}",
                    "detail": err_detail,
                }
                result["backend_risk"]["status"] = "NOT_ATTEMPTED"
                result["overall_status"] = (
                    "PARTIAL" if result["ai"]["status"] == "SUCCESS" else "FAILED"
                )
                return result

        except requests.ConnectionError as e:
            result["backend_telemetry"]["status"] = "FAILED"
            result["error"] = {
                "code": "BACKEND_UNAVAILABLE",
                "detail": f"Connection refused or network unreachable: {e}",
            }
            result["overall_status"] = (
                "PARTIAL" if result["ai"]["status"] == "SUCCESS" else "FAILED"
            )
            return result
        except requests.Timeout as e:
            result["backend_telemetry"]["status"] = "FAILED"
            result["error"] = {
                "code": "TIMEOUT",
                "detail": f"Request to backend timed out: {e}",
            }
            result["overall_status"] = (
                "PARTIAL" if result["ai"]["status"] == "SUCCESS" else "FAILED"
            )
            return result
        except requests.RequestException as e:
            result["backend_telemetry"]["status"] = "FAILED"
            result["error"] = {
                "code": "REQUEST_FAILED",
                "detail": str(e),
            }
            result["overall_status"] = (
                "PARTIAL" if result["ai"]["status"] == "SUCCESS" else "FAILED"
            )
            return result

        # 3. Risk Evaluation Dispatch (ONLY after successful telemetry creation with exact telemetry_id)
        risk_url = f"{self.backend_url}/hives/{hive_uuid}/risk/evaluate"
        risk_payload = {"telemetry_id": result["telemetry_id"]}

        try:
            r_risk = requests.post(
                risk_url,
                json=risk_payload,
                headers=headers,
                timeout=self.timeout,
            )
            result["backend_risk"]["http_status"] = r_risk.status_code

            if r_risk.status_code == 201:
                result["backend_risk"]["status"] = "SUCCESS"
            else:
                result["backend_risk"]["status"] = "FAILED"
                err_detail = "Backend risk evaluation failed"
                try:
                    err_json = r_risk.json()
                    err_detail = err_json.get("detail", str(err_json))
                except Exception:
                    err_detail = r_risk.text or err_detail
                result["error"] = {
                    "code": f"RISK_HTTP_{r_risk.status_code}",
                    "detail": err_detail,
                }

        except requests.ConnectionError as e:
            result["backend_risk"]["status"] = "FAILED"
            result["error"] = {
                "code": "BACKEND_UNAVAILABLE",
                "detail": f"Risk call connection failed: {e}",
            }
        except requests.Timeout as e:
            result["backend_risk"]["status"] = "FAILED"
            result["error"] = {
                "code": "TIMEOUT",
                "detail": f"Risk call timed out: {e}",
            }
        except requests.RequestException as e:
            result["backend_risk"]["status"] = "FAILED"
            result["error"] = {
                "code": "RISK_REQUEST_FAILED",
                "detail": str(e),
            }

        # 4. Compute Overall Status according to C3 exact semantics
        ai_ok = result["ai"]["status"] == "SUCCESS"
        telem_ok = result["backend_telemetry"]["status"] == "SUCCESS"
        risk_ok = result["backend_risk"]["status"] == "SUCCESS"

        if ai_ok and telem_ok and risk_ok:
            result["overall_status"] = "SUCCESS"
        elif telem_ok or ai_ok:
            result["overall_status"] = "PARTIAL"
        else:
            result["overall_status"] = "FAILED"

        return result

    def _dispatch_ai(self, telemetry: Dict[str, Any]):
        """Send telemetry to AI microservice. Never fabricates results."""
        if not self.ai_service_url:
            return (
                "UNAVAILABLE",
                None,
                {
                    "code": "AI_UNAVAILABLE",
                    "detail": "AI service URL not configured",
                },
            )

        url = f"{self.ai_service_url}/evaluate"
        try:
            r = requests.post(url, json=telemetry, timeout=self.timeout)
            if r.status_code == 200:
                try:
                    data = r.json()
                    if (
                        not isinstance(data, dict)
                        or "risk_score" not in data
                        or "risk_level" not in data
                    ):
                        return (
                            "FAILED",
                            None,
                            {
                                "code": "AI_RESPONSE_INVALID",
                                "detail": "AI service response missing expected keys",
                            },
                        )
                    return "SUCCESS", data, None
                except Exception as e:
                    return (
                        "FAILED",
                        None,
                        {
                            "code": "AI_RESPONSE_INVALID",
                            "detail": f"Failed to parse AI response JSON: {e}",
                        },
                    )
            elif r.status_code == 503:
                return (
                    "UNAVAILABLE",
                    None,
                    {
                        "code": "AI_UNAVAILABLE",
                        "detail": "AI model not ready or service unavailable (HTTP 503)",
                    },
                )
            else:
                return (
                    "FAILED",
                    None,
                    {
                        "code": f"AI_HTTP_{r.status_code}",
                        "detail": f"AI service returned HTTP {r.status_code}",
                    },
                )
        except (requests.ConnectionError, requests.Timeout) as e:
            return (
                "UNAVAILABLE",
                None,
                {
                    "code": "AI_UNAVAILABLE",
                    "detail": f"AI service unreachable: {e}",
                },
            )
        except requests.RequestException as e:
            return (
                "FAILED",
                None,
                {
                    "code": "AI_REQUEST_FAILED",
                    "detail": str(e),
                },
            )
