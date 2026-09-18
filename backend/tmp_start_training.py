from app.main import app
from fastapi.testclient import TestClient
import time
client = TestClient(app)
print('Loading dataset...')
r = client.post('/provinces/kwa-zulu-natal/load')
print('load status', r.status_code)
data = r.json()
dataset_id = data['dataset_id']
index_col = data['index_column']
col = data['dataset_summary']['numeric_columns'][0]
print('Starting training job (Prophet)...')
resp = client.post('/models/train', json={
    'dataset_id': dataset_id,
    'model_type': 'prophet',
    'date_column': index_col,
    'target': col,
    'features': [],
    'forecast_steps': 90,
})
print('start status', resp.status_code, resp.json())
job = resp.json()
job_id = job.get('job_id')
for _ in range(30):
    r2 = client.get(f'/models/jobs/{job_id}')
    print('job:', r2.json().get('status'), 'progress:', r2.json().get('progress'), 'msg:', r2.json().get('message'))
    if r2.json().get('status') in {'completed','failed'}:
        print('final:', r2.json().get('status'))
        break
    time.sleep(2)
print('done')
