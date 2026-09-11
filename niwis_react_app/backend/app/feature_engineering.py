import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple


def _infer_date_column(df: pd.DataFrame) -> Optional[str]:
    candidates = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            candidates.append(col)
            continue
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            parsed = pd.to_datetime(df[col], errors='coerce')
            if parsed.notna().sum() >= len(df) * 0.8:
                candidates.append(col)
    return candidates[0] if candidates else None


def _season_from_month(month: int) -> str:
    if month in {12, 1, 2}:
        return 'Summer'
    if month in {3, 4, 5}:
        return 'Autumn'
    if month in {6, 7, 8}:
        return 'Winter'
    return 'Spring'


def _normalize_minmax(series: pd.Series) -> pd.Series:
    min_val = series.min()
    max_val = series.max()
    if pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
        return series.fillna(0)
    return (series - min_val) / (max_val - min_val)


def _standardize(series: pd.Series) -> pd.Series:
    mean = series.mean()
    std = series.std()
    if pd.isna(mean) or pd.isna(std) or std == 0:
        return series.fillna(0)
    return (series - mean) / std


class FeatureEngineer:
    def __init__(self, df: pd.DataFrame, date_column: Optional[str] = None):
        self.df = df.copy()
        self.date_column = date_column or _infer_date_column(self.df)
        if self.date_column is None:
            raise ValueError('No date column could be inferred. Please provide a date_column.')
        if self.date_column not in self.df.columns:
            raise ValueError(f"Date column '{self.date_column}' not found.")

        self.df[self.date_column] = pd.to_datetime(self.df[self.date_column], errors='coerce')
        if self.df[self.date_column].isna().any():
            raise ValueError(f"Date column '{self.date_column}' contains invalid dates.")

        self.df = self.df.sort_values(self.date_column).reset_index(drop=True)
        self.df.set_index(self.date_column, inplace=True)

    def time_features(self) -> pd.DataFrame:
        df = self.df.copy()
        ts = df.index
        features = pd.DataFrame(index=ts)
        features['year'] = ts.year
        features['month'] = ts.month
        features['week_of_year'] = ts.isocalendar().week.astype(int)
        features['quarter'] = ts.quarter
        features['day'] = ts.day
        features['day_of_week'] = ts.dayofweek
        features['is_weekend'] = ts.dayofweek.isin([5, 6]).astype(int)
        features['season'] = ts.month.map(_season_from_month)
        return features

    def lag_features(self, columns: Optional[List[str]] = None, lags: Optional[List[int]] = None) -> pd.DataFrame:
        if columns is None:
            columns = [col for col in self.df.select_dtypes(include=[np.number]).columns]
        if lags is None:
            lags = [1, 2, 3]

        features = pd.DataFrame(index=self.df.index)
        for col in columns:
            for lag in lags:
                features[f'{col}_lag_{lag}'] = self.df[col].shift(lag)
        return features

    def rolling_features(self, columns: Optional[List[str]] = None, windows: Optional[List[int]] = None) -> pd.DataFrame:
        if columns is None:
            columns = [col for col in self.df.select_dtypes(include=[np.number]).columns]
        if windows is None:
            windows = [7, 14, 30]

        features = pd.DataFrame(index=self.df.index)
        for col in columns:
            for window in windows:
                series = self.df[col]
                features[f'{col}_roll_mean_{window}'] = series.rolling(window, min_periods=1).mean()
                features[f'{col}_roll_median_{window}'] = series.rolling(window, min_periods=1).median()
                features[f'{col}_roll_std_{window}'] = series.rolling(window, min_periods=1).std()
                features[f'{col}_roll_sum_{window}'] = series.rolling(window, min_periods=1).sum()
        return features

    def ema_features(self, columns: Optional[List[str]] = None, spans: Optional[List[int]] = None) -> pd.DataFrame:
        if columns is None:
            columns = [col for col in self.df.select_dtypes(include=[np.number]).columns]
        if spans is None:
            spans = [7, 14, 30]

        features = pd.DataFrame(index=self.df.index)
        for col in columns:
            for span in spans:
                features[f'{col}_ema_{span}'] = self.df[col].ewm(span=span, adjust=False).mean()
        return features

    def cumulative_features(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        if columns is None:
            columns = [col for col in self.df.select_dtypes(include=[np.number]).columns]

        features = pd.DataFrame(index=self.df.index)
        for col in columns:
            features[f'{col}_cum_sum'] = self.df[col].cumsum()
            features[f'{col}_cum_mean'] = self.df[col].expanding(min_periods=1).mean()
        return features

    def change_features(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        if columns is None:
            columns = [col for col in self.df.select_dtypes(include=[np.number]).columns]

        features = pd.DataFrame(index=self.df.index)
        for col in columns:
            series = self.df[col].ffill().bfill()
            features[f'{col}_pct_change'] = series.pct_change()
            features[f'{col}_growth_rate'] = series.pct_change().fillna(0)
            features[f'{col}_diff'] = series.diff()
            features[f'{col}_log'] = np.log1p(series.replace({0: np.nan}))
        return features

    def transform_features(self, columns: Optional[List[str]] = None, normalize: bool = True, standardize: bool = True) -> pd.DataFrame:
        if columns is None:
            columns = [col for col in self.df.select_dtypes(include=[np.number]).columns]

        features = pd.DataFrame(index=self.df.index)
        for col in columns:
            if normalize:
                features[f'{col}_minmax'] = _normalize_minmax(self.df[col])
            if standardize:
                features[f'{col}_zscore'] = _standardize(self.df[col])
        return features

    def generate_features(
        self,
        date_features: bool = True,
        lag_features: bool = True,
        rolling_features: bool = True,
        ema_features: bool = True,
        cumulative_features: bool = True,
        change_features: bool = True,
        transform_features: bool = True,
        target_columns: Optional[List[str]] = None,
        lags: Optional[List[int]] = None,
        rolling_windows: Optional[List[int]] = None,
        ema_spans: Optional[List[int]] = None,
        normalize: bool = True,
        standardize: bool = True,
    ) -> Tuple[pd.DataFrame, List[str]]:
        generated = []
        output = pd.DataFrame(index=self.df.index)

        if date_features:
            time_df = self.time_features()
            output = pd.concat([output, time_df], axis=1)
            generated.extend(time_df.columns.tolist())

        numeric_columns = target_columns or [col for col in self.df.select_dtypes(include=[np.number]).columns]

        if lag_features:
            lag_df = self.lag_features(columns=numeric_columns, lags=lags)
            output = pd.concat([output, lag_df], axis=1)
            generated.extend(lag_df.columns.tolist())

        if rolling_features:
            roll_df = self.rolling_features(columns=numeric_columns, windows=rolling_windows)
            output = pd.concat([output, roll_df], axis=1)
            generated.extend(roll_df.columns.tolist())

        if ema_features:
            ema_df = self.ema_features(columns=numeric_columns, spans=ema_spans)
            output = pd.concat([output, ema_df], axis=1)
            generated.extend(ema_df.columns.tolist())

        if cumulative_features:
            cum_df = self.cumulative_features(columns=numeric_columns)
            output = pd.concat([output, cum_df], axis=1)
            generated.extend(cum_df.columns.tolist())

        if change_features:
            change_df = self.change_features(columns=numeric_columns)
            output = pd.concat([output, change_df], axis=1)
            generated.extend(change_df.columns.tolist())

        if transform_features:
            transform_df = self.transform_features(columns=numeric_columns, normalize=normalize, standardize=standardize)
            output = pd.concat([output, transform_df], axis=1)
            generated.extend(transform_df.columns.tolist())

        return output, generated

    def summary(self, sample_rows: int = 10) -> Dict[str, Any]:
        summary = {
            'rows': len(self.df),
            'columns': len(self.df.columns),
            'start_date': str(self.df.index.min()),
            'end_date': str(self.df.index.max()),
            'duration_days': int((self.df.index.max() - self.df.index.min()).days),
            'missing_values_total': int(self.df.isna().sum().sum()),
            'missing_by_column': self.df.isna().sum().to_dict(),
            'numeric_summary': self.df.select_dtypes(include=[np.number]).describe().to_dict(),
            'date_column': self.date_column,
        }
        return summary
