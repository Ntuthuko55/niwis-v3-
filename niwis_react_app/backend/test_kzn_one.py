"""Test individual model speeds on KZN data - ONE AT A TIME."""
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

# Test just Naive first
from app.forecasting.kzn_pipeline import naive_forecast
start = time.time()
pred = naive_forecast(train, 365)
print(f"Naive: {time.time()-start:.3f}s")

# Test SeasonalNaive
from app.forecasting.kzn_pipeline import seasonal_naive
start = time.time()
pred = seasonal_naive(train, 365)
print(f"SeasonalNaive: {time.time()-start:.3f}s")

# Test AR
from app.forecasting.kzn_pipeline import ar_forecast
start = time.time()
pred = ar_forecast(train, 365)
print(f"AR: {time.time()-start:.3f}s")
