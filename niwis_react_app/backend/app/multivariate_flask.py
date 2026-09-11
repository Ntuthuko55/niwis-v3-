"""Flask API for Multivariate Analytics Studio.

The API deliberately stores uploaded data only in memory for the current
process.  It is suitable for a single-user local deployment; production
deployments should replace this registry with an authenticated object store.
"""
from __future__ import annotations

import io
from collections import defaultdict

import pandas as pd
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from app.multivariate.analyses.registry import get_analysis, list_methods
from app.multivariate.core.dataset_engine import DatasetEngine


app = Flask(__name__)
CORS(app)
engine = DatasetEngine()


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def recommendations(profile: dict) -> list[dict]:
    """Give conservative, dataset-driven guidance without running models."""
    buckets = profile["buckets"]
    numeric = buckets["numeric"] + buckets["ordinal"]
    categorical = buckets["categorical_like"]
    n_rows = profile["dimensions"]["rows"]
    result = []
    rules = {
        "regression": (len(numeric) >= 2 and n_rows >= 20,
                       "A continuous outcome and one or more predictors can be selected."),
        "pca": (len(numeric) >= 2 and n_rows >= 10,
                "At least two numeric variables are available for dimension reduction."),
        "cluster": (len(numeric) >= 2 and n_rows >= 10,
                    "A numeric feature matrix is available for segmentation."),
        "factor": (len(numeric) >= 3 and n_rows >= 30,
                   "Numeric variables are available; KMO and Bartlett diagnostics are still required."),
        "manova": (len(numeric) >= 2 and len(categorical) >= 1,
                   "Select two or more outcomes and a categorical grouping variable."),
        "discriminant": (len(numeric) >= 1 and len(categorical) >= 1,
                         "Select a class variable and numeric predictors."),
        "correspondence": (len(categorical) >= 2,
                           "Two categorical variables can form a contingency table."),
        "canonical": (len(numeric) >= 4 and n_rows >= 20,
                      "Two sets of at least two numeric variables can be selected."),
        "ica": (len(numeric) >= 2 and n_rows >= 10,
                "A numeric signal matrix is available."),
        "pls": (len(numeric) >= 2 and n_rows >= 20,
                "Numeric predictors and outcome variables can be selected."),
        "mds": (len(numeric) >= 2 and n_rows >= 4,
                "A numeric feature matrix can be converted to distances."),
    }
    for method in list_methods():
        applicable, reason = rules[method["id"]]
        result.append({**method, "status": "recommended" if applicable else "conditional",
                       "reason": reason})
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Multivariate Analytics Studio"}


@app.get("/api/methods")
def methods():
    return jsonify({"methods": list_methods()})


@app.post("/api/datasets")
def upload_dataset():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return error("Choose a CSV, XLS, or XLSX file to upload.")
    filename = uploaded.filename
    if not filename.lower().endswith((".csv", ".xls", ".xlsx")):
        return error("Unsupported file type. Upload CSV, XLS, or XLSX.")
    try:
        payload = uploaded.read()
        df = engine._read_file(io.BytesIO(payload), filename)
    except Exception as exc:
        return error(f"The file could not be read: {exc}")
    if df.empty or not len(df.columns):
        return error("The uploaded dataset has no rows or columns.")
    df.columns = [str(c).strip() or f"Unnamed_{i + 1}" for i, c in enumerate(df.columns)]
    dataset_id = engine.register(df, filename)
    profile = engine.profile(df)
    return jsonify({"dataset": engine.info(dataset_id), "profile": profile,
                    "recommendations": recommendations(profile)}), 201


@app.get("/api/datasets/<dataset_id>")
def dataset_profile(dataset_id: str):
    df = engine.get(dataset_id)
    if df is None:
        return error("Dataset not found. Upload it again and retry.", 404)
    profile = engine.profile(df)
    return jsonify({"dataset": engine.info(dataset_id), "profile": profile,
                    "recommendations": recommendations(profile)})


@app.get("/api/datasets/<dataset_id>/preview")
def dataset_preview(dataset_id: str):
    """Return a small, display-safe preview; never expose a whole upload."""
    df = engine.get(dataset_id)
    if df is None:
        return error("Dataset not found. Upload it again and retry.", 404)
    try:
        limit = min(max(int(request.args.get("limit", 10)), 1), 50)
    except ValueError:
        return error("Preview limit must be a number.")
    safe = df.head(limit).where(pd.notna(df.head(limit)), None)
    return jsonify({"columns": [str(c) for c in safe.columns],
                    "rows": safe.to_dict(orient="records"),
                    "total_rows": int(len(df))})


@app.post("/api/analyses/<method_id>/validate")
def validate_analysis(method_id: str):
    payload = request.get_json(silent=True) or {}
    dataset_id = payload.get("dataset_id")
    if engine.get(dataset_id) is None:
        return error("Dataset not found. Upload it again and retry.", 404)
    try:
        result = get_analysis(method_id, engine).run(dataset_id, payload.get("config", {}),
                                                      payload.get("type_map"))
    except (ValueError, ImportError, AttributeError) as exc:
        return error(str(exc))
    return jsonify({"applicable": result["applicable"], "preconditions": result["preconditions"],
                    "assumptions": result["assumptions"], "errors": result["errors"],
                    "warnings": result["warnings"]})


@app.post("/api/analyses/<method_id>")
def run_analysis(method_id: str):
    payload = request.get_json(silent=True) or {}
    dataset_id = payload.get("dataset_id")
    if engine.get(dataset_id) is None:
        return error("Dataset not found. Upload it again and retry.", 404)
    try:
        result = get_analysis(method_id, engine).run(dataset_id, payload.get("config", {}),
                                                      payload.get("type_map"))
    except (ValueError, ImportError, AttributeError) as exc:
        return error(str(exc))
    return jsonify(result)


@app.post("/api/exports/results.csv")
def export_results_csv():
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return error("Results rows must be a list.")
    buffer = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode("utf-8"))
    return send_file(buffer, mimetype="text/csv", as_attachment=True,
                     download_name="analysis-results.csv")


if __name__ == "__main__":
    # Uploaded datasets are intentionally held in this process's in-memory
    # registry.  Flask's debug reloader starts a replacement process whenever
    # it notices imports changing (including packages such as NumPy/Plotly),
    # which discards that registry and makes a just-uploaded dataset ID return
    # 404 on the next analysis request.  Keep the local app stateful and
    # predictable; restart Flask manually after editing backend code.
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


