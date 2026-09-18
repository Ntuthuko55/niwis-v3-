import { useEffect, useMemo, useState } from 'react'
import { analyze, generateFeatures, getDashboardOverview, forecast, exportFeaturesCSV, exportAnalysisJSON } from '../services/api'
import AnalysisChart from './AnalysisChart'

const dashboardTabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'trend', label: 'Trend Analysis' },
  { key: 'seasonal', label: 'Seasonal Analysis' },
  { key: 'cycle', label: 'Cycle Analysis' },
  { key: 'decomposition', label: 'Decomposition' },
  { key: 'stationarity', label: 'Stationarity' },
  { key: 'autocorrelation', label: 'Autocorrelation' },
  { key: 'partial_autocorrelation', label: 'PACF' },
  { key: 'spectral', label: 'Spectral Analysis' },
  { key: 'wavelet', label: 'Wavelet Analysis' },
  { key: 'change_point', label: 'Change Point' },
]

const analysisDescriptions = {
  trend: 'Long-term movement, trend slope, and persistence.',
  seasonal: 'Seasonal cycles by month, week, quarter, and year.',
  cycle: 'Slow-moving cycles beyond seasonality.',
  decomposition: 'Observed, trend, seasonal, and residual components.',
  stationarity: 'Stationarity tests and differencing recommendations.',
  autocorrelation: 'ACF values and persistence across lags.',
  partial_autocorrelation: 'PACF values to infer AR order.',
  spectral: 'Frequency domain insights using FFT.',
  wavelet: 'Time-frequency analysis with localized events.',
  change_point: 'Structural breaks and regime shifts.',
}

// Map overview response fields to tab keys
const overviewTabMapping = {
  trend: 'trend',
  seasonal: 'seasonal',
  stationarity: 'stationarity',
  autocorrelation: 'autocorrelation',
  spectral: 'spectral',
  change_point: 'change_points',  // Note: response uses 'change_points' (plural)
}

function FeatureEngineering({
  datasetId,
  columns,
  dateColumn,
  datasetSummary,
  selectedColumn,
}) {
  const [activeTab, setActiveTab] = useState('overview')
  const [analysisResult, setAnalysisResult] = useState(null)
  const [overviewData, setOverviewData] = useState(null)
  const [featureResult, setFeatureResult] = useState(null)
  const [forecastResult, setForecastResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState('Choose a tab and run dashboard analysis.')
  const [targetColumn, setTargetColumn] = useState(selectedColumn || '')

  useEffect(() => {
    setTargetColumn(selectedColumn || '')
  }, [selectedColumn])

  const numericColumns = useMemo(
    () => columns.filter((col) => col !== dateColumn),
    [columns, dateColumn],
  )

  const handleTabChange = async (tab) => {
    setActiveTab(tab)
    setAnalysisResult(null)
    setMessage('Loading dashboard content...')
    
    if (tab === 'overview') {
      setMessage('Overview shows dataset summary, missing values, and feature engineering readiness.')
      return
    }

    if (!datasetId || !targetColumn) {
      setMessage('Select a target column and dataset before running analysis.')
      return
    }

    // Load overview data (cached or fresh)
    setRunning(true)
    try {
      // If overview already loaded, use it; otherwise fetch once
      let overview = overviewData
      if (!overview) {
        overview = await getDashboardOverview(datasetId, dateColumn, targetColumn)
        setOverviewData(overview)
      }

      // Extract the specific tab data from the overview response
      const tabField = overviewTabMapping[tab]
      if (tabField && overview[tabField]) {
        setAnalysisResult(overview[tabField])
      } else {
        // Fallback to individual analysis call
        const result = await analyze(datasetId, tab, targetColumn, { period: 12, nlags: 20 })
        setAnalysisResult(result)
      }

      setMessage(analysisDescriptions[tab] || 'Analysis complete.')
    } catch (err) {
      console.error('Dashboard overview error:', err)
      setMessage(err.message || 'Unable to load dashboard analysis.')
      // Fallback to individual analysis
      try {
        const result = await analyze(datasetId, tab, targetColumn, { period: 12, nlags: 20 })
        setAnalysisResult(result)
        setMessage(analysisDescriptions[tab] || 'Analysis complete.')
      } catch (fallbackErr) {
        setMessage(fallbackErr.response?.data?.detail || fallbackErr.message || 'Unable to run dashboard analysis.')
      }
    } finally {
      setRunning(false)
    }
  }

  const runFeatureEngineering = async () => {
    if (!datasetId || !dateColumn) {
      setMessage('Set the date column before generating features.')
      return
    }
    setRunning(true)
    setMessage('Generating time-series features…')
    try {
      const payload = {
        date_column: dateColumn,
        target_columns: [targetColumn],
        lags: [1, 2, 3],
        rolling_windows: [7, 14, 30],
        ema_spans: [7, 14, 30],
        include_time_features: true,
        include_lag_features: true,
        include_rolling_features: true,
        include_ema_features: true,
        include_cumulative_features: true,
        include_change_features: true,
        include_transform_features: true,
        normalize: true,
        standardize: true,
        sample_rows: 10,
      }
      const result = await generateFeatures(datasetId, payload)
      setFeatureResult(result)
      setMessage('Feature engineering complete. Review generated feature samples below.')
      setActiveTab('overview')
    } catch (err) {
      setMessage(err.response?.data?.detail || err.message || 'Feature generation failed.')
    } finally {
      setRunning(false)
    }
  }

  const runForecast = async () => {
    if (!datasetId || !dateColumn || !targetColumn) {
      setMessage('Set date column and target column before forecasting.')
      return
    }
    setRunning(true)
    setMessage('Generating forecast with confidence intervals…')
    try {
      const result = await forecast(datasetId, dateColumn, targetColumn, 30)
      setForecastResult(result)
      setMessage(`Forecast complete: ${result.forecast_steps} periods predicted with R² = ${(result.model_performance.r_squared * 100).toFixed(1)}%`)
    } catch (err) {
      setMessage(err.response?.data?.detail || err.message || 'Forecast failed.')
    } finally {
      setRunning(false)
    }
  }

  const handleExport = async (type) => {
    try {
      if (type === 'features') {
        await exportFeaturesCSV(datasetId)
        setMessage('Features exported as CSV!')
      } else if (type === 'analysis') {
        await exportAnalysisJSON(datasetId, activeTab, targetColumn)
        setMessage(`${activeTab} analysis exported as JSON!`)
      }
    } catch (err) {
      setMessage(`Export failed: ${err.message}`)
    }
  }

  return (
    <section className="dashboard-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">DASHBOARD</p>
          <h2>Feature Engineering & Time Series Dashboard</h2>
          <p className="section-description">Tabbed insights for dataset summary, trend detection, seasonality, cycles, stationarity, and more.</p>
        </div>
      </div>
      <div className="dashboard-help">
        <p><strong>Quick start:</strong> select a target column, generate features, then use the Overview tab to understand data quality and trends before moving to deeper analysis.</p>
      </div>

      <div className="dashboard-tabs">
        {dashboardTabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab-button ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => handleTabChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="dashboard-actions">
        <label>
          Target column:
          <select value={targetColumn} onChange={(e) => setTargetColumn(e.target.value)}>
            <option value="">Select target</option>
            {numericColumns.map((col) => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </label>
        <button className="primary-button" onClick={runFeatureEngineering} disabled={!datasetId || !dateColumn || running}>
          {running ? 'Generating…' : 'Generate features'}
        </button>
        <button className="secondary-button" onClick={runForecast} disabled={!datasetId || !dateColumn || !targetColumn || running} title="Forecast next 30 periods">
          📈 Forecast
        </button>
        <button className="tertiary-button" onClick={() => handleExport('features')} disabled={!datasetId || running} title="Download generated features">
          ⬇ Export Features
        </button>
        <button className="tertiary-button" onClick={() => handleExport('analysis')} disabled={!datasetId || !targetColumn || running} title="Download analysis results">
          ⬇ Export Analysis
        </button>
      </div>

      <div className="dashboard-content">
        {activeTab === 'overview' ? (
          <>
            <div className="stat-grid">
              <div className="stat-card"><span>Rows</span><strong>{datasetSummary?.rows?.toLocaleString() || '—'}</strong></div>
              <div className="stat-card"><span>Columns</span><strong>{datasetSummary?.columns || '—'}</strong></div>
              <div className="stat-card"><span>Missing values</span><strong>{datasetSummary?.missing_values_total?.toLocaleString() || '—'}</strong></div>
              <div className="stat-card"><span>Date range</span><strong>{datasetSummary?.time_columns?.length ? datasetSummary?.time_columns.join(', ') : dateColumn || 'None'}</strong></div>
            </div>
            <div className="dashboard-overview">
              <div className="panel-box">
                <h3>Data quality and coverage</h3>
                <p>{datasetSummary?.rows ? `This dataset contains ${datasetSummary.rows.toLocaleString()} rows and ${datasetSummary.columns} columns.` : 'Upload a dataset to view summary.'}</p>
                <p>{datasetSummary?.missing_values_total ? `${datasetSummary.missing_values_total.toLocaleString()} missing values detected.` : 'No missing value summary available yet.'}</p>
              </div>
              <div className="panel-box">
                <h3>Feature engineering preview</h3>
                {featureResult ? (
                  <>
                    <p>Generated <strong>{featureResult.generated_features.length}</strong> new features.</p>
                    <div className="table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            {featureResult.sample_rows?.length ? Object.keys(featureResult.sample_rows[0]).map((key) => <th key={key}>{key}</th>) : <th>No sample available</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {featureResult.sample_rows?.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {Object.values(row).map((value, cellIndex) => <td key={cellIndex}>{value?.toString?.() ?? ''}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <p>Generate features to preview time-based, lag, rolling, cumulative, and transformation features.</p>
                )}
              </div>
              {forecastResult && (
                <div className="panel-box">
                  <h3>📈 Forecast Results</h3>
                  <div className="forecast-summary">
                    <div className="forecast-stat">
                      <span>Model</span>
                      <strong>{forecastResult.model_type}</strong>
                    </div>
                    <div className="forecast-stat">
                      <span>R² Score</span>
                      <strong>{(forecastResult.model_performance.r_squared * 100).toFixed(1)}%</strong>
                    </div>
                    <div className="forecast-stat">
                      <span>RMSE</span>
                      <strong>{forecastResult.model_performance.rmse.toFixed(2)}</strong>
                    </div>
                    <div className="forecast-stat">
                      <span>Periods</span>
                      <strong>{forecastResult.forecast_steps}</strong>
                    </div>
                  </div>
                  <p style={{ fontSize: '0.85em', color: '#666', marginTop: '8px' }}>
                    Next prediction: <strong>{forecastResult.forecast_values[0]?.toFixed(2)}</strong>
                    {forecastResult.upper_bound && forecastResult.lower_bound && 
                      ` (95% CI: ${forecastResult.lower_bound[0]?.toFixed(2)} to ${forecastResult.upper_bound[0]?.toFixed(2)})`
                    }
                  </p>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="panel-box">
              <h3>{analysisDescriptions[activeTab]}</h3>
              <p>Running the selected analysis on <strong>{targetColumn || 'target variable'}</strong>.</p>
            </div>
            {running && <div className="info-box">Running analysis...</div>}
            {analysisResult ? <AnalysisChart analysisResult={analysisResult} /> : <div className="info-box">{message}</div>}
          </>
        )}
      </div>

      <div className="dashboard-footer">
        <p>{message}</p>
      </div>
    </section>
  )
}

export default FeatureEngineering
