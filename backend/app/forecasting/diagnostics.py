"""Time-series diagnostics for daily climate data.

Produces the evidence the forecasting pipeline uses to decide whether the series is
non-stationary, carries a trend, and - crucially - how strong the ~365-day annual
cycle is. A large annual amplitude is exactly why a mean-converging AR model is
inappropriate and why we must use seasonal forecasters.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf


def run_diagnostics(y: pd.Series, freq: int = 365) -> dict[str, Any]:
    """Run a battery of diagnostics on a univariate daily time series."""
    clean = y.dropna()
    results: dict[str, Any] = {}

    # ---- Basic stats -------------------------------------------------------
    results["n_observations"] = int(len(clean))
    results["n_missing_after_impute"] = int(y.isna().sum())
    results["date_range"] = {"start": clean.index.min().isoformat(), "end": clean.index.max().isoformat()}
    results["frequency"] = "D"
    results["mean"] = float(clean.mean())
    results["std"] = float(clean.std())
    results["min"] = float(clean.min())
    results["max"] = float(clean.max())

    # ---- Stationarity tests ------------------------------------------------
    try:
        adf = adfuller(clean.dropna(), maxlag=10, regression="c")
        results["adf_test"] = {
            "statistic": float(adf[0]), "p_value": float(adf[1]), "used_lag": int(adf[2]),
            "decision": "Stationary" if adf[1] < 0.05 else "Non-stationary",
        }
    except Exception:
        pass
    try:
        kp = kpss(clean.dropna(), regression="c", nlags="auto")
        results["kpss_test"] = {
            "statistic": float(kp[0]), "p_value": float(kp[1]),
            "decision": "Stationary" if kp[1] > 0.05 else "Non-stationary",
        }
    except Exception:
        pass

    # ---- Rolling mean / std (trend + changing variance) --------------------
    for w in (30, 90, 365):
        rm = clean.rolling(window=w, min_periods=w // 2).mean()
        rs = clean.rolling(window=w, min_periods=w // 2).std()
        results[f"rolling_mean_{w}"] = {
            "start": float(rm.iloc[0]), "end": float(rm.iloc[-1]),
            "overall_drift": float(rm.iloc[-1] - rm.iloc[0]),
            "values": _safe_list(rm.tail(400)),
        }
        results[f"rolling_std_{w}"] = {"values": _safe_list(rs.tail(400))}

    # ---- Autocorrelation / partial autocorrelation -------------------------
    try:
        nlags = min(60, len(clean) // 4)
        acf_vals = acf(clean, nlags=nlags, fft=False)
        results["acf"] = {"values": _safe_list(acf_vals), "nlags": nlags, "index": list(range(nlags + 1))}
    except Exception:
        pass
    try:
        nlags = min(60, len(clean) // 4)
        pacf_vals = pacf(clean, nlags=nlags, method="ols")
        results["pacf"] = {"values": _safe_list(pacf_vals), "nlags": nlags, "index": list(range(nlags + 1))}
    except Exception:
        pass

    # ---- The annual cycle (365 / 365.25 day) -------------------------------
    doy_table = clean.groupby(clean.index.dayofyear).mean()
    if len(doy_table) >= 60:
        results["annual_seasonality"] = {
            "values": _safe_list(doy_table.values),
            "index": [int(i) for i in doy_table.index],
            "amplitude": float(doy_table.values.max() - doy_table.values.min()),
            "peak_doy": int(doy_table.idxmax()),
            "trough_doy": int(doy_table.idxmin()),
            "n_years": float(len(clean) / 365.25),
        }

    # Autocorrelation strength at the ~annual lag (365) - direct evidence.
    try:
        nc = len(clean)
        if nc > 367:
            acf_365 = float(acf(clean, nlags=366, fft=False)[365])
        else:
            acf_365 = float("nan")
        results["annual_lag_acf"] = {"lag_365": acf_365}
    except Exception:
        pass

    # ---- Weekly seasonality (lag-7 autocorrelation) ------------------------
    try:
        acf7 = float(acf(clean, nlags=14, fft=False)[7])
        results["weekly_seasonality"] = {"lag_7_acf": acf7, "weekly": bool(acf7 > 0.2)}
    except Exception:
        pass
    return _decomposition_and_trend(clean, y, results)


def _decomposition_and_trend(clean: pd.Series, y: pd.Series, results: dict[str, Any]) -> dict[str, Any]:
    """Append STL seasonal decomposition, trend, and a diagnostic note."""
    # ---- STL seasonal decomposition ----------------------------------------
    try:
        from statsmodels.tsa.seasonal import STL
        window = y.iloc[-1100:] if len(y) > 1100 else y
        stl = STL(window.dropna(), period=365, robust=True).fit()
        seasonal = stl.seasonal.values
        resid = stl.resid.values
        total_var = float(np.var(seasonal + stl.trend.values + resid))
        results["decomposition"] = {
            "period": 365,
            "method": "STL",
            "trend": _safe_list(stl.trend.values),
            "seasonal": _safe_list(seasonal),
            "resid": _safe_list(resid),
            "seasonal_strength": float(
                max(0.0, 1.0 - np.var(resid) / (total_var + 1e-12))
            ) if total_var > 0 else 0.0,
        }
    except Exception as e:  # noqa: BLE001
        results["decomposition"] = {"error": str(e)}

    # ---- Trend (linear slope over the full record) -------------------------
    try:
        x = np.arange(len(clean))
        slope = float(np.polyfit(x, clean.values, 1)[0])
        results["linear_trend"] = {"slope_per_day": slope, "slope_per_year": slope * 365.25}
    except Exception:
        pass

    results["diagnostic_notes"] = (
        "For daily climate series, test for an annual cycle around 365/365.25 days. "
        "If the ~365-lag autocorrelation or the seasonal amplitude from an STL or "
        "day-of-year decomposition is large, a seasonal model is required - a plain "
        "AR/ARIMA will otherwise converge toward the historical mean."
    )
    return results


def _safe_list(arr) -> list[float | None]:
    if arr is None:
        return []
    out = []
    for x in np.asarray(arr):
        if isinstance(x, (float, np.floating)) and not np.isfinite(x):
            out.append(None)
        else:
            out.append(float(x))
    return out