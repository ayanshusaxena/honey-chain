from pathlib import Path
import os
import sys
from flask import Flask, request, jsonify

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.anomaly_model import AnomalyModel, ModelLoadError, InferenceError, MODEL_VERSION
from ai.risk_engine import evaluate, validate_telemetry

app = Flask(__name__)

MODEL_PATH = Path(os.getenv("HONEY_CHAIN_MODEL_PATH", str(ROOT / "models" / "isolation_forest.pkl")))

model = AnomalyModel()
model_loaded = False
model_error = None

def init_model(path=MODEL_PATH):
    """Load the anomaly model artifact or record explicit failure state."""
    global model, model_loaded, model_error
    try:
        model = AnomalyModel()
        model.load(path)
        model_loaded = True
        model_error = None
    except Exception as e:
        model_loaded = False
        model_error = str(e)

init_model()

@app.get("/health")
def health():
    """Liveness check: process is alive."""
    return jsonify({
        "status": "ok",
        "service": "Honey Chain AI service",
        "live": True
    }), 200

@app.get("/readiness")
def readiness():
    """Readiness check: model is loaded and available for AI inference."""
    if model_loaded and model.model is not None:
        return jsonify({
            "status": "ready",
            "service": "Honey Chain AI service",
            "model_version": MODEL_VERSION,
            "ready": True
        }), 200
    else:
        return jsonify({
            "status": "not_ready",
            "service": "Honey Chain AI service",
            "ready": False,
            "error": "ModelUnavailable",
            "detail": model_error or "AI model is not loaded."
        }), 503

@app.post("/evaluate")
def evaluate_api():
    """Evaluate telemetry with explicit validation, model availability, and inference error handling."""
    # 1. Readiness check: No silent fallback to rules-only
    if not model_loaded or model.model is None:
        return jsonify({
            "error": "ModelUnavailable",
            "detail": model_error or "AI model is not loaded.",
            "service": "Honey Chain AI service"
        }), 503

    # 2. Content-Type and JSON body parsing
    if not request.is_json:
        return jsonify({
            "error": "ValidationError",
            "detail": "Request Content-Type must be application/json",
            "service": "Honey Chain AI service"
        }), 400

    telemetry = request.get_json(silent=True)
    if telemetry is None or not isinstance(telemetry, dict):
        return jsonify({
            "error": "ValidationError",
            "detail": "Request body must be a valid JSON object",
            "service": "Honey Chain AI service"
        }), 400

    # 3. Request payload validation
    ok, message = validate_telemetry(telemetry)
    if not ok:
        return jsonify({
            "error": "ValidationError",
            "detail": message,
            "service": "Honey Chain AI service"
        }), 400

    # 4. Inference & evaluation with explicit error handling
    try:
        result = evaluate(telemetry, model=model, require_model=True)
        return jsonify(result), 200
    except (InferenceError, Exception) as e:
        return jsonify({
            "error": type(e).__name__,
            "detail": str(e),
            "service": "Honey Chain AI service"
        }), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5050"))
    app.run(host=host, port=port)
