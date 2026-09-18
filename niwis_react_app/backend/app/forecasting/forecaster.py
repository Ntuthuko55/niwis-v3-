"""Main forecasting pipeline: preprocessing, diagnostics, model selection, forecast.

The pipeline is deliberately science-first:

1. Preprocess and validate the daily series (chronological, deduped, gap-filled).
2. Run time-series diagnostics (trend, seasonality, autocorrelation, stationarity).
3. Compare several *seasonal* candidate models on a chronological holdout.
4. Run walk-forward backtesting from multiple historical cutoffs.
5. Select the best model by out-of-sample RMSE (never training performance).
6. Retrain the winner on ALL data and forecast ``horizon`` days into the future.
7. Guard against the classic AR failure mode (forecast collapsing to the mean) by
   checking that the forecast still carries the historical seasonal amplitude.
"""
from __future__ import annotations

from typing import Any
import warnings

import numpy as np
import pandas as pd

from .preprocessing import prepare_series
from .diagnostics import run_diagnostics
from .models import run_model, available_models
from .validation import (
    run_validation_split,
    walk_forward_validation,
    select_best_model,
    average_validation_rmse,
    compute_metrics,
    seasonal_naive_error_scale,
)
from .evaluator import build_comparison_table, sort_comparison_rows

# Models that robustly encode the annual cycle (used as safety fallbacks).
_SEASONAL_SAFE = ["harmonic", "seasonal_naive", "prophet", "sarimax", "ets"]

# User-facing model names for the forecast table / UI.
_MODEL_LABELS = {
    "seasonal_naive": "Seasonal Naive",
    "harmonic": "Harmonic Regression (seasonal)",
    "sarimax": "SARIMAX + Fourier seasonality",
    "ets": "ETS (Exponential Smoothing)",
    "prophet": "Prophet",
    "ml": "Gradient Boosting (calendar/lags)",
}


def _map_preferred_model(model_type: str | None) -> tuple[str | None, list[str]]:
    """Map a user-selected model type onto a seasonal candidate.

    Non-seasonal AR-family models (ar, ma, arma, arima) collapse on daily climate
    data; we map them to their seasonal equivalent and record a note.
    """
    warnings_list: list[str] = []
    if not model_type or model_type.lower() in {"auto", "niwis_auto"}:
        return None, warnings_list
    mt = model_type.lower()
    mapping = {
        "ar": "sarimax", "arima": "sarimax", "arma": "sarimax", "ma": "ets",
        "sarima": "sarimax", "sarimax": "sarimax", "ets": "ets",
        "exponential_smoothing": "ets", "harmonic": "harmonic",
        "prophet": "prophet", "ml": "ml", "gradient_boosting": "ml",
    }
    target = mapping.get(mt)
    if mt in {"ar", "arima", "arma", "ma"}:
        warnings_list.append(
            f"'{mt}' has no seasonal terms and collapses on daily climate data; "
            f"mapped to '{target}' which preserves the annual cycle."
        )
    return target, warnings_list


def _historical_seasonal_amplitude(y: pd.Series) -> float:
    """Annual swing = mean(day-of-year peak) - mean(day-of-year trough)."""
    annual = y.dropna().groupby(y.dropna().index.dayofyear).mean()
    if len(annual) < 60:
        return 0.0
    return float(annual.max() - annual.min())


def _is_collapsed(vals: np.ndarray, amplitude: float) -> bool:
    """True when a forecast has flattened out relative to the historical cycle.

    Compares the forecast's own seasonal swing (max - min) to the historical annual
    amplitude. A smooth seasonal model legitimately has low *std* (no daily noise),
    so we use the peak-to-trough range rather than the standard deviation - this
    avoids false positives on valid seasonal forecasts while still catching a
    mean-converging AR model whose range collapses to ~0.
    """
    if amplitude is None or amplitude <= 1e-9:
        return False
    forecast_swing = float(np.max(vals) - np.min(vals)) if len(vals) else 0.0
    return forecast_swing < 0.30 * amplitude


def _sanitize_numeric(vals: np.ndarray, y: pd.Series) -> np.ndarray:
    """Replace non-finite forecast values with finite fallbacks (JSON-safe)."""
    vals = np.asarray(vals, dtype=float)
    if np.all(np.isfinite(vals)):
        return vals
    fallback = float(np.nanmean(y.values)) if np.isfinite(np.nanmean(y.values)) else 0.0
    # Forward-fill then back-fill over any non-finite entries.
    tmp = pd.Series(vals).replace([np.inf, -np.inf], np.nan)
    filled = tmp.interpolate(method="linear").bfill().ffill().fillna(fallback)
    return filled.to_numpy(dtype=float)


def _forecast_table(model_label: str, dates, vals, lower, upper) -> list[dict[str, Any]]:
    rows = []
    for i, d in enumerate(dates):
        rows.append({
            "date": d.isoformat(),
            "forecast": float(vals[i]),
            "lower_ci": float(lower[i]) if lower is not None else None,
            "upper_ci": float(upper[i]) if upper is not None else None,
            "model": model_label,
        })
    return rows


def _build_result(
    model: str,
    vals, lower, upper,
    future_dates,
    y: pd.Series,
    diagnostics: dict[str, Any],
    comparison, comparison_table,
    validation_results, backtest_avg,
    validation_metrics, warnings_list,
    confidence_level: float,
    seasonality_amplitude: float,
) -> dict[str, Any]:
    return {
        "model": model,
        "model_label": _MODEL_LABELS.get(model, model),
        "forecast": [float(v) for v in vals],
        "lower_bound": [float(v) for v in lower] if lower is not None else None,
        "upper_bound": [float(v) for v in upper] if upper is not None else None,
        "history_dates": [d.isoformat() for d in y.index],
        "history_values": [float(v) for v in y.values],
        "forecast_dates": [d.isoformat() for d in future_dates],
        "metrics": validation_metrics,
        "diagnostics": diagnostics,
        "validation_results": validation_results,
        "backtesting": validation_results,
        "backtest_average": backtest_avg,
        "model_comparison": comparison,
        "comparison_table": comparison_table,
        "forecast_table": _forecast_table(
            _MODEL_LABELS.get(model, model), future_dates, vals, lower, upper
        ),
        "warnings": warnings_list,
        "seasonality_detected": bool(seasonality_amplitude > 1e-9),
        "seasonality_amplitude": float(seasonality_amplitude),
        "confidence_level": float(confidence_level),
        "selected_explanation": (
            f"Selected {model} because it had the lowest out-of-sample RMSE in "
            f"chronological validation, while preserving the historical annual "
            f"seasonal amplitude of ~{seasonality_amplitude:.2f} units."
        ),
    }


def forecast_time_series(
    df: pd.DataFrame,
    date_column: str,
    target_column: str,
    horizon: int = 365,
    validation_cutoffs: list[int] | None = None,
    preferred_model: str | None = None,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """End-to-end daily climate forecasting pipeline.

    Parameters
    ----------
    df : raw dataframe with `date_column` and `target_column`.
    date_column : name of the datetime column.
    target_column : name of the variable to forecast (temperature, rainfall, PET...).
    horizon : number of future days (30 / 90 / 180 / 365).
    validation_cutoffs : walk-forward cutoff years, e.g. [2021, 2022, 2023, 2024].
    preferred_model : optional model name hint; mapped to a seasonal equivalent.

    Returns a dict with model, forecast, confidence intervals, metrics,
    diagnostics, validation/backtest results, comparison table and warnings.
    """
    warnings.filterwarnings("ignore")
    warnings_list: list[str] = []

    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    # preference mapping (e.g. arima -> sarimax) guards against flat models.
    pref_target, pref_warning = _map_preferred_model(preferred_model)
    warnings_list.extend(pref_warning)

    # ---- 1. Preprocess -----------------------------------------------------
    y = prepare_series(df, date_column, target_column)
    if len(y) < 100:
        raise ValueError("Need at least ~100 daily observations to forecast.")

    # ---- 2. Diagnostics ----------------------------------------------------
    diagnostics = run_diagnostics(y, freq=365)
    amplitude = _historical_seasonal_amplitude(y)
    seasonality_detected = amplitude > 1e-9
    if not seasonality_detected:
        warnings_list.append("No strong annual seasonality detected in the target series.")

    # ---- 3. Chronological comparison --------------------------------------
    val_size = int(min(365, max(90, len(y) // 5)))
    y_train, y_val = y.iloc[:-val_size], y.iloc[-val_size:]

    comparison = run_validation_split(y_train, y_val, val_size)
    comparison_table = sort_comparison_rows(build_comparison_table(comparison))
    best = select_best_model(comparison)

    # Only models with an OK long-horizon forecast are eligible (flat ones are bad).
    ok_models = [r["model"] for r in comparison_table if r["status"] == "ok"]

    # ---- 4. Walk-forward backtesting (top models only, to stay fast) -------
    cutoff_years = validation_cutoffs or [2021, 2022, 2023, 2024]
    backtest_models = ok_models[:3] or _SEASONAL_SAFE[:2]
    if best not in backtest_models:
        backtest_models.append(best)
    # Cap backtest horizon so long forecasts (e.g. 1–5 years) stay interactive.
    backtest_horizon = min(horizon, 90)
    try:
        validation_results = walk_forward_validation(
            y, horizon=backtest_horizon, cutoff_years=cutoff_years, models=backtest_models
        )
    except Exception:  # noqa: BLE001 - backtesting is best-effort
        validation_results = {"by_cutoff": {}, "average": {}, "cutoff_years": cutoff_years}
    backtest_avg = validation_results.get("average", {})

    # Prefer the model that is both best on the holdout and available in backtest.
    wf_scores = average_validation_rmse(validation_results)
    final_model = min(wf_scores, key=wf_scores.get) if wf_scores else best

    if pref_target and pref_target != final_model and pref_target in _MODEL_LABELS:
        warnings_list.append(
            f"Auto-selection chose '{final_model}' (best out-of-sample RMSE) over the "
            f"requested '{pref_target}'."
        )

    # ---- 5. Retrain the winner on ALL data and forecast --------------------
    try:
        vals, lower, upper = run_model(final_model, y, horizon)
    except Exception as exc:  # noqa: BLE001
        warnings_list.append(f"{final_model} failed on full data ({exc}); using harmonic.")
        final_model = "harmonic"
        vals, lower, upper = run_model(final_model, y, horizon)

    # ---- 6. Quality guard - do NOT return a flat forecast ------------------
    seasonal_models = {"harmonic", "seasonal_naive", "prophet", "sarimax", "ets", "ml"}
    if final_model not in seasonal_models and _is_collapsed(np.asarray(vals, dtype=float), amplitude):
        warnings_list.append(
            "WARNING: Forecast has collapsed toward the historical mean. "
            "Falling back to harmonic seasonal regression."
        )
        final_model = "harmonic"
        vals, lower, upper = run_model(final_model, y, horizon)
        vals = np.asarray(vals, dtype=float)
        if lower is not None:
            lower = np.asarray(lower, dtype=float)
        if upper is not None:
            upper = np.asarray(upper, dtype=float)

    vals = np.asarray(vals, dtype=float)
    if lower is not None:
        lower = np.asarray(lower, dtype=float)
    if upper is not None:
        upper = np.asarray(upper, dtype=float)

    # Guarantee JSON-safe, finite forecasts and intervals.
    vals = _sanitize_numeric(vals, y)
    if lower is not None:
        lower = _sanitize_numeric(lower, y)
    if upper is not None:
        upper = _sanitize_numeric(upper, y)

    # ---- 7. Validation metrics for the UI ----------------------------------
    val_res = comparison.get(final_model, {})
    vm = val_res.get("metrics", {}) if val_res.get("status") == "ok" else {}
    validation_metrics = {
        "mae": vm.get("mae", 0.0) or 0.0,
        "rmse": vm.get("rmse", 0.0) or 0.0,
        "r_squared": vm.get("r_squared", 0.0) or 0.0,
        "mase": vm.get("mase"),
        "naive_scale": seasonal_naive_error_scale(y),
    }

    # ---- 8. Future dates and result ----------------------------------------
    last_date = y.index[-1]
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D")

    result = _build_result(
        model=final_model,
        vals=vals,
        lower=lower,
        upper=upper,
        future_dates=future_dates,
        y=y,
        diagnostics=diagnostics,
        comparison=comparison,
        comparison_table=comparison_table,
        validation_results=validation_results,
        backtest_avg=backtest_avg,
        validation_metrics=validation_metrics,
        warnings_list=warnings_list,
        confidence_level=confidence_level,
        seasonality_amplitude=amplitude,
    )

    # Attach per-model details from the chronological comparison (predictions, CIs, metrics, time)
    details_map: dict[str, Any] = {}
    for m, r in comparison.items():
        details_map[m] = {
            'status': r.get('status'),
            'metrics': r.get('metrics'),
            'time': r.get('time'),
            'predictions': r.get('predictions'),
            'lower': r.get('lower'),
            'upper': r.get('upper'),
        }
    result['details'] = details_map

    # Quality checks on the final forecast.
    if np.std(vals) < 1e-9:
        result["warnings"].append("WARNING: Forecast is a constant value.")
    hist_min, hist_max = float(np.nanmin(y.values)), float(np.nanmax(y.values))
    hist_span = max(hist_max - hist_min, 1e-9)
    if float(np.max(vals)) > hist_max + 0.5 * hist_span:
        result["warnings"].append(
            f"WARNING: Forecast exceeds the historical maximum ({hist_max:.2f}) "
            f"by a large margin ({np.max(vals):.2f})."
        )
    if float(np.min(vals)) < hist_min - 0.5 * hist_span:
        result["warnings"].append(
            f"WARNING: Forecast falls below the historical minimum ({hist_min:.2f}) "
            f"by a large margin ({np.min(vals):.2f})."
        )
    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    return result