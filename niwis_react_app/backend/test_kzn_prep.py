"""Test just the KZN preprocessing."""
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
print(f"Column: {col}")

from app.forecasting.kzn_pipeline import _to_series
start = time.time()
y = _to_series(df, data['index_column'], col)
print(f"Preprocessing done in {time.time() - start:.1f}s")
print(f"Series length: {len(y)}")
print(f"First 3 values: {y.head(3).tolist()}")
print(f"Last 3 values: {y.tail(3).tolist()}")
