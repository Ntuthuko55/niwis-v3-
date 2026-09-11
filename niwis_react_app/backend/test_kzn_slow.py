"""Test individual model speeds on KZN data - slower models."""
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

models = [
    ("ARIMA", lambda: __import__('app.forecasting.kzn_pipeline', fromlist=['arima_forecast']).arima_forecast(train, 365)),
    ("SARIMA", lambda: __import__('app.forecasting.kzn_pipeline', fromlist=['sarima_forecast']).sarima_forecast(train, 365, seasonal_period=365)),
    ("Prophet", lambda: __import__('app.forecasting.kzn_pipeline', fromlist=['prophet_forecast']).prophet_forecast(train, 365)),
    ("StateSpace", lambda: __import__('app.forecasting.kzn_pipeline', fromlist=['state_space_forecast']).state_space_forecast(train, 365)),
]

for name, fn in models:
    start = time.time()
    try:
        pred = fn()
        mae = __import__('numpy').mean(__import__('numpy').abs(actual - pred))
        print(f"{name}: {time.time()-start:.1f}s, MAE={mae:.3f}")
    except Exception as e:
        print(f"{name}: FAIL in {time.time()-start:.1f}s: {str(e)[:100]}")
