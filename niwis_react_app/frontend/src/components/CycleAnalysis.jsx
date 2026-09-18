import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })

function downsample(arr, maxPoints = 800) {
  if (!arr || arr.length <= maxPoints) return arr
  const step = Math.max(1, Math.floor(arr.length / maxPoints))
  return arr.filter((_, i) => i % step === 0 || i === arr.length - 1)
}

function CycleAnalysis({ results }) {
  const index = results.index || []
  const values = results.values || []
  const trend = results.trend || []
  const cycle = results.cycle_component || []
  const peaks = results.peaks || []
  const troughs = results.troughs || []
  const stats = results.statistics || {}
  const peakDates = new Set(peaks.map((item) => String(item.date)))
  const troughDates = new Set(troughs.map((item) => String(item.date)))
  const step = Math.max(1, Math.floor(index.length / 800))
  const data = index.map((date, i) => i % step === 0 || i === index.length - 1 ? {
    date,
    value: values[i],
    trend: trend[i],
    cycle: cycle[i],
    peak: peakDates.has(String(date)) ? cycle[i] : null,
    trough: troughDates.has(String(date)) ? cycle[i] : null,
  } : null).filter(Boolean)
  return (
    <div className="cycle-results">
      <div className="cycle-summary">
        <div>
          <p className="eyebrow">AUTOMATIC CYCLE FINDINGS</p>
          <h3>{results.filter_name || 'Cycle analysis'}</h3>
          <p>{results.interpretation}</p>
        </div>
        <div className="cycle-metrics">
          <span><b>{stats.detected_cycle_length ? stats.detected_cycle_length.toFixed(1) : '—'}</b>Detected cycle length</span>
          <span><b>{stats.average_cycle_duration ? stats.average_cycle_duration.toFixed(1) : '—'}</b>Average peak duration</span>
          <span><b>{stats.cycle_amplitude ? format(stats.cycle_amplitude) : '—'}</b>Cycle amplitude</span>
          <span><b>{stats.peak_count || 0} / {stats.trough_count || 0}</b>Peaks / troughs</span>
        </div>
      </div>
      <div className="cycle-chart">
        <h3>Cycle component and turning points</h3>
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={35} />
            <YAxis />
            <Tooltip formatter={format} />
            <Legend />
            <ReferenceLine y={0} stroke="#94a3b8" />
            <Line type="monotone" dataKey="cycle" name="Cycle component" stroke="#0b6e69" dot={false} strokeWidth={2.4} />
            <Scatter dataKey="peak" name="Cycle peak" fill="#e56b3f" />
            <Scatter dataKey="trough" name="Cycle trough" fill="#3366cc" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="cycle-chart">
        <h3>Observed series and long-term trend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={35} />
            <YAxis />
            <Tooltip formatter={format} />
            <Legend />
            <Line type="monotone" dataKey="value" name="Observed" stroke="#6b7b94" dot={false} />
            <Line type="monotone" dataKey="trend" name="Long-term trend" stroke="#f97316" dot={false} strokeWidth={2.4} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="cycle-turning-points">
        <div>
          <h3>Cycle peaks</h3>
          {peaks.length ? <ol>{peaks.slice(0, 8).map((item) => <li key={`${item.date}-peak`}><span>{String(item.date)}</span><b>{format(item.value)}</b></li>)}</ol> : <p>No peaks detected.</p>}
        </div>
        <div>
          <h3>Cycle troughs</h3>
          {troughs.length ? <ol>{troughs.slice(0, 8).map((item) => <li key={`${item.date}-trough`}><span>{String(item.date)}</span><b>{format(item.value)}</b></li>)}</ol> : <p>No troughs detected.</p>}
        </div>
      </div>
    </div>
  )
}

export default CycleAnalysis
