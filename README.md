# Predictive Time Series Analysis App

This repository contains a starter application for time series analysis with:
- React frontend
- FastAPI backend
- CSV/Excel upload
- Dataset preview and column extraction
- Data cleaning and analysis scaffolding

## Features

- File upload (`csv`, `xls`, `xlsx`)
- Automatic dataset cleaning and preview
- Column listing for user-selected analyses
- Backend functions for:
  - Trend analysis
  - Seasonal analysis
  - Cycle analysis
  - Decomposition
  - Stationarity testing
  - Autocorrelation / Partial autocorrelation
  - Spectral analysis
  - Wavelet analysis
  - Change point detection
- Excel sheet selection support
- Pre-upload sheet preview for Excel files
- User-configurable analysis parameters (period / nlags)
- Export analysis reports and chart PNG files
- Inferred time columns and date index detection
- Time-series cleaning and smart interpolation

## How it works

1. Upload your time series dataset (CSV or Excel).
2. Select the correct date/time column as the time axis.
3. Pick a variable to analyze or generate new time-series features.
4. Use the dashboard tabs to inspect trends, seasonality, autocorrelation, and change points.
5. Download your feature matrix or analysis report as CSV, JSON, or PDF.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If you prefer to run from the repository root, use:

```bash
uvicorn backend.app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend is configured to proxy API requests to `http://localhost:8000`.
