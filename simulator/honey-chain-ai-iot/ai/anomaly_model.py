from pathlib import Path
import pickle

FEATURE_COLUMNS = [
    "weight_rolling_mean",
    "weight_change_rate",
    "temperature_deviation",
    "humidity_deviation",
]

MODEL_VERSION = "isolation-forest-v1"

class ModelLoadError(Exception):
    """Raised when model artifact cannot be found or loaded."""
    pass

class InferenceError(Exception):
    """Raised when model inference fails due to input or evaluation error."""
    pass

class AnomalyModel:
    def __init__(self, model=None):
        self.model = model

    def load(self, path):
        target = Path(path)
        if not target.exists():
            raise ModelLoadError(f"Model artifact not found at: {target}")
        try:
            with open(target, "rb") as f:
                self.model = pickle.load(f)
        except Exception as e:
            raise ModelLoadError(f"Failed to load model from {target}: {e}") from e
        return self

    def predict(self, features):
        if self.model is None:
            raise ModelLoadError("Model is not loaded.")
        try:
            x = [[features[c] for c in FEATURE_COLUMNS]]
            label = int(self.model.predict(x)[0])  # 1 normal, -1 anomaly
            raw = float(self.model.decision_function(x)[0])

            # Convert decision function to a simple 0..1 anomaly score.
            anomaly_score = max(0.0, min(1.0, 0.5 - raw))
            return {
                "is_anomaly": label == -1,
                "anomaly_score": round(anomaly_score, 3),
                "model_version": MODEL_VERSION,
            }
        except Exception as e:
            if isinstance(e, (KeyError, TypeError, ValueError, IndexError)):
                raise InferenceError(f"Inference failed on input features: {e}") from e
            raise
