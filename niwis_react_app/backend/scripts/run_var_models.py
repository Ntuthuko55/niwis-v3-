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

models = ['var', 'varmax']
features = ['daily_tmin', 'daily_tmax']

if __name__ == '__main__':
    try:
        print('Loading dataset...')
        load = post('/provinces/northern-cape/load')
        dataset_id = load['dataset_id']
        date_col = load.get('index_column') or load.get('indexColumn')
        cols = load.get('columns', [])
        print('Dataset id:', dataset_id)
        print('Available columns:', cols[:10], '...')

        results = {}
        for m in models:
            payload = {
                'dataset_id': dataset_id,
                'model_type': m,
                'date_column': date_col,
                'target': 'daily_rainfall',
                'features': [f for f in features if f in cols],
                'forecast_steps': 90,
            }
            print('\nStarting', m, 'with features', payload['features'])
            job = post('/models/train', payload)
            job_id = job.get('job_id')
            print('job id', job_id)
            status = None
            for i in range(600):
                status = get(f'/models/jobs/{job_id}')
                st = status.get('status')
                prog = status.get('progress')
                print(' ', m, 'status:', st, 'progress:', prog)
                if st in ('completed', 'failed'):
                    break
                time.sleep(1)
            results[m] = status
            print('\nFinal', m, 'status:', status.get('status'))
            if status.get('result'):
                print('Selected model:', status['result'].get('selected_model') or status['result'].get('model_type'))
                comp = status['result'].get('comparison_table')
                if comp:
                    print('Comparison entries (first 5):')
                    for row in comp[:5]:
                        print(' ', row.get('model'), 'rmse:', row.get('rmse'), 'status:', row.get('status'))
        print('\n=== SUMMARY ===')
        print(json.dumps({k: {'status': v.get('status'), 'message': v.get('message')} for k, v in results.items()}, indent=2))
    except HTTPError as e:
        print('HTTP error', e.code, e.reason)
    except URLError as e:
        print('URL error', e.reason)
    except Exception as e:
        print('Error', e)
