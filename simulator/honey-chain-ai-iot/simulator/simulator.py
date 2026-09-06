import os
import sys
import time
import random
from datetime import datetime, timezone
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from ai.anomaly_model import AnomalyModel
from ai.risk_engine import evaluate

HIVES = ["HIVE_001", "HIVE_002", "HIVE_003"]
ANOMALY_HIVE = "HIVE_003"
ANOMALY_MODE = True
INTERVAL_SECONDS = 3

SCENARIOS = ["NORMAL", "TEMP_ANOMALY", "HUMIDITY_ANOMALY", "WEIGHT_DROP", "COMBINED"]
DEFAULT_SCENARIO = "COMBINED" if ANOMALY_MODE else "NORMAL"
DEFAULT_SEED = 42

# Optional connection to the team's existing Honey Chain backend.
BACKEND_URL = os.getenv("HONEY_CHAIN_BACKEND_URL", "").strip()
BEARER_TOKEN = os.getenv("HONEY_CHAIN_TOKEN", "").strip()
HIVE_UUIDS = {
    h: os.getenv(f"{h}_UUID", "").strip()
    for h in HIVES
}

MODEL_PATH = os.path.join(ROOT, "models", "isolation_forest.pkl")
model = AnomalyModel()
if os.path.exists(MODEL_PATH):
    try:
        model.load(MODEL_PATH)
    except Exception:
        pass

def generate(hive_id, scenario=None, step=0, seed=DEFAULT_SEED, timestamp=None):
    """Generate deterministic simulated telemetry for a given hive, scenario, and step."""
    if scenario is None:
        scenario = os.getenv("SIMULATOR_SCENARIO", DEFAULT_SCENARIO)
    scenario = scenario.upper()

    # Deterministic seeded generator per (seed, scenario, hive_id, step)
    rng = random.Random(f"{seed}_{scenario}_{hive_id}_{step}")

    if scenario == "NORMAL":
        # Stable nominal telemetry without uncontrolled random fluctuations
        temp = 34.0 + rng.uniform(-0.4, 0.4)
        humidity = 60.0 + rng.uniform(-2.0, 2.0)
        weight = 42.0 + rng.uniform(-0.1, 0.1)

    elif scenario == "TEMP_ANOMALY":
        if hive_id == ANOMALY_HIVE:
            temp = 40.5 + rng.uniform(0.0, 1.5)
            humidity = 60.0 + rng.uniform(-2.0, 2.0)
            weight = 42.0 + rng.uniform(-0.1, 0.1)
        else:
            temp = 34.0 + rng.uniform(-0.4, 0.4)
            humidity = 60.0 + rng.uniform(-2.0, 2.0)
            weight = 42.0 + rng.uniform(-0.1, 0.1)

    elif scenario == "HUMIDITY_ANOMALY":
        if hive_id == ANOMALY_HIVE:
            temp = 34.0 + rng.uniform(-0.4, 0.4)
            humidity = 84.0 + rng.uniform(0.0, 5.0)
            weight = 42.0 + rng.uniform(-0.1, 0.1)
        else:
            temp = 34.0 + rng.uniform(-0.4, 0.4)
            humidity = 60.0 + rng.uniform(-2.0, 2.0)
            weight = 42.0 + rng.uniform(-0.1, 0.1)

    elif scenario == "WEIGHT_DROP":
        if hive_id == ANOMALY_HIVE:
            temp = 34.0 + rng.uniform(-0.4, 0.4)
            humidity = 60.0 + rng.uniform(-2.0, 2.0)
            if step == 0:
                weight = 42.0 + rng.uniform(-0.1, 0.1)
            else:
                weight = 35.0 + rng.uniform(-0.5, 0.5)
        else:
            temp = 34.0 + rng.uniform(-0.4, 0.4)
            humidity = 60.0 + rng.uniform(-2.0, 2.0)
            weight = 42.0 + rng.uniform(-0.1, 0.1)

    elif scenario == "COMBINED":
        if hive_id == ANOMALY_HIVE:
            temp = 39.0 + rng.uniform(0.0, 3.0)
            humidity = 80.0 + rng.uniform(0.0, 10.0)
            weight = 34.0 + rng.uniform(0.0, 3.0)
        else:
            temp = 34.0 + rng.uniform(-0.4, 0.4)
            humidity = 60.0 + rng.uniform(-2.0, 2.0)
            weight = 42.0 + rng.uniform(-0.1, 0.1)

    else:
        raise ValueError(f"Unknown scenario: '{scenario}'. Valid scenarios: {SCENARIOS}")

    ts = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()

    return {
        "hive_id": hive_id,
        "device_timestamp": ts,
        "temperature_c": round(temp, 2),
        "humidity_pct": round(humidity, 2),
        "weight_kg": round(weight, 2),
        "quality": "VALID",
        "simulated": True
    }

def send_to_backend(telemetry, result):
    if not BACKEND_URL or not BEARER_TOKEN:
        return "local-only"

    hive_id = telemetry["hive_id"]
    uuid = HIVE_UUIDS.get(hive_id)
    if not uuid:
        return "backend skipped: set HIVE_XXX_UUID"

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "device_timestamp": telemetry["device_timestamp"],
        "weight_kg": telemetry["weight_kg"],
        "temperature_c": telemetry["temperature_c"],
        "humidity_pct": telemetry["humidity_pct"],
        "quality": telemetry["quality"],
    }

    try:
        r = requests.post(
            f"{BACKEND_URL.rstrip('/')}/hives/{uuid}/telemetry",
            json=payload,
            headers=headers,
            timeout=5
        )
        return f"backend telemetry: HTTP {r.status_code}"
    except requests.RequestException as e:
        return f"backend error: {e}"

def run_simulation(scenario=None, cycles=None, interval=INTERVAL_SECONDS, seed=DEFAULT_SEED):
    """Execute the simulation loop for a set number of cycles or indefinitely."""
    if scenario is None:
        scenario = os.getenv("SIMULATOR_SCENARIO", DEFAULT_SCENARIO)
    scenario = scenario.upper()
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: '{scenario}'. Valid scenarios: {SCENARIOS}")

    print("=" * 60)
    print("HONEY CHAIN - AI + IoT SIMULATOR")
    print("SIMULATED / DEMO DATA")
    print(f"Scenario: {scenario} (Target: {ANOMALY_HIVE})")
    print(f"Seed: {seed}")
    if cycles is not None:
        print(f"Cycles: {cycles}")
    print("=" * 60)

    step = 0
    while True:
        for hive in HIVES:
            t = generate(hive, scenario=scenario, step=step, seed=seed)
            result = evaluate(t, model=model if model.model else None)

            print(f"\n{hive} | T={t['temperature_c']}°C | H={t['humidity_pct']}% | W={t['weight_kg']}kg")
            print(f"Risk: {result['risk_level']} ({result['risk_score']})")
            print("Reasons:", "; ".join(result["risk_reasons"]))
            print("Action:", result["recommended_action"])
            print("Features:", result["features"])
            print(send_to_backend(t, result))

        step += 1
        if cycles is not None and step >= cycles:
            break
        time.sleep(interval)

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Honey Chain AI + IoT Simulator")
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default=os.getenv("SIMULATOR_SCENARIO", DEFAULT_SCENARIO),
        help="Simulation scenario (default: %(default)s)"
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Number of simulation cycles to run (default: infinite)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=INTERVAL_SECONDS,
        help="Interval between cycles in seconds (default: %(default)s)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=int(os.getenv("SIMULATOR_SEED", str(DEFAULT_SEED))),
        help="Deterministic random seed (default: %(default)s)"
    )
    args = parser.parse_args(argv)
    run_simulation(
        scenario=args.scenario,
        cycles=args.cycles,
        interval=args.interval,
        seed=args.seed
    )

if __name__ == "__main__":
    main()
