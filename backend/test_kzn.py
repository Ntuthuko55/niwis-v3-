"""Quick test of the KZN forecasting endpoint."""
from app.main import app, DATASETS
from fastapi.testclient import TestClient
import time

client = TestClient(app)

# Load KZN dataset
r = client.post('/provinces/kwa-zulu-natal/load')
data = r.json()
dataset_id = data['dataset_id']
col = data['dataset_summary']['numeric_columns'][0]
print(f"Loaded KZN: {dataset_id[:8]} | Column: {col}")

# Run KZN forecast
print("Running KZN forecast pipeline...")
start = time.time()
r2 = client.post('/kzn/forecast', json={
    'dataset_id': dataset_id,
    'date_column': data['index_column'],
    'target_column': col,
    'forecast_steps': 365,
    'preferred_model': 'auto',
    'confidence_level': 0.95,
})
elapsed = time.time() - start
print(f"Status: {r2.status_code} | Time: {elapsed:.1f}s")

if r2.status_code == 200:
    res = r2.json()
    print(f"Best model: {res['model']}")
    print(f"Forecast steps: {len(res['forecast'])}")
    print(f"Comparison models: {len(res.get('comparison_table', []))}")
    print(f"Warnings: {res.get('warnings', [])}")
    print(f"Selected explanation: {res.get('selected_explanation', '')[:200]}")
else:
    print(f"Error: {r2.text[:500]}")
