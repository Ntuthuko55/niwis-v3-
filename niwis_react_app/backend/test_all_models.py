import sys
import os
import pandas as pd
import numpy as np

from app.model_training import train_model

def test_all_models():
    # Load KZN data
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'South_Africa_Provinces', 'KwaZulu_Natal.csv')
    df = pd.read_csv(csv_path)
    print(f"Loaded dataset: shape={df.shape}, columns={list(df.columns[:5])}")

    models = [
        'auto', 'naive', 'historicaverage', 'windowaverage', 'seasonalnaive',
        'ar', 'ma', 'arma', 'arima', 'sarima',
        'garch', 'state_space', 'lstm', 'transformer', 'prophet',
        'var', 'varmax'
    ]

    results = {}
    for m in models:
        print(f"\n--- Testing model: {m} ---")
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        target = 'daily_rainfall' if 'daily_rainfall' in df.columns else numeric_cols[0]
        extra_features = [c for c in numeric_cols if c != target][:2] if m in {'var', 'varmax'} else []
        
        config = {
            'model_type': m,
            'date_column': 'date',
            'target': target,
            'features': extra_features,
            'forecast_steps': 365,
        }
        try:
            res = train_model(df, config)
            print(f"SUCCESS: {m} -> model_type={res.get('model_type')}, forecast_len={len(res.get('forecast_values', []))}, metrics={res.get('metrics')}")
            results[m] = "OK"
        except Exception as e:
            print(f"FAILED: {m} -> {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results[m] = f"FAILED: {e}"

    print("\n================ SUMMARY ================")
    for m, status in results.items():
        print(f"{m:20s}: {status}")

if __name__ == '__main__':
    test_all_models()
