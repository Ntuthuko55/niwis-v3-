"""Preprocessing and model runners for the NIWIS forecasting workspace."""
from __future__ import annotations

from typing import Any, Dict
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Models that expect daily observations and forecast in days.
_DAILY_PIPELINE_MODELS = frozenset({
    'auto', 'prophet', 'sarimax', 'ets', 'ml', 'state_space', 'garch',
})

# Models trained on monthly aggregates; horizon is expressed in months.
_MONTHLY_MODELS = frozenset({
    'ar', 'ma', 'arma', 'arima', 'sarima',
    'naive', 'historicaverage', 'windowaverage', 'seasonalnaive',
})


def _forecast_horizon_months(steps: int) -> int:
    """Convert UI day-based forecast range to monthly step count."""
    steps = max(1, int(steps))
    if steps <= 60:
        return steps
    return max(1, round(steps / 30.437))


def _forecast_horizon_days(steps: int) -> int:
    """Normalize forecast horizon for the daily pipeline."""
    steps = max(1, int(steps))
    if steps <= 60:
        return max(30, steps * 30)
    return steps


def prepare_training_data(df: pd.DataFrame, config: Dict[str, Any]) -> tuple[pd.DataFrame, list[str]]:
    date_column, target = config['date_column'], config['target']
    group_column = config.get('group_column') or None
    features = config.get('features') or []
    required = [date_column, target] + ([group_column] if group_column else []) + features
    missing = [name for name in required if name not in df.columns]
    if missing:
        raise ValueError(f"Columns not found: {', '.join(missing)}")

    data = df.copy()
    data[date_column] = pd.to_datetime(data[date_column], errors='coerce')
    data = data.dropna(subset=[date_column]).sort_values(([group_column] if group_column else []) + [date_column])
    numeric_cols = data.select_dtypes(include='number').columns.tolist()
    if config.get('missing_strategy') == 'group_linear_bfill_ffill' and numeric_cols:
        if group_column:
            data[numeric_cols] = data.groupby(group_column, group_keys=False)[numeric_cols].transform(
                lambda values: values.interpolate(method='linear').bfill().ffill()
            )
        else:
            data[numeric_cols] = data[numeric_cols].interpolate(method='linear').bfill().ffill()
    data = data.dropna(subset=[target])
    if len(data) < 12:
        raise ValueError('At least 12 valid observations are required to train a time-series model.')
    return data, numeric_cols


def _metrics(actual, predicted) -> Dict[str, float]:
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return {
        'mae': float(np.mean(np.abs(actual - predicted))),
        'rmse': float(np.sqrt(np.mean((actual - predicted) ** 2))),
        'mape': float(np.mean(np.abs((actual - predicted) / np.maximum(np.abs(actual), 1e-8))) * 100),
    }


def _monthly_series(data: pd.DataFrame, date_column: str, target: str) -> pd.DataFrame:
    series = data[[date_column, target]].copy()
    series[date_column] = pd.to_datetime(series[date_column], errors='coerce')
    series = series.dropna(subset=[date_column, target]).sort_values(date_column)
    if series.empty:
        return series
    monthly = (series.set_index(date_column)[target].resample('ME').mean().dropna().reset_index())
    monthly.columns = [date_column, target]
    return monthly


def _split(data: pd.DataFrame, target: str, test_size: float):
    """Chronological split — never random."""
    test_count = max(2, int(len(data) * min(max(test_size, 0.05), 0.4)))
    train, test = data.iloc[:-test_count], data.iloc[-test_count:]
    if len(train) < 8:
        raise ValueError('Not enough observations remain after the test split.')
    return train, test


def _future_dates(dates: pd.Series, steps: int) -> list[str]:
    """Continue the source time index instead of restarting at an arbitrary date."""
    last_date = pd.to_datetime(dates.iloc[-1])
    frequency = pd.infer_freq(pd.to_datetime(dates).drop_duplicates()) if len(dates) >= 3 else None
    return [value.isoformat() for value in pd.date_range(last_date, periods=steps + 1, freq=frequency or 'D')[1:]]


def _niwis_forecast(data: pd.DataFrame, config: Dict[str, Any], numeric_cols: list[str]) -> Dict[str, Any]:
    """Run the new NIWIS forecasting pipeline."""
    from app.forecasting.forecaster import forecast_time_series

    date_column = config['date_column']
    target = config['target']
    horizon = _forecast_horizon_days(int(config.get('forecast_steps', 365)))

    # Build the raw dataframe for the forecaster
    raw = data[[date_column, target]].copy()
    raw.columns = ['date', 'value']

    result = forecast_time_series(
        df=raw,
        date_column='date',
        target_column='value',
        horizon=horizon,
        validation_cutoffs=[2021, 2022, 2023, 2024],
        preferred_model=config.get('model_type'),
    )

    # Build future dates from the result
    forecast_dates = result.get('forecast_dates', [])
    forecast_values = result.get('forecast', [])
    lower = result.get('lower_bound')
    upper = result.get('upper_bound')
    history_dates = result.get('history_dates', [])
    history_values = result.get('history_values', [])

    # Out-of-sample validation metrics come from the pipeline's chronological holdout.
    vm = result.get('metrics', {}) or {}
    metrics = {
        'mae': float(vm.get('mae', 0.0) or 0.0),
        'rmse': float(vm.get('rmse', 0.0) or 0.0),
        'r_squared': float(vm.get('r_squared', 0.0) or 0.0),
        'mase': vm.get('mase'),
        'mape': 0.0,
    }

    return {
        'model_type': result.get('model', 'niwis_auto'),
        'observations': len(history_values),
        'train_observations': len(history_values) - horizon,
        'test_observations': horizon,
        'features_used': ['calendar', 'lags', 'rolling'],
        'metrics': metrics,
        'actual': [],
        'predicted': [],
        'dates': history_dates[-min(horizon, len(history_dates)):],
        'history_dates': history_dates,
        'history_values': history_values,
        'forecast_dates': forecast_dates,
        'forecast_values': forecast_values,
        'lower_bound': lower,
        'upper_bound': upper,
        'diagnostics': result.get('diagnostics', {}),
        'validation_results': result.get('validation_results', {}),
        'model_comparison': result.get('model_comparison', {}),
        'warnings': result.get('warnings', []),
        'seasonality_detected': result.get('seasonality_detected', False),
        'comparison_table': result.get('comparison_table', []),
        'forecast_table': result.get('forecast_table', []),
        'selected_model': result.get('model_label', result.get('model', 'auto')),
        'backtest_average': result.get('backtest_average', {}),
    }


def _future_projection(data: pd.DataFrame, config: Dict[str, Any], numeric_cols: list[str]) -> np.ndarray:
    """Fit the selected model on all available observations and project forward."""
    model_type = config['model_type'].lower()

    # Route every univariate model (including legacy AR/ARIMA) through the seasonal
    # pipeline so the forecast cannot collapse to the historical mean.
    if model_type in {'prophet', 'sarimax', 'ets', 'ml', 'auto',
                      'ar', 'ma', 'arma', 'arima', 'sarima', 'state_space', 'garch'}:
        result = _niwis_forecast(data, config, numeric_cols)
        return np.asarray(result['forecast_values'], dtype=float)

    target = config['target']
    steps = int(config.get('forecast_steps', 365))
    y = data[target].astype(float)
    order = tuple(config.get('order', [1, 1, 1]))
    seasonal_order = tuple(config.get('seasonal_order', [1, 0, 1, 12]))
    features = [f for f in config.get('features', []) if f != target and f in numeric_cols]

    if model_type == 'ar':
        from statsmodels.tsa.ar_model import AutoReg
        # WARNING: AutoReg with lags=1 and trend='c' produces flat forecasts
        # because it has no seasonal terms. For daily climate data, this
        # converges toward the historical mean after a few steps.
        return np.asarray(AutoReg(y, lags=max(1, order[0]), trend='c').fit().predict(len(y), len(y) + steps - 1))
    if model_type in {'ma', 'arma', 'arima'}:
        from statsmodels.tsa.arima.model import ARIMA
        fitted_order = (0, 0, max(1, order[2])) if model_type == 'ma' else (max(1, order[0]), 0, max(1, order[2])) if model_type == 'arma' else order
        # WARNING: ARIMA without seasonal_order cannot capture annual cycles.
        # Use 'sarimax' or 'prophet' for daily climate data.
        return np.asarray(ARIMA(y, order=fitted_order).fit().forecast(steps))
    if model_type in {'sarima', 'state_space'}:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        exog = data[features] if model_type == 'state_space' and features else None
        # WARNING: Default seasonal_order=(1,0,1,12) is for monthly data.
        # For daily data with annual seasonality, use sarimax with Fourier
        # exogenous features instead (handled by the new pipeline).
        fit = SARIMAX(y, exog=exog, order=order, seasonal_order=seasonal_order if model_type == 'sarima' else (0, 0, 0, 0), enforce_stationarity=False).fit(disp=False)
        return np.asarray(fit.forecast(steps, exog=None if exog is None else np.repeat(exog.iloc[[-1]].values, steps, axis=0)))
    if model_type == 'var':
        from statsmodels.tsa.api import VAR
        targets = [target] + features
        # Validate requested target/feature columns exist in the prepared DataFrame
        missing = [c for c in targets if c not in data.columns]
        if missing:
            raise ValueError(f"VAR features not found in input data: {missing}")
        if len(targets) < 2:
            raise ValueError('VAR requires the target plus at least one additional numeric feature.')
        fitted = VAR(data[targets]).fit(maxlags=max(1, order[0]))
        return fitted.forecast(data[targets].values[-fitted.k_ar:], steps)[:, 0]
    if model_type == 'varmax':
        from statsmodels.tsa.statespace.varmax import VARMAX
        targets = [target] + features
        # Validate requested target/feature columns exist in the prepared DataFrame
        missing = [c for c in targets if c not in data.columns]
        if missing:
            raise ValueError(f"VARMAX features not found in input data: {missing}")
        if len(targets) < 2:
            raise ValueError('VARMAX requires the target plus at least one additional numeric feature.')
        return np.asarray(VARMAX(data[targets], order=(max(1, order[0]), max(0, order[2])), trend='c').fit(disp=False, maxiter=100).forecast(steps).iloc[:, 0])
    if model_type == 'prophet':
        from prophet import Prophet
        model_data = data[[config['date_column'], target]].rename(columns={config['date_column']: 'ds', target: 'y'})
        fitted = Prophet().fit(model_data)
        frequency = pd.infer_freq(pd.to_datetime(data[config['date_column']]).drop_duplicates()) if len(data) >= 3 else None
        future = fitted.make_future_dataframe(periods=steps, freq=frequency or 'D', include_history=False)
        return fitted.predict(future)['yhat'].to_numpy()
    if model_type in {'lstm', 'transformer'}:
        return _train_torch_sequence(y.values, steps, model_type)
    if model_type == 'garch':
        from arch import arch_model
        diffs = y.diff().dropna()
        if len(diffs) < 10 or diffs.std() < 1e-8:
            return np.full(steps, float(y.iloc[-1]))
        try:
            fit = arch_model(diffs, vol='Garch', p=max(1, order[0]), q=max(1, order[2]), rescale=True).fit(disp='off')
            vol = np.sqrt(fit.forecast(horizon=steps).variance.iloc[-1].values)
            return np.full(steps, float(y.iloc[-1])) + vol
        except Exception:
            return np.full(steps, float(y.iloc[-1]))
    raise ValueError('Future projection is not supported for this model type.')


def train_model(df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Train a forecasting model and return results."""
    data, numeric_cols = prepare_training_data(df, config)
    model_type = config['model_type'].lower()
    target = config['target']
    date_column = config['date_column']

    # Keep daily resolution for the NIWIS daily pipeline; aggregate to monthly only
    # for classical monthly models (SARIMA, naive baselines, etc.).
    if (
        model_type in _MONTHLY_MODELS
        and len(data) >= 30
        and (pd.api.types.is_numeric_dtype(data[target]) or target in data.columns)
    ):
        monthly = _monthly_series(data, date_column, target)
        if len(monthly) >= 12:
            data = monthly
            date_column = data.columns[0]
            target = data.columns[1]

    if model_type in {'auto', 'prophet', 'sarimax', 'ets', 'ml',
                      'ar', 'ma', 'arma', 'arima', 'sarima', 'state_space', 'garch'}:
        if model_type in {'ar', 'ma', 'arma', 'arima', 'sarima'}:
            from app.forecasting.kzn_pipeline import (
                naive_forecast,
                historic_average_forecast,
                window_average_forecast,
                seasonal_naive,
                ar_forecast,
                ma_forecast,
                arma_forecast,
                arima_forecast,
                sarima_forecast,
            )

            horizon = _forecast_horizon_months(config.get('forecast_steps', 365))
            series = pd.Series(data[target].astype(float).to_numpy(), index=pd.to_datetime(data[date_column]))
            if model_type == 'ar':
                forecast_values = ar_forecast(series, horizon)
            elif model_type == 'ma':
                forecast_values = ma_forecast(series, horizon)
            elif model_type == 'arma':
                forecast_values = arma_forecast(series, horizon)
            elif model_type == 'arima':
                forecast_values = arima_forecast(series, horizon)
            elif model_type == 'sarima':
                forecast_values = sarima_forecast(series, horizon, seasonal_period=12)
            else:
                forecast_values = naive_forecast(series, horizon)

            test_points = min(12, max(2, len(series) // 5))
            train_series = series.iloc[:-test_points]
            test_series = series.iloc[-test_points:]
            if model_type == 'ar':
                holdout_pred = ar_forecast(train_series, len(test_series))
            elif model_type == 'ma':
                holdout_pred = ma_forecast(train_series, len(test_series))
            elif model_type == 'arma':
                holdout_pred = arma_forecast(train_series, len(test_series))
            elif model_type == 'arima':
                holdout_pred = arima_forecast(train_series, len(test_series))
            elif model_type == 'sarima':
                holdout_pred = sarima_forecast(train_series, len(test_series), seasonal_period=12)
            else:
                holdout_pred = naive_forecast(train_series, len(test_series))

            full_dates = pd.date_range(series.index.min(), periods=len(series), freq='ME')
            future_dates = pd.date_range(series.index.max() + pd.offsets.MonthEnd(1), periods=horizon, freq='ME')
            return {
                'model_type': model_type,
                'observations': len(series),
                'train_observations': len(train_series),
                'test_observations': len(test_series),
                'features_used': [],
                'metrics': _metrics(test_series.values, holdout_pred),
                'actual': [float(v) for v in test_series.values],
                'predicted': [float(v) for v in np.asarray(holdout_pred)],
                'dates': [value.isoformat() for value in test_series.index],
                'history_dates': [value.isoformat() for value in series.index],
                'history_values': [float(value) for value in series.values],
                'forecast_dates': [value.isoformat() for value in future_dates],
                'forecast_values': [float(value) for value in np.asarray(forecast_values)],
                'lower_bound': None,
                'upper_bound': None,
                'selected_model': model_type,
            }
        return _niwis_forecast(data, config, numeric_cols)

    if model_type in {'naive', 'historicaverage', 'windowaverage', 'seasonalnaive'}:
        from app.forecasting.kzn_pipeline import (
            naive_forecast,
            historic_average_forecast,
            window_average_forecast,
            seasonal_naive,
        )
        horizon = _forecast_horizon_months(config.get('forecast_steps', 365))
        series = pd.Series(data[target].astype(float).to_numpy(), index=pd.to_datetime(data[date_column]))
        if model_type == 'naive':
            forecast_values = naive_forecast(series, horizon)
        elif model_type == 'historicaverage':
            forecast_values = historic_average_forecast(series, horizon)
        elif model_type == 'windowaverage':
            forecast_values = window_average_forecast(series, horizon, window=12)
        else:
            forecast_values = seasonal_naive(series, horizon, seasonal_period=12)

        test_points = min(12, max(2, len(series) // 5))
        train_series = series.iloc[:-test_points]
        test_series = series.iloc[-test_points:]
        if model_type == 'naive':
            holdout_pred = naive_forecast(train_series, len(test_series))
        elif model_type == 'historicaverage':
            holdout_pred = historic_average_forecast(train_series, len(test_series))
        elif model_type == 'windowaverage':
            holdout_pred = window_average_forecast(train_series, len(test_series), window=12)
        else:
            holdout_pred = seasonal_naive(train_series, len(test_series), seasonal_period=12)

        future_dates = pd.date_range(series.index.max() + pd.offsets.MonthEnd(1), periods=horizon, freq='ME')
        return {
            'model_type': model_type,
            'observations': len(series),
            'train_observations': len(train_series),
            'test_observations': len(test_series),
            'features_used': [],
            'metrics': _metrics(test_series.values, holdout_pred),
            'actual': [float(v) for v in test_series.values],
            'predicted': [float(v) for v in np.asarray(holdout_pred)],
            'dates': [value.isoformat() for value in test_series.index],
            'history_dates': [value.isoformat() for value in series.index],
            'history_values': [float(value) for value in series.values],
            'forecast_dates': [value.isoformat() for value in future_dates],
            'forecast_values': [float(value) for value in np.asarray(forecast_values)],
            'lower_bound': None,
            'upper_bound': None,
            'selected_model': model_type,
        }

    # Legacy model path for backward compatibility
    train, test = _split(data, target, config.get('test_size', .2))
    y_train, y_test = train[target].astype(float), test[target].astype(float)
    order = tuple(config.get('order', [1, 1, 1]))
    seasonal_order = tuple(config.get('seasonal_order', [1, 0, 1, 12]))
    features = [f for f in config.get('features', []) if f != target and f in numeric_cols]

    if model_type in {'ar', 'ma', 'arma', 'arima', 'sarima', 'state_space'}:
        from statsmodels.tsa.ar_model import AutoReg
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        if model_type == 'ar':
            fit = AutoReg(y_train, lags=max(1, order[0]), trend='c').fit()
            prediction = fit.predict(len(y_train), len(y_train) + len(y_test) - 1)
        elif model_type == 'ma':
            fit = ARIMA(y_train, order=(0, 0, max(1, order[2]))).fit()
            prediction = fit.forecast(len(y_test))
        elif model_type == 'arma':
            fit = ARIMA(y_train, order=(max(1, order[0]), 0, max(1, order[2]))).fit()
            prediction = fit.forecast(len(y_test))
        elif model_type == 'sarima':
            fit = SARIMAX(y_train, order=order, seasonal_order=seasonal_order, enforce_stationarity=False).fit(disp=False)
            prediction = fit.forecast(len(y_test))
        elif model_type == 'state_space':
            exog_train = train[features] if features else None
            exog_test = test[features] if features else None
            fit = SARIMAX(y_train, exog=exog_train, order=order, seasonal_order=(0, 0, 0, 0), enforce_stationarity=False).fit(disp=False)
            prediction = fit.forecast(len(y_test), exog=exog_test)
        else:
            fit = ARIMA(y_train, order=order).fit()
            prediction = fit.forecast(len(y_test))
    elif model_type == 'var':
        from statsmodels.tsa.api import VAR
        targets = [target] + [x for x in features if x in numeric_cols]
        if len(targets) < 2:
            available_extra = [c for c in numeric_cols if c != target and c in train.columns]
            if available_extra:
                targets = [target, available_extra[0]]
            else:
                raise ValueError('VAR needs the target plus at least one additional numeric feature.')
        fit = VAR(train[targets]).fit(maxlags=max(1, min(order[0], len(train) // 10)))
        prediction = fit.forecast(train[targets].values[-fit.k_ar:], len(test))[:, 0]
    elif model_type == 'varmax':
        from statsmodels.tsa.statespace.varmax import VARMAX
        targets = [target] + [x for x in features if x in numeric_cols]
        if len(targets) < 2:
            available_extra = [c for c in numeric_cols if c != target and c in train.columns]
            if available_extra:
                targets = [target, available_extra[0]]
            else:
                raise ValueError('VARMAX needs the target plus at least one additional numeric feature.')
        fit = VARMAX(train[targets], order=(max(1, order[0]), max(0, order[2])), trend='c').fit(disp=False, maxiter=50)
        prediction = fit.forecast(len(test)).iloc[:, 0]
    elif model_type == 'garch':
        from arch import arch_model
        diffs = y_train.diff().dropna()
        if len(diffs) < 10 or diffs.std() < 1e-8:
            prediction = np.full(len(y_test), float(y_train.iloc[-1]))
        else:
            try:
                fit = arch_model(diffs, vol='Garch', p=max(1, order[0]), q=max(1, order[2]), rescale=True).fit(disp='off')
                prediction = np.repeat(float(np.sqrt(fit.forecast(horizon=1).variance.iloc[-1, 0])), len(y_test))
            except Exception:
                prediction = np.full(len(y_test), float(y_train.iloc[-1]))
    elif model_type == 'prophet':
        from prophet import Prophet
        model_data = train[[date_column, target]].rename(columns={date_column: 'ds', target: 'y'})
        fit = Prophet().fit(model_data)
        future = pd.DataFrame({'ds': test[date_column]})
        prediction = fit.predict(future)['yhat'].values
    elif model_type in {'lstm', 'transformer'}:
        prediction = _train_torch_sequence(y_train.values, len(y_test), model_type)
    else:
        raise ValueError('Unsupported model type.')

    future_values = _future_projection(data, config, numeric_cols)
    future_dates = _future_dates(data[date_column], len(future_values))
    return {
        'model_type': model_type,
        'observations': len(data),
        'train_observations': len(train),
        'test_observations': len(test),
        'features_used': features,
        'metrics': _metrics(y_test.values, prediction),
        'actual': [float(v) for v in y_test.values],
        'predicted': [float(v) for v in np.asarray(prediction)],
        'dates': [value.isoformat() for value in test[date_column]],
        'history_dates': [value.isoformat() for value in data[date_column]],
        'history_values': [float(value) for value in data[target]],
        'forecast_dates': future_dates,
        'forecast_values': [float(value) for value in future_values],
    }


def _train_torch_sequence(values, test_length: int, model_type: str):
    import torch
    from torch import nn
    values = np.asarray(values, dtype=np.float32)
    mean, std = float(values.mean()), max(float(values.std()), 1e-6)
    scaled = (values - mean) / std
    window = min(12, max(3, len(scaled) // 5))
    if len(scaled) <= window:
        return np.full(test_length, mean)
    inputs = torch.tensor([scaled[i:i + window] for i in range(len(scaled) - window)], dtype=torch.float32).unsqueeze(-1)
    labels = torch.tensor(scaled[window:], dtype=torch.float32).unsqueeze(-1)
    if model_type == 'lstm':
        class Network(nn.Module):
            def __init__(self):
                super().__init__()
                self.layer = nn.LSTM(1, 24, batch_first=True)
                self.out = nn.Linear(24, 1)
            def forward(self, x):
                return self.out(self.layer(x)[0][:, -1, :])
    else:
        class Network(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Linear(1, 24)
                self.encoder = nn.TransformerEncoder(nn.TransformerEncoderLayer(24, 4, batch_first=True), 1)
                self.out = nn.Linear(24, 1)
            def forward(self, x):
                return self.out(self.encoder(self.embed(x))[:, -1, :])
    network = Network()
    optimizer = torch.optim.Adam(network.parameters(), lr=.01)
    for _ in range(30):
        optimizer.zero_grad()
        loss = nn.MSELoss()(network(inputs), labels)
        loss.backward()
        optimizer.step()
    history = list(scaled[-window:])
    output = []
    network.eval()
    with torch.no_grad():
        for _ in range(test_length):
            x_in = torch.tensor(history[-window:], dtype=torch.float32).view(1, window, 1)
            value = float(network(x_in).item())
            output.append(value)
            history.append(value)
    return np.asarray(output) * std + mean
