"""Quick test of KZN pipeline speed."""
from app.main import app, DATASETS
from fastapi.testclient import TestClient
import time

client = TestClient(app)
r = client.post('/provinces/kwa-zulu-natal/load')
data = r.json()
dataset_id = data['dataset_id']
df = DATASETS[dataset_id]['df']
col = data['dataset_summary']['numeric_columns'][0]

print(f"Dataset shape: {df.shape}")
print(f"Testing individual models...")

from app.forecasting.kzn_pipeline import _to_series, _chronological_split, arima_forecast, sarima_forecast
y = _to_series(df, data['index_column'], col)
train, test = _chronological_split(y, 365)
print(f"Train: {len(train)}, Test: {len(test)}")

for name, fn in [("ARIMA", arima_forecast), ("SARIMA", sarima_forecast)]:
    start = time.time()
    try:
        pred = fn(train, 365)
        print(f"{name}: {len(pred)} steps in {time.time()-start:.1f}s, mae={__import__('numpy').mean(__import__('numpy').abs(test.values - pred)):.3f}")
    except Exception as e:
        print(f"{name}: FAILED in {time.time()-start:.1f}s: {e}")
