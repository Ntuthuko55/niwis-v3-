import time

import pandas as pd

from app.forecasting.kzn_pipeline import sarima_forecast


def test_sarima_forecast_completes_for_daily_series():
    df = pd.read_csv(r'C:\Users\student\Desktop\New folder (2)\South_Africa_Provinces\KwaZulu_Natal.csv')
    series = pd.Series(df['daily_rainfall'].astype(float).to_numpy(), index=pd.to_datetime(df['date']))

    start = time.time()
    forecast = sarima_forecast(series, 6, seasonal_period=12)
    elapsed = time.time() - start

    assert len(forecast) == 6
    assert elapsed < 15, f'SARIMA took too long: {elapsed:.2f}s'
