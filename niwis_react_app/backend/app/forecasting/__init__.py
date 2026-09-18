"""NIWIS Forecasting Engine.

A science-first daily-climate forecasting pipeline:

* chronological (never random) preprocessing and validation,
* explicit annual-seasonality diagnostics,
* multiple seasonal candidate models compared out-of-sample,
* walk-forward backtesting,
* seasonality-preserving 365-day forecasts with widening confidence intervals,
* automatic warning if a forecast collapses toward the historical mean.

Primary entry point: ``forecast_time_series(df, date_column, target_column, horizon)``.
"""

