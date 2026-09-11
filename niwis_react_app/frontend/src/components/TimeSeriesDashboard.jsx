import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertCircle,
  BarChart2,
  Calendar,
  ChevronRight,
  Clock,
  Cpu,
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
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet'
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
import FeatureEngineering from './FeatureEngineering'
import ModelTraining from './ModelTraining'
import PartialAutocorrelationAnalysis from './PartialAutocorrelationAnalysis'
import SeasonalAnalysis from './SeasonalAnalysis'
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

const SA_TOPOJSON_URL = '/za_provinces.json'
const OSM_TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const CARTO_POSITRON_URL = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
// CARTO API key: prefer environment variable, fall back to provided key
// Read CARTO key from environment; do not fallback to a hard-coded key in source.
const CARTO_KEY = import.meta.env.VITE_CARTO_KEY || null
const CARTO_RASTER_URL = CARTO_KEY ? `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${CARTO_KEY}` : null

const normalizeProvinceKey = (value = '') => String(value).toLowerCase().replace(/[^a-z]/g, '')

const provinceIdFromGeoName = (name) => {
  const normalized = normalizeProvinceKey(name)
  return PROVINCES.find(([id]) => normalizeProvinceKey(id) === normalized)?.[0] || null
}

const PROVINCE_CENTROIDS = {
  'western-cape': '148,260',
  'northern-cape': '250,190',
  'north-west': '338,180',
  'free-state': '364,286',
  'gauteng': '448,264',
  'limpopo': '486,176',
  'mpumalanga': '536,286',
  'eastern-cape': '360,382',
  'kwa-zulu-natal': '520,374',
}

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
  { id: 'features', label: 'Feature Engineering', icon: Cpu, desc: 'Lags, rolling stats, EMA & date features' },
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
  const [mapData, setMapData] = useState(null)
  // default to CARTO raster tiles when key present, otherwise OSM
  const [tileUrl, setTileUrl] = useState(CARTO_KEY && CARTO_RASTER_URL ? CARTO_RASTER_URL : OSM_TILE_URL)
  const [maOverlays, setMaOverlays] = useState({ ma7: true, ma30: true, ma90: false, trend: true })

  useEffect(() => {
    fetch(SA_TOPOJSON_URL)
      .then((response) => response.json())
      .then((data) => setMapData(data))
      .catch(() => setMapData(null))
  }, [])

  // If OSM tiles fail (network or provider issues), fall back to Carto Positron
  const handleTileError = () => {
    if (tileUrl !== CARTO_POSITRON_URL) setTileUrl(CARTO_POSITRON_URL)
  }

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
      if (activeTab !== 'overview' && activeTab !== 'features') {
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
    if (tabId !== 'overview' && tabId !== 'features') {
      loadTabAnalysis(tabId)
    }
  }

  const handleExportPDF = async () => {
    if (!dataset || !selectedColumn) return
    setExporting(true)
    try {
      const blob = await downloadPdfReport(
        dataset.dataset_id,
        activeTab === 'features' ? 'trend' : activeTab,
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
        activeTab === 'features' ? 'trend' : activeTab,
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
            <span>TIME SERIES INTELLIGENCE</span>
          </div>
          <h1>Time Series Analysis Studio</h1>
          <p>
            Comprehensive diagnostic laboratory: explore trends, cyclical rhythms, stationarity, spectral frequencies, wavelets, and structural breaks.
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
            <span>South Africa Province Selector</span>
          </div>
          <span className="ts-map-status-pill">{loading ? 'Loading province…' : `${PROVINCES.find(([id]) => id === selectedProvince)?.[1] || 'Province'} selected`}</span>
        </div>

        <div className="ts-map-geo-wrap">
          <MapContainer center={[-28.5, 24.7]} zoom={6} minZoom={5} maxZoom={10} scrollWheelZoom className="ts-leaflet-map">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | &copy; <a href="https://carto.com/attributions">CARTO</a>'
              url={tileUrl}
              eventHandlers={{
                tileerror: handleTileError,
              }}
            />
            {mapData && (
              <GeoJSON
                data={mapData}
                style={(feature) => {
                  const provinceId = feature && feature.properties ? provinceIdFromGeoName(feature.properties.name) : null
                  const selected = provinceId === selectedProvince
                  return {
                    color: '#ffffff',
                    weight: 1.3,
                    opacity: 1,
                    fillColor: selected ? '#e47738' : '#dfeef0',
                    fillOpacity: 0.88,
                    stroke: true,
                  }
                }}
                onEachFeature={(feature, layer) => {
                  const provinceId = feature && feature.properties ? provinceIdFromGeoName(feature.properties.name) : null
                  if (!provinceId) return
                  layer.bindTooltip(feature.properties.name)
                  layer.on({
                    click: () => onSelectProvince(provinceId),
                    mouseover: (event) => {
                      const target = event.target
                      target.setStyle({ fillColor: '#9ad1c2', weight: 1.4, fillOpacity: 0.95 })
                    },
                    mouseout: (event) => {
                      const target = event.target
                      const isSelected = provinceId === selectedProvince
                      target.setStyle({ fillColor: isSelected ? '#e47738' : '#dfeef0', weight: 1.3, fillOpacity: 0.88 })
                    },
                  })
                }}
              />
            )}
          </MapContainer>
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
      </section>

      {/* Dataset Selection Bar */}
      <section className="ts-control-bar">
        <div className="ts-variable-picker" style={{ width: '100%' }}>
          <div className="ts-control-label">
            <Filter size={13} />
            <span>Analysis Variable</span>
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
                  <p>Historical trajectory with dynamic multi-scale rolling moving averages and linear trend decomposition.</p>
                </div>
                <div className="ts-chart-toggles">
                  <label className="toggle-chip">
                    <input
                      type="checkbox"
                      checked={maOverlays.ma7}
                      onChange={(e) => setMaOverlays({ ...maOverlays, ma7: e.target.checked })}
                    />
                    <span>7-Day MA</span>
                  </label>
                  <label className="toggle-chip">
                    <input
                      type="checkbox"
                      checked={maOverlays.ma30}
                      onChange={(e) => setMaOverlays({ ...maOverlays, ma30: e.target.checked })}
                    />
                    <span>30-Day MA</span>
                  </label>
                  <label className="toggle-chip">
                    <input
                      type="checkbox"
                      checked={maOverlays.ma90}
                      onChange={(e) => setMaOverlays({ ...maOverlays, ma90: e.target.checked })}
                    />
                    <span>90-Day MA</span>
                  </label>
                  <label className="toggle-chip">
                    <input
                      type="checkbox"
                      checked={maOverlays.trend}
                      onChange={(e) => setMaOverlays({ ...maOverlays, trend: e.target.checked })}
                    />
                    <span>Linear Trend</span>
                  </label>
                </div>
              </div>

              <div className="ts-chart-body" style={{ height: 380 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={masterChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" minTickGap={45} stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(val) => (val != null ? Number(val).toFixed(3) : '—')} />
                    <Legend />
                    <Line type="monotone" dataKey="raw" name="Observed Series" stroke="#0b6e69" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                    {maOverlays.ma7 && <Line type="monotone" dataKey="ma7" name="7-Day MA" stroke="#3b82f6" dot={false} strokeWidth={1.8} isAnimationActive={false} />}
                    {maOverlays.ma30 && <Line type="monotone" dataKey="ma30" name="30-Day MA" stroke="#f59e0b" dot={false} strokeWidth={2} isAnimationActive={false} />}
                    {maOverlays.ma90 && <Line type="monotone" dataKey="ma90" name="90-Day MA" stroke="#8b5cf6" dot={false} strokeWidth={2.2} isAnimationActive={false} />}
                    {maOverlays.trend && <Line type="monotone" dataKey="trend" name="Trend" stroke="#e47738" strokeDasharray="4 4" dot={false} strokeWidth={2} isAnimationActive={false} />}
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

        {/* TAB 12: FEATURE ENGINEERING */}
        {activeTab === 'features' && dataset && (
          <div className="ts-tab-content">
            <FeatureEngineering
              datasetId={dataset.dataset_id}
              columns={numericColumns}
              dateColumn={dateColumn}
              datasetSummary={dataset.dataset_summary}
              selectedColumn={selectedColumn}
            />
          </div>
        )}

          {dataset && (
            <div className="ts-forecasting-block">
              <div className="ts-section-intro">
                <p className="eyebrow">FORECASTING STUDIO</p>
                <h2>Predictive working section for {selectedColumn || 'the active series'}</h2>
                <p>Use the forecasting controls below to generate forward-looking projections for the loaded province dataset. This remains the final section of the studio workflow, beneath the analysis stack.</p>
              </div>
              <div className="ts-forecasting-shell">
                <ModelTraining
                  datasetId={dataset.dataset_id}
                  dateColumn={dateColumn}
                  numericColumns={numericColumns}
                  allColumns={dataset.columns || []}
                />
              </div>
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
          width: 100%;
          max-width: none;
          /* extend the map full-bleed across the content area */
          margin-left: -28px;
          margin-right: -28px;
          width: calc(100% + 56px);
          background: linear-gradient(135deg, #effaf7 0%, #f7fbfe 100%);
          border: 1px solid #dfeaf2;
          border-radius: 12px;
          overflow: hidden;
          padding: 0;
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
      `}</style>
    </div>
  )
}
