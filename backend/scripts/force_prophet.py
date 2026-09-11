import time
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = 'http://127.0.0.1:8000'

def post(path, data=None):
    url = BASE + path
    body = None
    headers = {'Content-Type': 'application/json'}
    if data is not None:
        body = json.dumps(data).encode('utf-8')
    req = Request(url, data=body, headers=headers, method='POST')
    with urlopen(req) as resp:
        return json.load(resp)

def get(path):
    url = BASE + path
    req = Request(url, method='GET')
    with urlopen(req) as resp:
        return json.load(resp)

if __name__ == '__main__':
    try:
        print('Loading dataset...')
        load = post('/provinces/northern-cape/load')
        dataset_id = load['dataset_id']
        print('Dataset id:', dataset_id)

        payload = {
            'dataset_id': dataset_id,
            'model_type': 'prophet',
            'date_column': load.get('index_column') or load.get('indexColumn'),
            'target': load['columns'][1] if len(load.get('columns', []))>1 else load['columns'][0],
            'forecast_steps': 90,
        }
        print('Starting Prophet training...')
        job = post('/models/train', payload)
        job_id = job['job_id']
        print('Job id:', job_id)

        for i in range(600):
            status = get(f'/models/jobs/{job_id}')
            print('status:', status.get('status'), 'progress:', status.get('progress'))
            if status.get('status') in ('completed', 'failed'):
                print('Final job:', json.dumps(status, indent=2))
                break
            time.sleep(2)
    except HTTPError as e:
        print('HTTP error', e.code, e.reason)
    except URLError as e:
        print('URL error', e.reason)
    except Exception as e:
        print('Error', e)
