"""Test SARIMA speed with timeout."""
import time
from app.main import app, DATASETS
from fastapi.testclient import TestClient

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

print("Testing SARIMA (seasonal_period=365)...")
start = time.time()
try:
    from app.forecasting.kzn_pipeline import sarima_forecast
    pred = sarima_forecast(train, 365, seasonal_period=365)
    print(f"SARIMA done in {time.time()-start:.1f}s")
except Exception as e:
    print(f"SARIMA FAIL in {time.time()-start:.1f}s: {str(e)[:200]}")
