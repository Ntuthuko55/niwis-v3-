"""Chronological (walk-forward) validation for time-series models.

Data is NEVER randomly shuffled or split here. Every training set ends strictly
before its validation period, so no future information can leak into training.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from .models import run_model, available_models

_SEASONAL_PERIOD = 365


def seasonal_naive_error_scale(y: pd.Series, period: int = _SEASONAL_PERIOD) -> float:
    """Mean absolute seasonal-naive one-step error over the training series.

    ``mean|y_t - y_{t-period}|`` is the scaling used by the MASE metric. It measures
    how wrong the trivial "same day last year" forecast is, averaged over history.
    """
    clean = y.dropna().values.astype(float)
    if len(clean) <= period:
        return float(clean.std()) if clean.size > 1 else 1.0
    err = np.abs(clean[period:] - clean[:-period])
    return float(np.mean(err)) if np.isfinite(err).all() else float(np.nanmean(err))


def compute_metrics(actual, predicted, naive_scale=None) -> dict[str, float]:
    """MAE, RMSE, R2 and (optionally) MASE for a pair of arrays."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    mae = float(np.mean(np.abs(a - p)))
    rmse = float(np.sqrt(np.mean((a - p) ** 2)))
    ss_res = float(np.sum((a - p) ** 2))
    ss_tot = float(np.sum((a - np.mean(a)) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    out = {"mae": mae, "rmse": rmse, "r_squared": r2, "mase": None}
    if naive_scale and np.isfinite(naive_scale) and naive_scale > 1e-12:
        out["mase"] = float(np.mean(np.abs(a - p)) / naive_scale)
    return out


def _safe_metrics(actual, predicted) -> dict[str, float]:
    """Backwards-compatible simple metric helper (no MASE scale)."""
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    mae = float(np.mean(np.abs(a - p)))
    rmse = float(np.sqrt(np.mean((a - p) ** 2)))
    ss_res = float(np.sum((a - p) ** 2))
    ss_tot = float(np.sum((a - np.mean(a)) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    return {"mae": mae, "rmse": rmse, "r_squared": r2}


def run_validation_split(y_train, actual, horizon: int, models=None) -> dict[str, Any]:
    """Fit every model on ``y_train`` and score it against ``actual``.

    Returns ``{model: {metrics, status, error, time}}``. Predictions are truncated to
    ``min(horizon, len(actual))`` for a fair, length-aligned comparison.
    """
    import time
    if models is None:
        models = available_models()
    naive_scale = seasonal_naive_error_scale(y_train)
    n_pred = min(horizon, len(actual))
    results: dict[str, Any] = {}
    for name in models:
        t0 = time.time()
        try:
            pred, lower, upper = run_model(name, y_train, horizon)
            pred = np.asarray(pred, dtype=float)[:n_pred]
            if not np.all(np.isfinite(pred)):
                raise ValueError("Forecast contains non-finite values")
            results[name] = {
                "metrics": compute_metrics(actual.values[:n_pred], pred, naive_scale),
                "status": "ok",
                "time": round(time.time() - t0, 3),
                "predictions": pred.tolist(),
                "lower": (None if lower is None else np.asarray(lower, dtype=float)[:n_pred].tolist()),
                "upper": (None if upper is None else np.asarray(upper, dtype=float)[:n_pred].tolist()),
            }
        except Exception as exc:  # noqa: BLE001 - report model-level failures
            results[name] = {"status": "failed", "error": str(exc), "time": round(time.time() - t0, 3)}
    return results


def walk_forward_validation(
    y: pd.Series,
    horizon: int = 365,
    cutoff_years: list[int] | None = None,
    models: list[str] | None = None,
) -> dict[str, Any]:
    """Run walk-forward backtests from multiple historical cutoffs.

    For each ``cutoff`` (e.g. the start of 2021/2022/2023/2024), train on everything
    up to the cutoff, forecast the next ``horizon`` days, and score against the true
    (unseen) observations. Returns per-cutoff results plus an averaged summary.
    """
    if cutoff_years is None:
        cutoff_years = [2021, 2022, 2023, 2024]
    if models is None:
        models = available_models()

    per_cutoff: dict[str, Any] = {}
    avg: dict[str, list[dict[str, float]]] = {m: [] for m in models}

    for year in cutoff_years:
        cutoff = pd.Timestamp(year=year, month=1, day=1)
        if cutoff not in y.index:
            continue
        train = y.loc[:cutoff]
        if len(train) < 2 * _SEASONAL_PERIOD:
            continue
        actual_end = cutoff + pd.Timedelta(days=horizon)
        actual = y.loc[cutoff + pd.Timedelta(days=1): actual_end]
        if len(actual) < max(10, horizon // 2):
            continue

        res = run_validation_split(train, actual, horizon, models)
        per_cutoff[str(year)] = res
        for name, r in res.items():
            if r.get("status") == "ok":
                avg[name].append(r["metrics"])

    summary: dict[str, Any] = {}
    for name, lst in avg.items():
        if not lst:
            summary[name] = {"status": "no_data"}
            continue
        keys = ["mae", "rmse", "r_squared", "mase"]
        row = {"status": "ok", "n_cutoffs": len(lst)}
        for k in keys:
            row[k] = float(np.nanmean([m[k] for m in lst])) if k in lst[0] else None
        summary[name] = row

    return {"by_cutoff": per_cutoff, "average": summary, "cutoff_years": cutoff_years}


def average_validation_rmse(validation_results: dict[str, Any]) -> dict[str, float]:
    """Average out-of-sample RMSE per model across all backtest folds."""
    avg = validation_results.get("average", {})
    scores: dict[str, float] = {}
    for model, row in avg.items():
        if row.get("status") == "ok" and row.get("rmse") is not None:
            scores[model] = float(row["rmse"])
    return scores


def select_best_model(comparison) -> str:
    """Select the model with the lowest out-of-sample RMSE.

    Accepts either the flat evaluator comparison ``{model: {metrics, status}}`` or
    the walk-forward result ``{by_cutoff: {...}, average: {...}}``.
    """
    if isinstance(comparison, dict) and "average" in comparison:
        scores = average_validation_rmse(comparison)
    else:
        scores = {}
        for model, res in comparison.items():
            if isinstance(res, dict) and res.get("status") == "ok" and "metrics" in res:
                rmse = res["metrics"].get("rmse")
                if isinstance(rmse, (int, float)):
                    scores[model] = float(rmse)
    if not scores:
        return "harmonic"  # robust seasonal default
    return min(scores, key=scores.get)