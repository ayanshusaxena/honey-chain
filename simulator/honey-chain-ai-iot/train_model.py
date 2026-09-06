from pathlib import Path
import csv, pickle
from sklearn.ensemble import IsolationForest

from ai.feature_engine import WINDOW, _history, add_and_generate_features
from ai.anomaly_model import FEATURE_COLUMNS, MODEL_VERSION

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "demo_normal_telemetry.csv"
OUT = ROOT / "models" / "isolation_forest.pkl"

def main():
    # Reset feature history before creating training features.
    _history.clear()
    features = []

    with open(DATA, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = {
                "hive_id": row["hive_id"],
                "temperature_c": float(row["temperature_c"]),
                "humidity_pct": float(row["humidity_pct"]),
                "weight_kg": float(row["weight_kg"]),
            }
            feat = add_and_generate_features(t)
            # Skip first few records of each hive while rolling baselines warm up.
            if len(_history[t["hive_id"]]) >= 3:
                features.append([feat[c] for c in FEATURE_COLUMNS])

    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,
        random_state=42
    )
    model.fit(features)

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "wb") as f:
        pickle.dump(model, f)

    print(f"Saved model: {OUT}")
    print(f"Model version: {MODEL_VERSION}")
    print(f"Training rows: {len(features)}")

if __name__ == "__main__":
    main()
