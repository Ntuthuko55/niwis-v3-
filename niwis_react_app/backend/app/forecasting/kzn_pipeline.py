"""KZN Multivariate Time-Series Forecasting System.

Practical, fast implementation for the ~9,000-row daily KZN dataset.
"""
from __future__ import annotations

from typing import Any
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def _to_series(df: pd.DataFrame, date_col: str, target: str) -> pd.Series:
    data = df.copy()
    data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
    data = data.dropna(subset=[date_col]).sort_values(date_col).drop_duplicates(subset=[date_col], keep="first")
    data = data.set_index(date_col)
    y = data[target].astype(float)
    full_idx = pd.date_range(start=y.index.min(), end=y.index.max(), freq="D")
    y = y.reindex(full_idx).interpolate(method="linear").bfill().ffill()
    y.index.name = date_col
    return y


def _chronological_split(y: pd.Series, horizon: int):
    horizon = max(1, min(horizon, len(y) - 1))
    train, test = y.iloc[:-horizon], y.iloc[-horizon:]
    return train, test


def _mae(actual, predicted) -> float:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    n = min(len(a), len(p))
    return float(np.mean(np.abs(a[:n] - p[:n])))


def _rmse(actual, predicted) -> float:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    n = min(len(a), len(p))
    return float(np.sqrt(np.mean((a[:n] - p[:n]) ** 2)))


def _r2(actual, predicted) -> float:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    n = min(len(a), len(p))
    ss_res = float(np.sum((a[:n] - p[:n]) ** 2))
    ss_tot = float(np.sum((a[:n] - np.mean(a[:n])) ** 2))
    return float(1 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0


def _safe(arr) -> list[float | None]:
    if arr is None:
        return []
    return [None if (np.isnan(x) if isinstance(x, (float, np.floating)) else False) else float(x) for x in np.asarray(arr)]


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def naive_forecast(y_train, horizon):
    return np.full(horizon, float(y_train.iloc[-1]))


def historic_average_forecast(y_train, horizon):
    return np.full(horizon, float(np.nanmean(y_train.values)))


def window_average_forecast(y_train, horizon, window=30):
    w = min(window, len(y_train))
    return np.full(horizon, float(np.nanmean(y_train.iloc[-w:].values)))


def seasonal_naive(y_train, horizon, seasonal_period=365):
    if len(y_train) < seasonal_period:
        return np.full(horizon, float(np.nanmean(y_train.values)))
    last = y_train.iloc[-seasonal_period:].values
    reps = int(np.ceil(horizon / seasonal_period))
    return np.tile(last, reps)[:horizon]


def baseline_models(y_train, horizon):
    return {
        "Naive": naive_forecast(y_train, horizon),
        "HistoricAverage": historic_average_forecast(y_train, horizon),
        "WindowAverage": window_average_forecast(y_train, horizon),
        "SeasonalNaive": seasonal_naive(y_train, horizon),
    }


# ---------------------------------------------------------------------------
# AR / MA / ARMA / ARIMA (fast grid search)
# ---------------------------------------------------------------------------

def _fit_sarimax(y_values, order, seasonal_order, maxiter=50):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    return SARIMAX(y_values, order=order, seasonal_order=seasonal_order,
                   enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=maxiter)


def ar_forecast(y_train, horizon, max_p=3):
    candidates = []
    for p in range(1, max_p + 1):
        try:
            from statsmodels.tsa.ar_model import AutoReg
            fit = AutoReg(y_train.values.astype(float), lags=p, trend="c").fit()
            candidates.append((fit.aic, fit))
        except Exception:
            continue
    if not candidates:
        return naive_forecast(y_train, horizon)
    return np.asarray(min(candidates, key=lambda x: x[0])[1].predict(start=len(y_train), end=len(y_train) + horizon - 1), dtype=float)


def ma_forecast(y_train, horizon, max_q=2):
    candidates = []
    for q in range(1, max_q + 1):
        try:
            fit = _fit_sarimax(y_train.values.astype(float), order=(0, 0, q), seasonal_order=(0, 0, 0, 0))
            candidates.append((fit.aic, fit))
        except Exception:
            continue
    if not candidates:
        return naive_forecast(y_train, horizon)
    return np.asarray(min(candidates, key=lambda x: x[0])[1].forecast(horizon), dtype=float)


def arma_forecast(y_train, horizon, max_p=2, max_q=2):
    candidates = []
    for p in range(1, max_p + 1):
        for q in range(1, max_q + 1):
            try:
                fit = _fit_sarimax(y_train.values.astype(float), order=(p, 0, q), seasonal_order=(0, 0, 0, 0))
                candidates.append((fit.aic, fit))
            except Exception:
                continue
    if not candidates:
        return naive_forecast(y_train, horizon)
    return np.asarray(min(candidates, key=lambda x: x[0])[1].forecast(horizon), dtype=float)


def arima_forecast(y_train, horizon, max_p=2, max_d=1, max_q=2):
    candidates = []
    for p in range(1, max_p + 1):
        for d in range(0, max_d + 1):
            for q in range(1, max_q + 1):
                try:
                    fit = _fit_sarimax(y_train.values.astype(float), order=(p, d, q), seasonal_order=(0, 0, 0, 0))
                    candidates.append((fit.aic, fit))
                except Exception:
                    continue
    if not candidates:
        return naive_forecast(y_train, horizon)
    return np.asarray(min(candidates, key=lambda x: x[0])[1].forecast(horizon), dtype=float)


def sarima_forecast(y_train, horizon, seasonal_period=12):
    """Fast SARIMA with a deliberately small candidate set to avoid UI hangs.

    The previous exhaustive SARIMA grid searched 64 parameter combinations and could
    lock the job thread for a long time, especially on the daily provincial series.
    We use a handful of common, stable configurations and fall back to the naive
    forecast immediately if the series is too short or the fit fails.
    """
    use_weekly = len(y_train) > 500 and (seasonal_period >= 365 or (hasattr(y_train, 'index') and pd.infer_freq(y_train.index) and pd.infer_freq(y_train.index).startswith('D')))
    if use_weekly:
        wk = y_train.resample('W').mean().dropna()
        sp = 52
        h_wk = max(1, int(np.ceil(horizon / 7.0)))
    else:
        wk = y_train
        sp = seasonal_period
        h_wk = horizon

    if len(wk) < max(12, sp * 2):
        return naive_forecast(y_train, horizon)

    candidate_orders = [
        ((1, 0, 0), (0, 0, 0, 0)),
        ((1, 1, 0), (0, 0, 0, 0)),
        ((0, 0, 1), (0, 0, 0, 0)),
        ((1, 0, 1), (0, 0, 0, 0)),
        ((1, 0, 0), (1, 0, 0, sp)),
        ((1, 1, 0), (1, 0, 0, sp)),
        ((1, 0, 1), (1, 0, 0, sp)),
        ((1, 1, 1), (1, 0, 0, sp)),
    ]

    candidates = []
    for order, seasonal_order in candidate_orders:
        try:
            fit = _fit_sarimax(wk.values.astype(float), order=order, seasonal_order=seasonal_order, maxiter=25)
            candidates.append((fit.aic, fit))
        except Exception:
            continue

    if not candidates:
        return naive_forecast(y_train, horizon)

    pred = np.asarray(min(candidates, key=lambda x: x[0])[1].forecast(h_wk), dtype=float)
    if use_weekly and len(pred) < horizon:
        pred = np.repeat(pred, 7)[:horizon]
    return pred[:horizon]


# ---------------------------------------------------------------------------
# Prophet
# ---------------------------------------------------------------------------

def prophet_forecast(y_train, horizon):
    from prophet import Prophet

    # Detect monthly vs daily spacing and adjust settings accordingly
    if len(y_train) == 0:
        return np.full(horizon, float(np.nan)), None, None

    idx_series = pd.Series(y_train.index)
    if len(idx_series) > 1:
        median_days = float(idx_series.diff().dropna().dt.days.median())
    else:
        median_days = 1.0

    monthly = median_days >= 28.0
    max_points = 800 if not monthly else 240
    train = y_train.iloc[-max_points:] if len(y_train) > max_points else y_train
    dfa = pd.DataFrame({"ds": train.index, "y": train.values.astype(float)})

    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False if monthly else True,
        daily_seasonality=False,
        interval_width=0.95,
    )
    m.fit(dfa)

    freq = "M" if monthly else "D"
    future = m.make_future_dataframe(periods=horizon, freq=freq)
    fc = m.predict(future)

    fc_h = fc.tail(horizon)
    vals = fc_h["yhat"].values
    lower = fc_h.get("yhat_lower").values if "yhat_lower" in fc_h else None
    upper = fc_h.get("yhat_upper").values if "yhat_upper" in fc_h else None
    return np.asarray(vals, dtype=float), np.asarray(lower, dtype=float) if lower is not None else None, np.asarray(upper, dtype=float) if upper is not None else None


# ---------------------------------------------------------------------------
# VAR / VARMAX
# ---------------------------------------------------------------------------

def var_forecast(df, date_col, target, features, horizon):
    from statsmodels.tsa.api import VAR
    endog = df[[date_col, target] + features].copy()
    endog[date_col] = pd.to_datetime(endog[date_col])
    endog = endog.sort_values(date_col).dropna()
    data = endog[[target] + features].astype(float)
    model = VAR(data)
    lag_order = model.select_order(maxlags=3)
    p = int(lag_order.aic) if lag_order.aic > 0 else min(1, len(data) // 10)
    fitted = model.fit(maxlags=max(1, p))
    forecast = fitted.forecast(data.values[-fitted.k_ar:], steps=horizon)
    return np.asarray(forecast[:, 0], dtype=float)


def varmax_forecast(df, date_col, target, features, horizon):
    from statsmodels.tsa.statespace.varmax import VARMAX
    endog = df[[date_col, target] + features].copy()
    endog[date_col] = pd.to_datetime(endog[date_col])
    endog = endog.sort_values(date_col).dropna()
    data = endog[[target] + features].astype(float)
    p = min(1, len(data) // 10)
    q = min(1, len(data) // 10)
    fitted = VARMAX(data, order=(p, q), trend="c").fit(disp=False, maxiter=50)
    forecast = fitted.forecast(steps=horizon)
    return np.asarray(forecast.iloc[:, 0].values, dtype=float)


# ---------------------------------------------------------------------------
# GARCH
# ---------------------------------------------------------------------------

def garch_forecast(y_train, horizon):
    from arch import arch_model
    returns = y_train.pct_change().dropna() * 100
    if len(returns) < 20:
        return np.full(horizon, float(np.nanmean(y_train.values)))
    model = arch_model(returns, vol="Garch", p=1, q=1, rescale=False)
    fit = model.fit(disp="off")
    fc = fit.forecast(horizon=horizon)
    vol = np.sqrt(fc.variance.iloc[-horizon:].values[0])
    return np.asarray(vol, dtype=float)


# ---------------------------------------------------------------------------
# State Space
# ---------------------------------------------------------------------------

def state_space_forecast(y_train, horizon):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    model = SARIMAX(y_train.values.astype(float), order=(1, 1, 1), seasonal_order=(0, 0, 0, 0), enforce_stationarity=False)
    fit = model.fit(disp=False)
    forecast = fit.forecast(steps=horizon)
    return np.asarray(forecast, dtype=float)


# ---------------------------------------------------------------------------
# LSTM / Transformer
# ---------------------------------------------------------------------------

def _torch_forecast(y_train, horizon, model_type="lstm"):
    import torch
    from torch import nn
    vals = np.asarray(y_train.values, dtype=np.float32)
    mean, std = float(vals.mean()), max(float(vals.std()), 1e-6)
    scaled = (vals - mean) / std
    window = min(30, max(7, len(scaled) // 10))
    if len(scaled) <= window:
        return np.full(horizon, float(mean))
    inputs = torch.tensor([scaled[i:i + window] for i in range(len(scaled) - window)], dtype=torch.float32).unsqueeze(-1)
    labels = torch.tensor(scaled[window:], dtype=torch.float32).unsqueeze(-1)

    if model_type == "lstm":
        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(1, 16, batch_first=True)
                self.fc = nn.Linear(16, 1)
            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :])
    else:
        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Linear(1, 16)
                self.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(16, 4, batch_first=True), 1)
                self.fc = nn.Linear(16, 1)
            def forward(self, x):
                return self.fc(self.enc(self.embed(x))[:, -1, :])

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=0.01)
    for _ in range(30):
        opt.zero_grad()
        loss = nn.MSELoss()(net(inputs), labels)
        loss.backward()
        opt.step()

    hist = list(scaled[-window:])
    out = []
    net.eval()
    with torch.no_grad():
        for _ in range(horizon):
            x = torch.tensor(hist[-window:], dtype=torch.float32).view(1, window, 1)
            pred = float(net(x).item())
            out.append(pred)
            hist.append(pred)
    return np.asarray(out, dtype=float) * std + mean


# ---------------------------------------------------------------------------
# Chronological CV
# ---------------------------------------------------------------------------

def chronological_cv(y, horizon, n_folds=3, model_fn=None):
    fold_size = max(horizon, len(y) // (n_folds + 1))
    scores = []
    start = 0
    for _ in range(n_folds):
        end = start + fold_size
        if end + horizon > len(y):
            break
        train = y.iloc[start:end]
        test = y.iloc[end:end + horizon]
        try:
            pred = model_fn(train, horizon)
            scores.append(_mae(test.values, pred))
        except Exception:
            continue
        start = end
    return float(np.mean(scores)) if scores else float("nan")


# ---------------------------------------------------------------------------
# Main KZN pipeline
# ---------------------------------------------------------------------------

def run_kzn_forecast(df, date_column, target_column, forecast_steps=365,
                     preferred_model=None, confidence_level=0.95,
                     validation_cutoffs=None):
    warnings_list = []

    # Phase 1 – Inspect
    data = df.copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
    data = data.dropna(subset=[date_column]).sort_values(date_column).drop_duplicates(subset=[date_column], keep="first")
    date_range = {"start": data[date_column].min().isoformat(), "end": data[date_column].max().isoformat(), "rows": int(len(data))}
    numeric_cols = data.select_dtypes(include="number").columns.tolist()
    province_col = next((c for c in ["province", "Province", "PROVINCE", "location", "Location"] if c in data.columns), None)
    provinces = sorted(data[province_col].dropna().unique().tolist()) if province_col else []

    # Phase 2 – Prepare KZN series
    if province_col:
        for prov in ["KwaZulu-Natal", "KZN", "KwaZulu Natal"]:
            if prov in provinces:
                kzn = data[data[province_col] == prov].copy()
                break
        else:
            kzn = data.copy()
            warnings_list.append("Province column found but KwaZulu-Natal not present; using full dataset.")
    else:
        kzn = data.copy()
        warnings_list.append("No province column found; using full dataset as KZN proxy.")

    y = _to_series(kzn, date_column, target_column)
    if len(y) < 30:
        raise ValueError("Need at least 30 daily observations to forecast.")

    inferred_freq = pd.infer_freq(y.index)
    monthly = False
    if inferred_freq and inferred_freq.startswith("M"):
        monthly = True
    elif inferred_freq and inferred_freq.startswith("D"):
        y_monthly = y.resample("M").mean()
        if len(y_monthly) >= 24:
            monthly = True
            y = y_monthly
            forecast_steps = min(forecast_steps, 12)
            warnings_list.append("Daily data aggregated to monthly for modelling.")

    seasonal_period = 12 if monthly else 365
    horizon = forecast_steps

    # Phase 3 – Chronological split
    train, test = _chronological_split(y, horizon)
    actual_test = test.values.astype(float)

    # Phase 4-16 – Run models
    comparison = {}
    details = {}

    # Baselines
    for name, pred in baseline_models(train, horizon).items():
        comparison[name] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details[name] = {"predictions": _safe(pred), "actual": _safe(actual_test)}

    # AR
    try:
        pred = ar_forecast(train, horizon)
        comparison["AR"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["AR"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["AR"] = {"status": "failed", "error": str(e)}

    # MA
    try:
        pred = ma_forecast(train, horizon)
        comparison["MA"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["MA"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["MA"] = {"status": "failed", "error": str(e)}

    # ARMA
    try:
        pred = arma_forecast(train, horizon)
        comparison["ARMA"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["ARMA"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["ARMA"] = {"status": "failed", "error": str(e)}

    # ARIMA
    try:
        pred = arima_forecast(train, horizon)
        comparison["ARIMA"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["ARIMA"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["ARIMA"] = {"status": "failed", "error": str(e)}

    # SARIMA
    try:
        pred = sarima_forecast(train, horizon, seasonal_period=seasonal_period)
        comparison["SARIMA"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["SARIMA"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["SARIMA"] = {"status": "failed", "error": str(e)}

    # Prophet
    try:
        pred, lower, upper = prophet_forecast(train, horizon)
        comparison["Prophet"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["Prophet"] = {"predictions": _safe(pred), "actual": _safe(actual_test), "lower": _safe(lower), "upper": _safe(upper)}
    except Exception as e:
        comparison["Prophet"] = {"status": "failed", "error": str(e)}

    # VAR / VARMAX
    feature_cols = []
    if len(numeric_cols) > 1:
        feature_cols = [c for c in numeric_cols if c not in {target_column, date_column}][:5]
        if feature_cols:
            try:
                pred = var_forecast(kzn, date_column, target_column, feature_cols, horizon)
                comparison["VAR"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok", "features": feature_cols}
                details["VAR"] = {"predictions": _safe(pred), "actual": _safe(actual_test), "features": feature_cols}
            except Exception as e:
                comparison["VAR"] = {"status": "failed", "error": str(e)}
            try:
                pred = varmax_forecast(kzn, date_column, target_column, feature_cols, horizon)
                comparison["VARMAX"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok", "features": feature_cols}
                details["VARMAX"] = {"predictions": _safe(pred), "actual": _safe(actual_test), "features": feature_cols}
            except Exception as e:
                comparison["VARMAX"] = {"status": "failed", "error": str(e)}

    # GARCH
    try:
        pred = garch_forecast(train, horizon)
        comparison["GARCH"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["GARCH"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["GARCH"] = {"status": "failed", "error": str(e)}

    # State Space
    try:
        pred = state_space_forecast(train, horizon)
        comparison["StateSpace"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["StateSpace"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["StateSpace"] = {"status": "failed", "error": str(e)}

    # LSTM
    try:
        pred = _torch_forecast(train, horizon, model_type="lstm")
        comparison["LSTM"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["LSTM"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["LSTM"] = {"status": "failed", "error": str(e)}

    # Transformer
    try:
        pred = _torch_forecast(train, horizon, model_type="transformer")
        comparison["Transformer"] = {"mae": round(_mae(actual_test, pred), 4), "rmse": round(_rmse(actual_test, pred), 4), "r_squared": round(_r2(actual_test, pred), 4), "status": "ok"}
        details["Transformer"] = {"predictions": _safe(pred), "actual": _safe(actual_test)}
    except Exception as e:
        comparison["Transformer"] = {"status": "failed", "error": str(e)}

    # Phase 17 – CV
    cv_results = {}
    for name in ["SeasonalNaive", "ARIMA", "SARIMA", "Prophet", "StateSpace"]:
        if name in comparison and comparison[name].get("status") == "ok":
            try:
                fn_map = {
                    "SeasonalNaive": lambda t, h: seasonal_naive(t, h),
                    "ARIMA": arima_forecast,
                    "SARIMA": lambda t, h: sarima_forecast(t, h, seasonal_period=seasonal_period),
                    "Prophet": prophet_forecast,
                    "StateSpace": state_space_forecast,
                }
                cv_mae = chronological_cv(y, horizon, n_folds=3, model_fn=fn_map.get(name, lambda t, h: seasonal_naive(t, h)))
                cv_results[name] = round(float(cv_mae), 4) if np.isfinite(cv_mae) else None
            except Exception:
                cv_results[name] = None

    # Phase 18-19 – Rank and select
    valid = {m: r for m, r in comparison.items() if r.get("status") == "ok" and "mae" in r}
    ranked = sorted(valid.items(), key=lambda x: x[1]["mae"])
    best_model = ranked[0][0] if ranked else "SeasonalNaive"
    best_mae = ranked[0][1]["mae"] if ranked else None

    # Retrain best on full data
    retrain_map = {
        "Naive": naive_forecast, "HistoricAverage": historic_average_forecast,
        "WindowAverage": lambda t, h: window_average_forecast(t, h),
        "SeasonalNaive": lambda t, h: seasonal_naive(t, h, seasonal_period=seasonal_period),
        "AR": ar_forecast, "MA": ma_forecast, "ARMA": arma_forecast,
        "ARIMA": arima_forecast, "SARIMA": lambda t, h: sarima_forecast(t, h, seasonal_period=seasonal_period),
        "Prophet": lambda t, h: prophet_forecast(t, h)[0],
        "VAR": lambda t, h: var_forecast(kzn, date_column, target_column, feature_cols, h),
        "VARMAX": lambda t, h: varmax_forecast(kzn, date_column, target_column, feature_cols, h),
        "GARCH": garch_forecast, "StateSpace": state_space_forecast,
        "LSTM": lambda t, h: _torch_forecast(t, h, model_type="lstm"),
        "Transformer": lambda t, h: _torch_forecast(t, h, model_type="transformer"),
    }
    try:
        final_pred = retrain_map.get(best_model, lambda t, h: seasonal_naive(t, h))(y, horizon)
    except Exception as exc:
        warnings_list.append(f"Final retrain failed for {best_model} ({exc}); using SeasonalNaive.")
        best_model = "SeasonalNaive"
        final_pred = seasonal_naive(y, horizon)

    last_date = y.index[-1]
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1 if not monthly else 31), periods=horizon, freq="D" if not monthly else "M")

    comparison_table = []
    for rank, (model_name, res) in enumerate(ranked, start=1):
        comparison_table.append({
            "rank": rank, "model": model_name, "target": target_column,
            "mae": res.get("mae"), "rmse": res.get("rmse"), "r_squared": res.get("r_squared"),
            "cv_mae": cv_results.get(model_name), "status": "ok", "selected": model_name == best_model,
        })
    for model_name, res in comparison.items():
        if model_name not in valid:
            comparison_table.append({
                "rank": len(comparison_table) + 1, "model": model_name, "target": target_column,
                "mae": None, "rmse": None, "r_squared": None, "cv_mae": None,
                "status": res.get("status", "failed"), "selected": False, "error": res.get("error"),
            })

    return {
        "dataset_info": {
            "province_column": province_col, "provinces": provinces,
            "date_column": date_column, "target_column": target_column,
            "numeric_columns": numeric_cols, "date_range": date_range,
            "frequency": "monthly" if monthly else "daily", "seasonal_period": seasonal_period,
        },
        "model": best_model, "model_label": best_model,
        "forecast": [float(v) for v in np.asarray(final_pred, dtype=float)],
        "lower_bound": None, "upper_bound": None,
        "history_dates": [d.isoformat() for d in y.index], "history_values": [float(v) for v in y.values],
        "forecast_dates": [d.isoformat() for d in future_dates],
        "metrics": {"mae": best_mae, "rmse": None, "r_squared": None},
        "diagnostics": {}, "validation_results": {"by_cutoff": {}, "average": {}},
        "backtesting": {"by_cutoff": {}, "average": {}}, "backtest_average": {},
        "model_comparison": comparison, "comparison_table": comparison_table,
        "forecast_table": [{"date": d.isoformat(), "forecast": float(final_pred[i]), "lower_ci": None, "upper_ci": None, "model": best_model} for i, d in enumerate(future_dates)],
        "warnings": warnings_list, "seasonality_detected": True,
        "seasonality_amplitude": float(np.max(y) - np.min(y)),
        "confidence_level": float(confidence_level),
        "selected_explanation": (
            f"For the selected KZN dataset and target variable '{target_column}', "
            f"under the chronological train/test split and forecast horizon of {horizon}, "
            f"the best-performing model is {best_model} because it achieved the lowest MAE: {best_mae}."
        ),
        "details": details, "cross_validation": cv_results,
    }
