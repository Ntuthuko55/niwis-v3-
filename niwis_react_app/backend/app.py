from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from flask import Flask, jsonify, request
from flask_cors import CORS

from core.engine import validate_inputs
from core.loader import ModelRegistry
from core.predictor import NIWISPredictor
from core.recommendations import RecommendationEngine
from utils import configure_logging, safe_float

logger = configure_logging("NIWIS.ReactBackend")
app = Flask(__name__)
CORS(app)

MODEL_REGISTRY = ModelRegistry().load()
PREDICTOR = NIWISPredictor(MODEL_REGISTRY)

DEFAULT_INPUTS = {
    "province": "Eastern Cape",
    "rainfall": 42.5,
    "rainfall_anomaly": 5.0,
    "rainfall_intensity": 8.2,
    "min_temperature": 12.4,
    "max_temperature": 27.0,
    "mean_temperature": 19.7,
    "temperature_anomaly": 1.2,
    "pet": 5.6,
    "et0": 4.1,
    "humidity": 54.0,
    "solar_radiation": 240.0,
    "wind_speed": 6.4,
    "seasonal_rainfall_3m": 130.0,
    "seasonal_rainfall_6m": 310.0,
}


def normalize_payload(payload: dict) -> dict:
    return {
        "province": payload.get("province", DEFAULT_INPUTS["province"]),
        "rainfall": safe_float(payload.get("rainfall", DEFAULT_INPUTS["rainfall"])),
        "rainfall_anomaly": safe_float(payload.get("rainfall_anomaly", DEFAULT_INPUTS["rainfall_anomaly"])),
        "rainfall_intensity": safe_float(payload.get("rainfall_intensity", DEFAULT_INPUTS["rainfall_intensity"])),
        "min_temperature": safe_float(payload.get("min_temperature", DEFAULT_INPUTS["min_temperature"])),
        "max_temperature": safe_float(payload.get("max_temperature", DEFAULT_INPUTS["max_temperature"])),
        "mean_temperature": safe_float(payload.get("mean_temperature", DEFAULT_INPUTS["mean_temperature"])),
        "temperature_anomaly": safe_float(payload.get("temperature_anomaly", DEFAULT_INPUTS["temperature_anomaly"])),
        "pet": safe_float(payload.get("pet", DEFAULT_INPUTS["pet"])),
        "et0": safe_float(payload.get("et0", DEFAULT_INPUTS["et0"])),
        "humidity": safe_float(payload.get("humidity", DEFAULT_INPUTS["humidity"])),
        "solar_radiation": safe_float(payload.get("solar_radiation", DEFAULT_INPUTS["solar_radiation"])),
        "wind_speed": safe_float(payload.get("wind_speed", DEFAULT_INPUTS["wind_speed"])),
        "seasonal_rainfall_3m": safe_float(payload.get("seasonal_rainfall_3m", DEFAULT_INPUTS["seasonal_rainfall_3m"])),
        "seasonal_rainfall_6m": safe_float(payload.get("seasonal_rainfall_6m", DEFAULT_INPUTS["seasonal_rainfall_6m"])),
    }


@app.get("/api/health")
def health() -> tuple[dict, int]:
    return jsonify({"status": "ok", "app": "NIWIS React + Flask"}), 200


@app.post("/api/predict")
def predict() -> tuple[dict, int]:
    payload = request.get_json(silent=True) or {}
    climate = normalize_payload(payload)

    validate_inputs(climate)
    bundle = PREDICTOR.predict(climate)
    recommendations = RecommendationEngine(
        risk=bundle.risk_label,
        consensus_spi=bundle.consensus_spi,
        drought_days=bundle.drought_days,
        hazard_ratio=bundle.hazard_ratio,
    ).generate()

    response = {
        "province": climate["province"],
        "bundle": {
            "linear": bundle.linear,
            "multiple": bundle.multiple,
            "polynomial": bundle.polynomial,
            "ridge": bundle.ridge,
            "lasso": bundle.lasso,
            "elastic": bundle.elastic,
            "q10": bundle.q10,
            "q50": bundle.q50,
            "q90": bundle.q90,
            "drought_days": bundle.drought_days,
            "hazard_ratio": bundle.hazard_ratio,
            "consensus_spi": bundle.consensus_spi,
            "confidence_score": bundle.confidence_score,
            "risk_label": bundle.risk_label,
            "drought_label": bundle.drought_label,
            "variable_importance": bundle.variable_importance,
            "hazard_days_to_moderate": bundle.hazard_days_to_moderate,
            "hazard_days_to_severe": bundle.hazard_days_to_severe,
        },
        "recommendations": [
            {
                "sector": r.sector,
                "title": r.title,
                "body": r.body,
                "priority": r.priority,
            }
            for r in recommendations
        ],
        "inputs": climate,
    }
    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
