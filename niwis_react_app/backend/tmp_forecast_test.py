from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
print('Loading dataset...')
r = client.post('/provinces/kwa-zulu-natal/load')
print('load status', r.status_code)
data = r.json()
print('keys:', list(data.keys()))
dataset_id = data['dataset_id']
index_col = data['index_column']
col = data['dataset_summary']['numeric_columns'][0]
print('dataset_id', dataset_id, 'index', index_col, 'col', col)
print('Calling /forecast...')
r2 = client.post('/forecast', json={
    'dataset_id': dataset_id,
    'date_column': index_col,
    'target_column': col,
    'forecast_steps': 365,
    'model_type':'auto'
})
print('status', r2.status_code)
try:
    res = r2.json()
    print('keys:', list(res.keys()))
    print('model_type', res.get('model_type'))
    print('forecast_steps', res.get('forecast_steps'))
    print('forecast_values length', len(res.get('forecast_values', [])))
except Exception as e:
    print('Error parsing JSON:', e)
    print(r2.text)
