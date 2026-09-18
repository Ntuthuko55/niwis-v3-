"""Test individual model speeds on KZN data."""
from app.main import app, DATASETS
from fastapi.testclient import TestClient
import time

client = TestClient(app)
r = client.post('/provinces/kwa-zulu-natal/load')
data = r.json()
dataset_id = data['dataset_id']
df = DATASETS[dataset_id]['df']
col = data['dataset_summary']['numeric_columns'][0]

from app.forecasting.kzn_pipeline import _to_series, _chronological_split
y = _to_series(df, data['index_column'], col)
train, test = _chronological_split(y, 365)
actual = test.values.astype(float)
print(f"Train: {len(train)}, Test: {len(test)}")

models = {
    "Naive": lambda t, h: __import__('app.forecasting.kzn_pipeline', fromlist=['naive_forecast']).naive_forecast(t, h),
    "SeasonalNaive": lambda t, h: __import__('app.forecasting.kzn_pipeline', fromlist=['seasonal_naive']).seasonal_naive(t, h),
    "AR": lambda t, h: __import__('app.forecasting.kzn_pipeline', fromlist=['ar_forecast']).ar_forecast(t, h),
    "ARIMA": lambda t, h: __import__('app.forecasting.kzn_pipeline', fromlist=['arima_forecast']).arima_forecast(t, h),
    "SARIMA": lambda t, h: __import__('app.forecasting.kzn_pipeline', fromlist=['sarima_forecast']).sarima_forecast(t, h, seasonal_period=365),
}

for name, fn in models.items():
    start = time.time()
    try:
        pred = fn(train, 365)
        mae = __import__('numpy').mean(__import__('numpy').abs(actual - pred))
        print(f"{name}: OK in {time.time()-start:.1f}s, MAE={mae:.3f}")
    except Exception as e:
        print(f"{name}: FAIL in {time.time()-start:.1f}s: {e}")
