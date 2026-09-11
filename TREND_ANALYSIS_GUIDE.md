# Trend Analysis Implementation - Complete Guide

## Overview

A comprehensive trend analysis system has been implemented for your NIWIS climate project. This includes:

1. **Interactive Jupyter Notebook** - For exploratory trend analysis
2. **Backend API endpoints** - For programmatic access to trend analysis
3. **Advanced statistical methods** - Multiple trend detection approaches
4. **Province-by-province comparison** - Identify regions with strongest climate changes

---

## What Was Created

### 1. Jupyter Notebook: `Trend_Analysis.ipynb`

An interactive notebook with 10 comprehensive sections:

**Section 1: Import Required Libraries**
- Imports: pandas, numpy, matplotlib, scipy, pymannkendall, statsmodels
- Checks for optional dependencies

**Section 2: Load and Prepare Time Series Data**
- Loads the climate dataset
- Filters by selected province
- Displays available climate variables

**Section 3: Plot Raw Time Series**
- Visualize raw daily data for key variables
- Shows: rainfall, temperature, PET, SPI

**Section 4: Calculate Rolling Averages**
- Computes 30-day, 90-day, 365-day moving averages
- Reveals underlying trends by smoothing daily noise

**Section 5: Compute Annual Aggregates**
- Resamples daily data to yearly means
- Makes long-term trends clearer

**Section 6: Fit Linear Regression Trend Lines**
- Uses scipy.stats.linregress
- Extracts: slope, intercept, R², p-value
- Interpretation: positive slope = increasing, negative = decreasing

**Section 7: Perform Mann–Kendall Trend Test**
- Non-parametric trend test (requires: `pip install pymannkendall`)
- Robust to outliers
- P-value < 0.05 = significant trend

**Section 8: Apply LOWESS Smoothing**
- Captures non-linear trends
- Useful when trend direction changes over time
- (Requires: `pip install statsmodels`)

**Section 9: Generate Province-by-Province Trend Comparison**
- Compares rainfall trends across all provinces
- Identifies regions with strongest climate changes
- Sorted by magnitude of trend

**Section 10: Create Summary Statistics Table**
- Comprehensive summary of all variables
- Shows slopes, p-values, R², trend direction
- Ready for reports and publications

---

### 2. Backend Module: `backend/app/trend_analysis.py`

Advanced statistical analysis engine with the `TrendAnalyzer` class.

**Key Methods:**

```python
analyzer = TrendAnalyzer(df, province="Eastern Cape")

# Get available variables
variables = analyzer.get_available_variables()

# Raw time series
analyzer.raw_time_series("daily_rainfall")

# Moving averages (30, 90, 365 day)
analyzer.moving_averages("daily_rainfall")

# Annual aggregates
analyzer.annual_trend("daily_rainfall")

# Linear regression
analyzer.linear_regression_trend("daily_rainfall")

# Mann-Kendall test
analyzer.mann_kendall_test("daily_rainfall")

# LOWESS smoothing
analyzer.lowess_trend("daily_rainfall")

# Comprehensive analysis (all methods)
analyzer.comprehensive_analysis("daily_rainfall")

# Province comparison
analyzer.province_comparison("daily_rainfall", provinces=None)
```

---

### 3. New API Endpoints: `backend/app/main.py`

Four new REST API endpoints for programmatic trend analysis:

#### GET `/trend/variables?dataset_id={id}&province={province}`
Get list of available climate variables for a dataset/province.

**Response:**
```json
{
  "variables": ["daily_rainfall", "daily_tmean", "spi_3m", ...],
  "province": "Eastern Cape"
}
```

#### POST `/trend/analyze`
Perform comprehensive or single-method trend analysis.

**Request:**
```json
{
  "dataset_id": "abc123",
  "variable": "daily_rainfall",
  "province": "Eastern Cape",
  "analysis_method": "all"
}
```

**Analysis Methods:**
- `"raw"` - Raw time series data
- `"moving_avg"` - 30/90/365-day moving averages
- `"annual"` - Annual aggregates
- `"regression"` - Linear regression trend line
- `"mk"` - Mann-Kendall test
- `"lowess"` - LOWESS smoothing
- `"all"` - Comprehensive analysis (all methods)

**Response:**
```json
{
  "dataset_id": "abc123",
  "variable": "daily_rainfall",
  "province": "Eastern Cape",
  "data_points": 8766,
  "methods": {
    "raw": { ... },
    "moving_avg": { ... },
    "annual": { ... },
    "regression": {
      "slope": -0.623,
      "p_value": 0.001,
      "r_squared": 0.456,
      "trend_direction": "Decreasing",
      ...
    },
    ...
  }
}
```

#### POST `/trend/compare`
Compare trends across multiple provinces.

**Request:**
```json
{
  "dataset_id": "abc123",
  "variable": "daily_rainfall",
  "provinces": ["Eastern Cape", "Western Cape", "KwaZulu-Natal"]
}
```

**Response:**
```json
{
  "variable": "daily_rainfall",
  "provinces": [
    {
      "province": "Eastern Cape",
      "slope": -0.623,
      "p_value": 0.001,
      "trend": "Decreasing",
      "significant": true
    },
    ...
  ]
}
```

#### GET `/trend/provinces?dataset_id={id}`
Get list of provinces in dataset.

**Response:**
```json
{
  "provinces": ["Eastern Cape", "Western Cape", "KwaZulu-Natal", ...]
}
```

---

### 4. Updated Schemas: `backend/app/schemas.py`

New Pydantic models for type validation:
- `TrendAnalysisRequest`
- `TrendAnalysisResponse`
- `ComparisonRequest`
- `AvailableVariablesResponse`

---

### 5. Updated Dependencies: `backend/requirements.txt`

Added packages:
- `pymannkendall` - Mann-Kendall trend test
- `matplotlib` - Visualization
- `seaborn` - Enhanced visualization

---

## Climate Variables Analyzed

### Precipitation
- `daily_rainfall` - Daily rainfall
- `rain_anomaly_mm` - Rainfall anomaly
- `rain_intensity_mm_h` - Rainfall intensity

### Temperature
- `daily_tmin` - Daily minimum temperature
- `daily_tmax` - Daily maximum temperature
- `daily_tmean` - Daily mean temperature
- `temp_anomaly_c` - Temperature anomaly

### Evapotranspiration
- `daily_pet` - Potential evapotranspiration
- `daily_et0` - Reference evapotranspiration

### Atmospheric
- `daily_relative_humidity` - Relative humidity
- `solar_radiation_w_m2` - Solar radiation
- `wind_speed_2m` - Wind speed

### Drought Indices
- `spi_1m`, `spi_3m`, `spi_6m`, `spi_12m`, `spi_24m` - Standardized Precipitation Index
- `spei_1m`, `spei_3m`, `spei_6m`, `spei_12m`, `spei_24m` - Standardized Precipitation-Evapotranspiration Index

---

## How to Use

### 1. Using the Jupyter Notebook

```bash
cd c:\Users\student\Desktop\pridictive
jupyter notebook Trend_Analysis.ipynb
```

**Steps:**
1. Select a province in Section 2 (line: `province = "Eastern Cape"`)
2. Run all cells sequentially
3. Review visualizations and summary table
4. Change province to analyze a different region

### 2. Using the Backend API

**Start the server:**
```bash
cd c:\Users\student\Desktop\pridictive\backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Example Python usage:**
```python
import requests

# Upload dataset
response = requests.post(
    "http://localhost:8000/upload",
    files={"file": open("niwis_daily_climate_master.csv", "rb")}
)
dataset_id = response.json()["dataset_id"]

# Get available variables
response = requests.get(
    f"http://localhost:8000/trend/variables",
    params={"dataset_id": dataset_id, "province": "Eastern Cape"}
)
print(response.json())

# Analyze rainfall trend
response = requests.post(
    "http://localhost:8000/trend/analyze",
    json={
        "dataset_id": dataset_id,
        "variable": "daily_rainfall",
        "province": "Eastern Cape",
        "analysis_method": "all"
    }
)
results = response.json()
print(results["methods"]["regression"])

# Compare provinces
response = requests.post(
    "http://localhost:8000/trend/compare",
    json={
        "dataset_id": dataset_id,
        "variable": "daily_rainfall"
    }
)
comparison = response.json()
for prov in comparison["provinces"]:
    print(f"{prov['province']}: {prov['slope']:.4f} ({prov['trend']})")
```

### 3. Using Within Your Frontend

Update your React frontend to call the new endpoints:

```javascript
// services/api.js
export async function getTrendVariables(datasetId, province) {
  const params = new URLSearchParams({
    dataset_id: datasetId,
    ...(province && { province })
  });
  return fetch(`/trend/variables?${params}`).then(r => r.json());
}

export async function analyzeTrend(datasetId, variable, province, method = 'all') {
  return fetch('/trend/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: datasetId,
      variable,
      province,
      analysis_method: method
    })
  }).then(r => r.json());
}

export async function compareProvinces(datasetId, variable) {
  return fetch('/trend/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: datasetId,
      variable
    })
  }).then(r => r.json());
}
```

---

## Installation of Optional Dependencies

For full functionality, install optional packages:

```bash
pip install pymannkendall statsmodels matplotlib seaborn
```

**What each provides:**
- `pymannkendall` - Mann-Kendall non-parametric trend test
- `statsmodels` - LOWESS smoothing and advanced stats
- `matplotlib` - Visualization plotting
- `seaborn` - Enhanced plot styling

---

## Expected Outputs

### Notebook Outputs

**Raw Time Series Plots:**
- Shows daily variability and seasonal patterns

**Moving Average Plots:**
- 30-day: short-term trends
- 90-day: medium-term trends
- 365-day: long-term underlying trend

**Annual Trend Plots:**
- Clear visualization of year-to-year changes

**Linear Regression Results:**
```
Variable             Slope        p-value    R²       Trend
daily_rainfall       -0.623121    0.0010     0.4560   Decreasing ✓ Sig.
daily_tmean          +0.043231    <0.001     0.8120   Increasing ✓ Sig.
spi_12m              -0.031452    0.0200     0.2340   Drying ✓ Sig.
```

**Mann-Kendall Test Results:**
```
Variable             Trend        p-value    Slope
daily_rainfall       decreasing   0.0040     -0.82
daily_tmean          increasing   <0.001     +0.51
```

**Province Comparison:**
- Bar chart showing which provinces have strongest trends
- Sorted by magnitude of change

---

## Interpretation Guide

### Slope
- **Positive** → Variable is increasing over time
- **Negative** → Variable is decreasing over time
- **Near 0** → Variable is relatively stable

### P-value
- **< 0.05** → Trend is statistically significant (likely real)
- **> 0.05** → Trend is not significant (could be random variation)

### R-squared
- **Close to 1** → Linear trend explains most of the variation
- **Close to 0** → Linear trend explains little variation

### mann-Kendall Trend
- Non-parametric test (doesn't assume linear relationship)
- Results: 'increasing', 'decreasing', or 'stable'
- More robust to outliers than linear regression

### LOWESS
- Useful when trend direction changes over time
- Captures non-linear patterns
- "Locally Weighted" = adapts to local changes

---

## Troubleshooting

### Error: "pymannkendall not installed"
```bash
pip install pymannkendall
```

### Error: "statsmodels not installed"
```bash
pip install statsmodels
```

### Error: "Module not found: app"
Make sure you're running from the `backend/` directory:
```bash
cd backend
python -m uvicorn app.main:app
```

### No data in results
Check that:
1. Dataset is uploaded successfully
2. Variable name is correct
3. Province name matches exactly (case-sensitive)
4. Variable has sufficient non-null data points (minimum 100 for most analyses)

---

## Next Steps

1. **Customize the notebook** for your specific provinces/variables
2. **Integrate API endpoints** into your React frontend
3. **Add visualizations** to your dashboard using the API results
4. **Generate reports** using the summary tables
5. **Extend analysis** with additional statistical methods as needed

---

## Files Modified/Created

**New Files:**
- `Trend_Analysis.ipynb` - Interactive notebook
- `backend/app/trend_analysis.py` - Analysis engine
- `backend/verify_setup.py` - Verification script

**Modified Files:**
- `backend/app/main.py` - Added 4 new endpoints
- `backend/app/schemas.py` - Added 4 new Pydantic models
- `backend/requirements.txt` - Added dependencies

---

## Support

For detailed implementation in your frontend, refer to:
- Jupyter notebook: `Trend_Analysis.ipynb` (examples and visualizations)
- Backend module: `backend/app/trend_analysis.py` (API documentation)
- API endpoints: See section "3. New API Endpoints" above

