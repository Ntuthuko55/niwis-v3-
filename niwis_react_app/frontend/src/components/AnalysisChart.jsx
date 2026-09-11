import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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

const palette = ['#2563eb', '#f97316', '#14b8a6', '#a855f7', '#f43f5e']

function safeNumber(value) {
  return value === null || value === undefined ? null : value
}

function downsample(arr, maxPoints = 800) {
  if (!arr || arr.length <= maxPoints) return arr
  const step = Math.max(1, Math.floor(arr.length / maxPoints))
  return arr.filter((_, i) => i % step === 0 || i === arr.length - 1)
}

function buildSeriesData(result) {
  const index = result.results.index || []
  const values = result.results.values || []
  const trend = result.results.trend || []
  const step = Math.max(1, Math.floor(index.length / 800))
  return index.map((x, i) => i % step === 0 || i === index.length - 1 ? { x, value: safeNumber(values[i]), trend: safeNumber(trend[i]) } : null).filter(Boolean)
}

function buildDecompositionData(result) {
  const index = result.results.index || []
  const observed = result.results.observed || []
  const trend = result.results.trend || []
  const seasonal = result.results.seasonal || []
  const step = Math.max(1, Math.floor(index.length / 800))
  return index.map((x, i) => i % step === 0 || i === index.length - 1 ? {
    x,
    observed: safeNumber(observed[i]),
    trend: safeNumber(trend[i]),
    seasonal: safeNumber(seasonal[i]),
  } : null).filter(Boolean)
}

function buildLagData(result, key) {
  const values = result.results[key] || []
  return values.map((value, index) => ({ x: index, value: safeNumber(value) }))
}

function buildSpectralData(result) {
  const freqs = result.results.frequencies || []
  const power = result.results.power || []
  const step = Math.max(1, Math.floor(freqs.length / 500))
  return freqs.map((frequency, index) => index % step === 0 || index === freqs.length - 1 ? { x: frequency, value: safeNumber(power[index]) } : null).filter(Boolean)
}

function buildWaveletData(result) {
  const scales = result.results.scales || []
  const meanPower = result.results.mean_power || []
  return scales.map((scale, index) => ({ x: scale, value: safeNumber(meanPower[index]) }))
}

function buildChangePointData(result) {
  const index = result.results.index || []
  const values = result.results.values || []
  const changePoints = new Set(result.results.change_points || [])
  const step = Math.max(1, Math.floor(index.length / 800))
  return index.map((x, i) => i % step === 0 || i === index.length - 1 || changePoints.has(i) ? { x, value: safeNumber(values[i]), change: changePoints.has(i) ? safeNumber(values[i]) : null } : null).filter(Boolean)
}

function AnalysisChart({ analysisResult }) {
  const [activeGroup, setActiveGroup] = useState(null)

  // Handle grouped analysis results
  if (analysisResult.grouped) {
    const groupBy = analysisResult.group_by
    const groups = analysisResult.groups || {}
    const groupNames = Object.keys(groups).sort()

    if (groupNames.length === 0) {
      return <div className="info-box">No groups available.</div>
    }

    const selectedGroup = activeGroup || groupNames[0]

    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <div className="group-tabs">
          <h3 style={{ marginBottom: '12px' }}>Grouped by: {groupBy}</h3>
          <div className="tabs-container" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
            {groupNames.map((group) => (
              <button
                key={group}
                className={`tab-button ${selectedGroup === group ? 'active' : ''}`}
                onClick={() => setActiveGroup(group)}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  backgroundColor: selectedGroup === group ? '#2563eb' : '#f5f5f5',
                  color: selectedGroup === group ? '#fff' : '#000',
                  fontWeight: selectedGroup === group ? 'bold' : 'normal',
                }}
              >
                {group}
              </button>
            ))}
          </div>
        </div>

        {/* Recursively render chart for selected group */}
        <AnalysisChart analysisResult={groups[selectedGroup]} />
      </div>
    )
  }

  const type = analysisResult.analysis_type
  const results = analysisResult.results

  if (type === 'stationarity') {
    return (
      <div className="info-box">
        <div>ADF statistic: {results.adf_statistic}</div>
        <div>P-value: {results.p_value}</div>
        <div>Used lag: {results.used_lag}</div>
        <div>Observations: {results.nobs}</div>
      </div>
    )
  }

  if (type === 'wavelet') {
    const data = buildWaveletData(analysisResult)
    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <h3>Wavelet Mean Power by Scale</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" label={{ value: 'Scale', position: 'insideBottom', dy: 10 }} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" name="Mean power" stroke={palette[0]} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'trend') {
    const data = buildSeriesData(analysisResult)
    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <h3>Trend Analysis</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" name="Value" stroke={palette[0]} dot={false} />
            <Line type="monotone" dataKey="trend" name="Trend" stroke={palette[1]} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'decomposition' || type === 'seasonal' || type === 'cycle') {
    const data = buildDecompositionData(analysisResult)
    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <h3>{type === 'decomposition' ? 'Decomposition' : type === 'seasonal' ? 'Seasonal Analysis' : 'Cycle Analysis'}</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="observed" name="Observed" stroke={palette[0]} dot={false} />
            <Line type="monotone" dataKey="trend" name="Trend" stroke={palette[1]} dot={false} />
            <Line type="monotone" dataKey="seasonal" name="Seasonal" stroke={palette[2]} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'autocorrelation' || type === 'partial_autocorrelation') {
    const data = buildLagData(analysisResult, type === 'autocorrelation' ? 'acf' : 'pacf')
    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <h3>{type === 'autocorrelation' ? 'Autocorrelation' : 'Partial Autocorrelation'} Plot</h3>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" label={{ value: 'Lag', position: 'insideBottom', dy: 10 }} />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill={palette[0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={palette[index % palette.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'spectral') {
    const data = buildSpectralData(analysisResult)
    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <h3>Spectral Analysis</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" label={{ value: 'Frequency', position: 'insideBottom', dy: 10 }} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" name="Power" stroke={palette[0]} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (type === 'change_point') {
    const data = buildChangePointData(analysisResult)
    return (
      <div id="analysis-chart-wrapper" className="chart-panel">
        <h3>Change Point Detection</h3>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="x" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" name="Value" stroke={palette[0]} dot={false} />
            <Scatter data={data.filter((item) => item.change !== null)} dataKey="change" fill={palette[1]} name="Change point" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    )
  }

  return <div className="info-box">No chart data available for this analysis.</div>
}

export default AnalysisChart
