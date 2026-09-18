import io
import uuid
import threading
import time
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query
import numpy as np
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.middleware.wsgi import WSGIMiddleware

from app.data_processing import (
    autocorrelation,
    change_point_detection,
    cycle_analysis,
    decomposition,
    load_dataset,
    clean_dataset,
    get_columns,
    get_dataset_summary,
    get_preview,
    make_pdf_report,
    partial_autocorrelation,
    seasonal_analysis,
    spectral_analysis,
    stationarity_test,
    trend_analysis,
    wavelet_analysis,
)
from app.feature_engineering import FeatureEngineer
from app.trend_analysis import TrendAnalyzer
from app.model_training import train_model
from app.forecasting.kzn_pipeline import run_kzn_forecast
from app.schemas import (
    AnalysisRequest, AnalysisResponse, DateColumnRequest, 
    ModelTrainingRequest, PreviewRequest, PreviewResponse, 
    ReportRequest, TrainingJobResponse, UploadResponse,
    FeatureEngineeringRequest, FeatureEngineeringResponse,
    TrendAnalysisRequest, TrendAnalysisResponse, 
    ComparisonRequest, AvailableVariablesResponse,
    DashboardOverviewRequest, DashboardOverviewResponse,
    ForecastingRequest, ForecastingResponse
)
from app.spatial_flask import app as spatial_app
from app.multivariate_flask import app as multivariate_app

# FastAPI app with enhanced metadata for Swagger UI
app = FastAPI(
    title="Predictive Time Series Analysis API",
    description="Advanced time series analysis, feature engineering, trend detection, and forecasting for climate and environmental data",
    version="2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The Spatialwise Flask application is mounted inside this FastAPI server.
# It is available under /spatial-api, so only this one backend process is needed.
app.mount("/spatial-api", WSGIMiddleware(spatial_app))
app.mount("/multivariate-api", WSGIMiddleware(multivariate_app))

# Global state
DATASETS: Dict[str, dict] = {}
TRAINING_JOBS: Dict[str, dict] = {}
ANALYSIS_CACHE: Dict[str, dict] = {}  # Cache with TTL for expensive analyses

PROVINCE_FILES = {
    'eastern-cape': 'Eastern_cape.csv', 'free-state': 'Free_state.csv',
    'gauteng': 'Gauteng.csv', 'kwa-zulu-natal': 'Kwazulu_natal.csv',
    'limpopo': 'Limpopo.csv', 'mpumalanga': 'Mpumalanga.csv',
    'north-west': 'North_west.csv', 'northern-cape': 'Northern_cape.csv',
    'western-cape': 'Western_cape.csv',
}
PROVINCE_DATA_DIR = Path(__file__).resolve().parents[2] / 'South_Africa_Provinces'

def cache_analysis_result(cache_key: str, result: dict, ttl_seconds: int = 3600):
    """Store analysis result with expiration time"""
    ANALYSIS_CACHE[cache_key] = {
        'result': result,
        'timestamp': datetime.now(),
        'expires': datetime.now() + timedelta(seconds=ttl_seconds)
    }

def get_cached_result(cache_key: str):
    """Retrieve cached result if not expired"""
    if cache_key in ANALYSIS_CACHE:
        cache_entry = ANALYSIS_CACHE[cache_key]
        if datetime.now() < cache_entry['expires']:
            return cache_entry['result']
        else:
            del ANALYSIS_CACHE[cache_key]
    return None


def build_overview_cache_key(dataset_id: str, date_column: str, selected_column: str) -> str:
    """Create a stable cache key for dashboard overview requests"""
    return f"dashboard_overview:{dataset_id}:{date_column}:{selected_column}"


def generate_csv(data: list, columns: list) -> str:
    """Convert list of dicts to CSV string"""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


@app.get('/provinces')
async def list_province_datasets():
    """List the provincial climate datasets available in this installation."""
    return {'provinces': [
        {'id': province_id, 'filename': filename, 'available': (PROVINCE_DATA_DIR / filename).exists()}
        for province_id, filename in PROVINCE_FILES.items()
    ]}


@app.post('/provinces/{province_id}/load', response_model=UploadResponse)
async def load_province_dataset(province_id: str):
    """Load one bundled provincial CSV into the normal analysis workflow."""
    filename = PROVINCE_FILES.get(province_id)
    file_path = PROVINCE_DATA_DIR / filename if filename else None
    if not filename or not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail='Province dataset not found')
    try:
        content = file_path.read_bytes()
        raw_df, sheets, current_sheet = load_dataset(content, filename)
        source_summary_df = raw_df.copy()
        df, inferred_time_columns, index_column = clean_dataset(raw_df)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Unable to load provincial dataset: {exc}')
    dataset_id = str(uuid.uuid4())
    DATASETS[dataset_id] = {
        'df': df, 'file_bytes': content, 'filename': filename,
        'sheet_names': sheets, 'current_sheet': current_sheet,
        'inferred_time_columns': inferred_time_columns, 'index_column': index_column,
        'dataset_summary': get_dataset_summary(source_summary_df, inferred_time_columns),
        'province_id': province_id,
    }
    return UploadResponse(
        dataset_id=dataset_id, columns=get_columns(df), preview=get_preview(df, rows=10),
        row_count=len(df), sheet_names=sheets, current_sheet=current_sheet,
        inferred_time_columns=inferred_time_columns, index_column=index_column,
        dataset_summary=DATASETS[dataset_id]['dataset_summary'],
    )


@app.get('/provinces/series/{dataset_id}')
async def province_time_series(dataset_id: str, column: str, frequency: str = 'monthly'):
    """Return chart-ready provincial observations, aggregated for a readable long-term graph."""
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail='Dataset not found')
    dataset = DATASETS[dataset_id]
    date_column, df = dataset.get('index_column'), dataset['df']
    if not date_column or column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
        raise HTTPException(status_code=400, detail='Choose a numeric variable and a valid date column')
    series = df[[date_column, column]].dropna().copy().set_index(date_column)[column].sort_index()
    rule = {'daily': 'D', 'monthly': 'MS', 'annual': 'YS'}.get(frequency, 'MS')
    series = series.resample(rule).mean().dropna()
    return {'date_column': date_column, 'column': column, 'frequency': frequency,
            'points': [{'date': timestamp.isoformat(), 'value': float(value)} for timestamp, value in series.items()]}


@app.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(None),
):
    content = await file.read()
    try:
        df, sheets, current_sheet = load_dataset(content, file.filename, sheet_name)
        source_summary_df = df.copy()
        df, inferred_time_columns, index_column = clean_dataset(df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to parse file: {exc}")

    dataset_id = str(uuid.uuid4())
    DATASETS[dataset_id] = {
        'df': df,
        'file_bytes': content,
        'filename': file.filename,
        'sheet_names': sheets,
        'current_sheet': current_sheet,
        'inferred_time_columns': inferred_time_columns,
        'index_column': index_column,
        'dataset_summary': get_dataset_summary(source_summary_df, inferred_time_columns),
    }

    return UploadResponse(
        dataset_id=dataset_id,
        columns=get_columns(df),
        preview=get_preview(df, rows=10),
        row_count=len(df),
        sheet_names=sheets,
        current_sheet=current_sheet,
        inferred_time_columns=inferred_time_columns,
        index_column=index_column,
        dataset_summary=DATASETS[dataset_id]['dataset_summary'],
    )


@app.post("/preview", response_model=PreviewResponse)
async def preview_dataset(request: PreviewRequest):
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dataset = DATASETS[request.dataset_id]

    if request.sheet_name:
        sheet_name = request.sheet_name
        sheet_names = dataset.get('sheet_names') or []
        if sheet_name not in sheet_names:
            raise HTTPException(status_code=400, detail="Sheet not found")

        df, _, _ = load_dataset(dataset['file_bytes'], dataset['filename'], sheet_name)
        source_summary_df = df.copy()
        df, inferred_time_columns, index_column = clean_dataset(df)
        dataset.update({
            'df': df,
            'current_sheet': sheet_name,
            'inferred_time_columns': inferred_time_columns,
            'index_column': index_column,
            'dataset_summary': get_dataset_summary(source_summary_df, inferred_time_columns),
        })

    df = dataset['df']
    return PreviewResponse(
        dataset_id=request.dataset_id,
        columns=get_columns(df),
        preview=get_preview(df, rows=request.rows),
        sheet_names=dataset.get('sheet_names'),
        current_sheet=dataset.get('current_sheet'),
        inferred_time_columns=dataset.get('inferred_time_columns'),
        index_column=dataset.get('index_column'),
        dataset_summary=dataset.get('dataset_summary'),
    )


@app.post("/dataset/date-column", response_model=PreviewResponse)
async def set_date_column(request: DateColumnRequest):
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dataset = DATASETS[request.dataset_id]
    try:
        raw_df, _, _ = load_dataset(
            dataset['file_bytes'], dataset['filename'], dataset.get('current_sheet') or None
        )
        source_summary_df = raw_df.copy()
        df, inferred_time_columns, index_column = clean_dataset(raw_df, request.date_column)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    dataset.update({
        'df': df,
        'inferred_time_columns': inferred_time_columns,
        'index_column': index_column,
        'dataset_summary': get_dataset_summary(source_summary_df, inferred_time_columns),
    })
    return PreviewResponse(
        dataset_id=request.dataset_id,
        columns=get_columns(df),
        preview=get_preview(df, rows=10),
        sheet_names=dataset.get('sheet_names'),
        current_sheet=dataset.get('current_sheet'),
        inferred_time_columns=inferred_time_columns,
        index_column=index_column,
        dataset_summary=dataset.get('dataset_summary'),
    )


def _run_training_job(job_id: str, dataset_id: str, config: dict):
    job = TRAINING_JOBS[job_id]
    try:
        job.update(status='running', progress=5, message='Preparing and cleaning the time series…', started_at=time.time())

        # Start a background progress smoother that increments progress
        # while the actual training work runs. This gives the UI feedback
        # so long-running models (Prophet, LSTM, Transformer) show activity.
        stop_flag = {'stop': False}

        def _progress_worker():
            p = 10
            while not stop_flag['stop'] and p < 95:
                try:
                    p = min(95, p + (1 + int((100 - p) * 0.05)))
                    job.update(progress=p, message=f"Training {config.get('model_type','model').upper()}... ({p}%)")
                except Exception:
                    pass
                import time as _t
                _t.sleep(2)

        import threading as _thr
        _thr.Thread(target=_progress_worker, daemon=True).start()

        job.update(progress=25, message=f"Training {config['model_type'].upper()} model…")
        result = train_model(DATASETS[dataset_id]['df'], config)

        # Stop the smoother and finalize
        stop_flag['stop'] = True
        job.update(status='completed', progress=100, message='Training complete.', result=result, completed_at=time.time())
    except Exception as exc:
        job.update(status='failed', progress=100, message=str(exc), completed_at=time.time())


@app.post('/models/train', response_model=TrainingJobResponse)
async def start_training(request: ModelTrainingRequest):
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail='Dataset not found')
    config = request.model_dump()
    job_id = str(uuid.uuid4())
    estimated_minutes = 3 if request.model_type.lower() in {'lstm', 'transformer', 'prophet'} else 1
    TRAINING_JOBS[job_id] = {'status': 'queued', 'progress': 0, 'message': 'Training job queued.', 'estimated_minutes': estimated_minutes}
    threading.Thread(target=_run_training_job, args=(job_id, request.dataset_id, config), daemon=True).start()
    return TrainingJobResponse(job_id=job_id, status='queued', message='Training started.', estimated_minutes=estimated_minutes)


@app.get('/models/jobs/{job_id}')
async def training_status(job_id: str):
    if job_id not in TRAINING_JOBS:
        raise HTTPException(status_code=404, detail='Training job not found')
    def _json_safe(obj):
        # Recursively convert numpy types and sanitize NaN/Inf
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_json_safe(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(_json_safe(v) for v in obj)
        # numpy arrays -> lists
        if hasattr(obj, 'tolist') and not isinstance(obj, (str, bytes, bytearray)):
            try:
                return _json_safe(obj.tolist())
            except Exception:
                pass
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        # numbers
        if isinstance(obj, (np.floating, float)):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        return obj

    return _json_safe(TRAINING_JOBS[job_id])


def compute_analysis(df, analysis_type, column, params, group_by=None):
    # If group_by is specified, perform analysis per group
    if group_by and group_by in df.columns:
        groups = df.groupby(group_by)
        results = {}
        for group_name, group_df in groups:
            try:
                results[str(group_name)] = compute_analysis(group_df, analysis_type, column, params, group_by=None)
            except Exception as e:
                results[str(group_name)] = {'error': str(e)}
        return {'grouped': True, 'group_by': group_by, 'groups': results}
    
    # Single analysis (no grouping)
    if analysis_type == 'trend':
        return trend_analysis(df, column)
    elif analysis_type == 'seasonal':
        return seasonal_analysis(df, column, period=params.get('period'))
    elif analysis_type == 'cycle':
        return cycle_analysis(df, column, period=params.get('period'), method=params.get('cycle_method', 'hp'))
    elif analysis_type == 'decomposition':
        return decomposition(df, column, period=params.get('period'), method=params.get('decomposition_method', 'additive'))
    elif analysis_type == 'stationarity':
        return stationarity_test(df, column)
    elif analysis_type == 'autocorrelation':
        return autocorrelation(df, column, nlags=params.get('nlags', 20))
    elif analysis_type == 'partial_autocorrelation':
        return partial_autocorrelation(df, column, nlags=params.get('nlags', 20))
    elif analysis_type == 'spectral':
        return spectral_analysis(df, column)
    elif analysis_type == 'wavelet':
        return wavelet_analysis(df, column)
    elif analysis_type == 'change_point':
        return change_point_detection(df, column, params=params)
    else:
        raise HTTPException(status_code=400, detail="Invalid analysis type")


@app.post("/analysis", response_model=AnalysisResponse)
async def run_analysis(request: AnalysisRequest):
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    df = DATASETS[request.dataset_id]['df']
    analysis_type = request.analysis_type.lower()
    column = request.column
    params = request.params or {}
    group_by = request.group_by
    try:
        results = compute_analysis(df, analysis_type, column, params, group_by=group_by)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AnalysisResponse(analysis_type=analysis_type, column=column, results=results)


@app.post("/report/pdf")
async def report_pdf(request: ReportRequest):
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = DATASETS[request.dataset_id]['df']
    analysis_type = request.analysis_type.lower()
    column = request.column
    params = request.params or {}
    group_by = request.group_by
    try:
        results = compute_analysis(df, analysis_type, column, params, group_by=group_by)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payload = {
        'dataset_id': request.dataset_id,
        'filename': DATASETS[request.dataset_id].get('filename'),
        'sheet': DATASETS[request.dataset_id].get('current_sheet'),
        'row_count': len(df),
        'index_column': DATASETS[request.dataset_id].get('index_column'),
        'time_columns': DATASETS[request.dataset_id].get('inferred_time_columns') or [],
        'analysis_type': analysis_type,
        'column': column,
        'params': params,
        'results': results,
    }

    pdf_bytes = make_pdf_report(payload)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="analysis_report_{analysis_type}.pdf"',
        },
    )


@app.post('/feature-engineering/generate', response_model=FeatureEngineeringResponse)
async def generate_feature_engineering(request: FeatureEngineeringRequest):
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail='Dataset not found')

    df = DATASETS[request.dataset_id]['df']
    try:
        engineer = FeatureEngineer(df, date_column=request.date_column)
        generated_df, generated_columns = engineer.generate_features(
            date_features=request.include_time_features,
            lag_features=request.include_lag_features,
            rolling_features=request.include_rolling_features,
            ema_features=request.include_ema_features,
            cumulative_features=request.include_cumulative_features,
            change_features=request.include_change_features,
            transform_features=request.include_transform_features,
            target_columns=request.target_columns,
            lags=request.lags,
            rolling_windows=request.rolling_windows,
            ema_spans=request.ema_spans,
            normalize=request.normalize,
            standardize=request.standardize,
        )
        sample = generated_df.head(request.sample_rows or 10).reset_index().to_dict(orient='records')
        DATASETS[request.dataset_id]['feature_engineering'] = {
            'date_column': engineer.date_column,
            'generated_columns': generated_columns,
            'generated_df': generated_df,
        }
        return FeatureEngineeringResponse(
            dataset_id=request.dataset_id,
            date_column=engineer.date_column,
            original_columns=[str(col) for col in df.columns],
            generated_features=generated_columns,
            sample_rows=sample,
            summary=engineer.summary(sample_rows=request.sample_rows or 10),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Advanced Trend Analysis Endpoints

@app.get("/trend/variables")
async def get_available_variables(dataset_id: str, province: str | None = None):
    """Get list of available climate variables for trend analysis"""
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = DATASETS[dataset_id]['df']
    
    try:
        analyzer = TrendAnalyzer(df, province=province)
        variables = analyzer.get_available_variables()
        return AvailableVariablesResponse(
            variables=variables,
            province=province
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/trend/analyze", response_model=TrendAnalysisResponse)
async def analyze_trend(request: TrendAnalysisRequest):
    """Perform comprehensive trend analysis on a climate variable"""
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = DATASETS[request.dataset_id]['df']
    
    try:
        analyzer = TrendAnalyzer(df, province=request.province)
        
        if request.analysis_method and request.analysis_method != 'all':
            # Single analysis method
            method = request.analysis_method.lower()
            
            if method == 'raw':
                result = analyzer.raw_time_series(request.variable)
            elif method == 'moving_avg':
                result = analyzer.moving_averages(request.variable)
            elif method == 'annual':
                result = analyzer.annual_trend(request.variable)
            elif method == 'regression':
                result = analyzer.linear_regression_trend(request.variable)
            elif method == 'mk':
                result = analyzer.mann_kendall_test(request.variable)
            elif method == 'lowess':
                result = analyzer.lowess_trend(request.variable)
            else:
                raise ValueError(f"Unknown analysis method: {method}")
            
            methods = {method: result}
        else:
            # Comprehensive analysis (all methods)
            result = analyzer.comprehensive_analysis(request.variable)
            methods = result.pop('methods')
        
        return TrendAnalysisResponse(
            dataset_id=request.dataset_id,
            variable=request.variable,
            province=request.province,
            data_points=len(df) if request.province is None else len(df[df['province'] == request.province]) if 'province' in df.columns else len(df),
            methods=methods
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/trend/compare")
async def compare_provinces(request: ComparisonRequest):
    """Compare trends across multiple provinces"""
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = DATASETS[request.dataset_id]['df']
    
    try:
        analyzer = TrendAnalyzer(df)
        result = analyzer.province_comparison(request.variable, provinces=request.provinces)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/trend/provinces")
async def get_provinces(dataset_id: str):
    """Get list of available provinces in dataset"""
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = DATASETS[dataset_id]['df']
    
    if 'province' in df.columns:
        provinces = df['province'].unique().tolist()
        return {'provinces': provinces}
    else:
        return {'provinces': []}


# Dashboard Overview Endpoint

@app.post("/dashboard/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(request: DashboardOverviewRequest):
    """Get comprehensive dashboard overview with all analyses aggregated"""
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = DATASETS[request.dataset_id]['df']
    
    try:
        # Validate columns exist
        if request.date_column not in df.columns:
            raise ValueError(f"Date column '{request.date_column}' not found in dataset")
        if request.selected_column not in df.columns:
            raise ValueError(f"Column '{request.selected_column}' not found in dataset")

        cache_key = build_overview_cache_key(request.dataset_id, request.date_column, request.selected_column)
        cached = get_cached_result(cache_key)
        if cached is not None:
            return cached
        
        # Get summary statistics
        summary_data = {
            'row_count': len(df),
            'date_range': {
                'start': df[request.date_column].min().isoformat() if pd.api.types.is_datetime64_any_dtype(df[request.date_column]) else str(df[request.date_column].min()),
                'end': df[request.date_column].max().isoformat() if pd.api.types.is_datetime64_any_dtype(df[request.date_column]) else str(df[request.date_column].max()),
            },
            'missing_values': int(df[request.selected_column].isna().sum()),
            'missing_percentage': float(df[request.selected_column].isna().sum() / len(df) * 100),
            'data_type': str(df[request.selected_column].dtype),
            'min_value': float(df[request.selected_column].min()) if pd.api.types.is_numeric_dtype(df[request.selected_column]) else None,
            'max_value': float(df[request.selected_column].max()) if pd.api.types.is_numeric_dtype(df[request.selected_column]) else None,
            'mean_value': float(df[request.selected_column].mean()) if pd.api.types.is_numeric_dtype(df[request.selected_column]) else None,
            'std_value': float(df[request.selected_column].std()) if pd.api.types.is_numeric_dtype(df[request.selected_column]) else None,
        }
        
        # Run all analyses
        trend_result = trend_analysis(df, request.selected_column)
        seasonal_result = seasonal_analysis(df, request.selected_column)
        stationarity_result = stationarity_test(df, request.selected_column)
        acf_result = autocorrelation(df, request.selected_column)
        spectral_result = spectral_analysis(df, request.selected_column)
        change_points_result = change_point_detection(df, request.selected_column)
        
        response_payload = DashboardOverviewResponse(
            dataset_id=request.dataset_id,
            column=request.selected_column,
            date_column=request.date_column,
            summary=summary_data,
            trend=trend_result,
            seasonal=seasonal_result,
            stationarity=stationarity_result,
            autocorrelation=acf_result,
            spectral=spectral_result,
            change_points=change_points_result,
        )

        cache_analysis_result(cache_key, response_payload.dict())
        return response_payload
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Export & Download Endpoints

@app.get("/export/features/{dataset_id}")
async def export_features_csv(dataset_id: str, format: str = "csv"):
    """Export generated features as CSV"""
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    try:
        dataset = DATASETS[dataset_id]
        df = dataset['df']
        
        # Convert to CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=features_{dataset_id[:8]}.csv"}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/export/analysis")
async def export_analysis_results(dataset_id: str = Query(...), analysis_type: str = Query(...), column: str = Query(...)):
    """Export analysis results as JSON"""
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    try:
        df = DATASETS[dataset_id]['df']
        
        # Run the requested analysis
        if analysis_type == 'trend':
            result = trend_analysis(df, column)
        elif analysis_type == 'seasonal':
            result = seasonal_analysis(df, column)
        elif analysis_type == 'stationarity':
            result = stationarity_test(df, column)
        elif analysis_type == 'autocorrelation':
            result = autocorrelation(df, column)
        elif analysis_type == 'spectral':
            result = spectral_analysis(df, column)
        elif analysis_type == 'change_point':
            result = change_point_detection(df, column)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
        
        # Convert to JSON download
        import json
        json_content = json.dumps(result, default=str, indent=2)
        
        return StreamingResponse(
            iter([json_content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_type}_{dataset_id[:8]}.json"}
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Forecasting Endpoint

@app.post('/analysis/comprehensive')
async def comprehensive_analysis(request: AnalysisRequest):
    """Run all 10 time series analyses in one call for the selected province column."""
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    df = DATASETS[request.dataset_id]['df']
    analysis_type = request.analysis_type.lower()
    column = request.column
    params = request.params or {}
    group_by = request.group_by

    cache_key = f"comprehensive:{request.dataset_id}:{column}:{analysis_type}:{params}:{group_by}"
    cached = get_cached_result(cache_key)
    if cached is not None:
        return cached

    try:
        results = compute_analysis(df, analysis_type, column, params, group_by=group_by)
        response = {'analysis_type': analysis_type, 'column': column, 'results': results}
        cache_analysis_result(cache_key, response, ttl_seconds=1800)
        return response
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/forecast", response_model=ForecastingResponse)
async def forecast_values(request: ForecastingRequest):
    """Generate a scientifically robust time series forecast with confidence intervals."""
    if request.dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = DATASETS[request.dataset_id]['df']

    try:
        if request.date_column not in df.columns:
            raise ValueError(f"Date column '{request.date_column}' not found")
        if request.target_column not in df.columns:
            raise ValueError(f"Target column '{request.target_column}' not found")

        # Use the new NIWIS forecasting pipeline
        from app.model_training import _niwis_forecast
        config = {
            'date_column': request.date_column,
            'target': request.target_column,
            'forecast_steps': request.forecast_steps,
            'model_type': request.model_type or 'auto',
        }
        result = _niwis_forecast(df, config, df.select_dtypes(include='number').columns.tolist())

        forecast_values = result.get('forecast_values', [])
        forecast_dates = result.get('forecast_dates', [])
        lower = result.get('lower_bound')
        upper = result.get('upper_bound')
        history_dates = result.get('history_dates', [])
        history_values = result.get('history_values', [])
        metrics = result.get('metrics', {})
        diagnostics = result.get('diagnostics', {})

        return ForecastingResponse(
            dataset_id=request.dataset_id,
            target_column=request.target_column,
            model_type=result.get('model_type', request.model_type or 'auto'),
            forecast_steps=len(forecast_values),
            forecast_values=[float(v) for v in forecast_values],
            forecast_dates=forecast_dates,
            lower_bound=[float(v) for v in lower] if lower else None,
            upper_bound=[float(v) for v in upper] if upper else None,
            model_performance={
                'mae': metrics.get('mae', 0),
                'rmse': metrics.get('rmse', 0),
                'r_squared': metrics.get('r_squared', 0) or 0.0,
                'training_points': len(history_values),
            },
            model_params={
                'method': 'niwis_auto',
                'confidence_level': request.confidence_level,
                'seasonality_detected': result.get('seasonality_detected', False),
                'warnings': result.get('warnings', []),
                'diagnostics': diagnostics,
                'validation_results': result.get('validation_results', {}),
                'model_comparison': result.get('model_comparison', {}),
            },
            history_dates=history_dates,
            history_values=history_values,
            details=result.get('details'),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# KZN Multivariate Forecasting Endpoint
# ---------------------------------------------------------------------------

from fastapi import Body

@app.post("/kzn/forecast")
async def kzn_forecast(payload: dict[str, Any] = Body(...)):
    """Run the full KZN multivariate forecasting pipeline.

    Expected body:
        dataset_id: str
        date_column: str
        target_column: str
        forecast_steps: int = 365
        preferred_model: str | None = None
        confidence_level: float = 0.95
    """
    dataset_id = payload.get("dataset_id")
    date_column = payload.get("date_column")
    target_column = payload.get("target_column")
    forecast_steps = int(payload.get("forecast_steps", 365))
    preferred_model = payload.get("preferred_model")
    confidence_level = float(payload.get("confidence_level", 0.95))

    if not dataset_id or dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")
    df = DATASETS[dataset_id]["df"]
    if date_column not in df.columns:
        raise HTTPException(status_code=400, detail=f"Date column '{date_column}' not found")
    if target_column not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_column}' not found")

    try:
        result = run_kzn_forecast(
            df=df,
            date_column=date_column,
            target_column=target_column,
            forecast_steps=forecast_steps,
            preferred_model=preferred_model,
            confidence_level=confidence_level,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# Health Check

@app.get("/health")
async def health_check():
    """API health check"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'datasets_loaded': len(DATASETS),
        'cache_entries': len(ANALYSIS_CACHE)
    }
