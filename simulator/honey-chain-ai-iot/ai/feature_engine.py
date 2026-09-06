from collections import defaultdict, deque
from statistics import mean

WINDOW = 10
_history = defaultdict(lambda: deque(maxlen=WINDOW))

# Established comfort boundaries and nominal references from existing risk rules
COMFORT_TEMP_MIN = 30.0
COMFORT_TEMP_MAX = 38.0
COMFORT_HUMIDITY_MIN = 40.0
COMFORT_HUMIDITY_MAX = 75.0
BASELINE_WEIGHT_FLOOR = 20.0

NOMINAL_TEMPERATURE = 34.0
NOMINAL_HUMIDITY = 60.0
NOMINAL_WEIGHT = 42.0

WARMUP_SAMPLES = 3

def _safe_mean(values):
    return mean(values) if values else 0.0

def add_and_generate_features(telemetry):
    """Add rolling/trend features for one hive. History is kept in memory."""
    hive_id = telemetry["hive_id"]
    temp = float(telemetry["temperature_c"])
    humidity = float(telemetry["humidity_pct"])
    weight = float(telemetry["weight_kg"])

    history = _history[hive_id]
    history.append({
        "temperature_c": temp,
        "humidity_pct": humidity,
        "weight_kg": weight
    })

    previous = list(history)[:-1]
    baseline_temp = _safe_mean([x["temperature_c"] for x in previous])
    baseline_humidity = _safe_mean([x["humidity_pct"] for x in previous])
    baseline_weight = _safe_mean([x["weight_kg"] for x in previous])

    # Until enough history exists, initialize baseline.
    # If initial reading is within comfort range, use it as baseline.
    # If initial reading is outside comfort range, fall back to nominal reference
    # so extreme initial readings do NOT self-baseline into false-safe LOW risk.
    if not previous:
        if COMFORT_TEMP_MIN <= temp <= COMFORT_TEMP_MAX:
            baseline_temp = temp
        else:
            baseline_temp = NOMINAL_TEMPERATURE

        if COMFORT_HUMIDITY_MIN <= humidity <= COMFORT_HUMIDITY_MAX:
            baseline_humidity = humidity
        else:
            baseline_humidity = NOMINAL_HUMIDITY

        if weight >= BASELINE_WEIGHT_FLOOR:
            baseline_weight = weight
        else:
            baseline_weight = NOMINAL_WEIGHT

    if len(previous) >= 1:
        prev_weight = previous[-1]["weight_kg"]
        weight_change_rate = weight - prev_weight
    else:
        weight_change_rate = 0.0

    baseline_state = "WARMING_UP" if len(history) < WARMUP_SAMPLES else "ESTABLISHED"

    return {
        "weight_rolling_mean": round(_safe_mean([x["weight_kg"] for x in history]), 4),
        "weight_change_rate": round(weight_change_rate, 4),
        "temperature_deviation": round(temp - baseline_temp, 4),
        "humidity_deviation": round(humidity - baseline_humidity, 4),
        "temperature_baseline": round(baseline_temp, 4),
        "humidity_baseline": round(baseline_humidity, 4),
        "weight_baseline": round(baseline_weight, 4),
        "baseline_state": baseline_state,
        "history_count": len(history),
    }

def reset_history():
    _history.clear()
