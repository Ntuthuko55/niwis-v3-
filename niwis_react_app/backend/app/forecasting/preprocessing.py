"""Time series preprocessing for climate forecasting."""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd


def prepare_series(
    df: pd.DataFrame,
    date_column: str,
    target_column: str,
    freq: str = "D",
) -> pd.Series:
    """Clean and prepare a daily climate time series for forecasting.

    Steps:
    1. Parse dates.
    2. Drop rows with missing dates.
    3. Sort chronologically.
    4. Remove duplicate dates (keep first).
    5. Reindex to a complete daily frequency, marking gaps.
    6. Interpolate missing target values linearly, then bfill/ffill edges.
    7. Return a clean Series with DatetimeIndex.
    """
    data = df.copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
    data = data.dropna(subset=[date_column])
    data = data.sort_values(date_column).drop_duplicates(subset=[date_column], keep="first")
    data = data.set_index(date_column)

    full_idx = pd.date_range(start=data.index.min(), end=data.index.max(), freq=freq)
    data = data.reindex(full_idx)
    data.index.name = date_column

    if target_column not in data.columns:
        raise ValueError(f"Target column '{target_column}' not found after reindexing.")

    y = data[target_column].copy()
    n_missing = y.isna().sum()
    if n_missing > 0:
        y = y.interpolate(method="linear").bfill().ffill()

    y.name = target_column
    return y


def detect_frequency(dates: pd.Series) -> str:
    """Infer the most likely frequency of a datetime series."""
    inferred = pd.infer_freq(dates.drop_duplicates())
    return inferred or "D"


def calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Generate calendar features for daily data with cyclical encoding."""
    day_of_year = index.dayofyear
    month = index.month
    day_of_month = index.day
    week_of_year = index.isocalendar().week.astype(float)

    feats = pd.DataFrame(
        {
            "day_of_year": day_of_year,
            "month": month,
            "day_of_month": day_of_month,
            "week_of_year": week_of_year,
            "sin_doy": np.sin(2 * np.pi * day_of_year / 365.25),
            "cos_doy": np.cos(2 * np.pi * day_of_year / 365.25),
            "sin_2doy": np.sin(4 * np.pi * day_of_year / 365.25),
            "cos_2doy": np.cos(4 * np.pi * day_of_year / 365.25),
            "sin_month": np.sin(2 * np.pi * month / 12),
            "cos_month": np.cos(2 * np.pi * month / 12),
            "trend": np.arange(len(index)),
        },
        index=index,
    )
    return feats


def lag_features(
    series: pd.Series,
    lags: list[int] = (1, 7, 14, 30, 90, 180, 365),
) -> pd.DataFrame:
    """Create lag features for the target series."""
    feats = pd.DataFrame(index=series.index)
    for lag in lags:
        if lag < len(series):
            feats[f"lag_{lag}"] = series.shift(lag)
    return feats


def rolling_features(
    series: pd.Series,
    windows: list[int] = (7, 30, 90, 180, 365),
) -> pd.DataFrame:
    """Create rolling-window statistics."""
    feats = pd.DataFrame(index=series.index)
    for w in windows:
        if w < len(series):
            feats[f"rolling_mean_{w}"] = series.rolling(window=w, min_periods=max(1, w // 2)).mean()
            feats[f"rolling_std_{w}"] = series.rolling(window=w, min_periods=max(1, w // 2)).std()
    return feats
