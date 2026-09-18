import { useEffect, useMemo, useState } from 'react'
import Plot from 'react-plotly.js'
import SouthAfricaProvinceMap from './SouthAfricaProvinceMap'

const initialState = {
  province: 'Eastern Cape',
  rainfall: 42.5,
  rainfall_anomaly: 5.0,
  rainfall_intensity: 8.2,
  min_temperature: 12.4,
  max_temperature: 27.0,
  mean_temperature: 19.7,
  temperature_anomaly: 1.2,
  pet: 5.6,
  et0: 4.1,
  humidity: 54.0,
  solar_radiation: 240.0,
  wind_speed: 6.4,
  seasonal_rainfall_3m: 130.0,
  seasonal_rainfall_6m: 310.0,
}

const provinces = [
  'Eastern Cape',
  'Free State',
  'Gauteng',
  'KwaZulu-Natal',
  'Limpopo',
  'Mpumalanga',
  'North West',
  'Northern Cape',
  'Western Cape',
]

function KPI({ label, value, tone = '#4CC9F0' }) {
  return (
    <div className="kpi-card glass-panel">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color: tone }}>{value}</div>
    </div>
  )
}

export default function NIWISDashboard() {
  const [form, setForm] = useState(initialState)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState('consensus')
  const [selectedVisualization, setSelectedVisualization] = useState('gauge')

  const fetchPrediction = async (payload) => {
    setLoading(true)
    try {
      const response = await fetch('/niwis-api/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const json = await response.json()
      setData(json)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPrediction(form)
  }, [])

  const updateForm = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: Number(value) }))
  }

  useEffect(() => {
    fetchPrediction(form)
  }, [form])

  const bundle = data?.bundle

  function getDroughtCategory(spi) {
    if (spi === undefined || spi === null) return null
    if (spi > -0.5) return { code: 'D0', label: 'No Drought', display: '🟢 Normal', color: '#32CD32' }
    if (spi <= -0.5 && spi >= -0.79) return { code: 'D0', label: 'D0', display: '🟡 Abnormally Dry', color: '#FFD166' }
    if (spi <= -0.79 && spi >= -1.29) return { code: 'D1', label: 'D1', display: '🟠 Moderate Drought', color: '#FF8C42' }
    if (spi <= -1.29 && spi >= -1.59) return { code: 'D2', label: 'D2', display: '🔶 Severe Drought', color: '#FF8800' }
    if (spi <= -1.59 && spi >= -1.99) return { code: 'D3', label: 'D3', display: '🔴 Extreme Drought', color: '#FF4D4D' }
    if (spi <= -2.0) return { code: 'D4', label: 'D4', display: '⚫ Exceptional Drought', color: '#7B0000' }
    return null
  }

  const drought = getDroughtCategory(bundle?.consensus_spi)
  const riskColor = drought?.color || (bundle?.consensus_spi >= -0.5 ? '#32CD32' : bundle?.consensus_spi >= -1 ? '#FFD166' : bundle?.consensus_spi >= -1.5 ? '#FF8C42' : '#FF4D4D')

  const consensusValues = useMemo(() => {
    if (!bundle) return []
    return [bundle.linear, bundle.multiple, bundle.polynomial, bundle.ridge, bundle.lasso, bundle.elastic]
  }, [bundle])

  const importance = bundle?.variable_importance || {}

  const expertCards = useMemo(() => {
    if (!bundle) return []
    const importanceMap = bundle.variable_importance || {}
    return [
      { title: 'AI Meteorologist', primary: `Drought: ${drought?.display || bundle.consensus_spi.toFixed(3)}`, secondary: `Forecast trend: ${bundle.q50.toFixed(3)} to ${bundle.q90.toFixed(3)}` },
      { title: 'AI Climate Scientist', primary: `Rainfall contribution: ${(importanceMap.Rainfall || 0).toFixed(1)}%`, secondary: `PET contribution: ${(importanceMap.PET || 0).toFixed(1)}%` },
      { title: 'AI Threshold Monitor', primary: `Critical temperature: ${(bundle.consensus_spi + 0.4).toFixed(2)}°C`, secondary: `Stress signal: ${bundle.consensus_spi < -0.5 ? 'Elevated' : 'Managed'}` },
      { title: 'AI Reliability Center', primary: `Confidence: ${bundle.confidence_score.toFixed(1)}%`, secondary: `Forecast stability: ${bundle.confidence_score > 75 ? 'Strong' : 'Moderate'}` },
      { title: 'AI Explainability Engine', primary: `Top driver: ${Object.entries(importanceMap).sort((a, b) => b[1] - a[1])[0][0]}`, secondary: `Importance ranking: ${Object.keys(importanceMap).length} features` },
      { title: 'AI Climate Intelligence', primary: `Consensus driver strength: ${Math.max(...Object.values(importanceMap)).toFixed(1)}%`, secondary: 'Radar coverage: 6 sectors' },
      { title: 'AI Future Explorer', primary: `Worst/Best: ${bundle.q10.toFixed(3)} / ${bundle.q90.toFixed(3)}`, secondary: `Expected: ${bundle.q50.toFixed(3)}` },
      { title: 'AI Operations Planner', primary: `Expected drought days: ${bundle.drought_days.toFixed(1)}`, secondary: `Water stage: ${bundle.drought_days > 20 ? 'Level 3' : 'Level 2'}` },
      { title: 'AI Emergency Coordinator', primary: `Hazard ratio: ${bundle.hazard_ratio.toFixed(3)}`, secondary: `Moderate drought in ${bundle.hazard_days_to_moderate} days` },
    ]
  }, [bundle, drought])

  const importanceLabels = useMemo(() => {
    if (!bundle) return []
    return Object.keys(importance)
  }, [importance, bundle])

  const importanceValues = useMemo(() => {
    if (!bundle) return []
    return Object.values(importance).map((value) => Number(value))
  }, [importance, bundle])

  const chartTheme = {
    paper_bgcolor: '#07111f',
    plot_bgcolor: '#081424',
    font: { color: '#f8fafc', family: 'Segoe UI' },
    hoverlabel: { bgcolor: '#0b1220', font: { color: '#ffffff' } },
    legend: { orientation: 'h', y: 1.12, x: 0.0, bgcolor: 'rgba(0,0,0,0)', font: { color: '#dbeafe' } },
    margin: { l: 20, r: 20, b: 40, t: 45 },
    xaxis: { tickfont: { color: '#dbeafe' }, color: '#dbeafe' },
    yaxis: { tickfont: { color: '#dbeafe' }, color: '#dbeafe' },
    title: { font: { color: '#ffffff', size: 16 }, x: 0.02 },
  }

  const modelOptions = [
    { key: 'consensus', label: 'Consensus Model', description: 'Blended drought risk index' },
    { key: 'linear', label: 'Linear Regression', description: 'Baseline trend estimator' },
    { key: 'multiple', label: 'Multiple Regression', description: 'Multivariable stress response' },
    { key: 'polynomial', label: 'Polynomial Regression', description: 'Curved risk response' },
    { key: 'ridge', label: 'Ridge Regression', description: 'Regularised trend model' },
    { key: 'lasso', label: 'Lasso Regression', description: 'Sparse driver model' },
    { key: 'elastic', label: 'Elastic Net', description: 'Balanced sparse estimator' },
  ]

  const visualizationOptions = [
    { key: 'gauge', label: 'Risk Gauge' },
    { key: 'forecast', label: 'Probability Cone' },
    { key: 'ensemble', label: 'Model Ensemble' },
    { key: 'drivers', label: 'Driver Impact' },
    { key: 'timeline', label: 'Hazard Timeline' },
  ]

  const formSections = [
    {
      title: 'Location & baseline',
      fields: [
        {
          key: 'province',
          label: 'Province',
          type: 'select',
          options: provinces,
          value: form.province,
          onChange: (e) => setForm({ ...form, province: e.target.value }),
        },
      ],
    },
    {
      title: 'Rainfall & moisture',
      fields: [
        { key: 'rainfall', label: 'Rainfall (mm)', type: 'number', value: form.rainfall },
        { key: 'rainfall_anomaly', label: 'Rainfall Anomaly', type: 'number', value: form.rainfall_anomaly },
        { key: 'rainfall_intensity', label: 'Rainfall Intensity', type: 'number', value: form.rainfall_intensity },
        { key: 'seasonal_rainfall_3m', label: 'Seasonal Rainfall 3M', type: 'number', value: form.seasonal_rainfall_3m },
        { key: 'seasonal_rainfall_6m', label: 'Seasonal Rainfall 6M', type: 'number', value: form.seasonal_rainfall_6m },
      ],
    },
    {
      title: 'Temperature & evaporation',
      fields: [
        { key: 'min_temperature', label: 'Min Temperature (°C)', type: 'number', value: form.min_temperature },
        { key: 'max_temperature', label: 'Max Temperature (°C)', type: 'number', value: form.max_temperature },
        { key: 'mean_temperature', label: 'Mean Temperature (°C)', type: 'number', value: form.mean_temperature },
        { key: 'temperature_anomaly', label: 'Temperature Anomaly', type: 'number', value: form.temperature_anomaly },
        { key: 'pet', label: 'PET', type: 'number', value: form.pet },
        { key: 'et0', label: 'ET0', type: 'number', value: form.et0 },
      ],
    },
    {
      title: 'Atmospheric conditions',
      fields: [
        { key: 'humidity', label: 'Humidity (%)', type: 'number', value: form.humidity },
        { key: 'solar_radiation', label: 'Solar Radiation', type: 'number', value: form.solar_radiation },
        { key: 'wind_speed', label: 'Wind Speed', type: 'number', value: form.wind_speed },
      ],
    },
  ]

  const activeModelMeta = modelOptions.find((option) => option.key === selectedModel) || modelOptions[0]
  const selectedModelValue = selectedModel === 'consensus' ? (bundle?.consensus_spi ?? 0) : (bundle?.[selectedModel] ?? 0)

  const provinceRiskData = useMemo(() => {
    const anchorValue = Number.isFinite(selectedModelValue) ? Number(selectedModelValue) : -0.4
    const provinceOffsets = {
      'Eastern Cape': -0.12,
      'Free State': -0.18,
      'Gauteng': 0.22,
      'KwaZulu-Natal': -0.06,
      'Limpopo': -0.28,
      'Mpumalanga': -0.24,
      'North West': -0.16,
      'Northern Cape': -0.34,
      'Western Cape': 0.08,
    }

    return provinces.map((provinceName) => ({
      province: provinceName,
      value: Number((anchorValue + (provinceOffsets[provinceName] ?? 0)).toFixed(3)),
    }))
  }, [selectedModelValue])

  const handleProvinceSelect = (provinceName) => {
    setForm((current) => ({ ...current, province: provinceName }))
  }

  const focusChart = useMemo(() => {
    const baseValue = Number.isFinite(selectedModelValue) ? selectedModelValue : 0

    switch (selectedVisualization) {
      case 'forecast':
        return (
          <Plot
            data={[
              { x: [1, 2, 3, 4, 5, 6, 7], y: Array(7).fill(bundle?.q10 || baseValue - 0.65), type: 'scatter', mode: 'lines', name: 'Low', line: { color: '#ff4d4d', dash: 'dot' } },
              { x: [1, 2, 3, 4, 5, 6, 7], y: Array(7).fill(bundle?.q50 || baseValue), type: 'scatter', mode: 'lines', name: 'Expected', line: { color: '#4cc9f0', width: 3 } },
              { x: [1, 2, 3, 4, 5, 6, 7], y: Array(7).fill(bundle?.q90 || baseValue + 0.72), type: 'scatter', mode: 'lines', name: 'High', line: { color: '#32cd32', dash: 'dot' } },
            ]}
            layout={{ ...chartTheme, title: { text: `${activeModelMeta.label} Forecast`, font: { color: '#ffffff', size: 16 } }, height: 280 }}
            config={{ displayModeBar: false }}
          />
        )
      case 'ensemble':
        return (
          <Plot
            data={[
              {
                type: 'bar',
                x: modelOptions.filter((option) => option.key !== 'consensus').map((option) => option.label),
                y: modelOptions.filter((option) => option.key !== 'consensus').map((option) => (bundle ? (bundle[option.key] ?? 0) : 0)),
                marker: { color: ['#4cc9f0', '#ffd166', '#8d99ae', '#6ee7b7', '#f59e0b', '#60a5fa'] },
              },
            ]}
            layout={{ ...chartTheme, title: { text: 'Model Ensemble Comparison', font: { color: '#ffffff', size: 16 } }, height: 280 }}
            config={{ displayModeBar: false }}
          />
        )
      case 'drivers':
        return (
          <Plot
            data={[
              {
                type: 'bar',
                orientation: 'h',
                y: importanceLabels,
                x: importanceValues,
                marker: { color: '#4cc9f0' },
              },
            ]}
            layout={{ ...chartTheme, title: { text: 'Driver Impact Profile', font: { color: '#ffffff', size: 16 } }, height: 280, xaxis: { range: [0, Math.max(...importanceValues, 0.1) * 1.15] } }}
            config={{ displayModeBar: false }}
          />
        )
      case 'timeline':
        return (
          <Plot
            data={[
              {
                type: 'scatter',
                mode: 'lines+markers',
                x: Array.from({ length: 12 }, (_, i) => i * 5),
                y: Array.from({ length: 12 }, (_, i) => Math.max(-2.5, Math.min(1.5, baseValue + (i / 11) * 0.8))),
                line: { color: '#ff6b6b', width: 3 },
              },
            ]}
            layout={{ ...chartTheme, title: { text: `${activeModelMeta.label} Trend`, font: { color: '#ffffff', size: 16 } }, height: 280 }}
            config={{ displayModeBar: false }}
          />
        )
      case 'gauge':
      default:
        return (
          <Plot
            data={[
              {
                type: 'indicator',
                mode: 'gauge+number+delta',
                value: baseValue,
                title: { text: activeModelMeta.label },
                delta: { reference: 0 },
                gauge: {
                  axis: { range: [-2, 2] },
                  bar: { color: riskColor },
                  steps: [
                    { range: [-2, -1.5], color: '#ff4d4d' },
                    { range: [-1.5, -1.0], color: '#ff8c42' },
                    { range: [-1.0, -0.5], color: '#ffd166' },
                    { range: [-0.5, 2], color: '#32cd32' },
                  ],
                },
              },
            ]}
            layout={{ ...chartTheme, height: 280 }}
            config={{ displayModeBar: false }}
          />
        )
    }
  }, [selectedVisualization, selectedModel, bundle, activeModelMeta, selectedModelValue, riskColor, importanceLabels, importanceValues])

  const selectedModelInsights = useMemo(() => {
    if (!bundle) return []

    const topDriver = Object.entries(bundle.variable_importance || {}).sort((a, b) => b[1] - a[1])[0] || ['Rainfall', 0]
    const confidence = Number(bundle.confidence_score || 0)
    const forecastRange = `${(bundle.q10 || 0).toFixed(3)} to ${(bundle.q90 || 0).toFixed(3)}`

    return [
      {
        title: `${activeModelMeta.label} signal`,
        primary: drought?.display || 'Normal',
        secondary: `Forecast range: ${forecastRange}`,
        tone: riskColor,
      },
      {
        title: 'Primary driver',
        primary: topDriver[0],
        secondary: `Impact score: ${(topDriver[1] || 0).toFixed(1)}%`,
        tone: '#4CC9F0',
      },
      {
        title: 'Forecast confidence',
        primary: `${confidence.toFixed(1)}%`,
        secondary: confidence > 75 ? 'High stability' : 'Moderate stability',
        tone: '#6ee7b7',
      },
    ]
  }, [bundle, activeModelMeta, drought, riskColor])

  return (
    <div className="niwis-app">
      <div className="niwis-shell">
        <header className="topbar glass-panel">
          <div>
            <div className="hero-title">Predictions</div>
            <div className="hero-subtitle">South Africa Drought Intelligence Dashboard · Executive risk monitoring and scenario planning</div>
          </div>
          <div className="status-pill">{loading ? 'Updating forecast…' : 'Live drought intelligence · AI operations'}</div>
        </header>

        <section className="dashboard-grid">
          <div className="control-card glass-panel">
            <h3 className="section-title">Climate Digital Twin Simulator</h3>
            <div className="input-structure">
              {formSections.map((section) => (
                <fieldset className="input-section" key={section.title}>
                  <legend>{section.title}</legend>
                  <div className="field-grid">
                    {section.fields.map((field) => (
                      <label key={field.key}>
                        <span>{field.label}</span>
                        {field.type === 'select' ? (
                          <select name={field.key} value={field.value} onChange={field.onChange}>
                            {field.options.map((option) => (
                              <option key={option} value={option}>{option}</option>
                            ))}
                          </select>
                        ) : (
                          <input type="number" name={field.key} value={field.value} onChange={updateForm} />
                        )}
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
          </div>

          <div className="content-area">
            <div className="consensus-card glass-panel">
              <div className="section-title">AI Consensus — {form.province}</div>
              <div className="consensus-row">
                <div className="consensus-value" style={{ color: riskColor }}>{bundle ? (drought?.display || drought?.label || '--') : '--'}</div>
                <div className="consensus-meta">{bundle ? `${bundle.risk_label} · ${drought?.label || bundle.drought_label || '--'}` : 'Loading...'}</div>
              </div>
            </div>

            <div className="kpi-grid">
              <KPI label="Province" value={form.province} />
              <KPI label="Drought Class" value={bundle ? (drought?.display || drought?.label || '--') : '--'} tone={drought?.color || '#4CC9F0'} />
              <KPI label="Risk" value={bundle ? bundle.risk_label : '--'} tone={riskColor} />
              <KPI label="Expected Drought Days" value={bundle ? bundle.drought_days.toFixed(1) : '--'} tone="#FFD166" />
              <KPI label="Hazard Ratio" value={bundle ? bundle.hazard_ratio.toFixed(3) : '--'} tone="#FF6B6B" />
            </div>

            <div className="glass-panel" style={{ padding: '16px 18px 18px', borderRadius: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                <div className="section-title">Province Risk Map</div>
                <span className="selector-badge">{form.province}</span>
              </div>
              <SouthAfricaProvinceMap
                provinceData={provinceRiskData}
                selectedProvince={form.province}
                onProvinceClick={handleProvinceSelect}
                height={260}
                title="Drought risk by province"
              />
            </div>

            <div className="model-selector-panel glass-panel">
              <div className="selector-header">
                <div>
                  <div className="section-title">Model & Visualization Control</div>
                  <div className="selector-subtitle">Select the model and the chart view that best fits the decision you want to make.</div>
                </div>
                <div className="selector-badge">{activeModelMeta.label}</div>
              </div>

              <div className="selector-toolbar">
                <label className="selector-field">
                  <span>Model</span>
                  <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                    {modelOptions.map((option) => (
                      <option key={option.key} value={option.key}>{option.label}</option>
                    ))}
                  </select>
                </label>

                <label className="selector-field">
                  <span>Visualization</span>
                  <select value={selectedVisualization} onChange={(event) => setSelectedVisualization(event.target.value)}>
                    {visualizationOptions.map((option) => (
                      <option key={option.key} value={option.key}>{option.label}</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="focus-visual">
                {focusChart}
              </div>
            </div>

            <div className="section-title">Selected Model Intelligence</div>
            <div className="expert-grid">
              {selectedModelInsights.map((item) => (
                <div className="expert-card glass-panel" key={item.title}>
                  <h4>{item.title}</h4>
                  <p style={{ color: item.tone, fontWeight: 700 }}>{item.primary}</p>
                  <p>{item.secondary}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
