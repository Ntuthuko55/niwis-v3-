"""Test Prophet speed with timeout."""
import signal
import time
import pandas as pd
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

print("Testing Prophet...")
start = time.time()
try:
    from prophet import Prophet
    dfa = pd.DataFrame({"ds": train.index, "y": train.values.astype(float)})
    m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    m.fit(dfa)
    future = m.make_future_dataframe(periods=365, freq="D", include_history=False)
    fc = m.predict(future)
    print(f"Prophet done in {time.time()-start:.1f}s")
except Exception as e:
    print(f"Prophet FAIL in {time.time()-start:.1f}s: {str(e)[:200]}")
