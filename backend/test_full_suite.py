import sys
import os
import pandas as pd
import numpy as np

from app.main import app, DATASETS
from fastapi.testclient import TestClient

def run_full_suite():
    client = TestClient(app)
    print("1. Loading Gauteng dataset...")
    r = client.post('/provinces/gauteng/load')
    assert r.status_code == 200, f"Load failed: {r.text}"
    data = r.json()
    dataset_id = data['dataset_id']
    num_cols = data['dataset_summary']['numeric_columns']
    date_col = data['index_column'] or 'date'
    target_col = 'daily_rainfall' if 'daily_rainfall' in num_cols else num_cols[0]
    print(f"   -> Loaded dataset_id={dataset_id[:8]}, date_col={date_col}, target={target_col}, cols={len(num_cols)}")

    print("\n2. Testing Dashboard Overview (/dashboard/overview)...")
    r_ov = client.post('/dashboard/overview', json={
        'dataset_id': dataset_id,
        'date_column': date_col,
        'selected_column': target_col
    })
    assert r_ov.status_code == 200, f"Overview failed: {r_ov.text}"
    ov_data = r_ov.json()
    print(f"   -> Overview OK: row_count={ov_data['summary']['row_count']}, stationarity={ov_data['stationarity']['decision']}")

    print("\n3. Testing All 10 Time Series Analyses (/analysis)...")
    analyses = [
        ('trend', {}),
        ('seasonal', {'period': 12}),
        ('cycle', {'period': 12}),
        ('decomposition', {'period': 12}),
        ('stationarity', {}),
        ('autocorrelation', {'nlags': 20}),
        ('partial_autocorrelation', {'nlags': 20}),
        ('spectral', {}),
        ('wavelet', {}),
        ('change_point', {}),
    ]

    for atype, params in analyses:
        r_an = client.post('/analysis', json={
            'dataset_id': dataset_id,
            'analysis_type': atype,
            'column': target_col,
            'params': params
        })
        assert r_an.status_code == 200, f"Analysis {atype} failed: {r_an.text}"
        print(f"   -> {atype:25s}: OK")

    print("\n4. Testing Feature Engineering (/feature-engineering/generate)...")
    r_fe = client.post('/feature-engineering/generate', json={
        'dataset_id': dataset_id,
        'date_column': date_col,
        'target_columns': [target_col],
        'include_time_features': True,
        'include_lag_features': True,
        'include_rolling_features': True,
        'lags': [1, 7, 30],
        'rolling_windows': [7, 30],
        'sample_rows': 5
    })
    assert r_fe.status_code == 200, f"Feature engineering failed: {r_fe.text}"
    fe_data = r_fe.json()
    print(f"   -> Generated {len(fe_data['generated_features'])} features: OK")

    print("\n5. Testing PDF Report Generation (/report/pdf)...")
    r_pdf = client.post('/report/pdf', json={
        'dataset_id': dataset_id,
        'analysis_type': 'trend',
        'column': target_col,
        'params': {'period': 12}
    })
    assert r_pdf.status_code == 200, f"PDF report failed: {r_pdf.text}"
    assert len(r_pdf.content) > 1000, "PDF content too small"
    print(f"   -> PDF generated ({len(r_pdf.content)} bytes): OK")

    print("\n6. Testing Key Model Types (/models/train)...")
    from app.model_training import train_model
    df = DATASETS[dataset_id]['df']
    test_models = ['auto', 'naive', 'seasonalnaive', 'ar', 'arima', 'prophet', 'lstm', 'var']
    for m in test_models:
        extra_features = [c for c in num_cols if c != target_col][:2] if m == 'var' else []
        config = {
            'model_type': m,
            'date_column': date_col,
            'target': target_col,
            'features': extra_features,
            'forecast_steps': 12,
        }
        res = train_model(df, config)
        print(f"   -> Model {m:15s}: OK (forecast_len={len(res.get('forecast_values', []))})")

    print("\n================ ALL SYSTEMS VERIFIED SUCCESSFULLY! ================\n")

if __name__ == '__main__':
    run_full_suite()
