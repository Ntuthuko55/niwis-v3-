import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertCircle,
  BarChart2,
  Calendar,
  ChevronRight,
  Clock,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  Layers,
  MapPin,
  Maximize2,
  RefreshCw,
  Sliders,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  analyze,
  downloadPdfReport,
  exportAnalysisJSON,
  getDashboardOverview,
  loadProvince,
  setDateColumn,
} from '../services/api'
import AutocorrelationAnalysis from './AutocorrelationAnalysis'
import CycleAnalysis from './CycleAnalysis'
import DataPreview from './DataPreview'
import DecompositionAnalysis from './DecompositionAnalysis'
import PartialAutocorrelationAnalysis from './PartialAutocorrelationAnalysis'
import SeasonalAnalysis from './SeasonalAnalysis'
import SouthAfricaProvinceMap from './SouthAfricaProvinceMap'
import SpectralAnalysis from './SpectralAnalysis'
import StationarityAnalysis from './StationarityAnalysis'
import WaveletAnalysis from './WaveletAnalysis'

const PROVINCES = [
  ['gauteng', 'Gauteng', 'GP'],
  ['western-cape', 'Western Cape', 'WC'],
  ['kwa-zulu-natal', 'KwaZulu-Natal', 'KZN'],
  ['eastern-cape', 'Eastern Cape', 'EC'],
  ['limpopo', 'Limpopo', 'LP'],
  ['mpumalanga', 'Mpumalanga', 'MP'],
  ['north-west', 'North West', 'NW'],
  ['free-state', 'Free State', 'FS'],
  ['northern-cape', 'Northern Cape', 'NC'],
]

const TABS = [
  { id: 'overview', label: 'Executive Overview', icon: Activity, desc: 'Master visualizer & dataset KPIs' },
  { id: 'trend', label: 'Trend & Regression', icon: TrendingUp, desc: 'Mann-Kendall, Sen slope & polynomials' },
  { id: 'seasonal', label: 'Seasonality & Calendar', icon: Calendar, desc: 'Monthly averages, polar radar & heatmap' },
  { id: 'cycle', label: 'Cycle & Turning Points', icon: RefreshCw, desc: 'HP filter, peaks, troughs & duration' },
  { id: 'decomposition', label: 'STL Decomposition', icon: Layers, desc: 'Observed, trend, seasonal & residual' },
  { id: 'stationarity', label: 'Stationarity & Tests', icon: Sliders, desc: 'ADF, KPSS, PP & differencing' },
  { id: 'autocorrelation', label: 'Autocorrelation (ACF)', icon: BarChart2, desc: '95% Bartlett bounds & persistence' },
  { id: 'pacf', label: 'Partial ACF (PACF)', icon: Filter, desc: 'Direct lag relationship & AR guidance' },
  { id: 'spectral', label: 'Spectral & FFT', icon: Zap, desc: 'Periodogram & dominant cycle peaks' },
  { id: 'wavelet', label: 'Wavelet Scalogram', icon: Clock, desc: '2D time-frequency power & shocks' },
  { id: 'change_point', label: 'Change Point Detection', icon: AlertCircle, desc: 'Structural breaks & regime shifts' },
]

export default function TimeSeriesDashboard() {
  const [selectedProvince, setSelectedProvince] = useState('gauteng')
  const [dataset, setDataset] = useState(null)
  const [selectedColumn, setSelectedColumn] = useState('')
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [overviewData, setOverviewData] = useState(null)
  const [tabResult, setTabResult] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [message, setMessage] = useState('')
  const [maOverlays, setMaOverlays] = useState({ ma7: true, ma30: true, ma90: false, trend: true })

  // Auto-load default province on mount
  useEffect(() => {
    onSelectProvince('gauteng')
  }, [])

  const onSelectProvince = async (provinceId) => {
    setSelectedProvince(provinceId)
    setLoading(true)
    setMessage(`Loading ${PROVINCES.find(([id]) => id === provinceId)?.[1] || provinceId} climate series...`)
    try {
      const data = await loadProvince(provinceId)
      setDataset(data)
      const numCols = data.dataset_summary?.numeric_columns || []
      const defaultCol = numCols.includes('daily_rainfall')
        ? 'daily_rainfall'
        : numCols.includes('daily_tmax')
        ? 'daily_tmax'
        : numCols[0] || ''
      setSelectedColumn(defaultCol)
      setMessage(`${PROVINCES.find(([id]) => id === provinceId)?.[1]} dataset loaded successfully.`)
      // Refresh dashboard overview
      if (defaultCol) {
        fetchOverview(data.dataset_id, data.index_column || 'date', defaultCol)
      }
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Unable to load provincial dataset.')
    } finally {
      setLoading(false)
    }
  }

  const fetchOverview = async (datasetId, dateCol, col) => {
    if (!datasetId || !col) return
    setAnalyzing(true)
    try {
      const overview = await getDashboardOverview(datasetId, dateCol, col)
      setOverviewData(overview)
    } catch (err) {
      console.error('Overview fetch error:', err)
    } finally {
      setAnalyzing(false)
    }
  }

  // Handle variable change
  const handleColumnChange = (newCol) => {
    setSelectedColumn(newCol)
    setTabResult(null)
    if (dataset) {
      const dateCol = dataset.index_column || dataset.inferred_time_columns?.[0] || 'date'
      fetchOverview(dataset.dataset_id, dateCol, newCol)
      if (activeTab !== 'overview') {
        loadTabAnalysis(activeTab, newCol)
      }
    }
  }

  // Load specific tab analysis on demand
  const loadTabAnalysis = async (tabId, colOverride = null) => {
    if (!dataset) return
    const col = colOverride || selectedColumn
    if (!col) return

    setAnalyzing(true)
    try {
      if (tabId === 'pacf') {
        const res = await analyze(dataset.dataset_id, 'partial_autocorrelation', col, { nlags: 20 })
        setTabResult(res.results || res)
      } else if (tabId === 'change_point') {
        const res = await analyze(dataset.dataset_id, 'change_point', col, {})
        setTabResult(res.results || res)
      } else if (['trend', 'seasonal', 'cycle', 'decomposition', 'stationarity', 'autocorrelation', 'spectral', 'wavelet'].includes(tabId)) {
        const res = await analyze(dataset.dataset_id, tabId, col, { period: 12, nlags: 20 })
        setTabResult(res.results || res)
      }
    } catch (err) {
      console.error(`Error loading ${tabId}:`, err)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleTabClick = (tabId) => {
    setActiveTab(tabId)
    if (tabId !== 'overview') {
      loadTabAnalysis(tabId)
    }
  }

  const handleExportPDF = async () => {
    if (!dataset || !selectedColumn) return
    setExporting(true)
    try {
      const blob = await downloadPdfReport(
        dataset.dataset_id,
        activeTab,
        selectedColumn,
        { period: 12 }
      )
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `timeseries_report_${selectedColumn}_${activeTab}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.parentNode.removeChild(link)
    } catch (err) {
      alert('Unable to generate PDF report. Please ensure the analysis is loaded.')
    } finally {
      setExporting(false)
    }
  }

  const handleExportJSON = async () => {
    if (!dataset || !selectedColumn) return
    try {
      await exportAnalysisJSON(
        dataset.dataset_id,
        activeTab,
        selectedColumn
      )
    } catch (err) {
      alert('Export failed.')
    }
  }

  const dateColumn = dataset?.index_column || dataset?.inferred_time_columns?.[0] || 'date'
  const numericColumns = dataset?.dataset_summary?.numeric_columns || []
  const summary = overviewData?.summary || {}
  const trendData = overviewData?.trend || tabResult

  const provinceSelectorData = useMemo(
    () =>
      PROVINCES.map(([id, label]) => ({
        province: label,
        value: id === selectedProvince ? 0.42 : -0.25 - (PROVINCES.findIndex(([provinceId]) => provinceId === id) % 4) * 0.08,
      })),
    [selectedProvince]
  )

  const selectedProvinceLabel = PROVINCES.find(([id]) => id === selectedProvince)?.[1] || 'Gauteng'

  // Master Chart Data formatting for Overview
  const masterChartData = useMemo(() => {
    if (!overviewData?.trend?.index || !overviewData?.trend?.values) return []
    const idx = overviewData.trend.index
    const vals = overviewData.trend.values
    const trendVals = overviewData.trend.trend || []
    const roll7 = overviewData.trend.moving_average?.['7d'] || []
    const roll30 = overviewData.trend.moving_average?.['30d'] || []
    const roll90 = overviewData.trend.moving_average?.['90d'] || []

    const step = Math.max(1, Math.floor(idx.length / 600))
    const points = []
    for (let i = 0; i < idx.length; i += step) {
      points.push({
        date: String(idx[i]).slice(0, 10),
        raw: vals[i] != null ? Number(vals[i]) : null,
        trend: trendVals[i] != null ? Number(trendVals[i]) : null,
        ma7: roll7[i] != null ? Number(roll7[i]) : null,
        ma30: roll30[i] != null ? Number(roll30[i]) : null,
        ma90: roll90[i] != null ? Number(roll90[i]) : null,
      })
    }
    return points
  }, [overviewData])

  return (
    <div className="ts-studio">
      {/* Studio Header */}
      <header className="ts-header">
        <div className="ts-header-left">
          <div className="ts-badge-pill">
            <Sparkles size={14} />
            <span>Department of Water and Sanitation · NIWIS</span>
          </div>
          <h1>Climate &amp; Weather Observatory</h1>
          <p>
            Provincial time-series monitoring, diagnostic analysis and evidence-ready reporting.
          </p>
        </div>
        <div className="ts-header-actions">
          <button
            className="ts-btn-primary"
            onClick={handleExportPDF}
            disabled={exporting || !selectedColumn}
            title="Generate executive PDF report for active analysis"
          >
            <FileText size={15} />
            <span>{exporting ? 'Generating PDF…' : 'Export PDF Report'}</span>
          </button>
        </div>
      </header>

      <section className="ts-province-map-panel">
        <div className="ts-map-header">
          <div className="ts-control-label">
            <MapPin size={13} />
            <span>1 · Study area</span>
          </div>
          <span className="ts-map-status-pill">{loading ? 'Loading province…' : `${PROVINCES.find(([id]) => id === selectedProvince)?.[1] || 'Province'} selected`}</span>
        </div>

        <div className="ts-province-selector-layout">
          <div className="ts-map-geo-wrap">
            <SouthAfricaProvinceMap
              provinceData={provinceSelectorData}
              selectedProvince={selectedProvinceLabel}
              onProvinceClick={(provinceName) => {
                const match = PROVINCES.find(([, label]) => label === provinceName)
                if (match) onSelectProvince(match[0])
              }}
              height={224}
              selectorOnly
            />
          </div>

          <div className="ts-province-selector-copy">
            <div>
              <span className="ts-selector-eyebrow">Selected province</span>
              <h3>{selectedProvinceLabel}</h3>
              <p>Live NIWIS climate record · choose another province to update the study area.</p>
            </div>
            <div className="ts-province-chips">
              {PROVINCES.map(([id, label, short]) => (
                <button
                  key={id}
                  className={`ts-prov-chip ${selectedProvince === id ? 'active' : ''}`}
                  onClick={() => onSelectProvince(id)}
                  disabled={loading}
                >
                  <span className="chip-code">{short}</span>
                  <span className="chip-name">{label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Dataset Selection Bar */}
      <section className="ts-control-bar">
        <div className="ts-variable-picker" style={{ width: '100%' }}>
          <div className="ts-control-label">
            <Filter size={13} />
            <span>2 · Analysis variable</span>
          </div>
          <select
            value={selectedColumn}
            onChange={(e) => handleColumnChange(e.target.value)}
            disabled={loading || numericColumns.length === 0}
            className="ts-select"
          >
            {numericColumns.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Executive KPI Summary Cards */}
      <div className="ts-results-heading">
        <div>
          <span>Current series</span>
          <strong>{selectedProvinceLabel} · {selectedColumn || 'Loading variable'}</strong>
        </div>
        <small>NIWIS climate warehouse · live provincial record</small>
      </div>
      <section className="ts-kpi-grid">
        <div className="ts-kpi-card">
          <div className="ts-kpi-head">
            <span>OBSERVATIONS</span>
            <Activity size={16} className="text-teal" />
          </div>
          <strong>{summary.row_count ? summary.row_count.toLocaleString() : dataset?.row_count?.toLocaleString() || '—'}</strong>
          <small>
            {summary.date_range?.start ? `${String(summary.date_range.start).slice(0, 10)} → ${String(summary.date_range.end).slice(0, 10)}` : 'Full temporal coverage'}
          </small>
        </div>

        <div className="ts-kpi-card">
          <div className="ts-kpi-head">
            <span>SERIES MEAN ± STD</span>
            <Sliders size={16} className="text-amber" />
          </div>
          <strong>
            {summary.mean_value != null ? summary.mean_value.toFixed(2) : '—'}
            <small style={{ fontWeight: 400, fontSize: '0.85rem', color: '#64748b' }}>
              {summary.std_value != null ? ` ± ${summary.std_value.toFixed(2)}` : ''}
            </small>
          </strong>
          <small>
            Min: {summary.min_value != null ? summary.min_value.toFixed(2) : '—'} · Max: {summary.max_value != null ? summary.max_value.toFixed(2) : '—'}
          </small>
        </div>

        <div className="ts-kpi-card">
          <div className="ts-kpi-head">
            <span>MISSING VALUES</span>
            <AlertCircle size={16} className="text-coral" />
          </div>
          <strong>
            {summary.missing_values != null ? `${summary.missing_values} (${summary.missing_percentage?.toFixed(1)}%)` : '0 (0.0%)'}
          </strong>
          <small>Data quality index: {100 - (summary.missing_percentage || 0).toFixed(1)}%</small>
        </div>

        <div className="ts-kpi-card">
          <div className="ts-kpi-head">
            <span>STATIONARITY STATUS</span>
            <RefreshCw size={16} className="text-indigo" />
          </div>
          <strong>
            {overviewData?.stationarity?.decision ? (
              <span className={`ts-badge ${overviewData.stationarity.stationary ? 'stationary' : 'non-stationary'}`}>
                {overviewData.stationarity.decision}
              </span>
            ) : (
              'Analysing…'
            )}
          </strong>
          <small>{overviewData?.stationarity?.stationary ? 'No unit root detected' : 'Differencing recommended'}</small>
        </div>
      </section>

      {/* Interactive Tabs Navigation */}
      <nav className="ts-tab-bar" aria-label="Analysis Tabs">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              className={`ts-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => handleTabClick(tab.id)}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </nav>

      {/* Main Studio Viewport */}
      <main className="ts-viewport">
        <div className="ts-content-stack">
          {analyzing && (
            <div className="ts-loading-curtain">
              <div className="spinner" />
              <span>Computing mathematical algorithms & diagnostics…</span>
            </div>
          )}

          {/* TAB 1: EXECUTIVE OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="ts-tab-content">
            <div className="ts-chart-card">
              <div className="ts-chart-header">
                <div>
                  <h3>Master Time Series Visualizer: {selectedColumn}</h3>
                  <p>Executive one-line view of the observed series with a directional trend overlay.</p>
                </div>
              </div>

              <div className="ts-chart-body" style={{ height: 380 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={masterChartData} margin={{ top: 12, right: 18, left: 0, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#dbe7f1" />
                    <XAxis dataKey="date" minTickGap={45} stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(val) => (val != null ? Number(val).toFixed(3) : '—')}
                      contentStyle={{
                        borderRadius: 12,
                        border: '1px solid #d7e4ef',
                        background: 'rgba(255,255,255,0.96)',
                        color: '#0f172a',
                        boxShadow: '0 10px 20px rgba(15, 23, 42, 0.08)',
                      }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="raw"
                      name="Observed Series"
                      stroke="#0b6e69"
                      dot={false}
                      strokeWidth={2.2}
                      activeDot={{ r: 5, fill: '#0b6e69', stroke: '#ffffff', strokeWidth: 2 }}
                      isAnimationActive={false}
                    />
                    {maOverlays.trend && (
                      <Line
                        type="monotone"
                        dataKey="trend"
                        name="Trend"
                        stroke="#e47738"
                        strokeDasharray="5 5"
                        dot={false}
                        strokeWidth={2.2}
                        isAnimationActive={false}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Quick Actions & Features Preview Grid */}
            <div className="ts-overview-bottom-grid">
              <div className="ts-panel-card">
                <h3>Executive Summary & Statistics</h3>
                <div className="ts-summary-table">
                  <div><span>Target Variable:</span> <strong>{selectedColumn}</strong></div>
                  <div><span>Time Axis Index:</span> <strong>{dateColumn}</strong></div>
                  <div><span>Trend Direction:</span> <strong>{trendData?.linear_regression?.slope > 0 ? 'Increasing (+)' : trendData?.linear_regression?.slope < 0 ? 'Decreasing (-)' : 'Stable'}</strong></div>
                  <div><span>Trend Slope:</span> <strong>{trendData?.linear_regression?.slope != null ? `${trendData.linear_regression.slope.toFixed(5)} units/step` : '—'}</strong></div>
                  <div><span>Model Fit (R²):</span> <strong>{trendData?.linear_regression?.r_squared != null ? `${(trendData.linear_regression.r_squared * 100).toFixed(1)}%` : '—'}</strong></div>
                  <div><span>Trend P-Value:</span> <strong>{trendData?.linear_regression?.p_value != null ? trendData.linear_regression.p_value.toFixed(5) : '—'}</strong></div>
                </div>
              </div>

              <div className="ts-panel-card">
                <h3>Data Quality & Export Center</h3>
                <p>Export ready-to-publish scientific reports or clean analytical data matrices for downstream machine learning.</p>
                <div className="ts-export-btn-group">
                  <button className="ts-btn-outline" onClick={handleExportPDF} disabled={exporting}>
                    <FileText size={15} /> Download PDF Report
                  </button>
                  <button className="ts-btn-outline" onClick={handleExportJSON}>
                    <Download size={15} /> Download JSON Data
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: TREND ANALYSIS */}
        {activeTab === 'trend' && (
          <div className="ts-tab-content">
            {tabResult || overviewData?.trend ? (
              <div className="ts-tab-inner">
                <div className="ts-section-intro">
                  <p className="eyebrow">TREND ANALYSIS & MANN-KENDALL</p>
                  <h2>Long-Term Directional Movement: {selectedColumn}</h2>
                  <p>{(tabResult || overviewData?.trend)?.interpretation?.summary || 'Linear and non-linear trend models fitted across the full historical time span.'}</p>
                </div>

                <div className="ts-trend-kpi-row">
                  <div className="ts-stat-badge">
                    <span>DIRECTION</span>
                    <strong>{(tabResult || overviewData?.trend)?.interpretation?.direction || 'Stable'}</strong>
                  </div>
                  <div className="ts-stat-badge">
                    <span>SLOPE (SEN / OLS)</span>
                    <strong>{(tabResult || overviewData?.trend)?.linear_regression?.slope?.toFixed(5)}</strong>
                  </div>
                  <div className="ts-stat-badge">
                    <span>P-VALUE</span>
                    <strong>{(tabResult || overviewData?.trend)?.linear_regression?.p_value?.toFixed(5)}</strong>
                  </div>
                  <div className="ts-stat-badge">
                    <span>EXPLANATORY POWER (R²)</span>
                    <strong>{(((tabResult || overviewData?.trend)?.linear_regression?.r_squared || 0) * 100).toFixed(1)}%</strong>
                  </div>
                </div>

                <div className="ts-chart-card" style={{ marginTop: 20 }}>
                  <h3>Polynomial & Exponential Trend Models</h3>
                  <div style={{ height: 340 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={masterChartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="date" minTickGap={45} />
                        <YAxis />
                        <Tooltip formatter={(v) => (v != null ? Number(v).toFixed(3) : '—')} />
                        <Legend />
                        <Line dataKey="raw" name="Observed" stroke="#64748b" dot={false} />
                        <Line dataKey="trend" name="Linear Trend Line" stroke="#e47738" strokeWidth={2.5} dot={false} />
                        <Line dataKey="ma30" name="30-Day Smoothing" stroke="#0b6e69" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            ) : (
              <div className="ts-empty-state">Select a variable and wait for analysis to load.</div>
            )}
          </div>
        )}

        {/* TAB 3: SEASONALITY */}
        {activeTab === 'seasonal' && (
          <div className="ts-tab-content">
            {tabResult || overviewData?.seasonal ? (
              <SeasonalAnalysis results={tabResult || overviewData.seasonal} />
            ) : (
              <div className="ts-empty-state">Seasonal analysis loading…</div>
            )}
          </div>
        )}

        {/* TAB 4: CYCLE ANALYSIS */}
        {activeTab === 'cycle' && (
          <div className="ts-tab-content">
            {tabResult ? (
              <CycleAnalysis results={tabResult} />
            ) : (
              <div className="ts-empty-state">Cycle analysis loading…</div>
            )}
          </div>
        )}

        {/* TAB 5: DECOMPOSITION */}
        {activeTab === 'decomposition' && (
          <div className="ts-tab-content">
            {tabResult ? (
              <DecompositionAnalysis results={tabResult} />
            ) : (
              <div className="ts-empty-state">Decomposition analysis loading…</div>
            )}
          </div>
        )}

        {/* TAB 6: STATIONARITY */}
        {activeTab === 'stationarity' && (
          <div className="ts-tab-content">
            {tabResult || overviewData?.stationarity ? (
              <StationarityAnalysis results={tabResult || overviewData.stationarity} />
            ) : (
              <div className="ts-empty-state">Stationarity test results loading…</div>
            )}
          </div>
        )}

        {/* TAB 7: AUTOCORRELATION (ACF) */}
        {activeTab === 'autocorrelation' && (
          <div className="ts-tab-content">
            {tabResult || overviewData?.autocorrelation ? (
              <AutocorrelationAnalysis results={tabResult || overviewData.autocorrelation} />
            ) : (
              <div className="ts-empty-state">Autocorrelation analysis loading…</div>
            )}
          </div>
        )}

        {/* TAB 8: PARTIAL AUTOCORRELATION (PACF) */}
        {activeTab === 'pacf' && (
          <div className="ts-tab-content">
            {tabResult ? (
              <PartialAutocorrelationAnalysis results={tabResult} />
            ) : (
              <div className="ts-empty-state">Partial autocorrelation (PACF) loading…</div>
            )}
          </div>
        )}

        {/* TAB 9: SPECTRAL ANALYSIS */}
        {activeTab === 'spectral' && (
          <div className="ts-tab-content">
            {tabResult || overviewData?.spectral ? (
              <SpectralAnalysis results={tabResult || overviewData.spectral} />
            ) : (
              <div className="ts-empty-state">Spectral analysis loading…</div>
            )}
          </div>
        )}

        {/* TAB 10: WAVELET ANALYSIS */}
        {activeTab === 'wavelet' && (
          <div className="ts-tab-content">
            {tabResult ? (
              <WaveletAnalysis results={tabResult} />
            ) : (
              <div className="ts-empty-state">Wavelet scalogram loading…</div>
            )}
          </div>
        )}

        {/* TAB 11: CHANGE POINT DETECTION */}
        {activeTab === 'change_point' && (
          <div className="ts-tab-content">
            {tabResult || overviewData?.change_points ? (
              <div className="ts-tab-inner">
                <div className="ts-section-intro">
                  <p className="eyebrow">STRUCTURAL BREAK DETECTION</p>
                  <h2>Regime Shifts & Change Points: {selectedColumn}</h2>
                  <p>{(tabResult || overviewData?.change_points)?.explanation}</p>
                </div>
                {/* Change Points Summary */}
                <div className="ts-change-points-wrap">
                  <div className="ts-stat-badge">
                    <span>DETECTED CHANGE POINTS</span>
                    <strong>{(tabResult || overviewData?.change_points)?.timeline?.count || (tabResult || overviewData?.change_points)?.change_points?.length || 0}</strong>
                  </div>
                  <div className="ts-stat-badge">
                    <span>CONFIDENCE INDEX</span>
                    <strong>{(((tabResult || overviewData?.change_points)?.confidence || 0) * 100).toFixed(1)}%</strong>
                  </div>
                </div>
              </div>
            ) : (
              <div className="ts-empty-state">Change point detection loading…</div>
            )}
          </div>
        )}

        </div>
      </main>

      {/* Styled JSX for the Dashboard */}
      <style>{`
        .ts-studio {
          max-width: 1280px;
          margin: 0 auto;
          padding: 28px 24px 72px;
          font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: #162b31;
        }

        .ts-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 24px;
          margin-bottom: 24px;
          padding: 32px 36px;
          background: linear-gradient(120deg, #0a333c 0%, #0d5659 60%, #0b6e69 100%);
          border-radius: 20px;
          color: #fff;
          box-shadow: 0 16px 40px rgba(10, 51, 60, 0.16);
          position: relative;
          overflow: hidden;
        }

        .ts-header::after {
          content: '';
          position: absolute;
          right: -80px;
          top: -120px;
          width: 360px;
          height: 360px;
          border-radius: 50%;
          background: radial-gradient(circle, rgba(162, 236, 217, 0.15) 0%, transparent 70%);
          pointer-events: none;
        }

        .ts-header-left {
          max-width: 720px;
          position: relative;
          z-index: 1;
        }

        .ts-badge-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 999px;
          background: rgba(162, 236, 217, 0.18);
          border: 1px solid rgba(162, 236, 217, 0.3);
          color: #a2ecd9;
          font-size: 0.72rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          margin-bottom: 12px;
        }

        .ts-header h1 {
          margin: 0 0 8px;
          font-size: 2.1rem;
          letter-spacing: -0.03em;
          color: #ffffff;
        }

        .ts-header p {
          margin: 0;
          color: #d1eae4;
          font-size: 0.95rem;
          line-height: 1.55;
        }

        .ts-header-actions {
          display: flex;
          align-items: center;
          gap: 12px;
          position: relative;
          z-index: 1;
        }

        .ts-btn-glass {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 18px;
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.14);
          border: 1px solid rgba(255, 255, 255, 0.25);
          color: #ffffff;
          font-weight: 700;
          font-size: 0.85rem;
          cursor: pointer;
          backdrop-filter: blur(10px);
          transition: all 0.2s ease;
        }

        .ts-btn-glass:hover {
          background: rgba(255, 255, 255, 0.24);
          transform: translateY(-1px);
        }

        .ts-btn-primary {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 20px;
          border-radius: 10px;
          background: #e47738;
          border: 1px solid #d5692b;
          color: #ffffff;
          font-weight: 700;
          font-size: 0.85rem;
          cursor: pointer;
          box-shadow: 0 4px 14px rgba(228, 119, 56, 0.35);
          transition: all 0.2s ease;
        }

        .ts-btn-primary:hover:not(:disabled) {
          background: #d5692b;
          transform: translateY(-1px);
        }

        .ts-btn-primary:disabled {
          opacity: 0.65;
          cursor: not-allowed;
        }

        /* Control Bar */
        .ts-province-map-panel {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 16px;
          padding: 12px 12px 10px;
          box-shadow: 0 8px 24px rgba(22, 43, 49, 0.04);
          margin-bottom: 20px;
        }

        .ts-map-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 8px;
          margin-bottom: 6px;
          flex-wrap: wrap;
        }

        .ts-map-status-pill {
          display: inline-flex;
          align-items: center;
          padding: 4px 8px;
          border-radius: 999px;
          background: #ecfdf5;
          color: #065f46;
          border: 1px solid #a7f3d0;
          font-size: 0.68rem;
          font-weight: 700;
        }

        .ts-map-geo-wrap {
          width: min(320px, 38%);
          flex: 0 0 min(320px, 38%);
          background: #f7faf9;
          border: 1px solid #dfeaf2;
          border-radius: 10px;
          overflow: hidden;
          padding: 0;
        }

        .ts-province-selector-layout {
          display: flex;
          gap: 22px;
          align-items: stretch;
        }

        .ts-province-selector-copy {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: 20px;
          padding: 18px 8px 12px 0;
        }

        .ts-selector-eyebrow {
          display: block;
          margin-bottom: 6px;
          color: #0b6e69;
          font-size: 0.66rem;
          font-weight: 800;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }

        .ts-province-selector-copy h3 {
          margin: 0 0 6px;
          color: #143a3d;
          font-size: 1.35rem;
          letter-spacing: -0.025em;
        }

        .ts-province-selector-copy p {
          max-width: 440px;
          margin: 0;
          color: #64748b;
          font-size: 0.83rem;
          line-height: 1.55;
        }

        .ts-leaflet-map {
          width: 100%;
          height: 640px;
          min-height: 600px;
          background: #dfeef0;
        }

        .ts-map-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 290px;
          color: #475569;
          font-size: 0.9rem;
          font-weight: 700;
          background: linear-gradient(135deg, #effaf7 0%, #f7fbfe 100%);
        }

        .ts-map-geo-wrap .leaflet-container {
          width: 100%;
          height: 100%;
          background: #dfeef0;
        }

        .ts-map-geo-wrap .leaflet-pane,
        .ts-map-geo-wrap .leaflet-control-container {
          border-radius: 12px;
        }

        .ts-control-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 20px;
          padding: 16px 20px;
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 16px;
          margin-bottom: 22px;
          box-shadow: 0 4px 20px rgba(22, 43, 49, 0.03);
          flex-wrap: wrap;
        }

        .ts-control-label {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.73rem;
          font-weight: 800;
          color: #0b6e69;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 8px;
        }

        .ts-province-chips {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
          align-items: center;
          justify-content: flex-start;
        }

        .ts-prov-chip {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          padding: 2px 6px;
          border-radius: 6px;
          border: 1px solid #dce8e4;
          background: #f8fafc;
          color: #334155;
          font-size: 0.6rem;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.15s ease;
          line-height: 1.15;
        }

        .ts-prov-chip:hover {
          background: #f1f5f9;
          border-color: #cbd5e1;
          transform: translateY(-1px);
        }

        .ts-prov-chip.active {
          background: #0b6e69;
          color: #ffffff;
          border-color: #0b6e69;
          box-shadow: 0 2px 8px rgba(11, 110, 105, 0.18);
        }

        .chip-code {
          font-size: 0.58rem;
          font-weight: 800;
          opacity: 0.8;
        }

        .ts-variable-picker {
          min-width: 220px;
        }

        .ts-select {
          width: 100%;
          min-height: 38px;
          padding: 6px 12px;
          border-radius: 8px;
          border: 1px solid #cbd5e1;
          background: #f8fafc;
          font-size: 0.88rem;
          font-weight: 600;
          color: #0f172a;
          outline: none;
        }

        .ts-select:focus {
          border-color: #0b6e69;
          box-shadow: 0 0 0 3px rgba(11, 110, 105, 0.12);
        }

        /* Upload Collapsible */
        .ts-upload-panel {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 16px;
          padding: 24px;
          margin-bottom: 22px;
          box-shadow: 0 8px 24px rgba(22, 43, 49, 0.05);
        }

        .ts-upload-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .ts-btn-close {
          background: transparent;
          border: none;
          font-size: 1.2rem;
          color: #64748b;
          cursor: pointer;
        }

        /* KPI Cards Grid */
        .ts-kpi-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
          margin-bottom: 24px;
        }

        .ts-kpi-card {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 14px;
          padding: 18px 20px;
          box-shadow: 0 4px 16px rgba(22, 43, 49, 0.03);
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .ts-kpi-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .ts-kpi-head span {
          font-size: 0.72rem;
          font-weight: 800;
          color: #64748b;
          letter-spacing: 0.06em;
        }

        .ts-kpi-card strong {
          font-size: 1.35rem;
          font-weight: 800;
          color: #0f172a;
          letter-spacing: -0.02em;
          margin: 4px 0 2px;
        }

        .ts-kpi-card small {
          font-size: 0.78rem;
          color: #64748b;
          line-height: 1.4;
        }

        .ts-badge {
          display: inline-block;
          padding: 3px 9px;
          border-radius: 999px;
          font-size: 0.78rem;
          font-weight: 700;
        }

        .ts-badge.stationary {
          background: #ecfdf5;
          color: #065f46;
          border: 1px solid #a7f3d0;
        }

        .ts-badge.non-stationary {
          background: #fffbeb;
          color: #92400e;
          border: 1px solid #fde68a;
        }

        /* Tab Navigation */
        .ts-tab-bar {
          display: flex;
          gap: 6px;
          overflow-x: auto;
          padding-bottom: 8px;
          margin-bottom: 20px;
          border-bottom: 2px solid #e2e8f0;
        }

        .ts-tab-btn {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 10px 16px;
          border-radius: 10px;
          background: transparent;
          border: none;
          color: #475569;
          font-size: 0.85rem;
          font-weight: 700;
          cursor: pointer;
          white-space: nowrap;
          transition: all 0.15s ease;
        }

        .ts-tab-btn:hover {
          background: #f1f5f9;
          color: #0f172a;
        }

        .ts-tab-btn.active {
          background: #0b6e69;
          color: #ffffff;
          box-shadow: 0 4px 12px rgba(11, 110, 105, 0.2);
        }

        /* Viewport & Cards */
        .ts-viewport {
          position: relative;
          min-height: 420px;
          width: 100%;
        }

        .ts-content-stack {
          display: flex;
          flex-direction: column;
          gap: 28px;
          width: 100%;
        }

        .ts-tab-content,
        .ts-tab-inner,
        .ts-forecasting-block,
        .ts-forecasting-shell {
          width: 100%;
          display: block;
        }

        .ts-forecasting-block {
          margin-top: 4px;
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 18px;
          padding: 28px;
          box-shadow: 0 6px 20px rgba(22, 43, 49, 0.04);
        }

        .ts-section-intro {
          margin-bottom: 20px;
        }

        .ts-section-intro .eyebrow {
          margin-bottom: 10px;
        }

        .ts-section-intro h2 {
          margin: 0 0 8px;
          font-size: clamp(1.35rem, 2vw, 2rem);
          letter-spacing: -0.03em;
          color: #0f172a;
        }

        .ts-section-intro p {
          margin: 0;
          color: #64748b;
          line-height: 1.6;
        }

        .ts-loading-curtain {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 24px;
          margin-bottom: 20px;
          background: #f0fdf4;
          border: 1px solid #bbf7d0;
          border-radius: 12px;
          color: #166534;
          font-weight: 700;
          font-size: 0.9rem;
        }

        .ts-chart-card {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 16px;
          padding: 24px;
          box-shadow: 0 6px 20px rgba(22, 43, 49, 0.04);
          margin-bottom: 22px;
        }

        .ts-chart-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          margin-bottom: 18px;
          flex-wrap: wrap;
        }

        .ts-chart-header h3 {
          margin: 0 0 4px;
          font-size: 1.15rem;
          color: #0f172a;
        }

        .ts-chart-header p {
          margin: 0;
          font-size: 0.85rem;
          color: #64748b;
        }

        .ts-chart-toggles {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .toggle-chip {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 6px;
          background: #f1f5f9;
          border: 1px solid #cbd5e1;
          font-size: 0.75rem;
          font-weight: 600;
          cursor: pointer;
          user-select: none;
        }

        .ts-overview-bottom-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 20px;
        }

        .ts-panel-card {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 16px;
          padding: 22px;
          box-shadow: 0 4px 16px rgba(22, 43, 49, 0.03);
        }

        .ts-panel-card h3 {
          margin: 0 0 14px;
          font-size: 1.05rem;
          color: #0f172a;
        }

        .ts-summary-table {
          display: grid;
          gap: 10px;
        }

        .ts-summary-table div {
          display: flex;
          justify-content: space-between;
          border-bottom: 1px solid #f1f5f9;
          padding-bottom: 6px;
          font-size: 0.85rem;
        }

        .ts-summary-table span {
          color: #64748b;
        }

        .ts-summary-table strong {
          color: #0f172a;
        }

        .ts-export-btn-group {
          display: flex;
          gap: 12px;
          margin-top: 18px;
          flex-wrap: wrap;
        }

        .ts-btn-outline {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 9px 16px;
          border-radius: 8px;
          border: 1px solid #cbd5e1;
          background: #f8fafc;
          color: #0f172a;
          font-size: 0.85rem;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .ts-btn-outline:hover {
          background: #f1f5f9;
          border-color: #94a3b8;
        }

        .ts-trend-kpi-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 14px;
          margin-top: 16px;
        }

        .ts-stat-badge {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 12px;
          padding: 14px 16px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        }

        .ts-stat-badge span {
          display: block;
          font-size: 0.7rem;
          font-weight: 800;
          color: #64748b;
          letter-spacing: 0.06em;
          margin-bottom: 4px;
        }

        .ts-stat-badge strong {
          display: block;
          font-size: 1.15rem;
          color: #0f172a;
        }

        .ts-empty-state {
          padding: 48px;
          text-align: center;
          background: #ffffff;
          border: 1px dashed #cbd5e1;
          border-radius: 16px;
          color: #64748b;
          font-size: 0.95rem;
        }

        @media (max-width: 960px) {
          .ts-province-selector-layout {
            gap: 14px;
          }

          .ts-map-geo-wrap {
            width: min(290px, 42%);
            flex-basis: min(290px, 42%);
          }

          .ts-kpi-grid {
            grid-template-columns: repeat(2, 1fr);
          }
          .ts-overview-bottom-grid {
            grid-template-columns: 1fr;
          }
          .ts-trend-kpi-row {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 640px) {
          .ts-province-selector-layout {
            flex-direction: column;
          }

          .ts-map-geo-wrap {
            width: 100%;
            flex-basis: auto;
          }

          .ts-province-selector-copy {
            padding: 0 2px 4px;
          }

          .ts-header {
            flex-direction: column;
            padding: 24px 20px;
          }
          .ts-kpi-grid {
            grid-template-columns: 1fr;
          }
          .ts-control-bar {
            flex-direction: column;
            align-items: stretch;
          }
        }

        /* NIWIS observatory system: practical government information design. */
        .ts-studio {
          max-width: 1180px;
          padding: 20px 20px 56px;
        }

        .ts-header {
          align-items: center;
          margin-bottom: 14px;
          padding: 20px 24px;
          border: 1px solid #164e63;
          border-radius: 10px;
          background: linear-gradient(110deg, #103c4b, #175d6a);
          box-shadow: none;
        }

        .ts-header::after { display: none; }
        .ts-badge-pill {
          margin-bottom: 8px;
          padding: 3px 8px;
          background: rgba(255,255,255,.08);
          border-color: rgba(255,255,255,.18);
          color: #c8e4e6;
          font-size: .61rem;
        }
        .ts-header h1 { margin-bottom: 4px; font-size: 1.65rem; letter-spacing: -.025em; }
        .ts-header p { max-width: 680px; font-size: .8rem; line-height: 1.45; }
        .ts-btn-primary { padding: 8px 12px; border-radius: 6px; background: #d89b37; border-color: #c78a2d; box-shadow: none; font-size: .74rem; }

        .ts-province-map-panel, .ts-control-bar {
          margin-bottom: 12px;
          border-color: #d7e1e2;
          border-radius: 10px;
          box-shadow: none;
        }
        .ts-province-map-panel { padding: 12px; }
        .ts-map-header { margin-bottom: 10px; }
        .ts-map-status-pill { padding: 3px 7px; border-radius: 4px; font-size: .62rem; }
        .ts-province-selector-layout { gap: 18px; }
        .ts-map-geo-wrap { width: min(275px, 35%); flex-basis: min(275px, 35%); border-radius: 7px; }
        .ts-province-selector-copy { gap: 13px; padding: 8px 4px 4px 0; }
        .ts-selector-eyebrow { margin-bottom: 4px; font-size: .59rem; }
        .ts-province-selector-copy h3 { margin-bottom: 3px; font-size: 1.08rem; }
        .ts-province-selector-copy p { font-size: .73rem; line-height: 1.4; }
        .ts-province-chips { gap: 5px; }
        .ts-prov-chip { min-height: 28px; padding: 4px 7px; border-radius: 5px; font-size: .63rem; }
        .chip-code { font-size: .56rem; }

        .ts-control-bar { padding: 11px 14px; }
        .ts-control-label { margin-bottom: 5px; font-size: .63rem; }
        .ts-select { min-height: 34px; padding: 5px 9px; border-radius: 5px; font-size: .8rem; }
        .ts-results-heading { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin: 15px 0 8px; }
        .ts-results-heading span { display: block; margin-bottom: 3px; color: #5d7479; font-size: .59rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
        .ts-results-heading strong { color: #173f48; font-size: .96rem; }
        .ts-results-heading small { color: #6b7f85; font-size: .67rem; }

        .ts-kpi-grid { gap: 9px; margin-bottom: 14px; }
        .ts-kpi-card { min-height: 112px; padding: 12px 14px; border-color: #d7e1e2; border-radius: 8px; box-shadow: none; }
        .ts-kpi-head span { font-size: .61rem; }
        .ts-kpi-card strong { margin: 2px 0; font-size: 1.12rem; }
        .ts-kpi-card small { font-size: .67rem; }
        .ts-badge { padding: 3px 7px; font-size: .68rem; }

        .ts-tab-bar { gap: 0; margin-bottom: 14px; padding: 0; border-bottom: 1px solid #cedbdd; }
        .ts-tab-btn { padding: 9px 12px; border-radius: 0; color: #587078; font-size: .72rem; }
        .ts-tab-btn.active { color: #0f6463; background: #edf6f4; box-shadow: inset 0 -3px 0 #0f7771; }
        .ts-tab-btn:hover { background: #f3f7f7; }
        .ts-content-stack { gap: 16px; }
        .ts-chart-card, .ts-panel-card, .ts-forecasting-block { margin-bottom: 14px; padding: 16px; border-color: #d7e1e2; border-radius: 9px; box-shadow: none; }
        .ts-chart-header { margin-bottom: 10px; }
        .ts-chart-header h3 { font-size: .95rem; }
        .ts-chart-header p, .ts-section-intro p { font-size: .75rem; }
        .ts-chart-body { height: 320px !important; }
        .ts-panel-card h3 { margin-bottom: 9px; font-size: .9rem; }
        .ts-summary-table { gap: 7px; }
        .ts-summary-table div { padding-bottom: 5px; font-size: .76rem; }
        .ts-btn-outline { padding: 7px 10px; border-radius: 5px; font-size: .7rem; }

        @media (max-width: 640px) {
          .ts-studio { padding: 12px 12px 40px; }
          .ts-header { padding: 16px; }
          .ts-results-heading { align-items: flex-start; flex-direction: column; gap: 3px; }
          .ts-map-geo-wrap { width: 100%; flex-basis: auto; }
        }
      `}</style>
    </div>
  )
}
