"""Feature engineering for time series forecasting."""
from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd

from .preprocessing import calendar_features, lag_features, rolling_features


def build_feature_matrix(
    y: pd.Series,
    calendar: bool = True,
    lags: bool = True,
    rolling: bool = True,
) -> pd.DataFrame:
    """Build a feature matrix aligned with the target series.

    Returns a DataFrame with the same index as `y`.
    Rows with any NaN are dropped (first year due to lags/rolling).
    """
    feats = pd.DataFrame(index=y.index)
    if calendar:
        feats = feats.join(calendar_features(y.index), how="left")
    if lags:
        feats = feats.join(lag_features(y), how="left")
    if rolling:
        feats = feats.join(rolling_features(y), how="left")
    return feats
