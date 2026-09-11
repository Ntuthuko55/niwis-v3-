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

models = ['var', 'varmax', 'state_space', 'lstm', 'transformer', 'prophet']

if __name__ == '__main__':
    try:
        print('Loading dataset...')
        load = post('/provinces/northern-cape/load')
        dataset_id = load['dataset_id']
        date_col = load.get('index_column') or load.get('indexColumn')
        # Prefer a numeric default target and a numeric feature for multivariate models
        cols = load.get('columns', [])
        # common numeric columns in province CSVs
        preferred_targets = ['daily_rainfall', 'daily_tmean', 'daily_tmax', 'monthly_rainfall']
        target = next((c for c in preferred_targets if c in cols), None)
        if target is None:
            # fallback to first non-string-like column (skip province and date)
            target = next((c for c in cols if c.lower() not in ('province', 'date')), cols[0] if cols else None)
        feature_for_multivariate = next((c for c in preferred_targets if c in cols and c != target), None)
        if feature_for_multivariate is None:
            feature_for_multivariate = target
        print('Dataset id:', dataset_id, 'date_col:', date_col, 'target:', target)

        results = {}
        for m in models:
            payload = {
                'dataset_id': dataset_id,
                'model_type': m,
                'date_column': date_col,
                'target': target,
                'forecast_steps': 90,
            }
            # provide a numeric feature for VAR/VARMAX/state_space
            if m in ('var', 'varmax', 'state_space'):
                payload['features'] = [feature_for_multivariate]
            print('\nStarting', m)
            try:
                job = post('/models/train', payload)
            except HTTPError as e:
                print('HTTP error starting', m, e.code, e.reason)
                results[m] = {'error': f'HTTP {e.code} {e.reason}'}
                continue
            except URLError as e:
                print('URL error starting', m, e.reason)
                results[m] = {'error': f'URL {e.reason}'}
                continue
            job_id = job.get('job_id')
            print('job id', job_id)
            status = None
            for i in range(300):
                try:
                    status = get(f'/models/jobs/{job_id}')
                except Exception as e:
                    print('Error fetching job status for', m, e)
                    status = {'error': str(e)}
                    break
                st = status.get('status')
                prog = status.get('progress')
                print(' ', m, 'status:', st, 'progress:', prog)
                if st in ('completed', 'failed'):
                    break
                time.sleep(1)
            results[m] = status
        print('\n=== RESULTS SUMMARY ===')
        print(json.dumps({k: (v.get('status'), v.get('message') if isinstance(v, dict) else str(v)) for k, v in results.items()}, indent=2))
    except Exception as e:
        print('Error', e)
