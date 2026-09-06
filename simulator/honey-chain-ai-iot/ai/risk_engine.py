from .anomaly_model import AnomalyModel, ModelLoadError, InferenceError
from .feature_engine import add_and_generate_features

BASELINE_VERSION = "rules-baseline-v2"
MODEL_PATH = "models/isolation_forest.pkl"

def validate_telemetry(t):
    required = ["hive_id", "temperature_c", "humidity_pct", "weight_kg"]
    for field in required:
        if field not in t or t[field] is None:
            return False, f"Missing telemetry field: {field}"

    try:
        temp = float(t["temperature_c"])
        humidity = float(t["humidity_pct"])
        weight = float(t["weight_kg"])
    except (TypeError, ValueError):
        return False, "Telemetry contains a non-numeric sensor value"

    if not -10 <= temp <= 60:
        return False, "Temperature reading is invalid"
    if not 0 <= humidity <= 100:
        return False, "Humidity reading is invalid"
    if weight < 0:
        return False, "Weight reading is invalid"
    if t.get("quality", "VALID") == "INVALID":
        return False, "Telemetry quality is INVALID"

    return True, "Telemetry data is valid"

def rule_score(t, features):
    score = 0.0
    reasons = []

    temp = float(t["temperature_c"])
    humidity = float(t["humidity_pct"])
    weight = float(t["weight_kg"])

    if abs(features["temperature_deviation"]) > 3:
        score += 0.25
        reasons.append("Temperature is significantly different from the recent baseline")

    if abs(features["humidity_deviation"]) > 15:
        score += 0.20
        reasons.append("Humidity is significantly different from the recent baseline")

    if features["weight_change_rate"] < -0.8:
        score += 0.25
        reasons.append("Hive weight is decreasing rapidly")

    if weight < 20:
        score += 0.15
        reasons.append("Hive weight is below the configured baseline range")

    if temp > 38 or temp < 30:
        score += 0.10
        reasons.append("Temperature is outside the configured comfort range")

    if humidity > 75 or humidity < 40:
        score += 0.10
        reasons.append("Humidity is outside the configured comfort range")

    return min(score, 1.0), reasons

def evaluate(telemetry, model=None, require_model=False):
    ok, message = validate_telemetry(telemetry)
    if not ok:
        return {
            "risk_score": None,
            "risk_level": "UNKNOWN",
            "risk_reasons": [message],
            "recommended_action": "Check sensor data before making a risk assessment",
            "baseline_version": BASELINE_VERSION,
            "model_version": None,
            "features": {},
        }

    features = add_and_generate_features(telemetry)
    rules, reasons = rule_score(telemetry, features)

    ml_score = 0.0
    model_version = None
    if model is not None:
        ml = model.predict(features)
        ml_score = ml["anomaly_score"]
        model_version = ml["model_version"]
        if ml["is_anomaly"]:
            reasons.append("Isolation Forest flagged the telemetry pattern as unusual")
    elif require_model:
        raise ModelLoadError("Model is required for AI risk evaluation but was not provided or loaded.")

    # Combined risk: rules remain explainable; ML adds anomaly evidence.
    combined = min(1.0, 0.7 * rules + 0.3 * ml_score)

    # Prevent cold-start/warm-up anomalies with active rule violations from being suppressed to false-safe LOW
    if features.get("baseline_state") == "WARMING_UP" and len(reasons) > 0 and combined < 0.30:
        combined = max(combined, 0.35)

    if combined < 0.30:
        level = "LOW"
    elif combined < 0.70:
        level = "MEDIUM"
    else:
        level = "HIGH"

    if not reasons:
        reasons = ["Hive telemetry is close to its recent baseline"]

    action = "Continue monitoring"
    if level == "MEDIUM":
        action = "Monitor closely and inspect recent telemetry"
    elif level == "HIGH":
        action = "Inspect hive and sensor readings"

    return {
        "risk_score": round(combined, 3),
        "risk_level": level,
        "risk_reasons": reasons,
        "recommended_action": action,
        "baseline_version": BASELINE_VERSION,
        "model_version": model_version,
        "features": features,
    }

class AIRiskEvaluator:
    """Explicit AI + Rules evaluation boundary."""

    def __init__(self, model_path=None, auto_load=True):
        self.model = AnomalyModel()
        self.model_path = model_path or MODEL_PATH
        if auto_load:
            self.load()

    def load(self, path=None):
        target = path or self.model_path
        self.model.load(target)
        return self

    def evaluate(self, telemetry):
        return evaluate(telemetry, model=self.model, require_model=True)

