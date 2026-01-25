from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

from prometheus_client import Histogram, Counter, REGISTRY
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app, registry=REGISTRY)


cache_operation_latency = Histogram(
    'cache_operation_seconds',
    'Cache operation duration',
    labelnames=['op'],
    registry=REGISTRY
)
cache_hits = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['endpoint'],
    registry=REGISTRY  
)

cache_misses = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['endpoint'],
    registry=REGISTRY
)


from joblib import load
import pandas as pd
import numpy as np
import redis
import time



app.config['data_buffer'] = []
app.config['last_prediction'] = 62.5
# Test mode flag
TEST_MODE = False

# ── Redis client ───────────────────────────────────────────────
redis_client = redis.Redis(
    host='redis',          # docker service name
    port=6379,
    db=0,
    decode_responses=True  # get strings, not bytes
)
# Load model and validate
try:
    model = load('LIN_model.joblib')
    expected_features = model.feature_names_in_.tolist() if hasattr(model, 'feature_names_in_') else []
    print(f"Model loaded successfully. Expected features: {expected_features}")
    if not TEST_MODE:
        model_coefficients = dict(zip(expected_features, model.coef_))
except Exception as e:
    print(f"Error loading model: {str(e)}")
    model = None
    expected_features = []
    model_coefficients = {}




# ── Helper: make cache key from input features ─────────────────
def make_cache_key(data: dict) -> str:
    # Sort keys + values to make deterministic key
    sorted_items = sorted(data.items())
    key_str = ",".join(f"{k}:{v}" for k, v in sorted_items)
    return f"predict:{key_str}"

# ── Endpoint 1: No cache (always runs model) ───────────────────
@app.route('/predict-nocache', methods=['POST'])
def predict_nocache():
    start = time.perf_counter()
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    try:
        df = pd.DataFrame([data])
        prediction = model.predict(df)[0]
        latency = time.perf_counter() - start
        print(f"[NoCache] Inference took {latency:.4f}s")
        return jsonify({"prediction": float(prediction)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Endpoint 2: Cache-aside ────────────────────────────────────
@app.route('/predict-cached', methods=['POST'])
def predict_cached():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    key = make_cache_key(data)
    print(f"[DEBUG] Cache key: {key}")
    # Get from cache
    with cache_operation_latency.labels(op='get').time():
        cached = redis_client.get(key)
        
    if cached is not None:
        cache_hits.labels(endpoint='predict-cached').inc()  
        print(f"[Cached] HIT for key {key}")
        return jsonify({"prediction": float(cached), "from_cache": True})

    # MISS
    cache_misses.labels(endpoint='predict-cached').inc()   
    print(f"[Cached] MISS for key {key} → computing")

    lock_key = f"lock:{key}"
    acquired = redis_client.set(lock_key, "1", nx=True, ex=10)

    if acquired:
        try:
            # double check (вдруг кто-то успел записать за нас)
            cached = redis_client.get(key)
            if cached is not None:
                cache_hits.labels(endpoint='predict-cached').inc()
                print(f"[Cached] HIT after lock for key {key}")
                return jsonify({"prediction": float(cached), "from_cache": True})

            # expensive work
            df = pd.DataFrame([data])
            prediction = model.predict(df)[0]

            # СОХРАНЯЕМ В КЭШ — это главное!
            with cache_operation_latency.labels(op='set').time():
                redis_client.set(key, str(prediction), ex=30)

            print(f"[Cached] Saved to cache: {key} = {prediction}")

            return jsonify({"prediction": float(prediction), "from_cache": False})

        finally:
            redis_client.delete(lock_key)
    else:
        # spin-lock
        for _ in range(20):
            time.sleep(0.05)
            cached = redis_client.get(key)
            if cached is not None:
                cache_hits.labels(endpoint='predict-cached').inc()
                return jsonify({"prediction": float(cached), "from_cache": True})

    # fallback (если lock не получен)
    start = time.perf_counter()
    try:
        df = pd.DataFrame([data])
        prediction = model.predict(df)[0]
        latency = time.perf_counter() - start

        with cache_operation_latency.labels(op='set').time():
            
            set_result = redis_client.set(key, str(prediction), ex=30)
            print(f"[DEBUG] redis.set result for key {key}: {set_result}")  # ← добавь это!
        print(f"[Cached] Inference + cache set took {latency:.4f}s")
        return jsonify({"prediction": float(prediction), "from_cache": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
# Define required features
required_features = expected_features or [
    'Total charge rate, t/h',
    'Overall blast volume, m3/h',
    'Oxygen content in the blast, %',
    'Temperature of exhaust gases in the off-gas duct, °C',
    'Temperature of feed in the smelting zone, °C',
    'feeder 2, speed'
]

# Normative ranges for adjustable parameters
normative_ranges = {
    'Overall blast volume, m3/h': (15000, 35000),
    'feeder 2, speed': (15, 45),
}

# Manual coefficients for test mode
if TEST_MODE:
    model_coefficients = {
        'Overall blast volume, m3/h': 0.002,
        'feeder 2, speed': -0.1,  # Corrected to negative as per typical process logic
    }

adjustment_count = 0

# Minimum data points required for prediction
MIN_DATA_POINTS = 20

TARGET = 62.5

def simulate_prediction(adjustment_count):
    noise = np.random.normal(0, 0.5)
    if adjustment_count == 0:
        return max(50.0, min(60.0, 55.0 + noise))  # Below target
    elif adjustment_count == 1:
        return max(55.0, min(61.0, 58.0 + noise))  # After first adjustment
    else:
        return max(60.0, min(65.0, 62.5 + noise))  # After second adjustment

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        df_input = pd.DataFrame([data])
        missing_features = [f for f in required_features if f not in df_input.columns]
        if missing_features:
            return jsonify({"error": f"Missing features: {missing_features}"}), 400

        for feature in required_features:
            df_input[feature] = pd.to_numeric(df_input[feature], errors='coerce')
            if df_input[feature].isna().any():
                return jsonify({"error": f"Non-numeric or invalid value for feature: {feature}"}), 400

        # Add to buffer
        app.config['data_buffer'].append(df_input.iloc[0].to_dict())

        if len(app.config['data_buffer']) < MIN_DATA_POINTS:
            return jsonify({"status": "gathering_data", "message": f"Accumulated {len(app.config['data_buffer'])}/{MIN_DATA_POINTS} data points. Waiting for more data."})

        # When buffer is full, create DataFrame, average features, predict
        df_buffer = pd.DataFrame(app.config['data_buffer'])
        df_avg = df_buffer[expected_features].mean().to_frame().T  # Average over buffer
        if not TEST_MODE:
            if not model:
                return jsonify({"error": "Model not loaded properly"}), 500
            app.config['last_prediction'] = model.predict(df_avg[expected_features])[0]
        else:
            app.config['last_prediction'] = simulate_prediction(adjustment_count)

        # slide buffer by 1
        app.config['data_buffer'] = app.config['data_buffer'][10:]

        return jsonify({"prediction": float(app.config['last_prediction'])})

    except Exception as e:
        print(f"Error in /predict: {str(e)}")
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500

@app.route("/recommend", methods=["POST"])
def recommend():
    global adjustment_count
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        df_input = pd.DataFrame([data])

        for feature in required_features:
            df_input[feature] = pd.to_numeric(df_input[feature], errors='coerce')
            if df_input[feature].isna().any():
                return jsonify({"error": f"Non-numeric or invalid value for feature: {feature}"}), 400
        df_input = df_input[expected_features]
            
        deviation = TARGET - app.config['last_prediction']

        recommendations = []
        adjustable_params = ['Overall blast volume, m3/h', 'feeder 2, speed']
        for param in adjustable_params:
            coef = model_coefficients.get(param, 0)
            if abs(deviation) > 0.5 and coef != 0:
                if deviation > 0:  # Need to increase Cu
                    direction = 'Увеличить' if coef > 0 else 'Уменьшить'
                else:  # Need to decrease Cu
                    direction = 'Уменьшить' if coef > 0 else 'Увеличить'
               
                current_val = float(df_input[param].iloc[0])
                norm_min, norm_max = normative_ranges.get(param, (None, None))
                change = abs(deviation) * 10  # Adjust change factor as needed
                if direction == 'Увеличить':
                    recommended_val = min(current_val + change, norm_max) if norm_max else current_val + change
                else:
                    recommended_val = max(current_val - change, norm_min) if norm_min else current_val - change
                recommendations.append({
                    "parameter": param,
                    "action": direction,
                    "current_value": current_val,
                    "recommended_value": recommended_val,
                    "change": abs(recommended_val - current_val),
                    "importance": abs(coef),
                    "safety_limit": f"{norm_min}-{norm_max}" if norm_min and norm_max else "N/A"
                })

        recommendations = sorted(recommendations, key=lambda x: x["importance"], reverse=True)

        if TEST_MODE:
            adjustment_count = min(adjustment_count + 1, 2)

        return jsonify({
            "recommendations": recommendations
        })

    except Exception as e:
        print(f"Error in /recommend: {str(e)}")
        return jsonify({"error": f"Recommendation failed: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5002, debug=False)