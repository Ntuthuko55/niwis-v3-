# Quick Start: Trend Analysis

## Installation (1 minute)

```bash
cd c:\Users\student\Desktop\pridictive\backend
pip install -r requirements.txt
```

---

## Option 1: Interactive Notebook (Fastest)

```bash
cd c:\Users\student\Desktop\pridictive
jupyter notebook Trend_Analysis.ipynb
```

Then:
1. Change `province = "Eastern Cape"` to your desired province
2. Run all cells (Ctrl+A, then Ctrl+Enter)
3. Review all 10 sections of analysis

**Time needed:** 2-5 minutes per province

---

## Option 2: Backend API (Programmatic)

### Start Server
```bash
cd c:\Users\student\Desktop\pridictive\backend
uvicorn app.main:app --reload
```

### Test with Python
```python
import requests

# Get dataset ID (upload first if needed)
dataset_id = "your-dataset-id"

# 1. Get available provinces
r = requests.get(f"http://localhost:8000/trend/provinces?dataset_id={dataset_id}")
print(r.json())

# 2. Get available variables for a province
r = requests.get(
    "http://localhost:8000/trend/variables",
    params={"dataset_id": dataset_id, "province": "Eastern Cape"}
)
print(r.json()["variables"])

# 3. Analyze rainfall trend
r = requests.post(
    "http://localhost:8000/trend/analyze",
    json={
        "dataset_id": dataset_id,
        "variable": "daily_rainfall",
        "province": "Eastern Cape",
        "analysis_method": "all"
    }
)
results = r.json()

# Print regression results
regression = results["methods"]["regression"]
print(f"Slope: {regression['slope']:.4f}")
print(f"Trend: {regression['trend_direction']}")
print(f"Significant: {regression['significance']}")

# 4. Compare across provinces
r = requests.post(
    "http://localhost:8000/trend/compare",
    json={
        "dataset_id": dataset_id,
        "variable": "daily_rainfall"
    }
)
comparison = r.json()
for prov in comparison["provinces"]:
    print(f"{prov['province']}: {prov['slope']:>7.4f} ({prov['trend']})")
```

---

## Option 3: Frontend Integration

In your React app, use the API endpoints:

```javascript
// Get provinces
const response = await fetch(`/trend/provinces?dataset_id=${id}`);
const { provinces } = await response.json();

// Analyze a variable
const trendData = await fetch('/trend/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    dataset_id: id,
    variable: 'daily_rainfall',
    province: selectedProvince,
    analysis_method: 'all'
  })
}).then(r => r.json());

// Display results
const regression = trendData.methods.regression;
console.log(`${regression.variable}: ${regression.trend_direction}`);
console.log(`Slope: ${regression.slope.toFixed(4)}`);
console.log(`P-value: ${regression.p_value.toFixed(4)}`);
```

---

## Key Trend Analysis Methods

| Method | What It Shows | When to Use |
|--------|--------------|-----------|
| **Raw Time Series** | Daily variability | For overview, see noise level |
| **Moving Average** | Short/medium/long-term trends | Smooth out daily noise |
| **Annual Aggregate** | Year-to-year changes | Easy trend visualization |
| **Linear Regression** | Directional trend & strength | Quantify trend, get p-value |
| **Mann-Kendall** | Non-parametric trend | More robust to outliers |
| **LOWESS** | Non-linear trends | When direction changes over time |
| **Province Comparison** | Regional differences | Identify hotspots of change |

---

## Expected Results for NIWIS Data

### Rainfall
- **Historic trend:** Decreasing in most provinces
- **Strongest in:** Drought-prone regions
- **Example:** Eastern Cape: slope = -0.62 mm/year (significant, p < 0.05)

### Temperature
- **Historic trend:** Increasing across all regions
- **Strength:** Strong in most provinces
- **Example:** Daily mean: +0.04°C/year (significant, p < 0.001)

### SPI (Drought Index)
- **Historic trend:** Usually decreasing (more drought)
- **Significance:** Varies by province
- **Importance:** Key climate change indicator

---

## Interpretation Examples

**Rainfall slope = -0.623**
- Rainfall is decreasing by ~0.6mm per year
- Over 20 years: ~12mm annual decrease
- P-value < 0.05: This trend is statistically significant

**Temperature slope = +0.043°C**
- Temperature is warming by ~0.04°C per year
- Over 50 years: ~2°C warming
- This matches historical climate change patterns

**SPI slope = -0.031**
- Standardized drought index decreasing (more drought)
- Indicates "drying trend" over analysis period

---

## Customize Analysis

**For Different Province:**
Edit `Trend_Analysis.ipynb` Section 2:
```python
province = "Western Cape"  # Change this
```

**For Different Variable:**
Edit Section 6 (regression):
```python
key_variables = ['daily_pet', 'spi_6m', 'daily_tmax']  # Change this
```

**For Different Time Period:**
Filter in Section 2:
```python
start_year = 2010
ts = ts[ts.index.year >= start_year]
```

---

## Next Steps

1. **Run the notebook** for your primary province
2. **Review the summary table** for key findings
3. **Export results** using the API
4. **Integrate into frontend** with visualizations
5. **Generate reports** for stakeholders

---

## Troubleshooting

**Error: "No data points"**
→ Check variable name and province spelling

**Error: "pymannkendall not installed"**
→ Run: `pip install pymannkendall`

**Trend analysis says "Not Significant"**
→ That's OK! It means we can't be confident in the trend (could be random variation)

**Want to use a different method?**
→ See `TREND_ANALYSIS_GUIDE.md` for detailed documentation

---

## Questions?

Refer to:
- Full guide: `TREND_ANALYSIS_GUIDE.md`
- Notebook reference: `Trend_Analysis.ipynb`
- Code docs: `backend/app/trend_analysis.py`
