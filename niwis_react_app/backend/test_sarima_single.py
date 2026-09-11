"""Test SARIMA with a single config."""
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

# Weekly subsample
wk = train.resample('W').mean().dropna()
print(f"Weekly length: {len(wk)}")

from statsmodels.tsa.statespace.sarimax import SARIMAX
start = time.time()
try:
    fit = SARIMAX(wk.values.astype(float), order=(1, 1, 1), seasonal_order=(1, 1, 1, 52),
                  enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=50)
    pred = fit.forecast(2)
    print(f"SARIMA single config: {time.time()-start:.1f}s")
except Exception as e:
    print(f"SARIMA FAIL in {time.time()-start:.1f}s: {str(e)[:200]}")
