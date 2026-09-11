import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ensure backend/ on sys.path
from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)
print('Loading province dataset...')
r = client.post('/provinces/kwa-zulu-natal/load')
print('Load status', r.status_code)
data = r.json()
print('Dataset id:', data.get('dataset_id'))
col = data['dataset_summary']['numeric_columns'][0]
print('Index column:', data['index_column'], 'target col:', col)

config = {
    'dataset_id': data['dataset_id'],
    'model_type': 'prophet',
    'date_column': data['index_column'],
    'target': col,
    'group_column': None,
    'features': [],
    'forecast_steps': 365,
}
print('Starting training job for Prophet...')
r = client.post('/models/train', json=config)
print('Train response status:', r.status_code)
try:
    print(json.dumps(r.json(), indent=2)[:1000])
except Exception as e:
    print('Could not parse response as JSON:', e)
resp = r.json()
job_id = resp.get('job_id')
if job_id:
    import time
    print('Polling job status for', job_id)
    for _ in range(300):
        r2 = client.get(f'/models/jobs/{job_id}')
        st = r2.json()
        print('status:', st.get('status'), 'progress:', st.get('progress'))
        if st.get('status') in {'completed', 'failed'}:
            print('Final job result:', json.dumps(st, indent=2)[:2000])
            break
        time.sleep(1)
