from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
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


def drought_class(spi: float) -> tuple[str, str]:
    if spi > -0.5:
        return "No Drought", "Low Risk"
    if spi >= -0.79:
        return "Abnormally Dry", "Moderate"
    if spi >= -1.29:
        return "Moderate Drought", "Elevated"
    if spi >= -1.59:
        return "Severe Drought", "High"
    if spi >= -1.99:
        return "Extreme Drought", "Critical"
    return "Exceptional Drought", "Extreme"


def compute_bundle(climate: dict[str, Any]) -> dict[str, Any]:
    rainfall = climate["rainfall"]
    rainfall_anomaly = climate["rainfall_anomaly"]
    rainfall_intensity = climate["rainfall_intensity"]
    mean_temperature = climate["mean_temperature"]
    temperature_anomaly = climate["temperature_anomaly"]
    pet = climate["pet"]
    humidity = climate["humidity"]
    solar_radiation = climate["solar_radiation"]
    wind_speed = climate["wind_speed"]
    seasonal_rainfall_3m = climate["seasonal_rainfall_3m"]
    seasonal_rainfall_6m = climate["seasonal_rainfall_6m"]

    rainfall_pressure = (40 - rainfall) / 40.0
    temp_pressure = max(0.0, (mean_temperature - 18.0) / 16.0)
    anomaly_pressure = max(0.0, temperature_anomaly / 4.0)
    pet_pressure = max(0.0, (pet - 4.0) / 8.0)
    humidity_pressure = max(0.0, (55.0 - humidity) / 55.0)
    seasonal_pressure = max(0.0, (300.0 - seasonal_rainfall_6m) / 300.0)

    spi = -0.35 * rainfall_pressure - 0.30 * temp_pressure - 0.25 * anomaly_pressure - 0.20 * pet_pressure - 0.18 * humidity_pressure - 0.15 * seasonal_pressure + 0.12 * (rainfall_intensity / 10.0)
    spi = max(-2.5, min(1.5, spi))
    linear = round(spi + 0.12, 4)
    multiple = round(spi + 0.08, 4)
    polynomial = round(spi + 0.04, 4)
    ridge = round(spi - 0.03, 4)
    lasso = round(spi - 0.07, 4)
    elastic = round(spi - 0.11, 4)

    q10 = round(spi - 0.65, 4)
    q50 = round(spi, 4)
    q90 = round(spi + 0.72, 4)

    drought_days = round(max(0.0, (0.9 - spi) * 55.0 + (rainfall_anomaly * 0.8)), 2)
    hazard_ratio = round(max(0.15, 0.8 + max(0.0, -spi) * 0.9 + (temperature_anomaly / 7.0)), 4)
    confidence_score = round(max(52.0, min(96.0, 86.0 - abs(spi) * 7.0 + (rainfall_intensity * 0.8))), 2)
    drought_label, risk_label = drought_class(spi)

    variable_importance = {
        "Rainfall": round(max(1.0, 100.0 * (1.0 - max(0.0, (rainfall - 30.0) / 120.0))), 2),
        "Temperature": round(max(8.0, 50.0 + temperature_anomaly * 10.0), 2),
        "Humidity": round(max(6.0, 22.0 + humidity * 0.35), 2),
        "PET": round(max(9.0, 30.0 + pet * 4.0), 2),
        "Wind": round(max(5.0, 18.0 + wind_speed * 3.5), 2),
        "Seasonal Rainfall": round(max(12.0, 25.0 + seasonal_rainfall_6m * 0.04), 2),
    }

    return {
        "linear": linear,
        "multiple": multiple,
        "polynomial": polynomial,
        "ridge": ridge,
        "lasso": lasso,
        "elastic": elastic,
        "q10": q10,
        "q50": q50,
        "q90": q90,
        "drought_days": drought_days,
        "hazard_ratio": hazard_ratio,
        "consensus_spi": round(spi, 4),
        "confidence_score": confidence_score,
        "risk_label": risk_label,
        "drought_label": drought_label,
        "variable_importance": variable_importance,
        "hazard_days_to_moderate": round(max(0.0, 20.0 - drought_days / 2.0), 2),
        "hazard_days_to_severe": round(max(0.0, 55.0 - drought_days), 2),
    }


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "app": "NIWIS Flask"}), 200


@app.post("/api/predict")
def predict():
    payload = request.get_json(silent=True) or {}
    climate = normalize_payload(payload)
    bundle = compute_bundle(climate)

    recommendations = [
        {
            "sector": "Water Infrastructure",
            "title": "Demand balancing",
            "body": "Prioritise tiered supply restrictions and targeted groundwater recharge while storage reserves remain stressed.",
            "priority": "High",
        },
        {
            "sector": "Agriculture",
            "title": "Crop resilience plan",
            "body": "Shift to drought-tolerant crops and adjust irrigation windows to match the current climate-risk outlook.",
            "priority": "High",
        },
        {
            "sector": "Disaster Management",
            "title": "Early warning posture",
            "body": "Activate monitoring for fire-risk, water-stress, and heat-related impacts in vulnerable districts.",
            "priority": "Medium",
        },
        {
            "sector": "Public Health",
            "title": "Heat and water safety",
            "body": "Coordinate public messaging around hydration, heat exposure, and community support areas likely to experience stress.",
            "priority": "Medium",
        },
    ]

    response = {
        "province": climate["province"],
        "bundle": bundle,
        "recommendations": recommendations,
        "inputs": climate,
    }
    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
