import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })

function downsample(arr, maxPoints = 800) {
  if (!arr || arr.length <= maxPoints) return arr
  const step = Math.max(1, Math.floor(arr.length / maxPoints))
  return arr.filter((_, i) => i % step === 0 || i === arr.length - 1)
}

function SeriesChart({ title, index, values, color }) {
  const dIndex = downsample(index || [])
  const dValues = downsample(values || [])
  const step = dIndex.length ? Math.max(1, Math.floor((index || []).length / dIndex.length)) : 1
  const data = dIndex.map((date, i) => ({ date, value: dValues[i] }))
  return (
    <div className="stationarity-chart">
      <h3>{title}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" minTickGap={35} />
          <YAxis />
          <Tooltip formatter={format} />
          <Legend />
          <Line dataKey="value" name="Value" type="monotone" stroke={color} dot={false} strokeWidth={2.3} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function TestCard({ test }) {
  return (
    <div className={`test-card ${test.decision === 'Stationary' ? 'stationary' : 'non-stationary'}`}>
      <div>
        <h3>{test.name}</h3>
        <span>{test.decision}</span>
      </div>
      <p>{test.null_hypothesis}</p>
      <dl>
        <div><dt>Test statistic</dt><dd>{format(test.statistic)}</dd></div>
        <div><dt>P-value</dt><dd>{format(test.p_value)}</dd></div>
      </dl>
      <small>Critical values: {Object.entries(test.critical_values || {}).map(([level, value]) => `${level} ${format(value)}`).join(' · ')}</small>
    </div>
  )
}

function StationarityAnalysis({ results }) {
  const after = results.after_differencing || {}
  const tests = Object.values(results.tests || {})
  return (
    <div className="stationarity-results">
      <div className={`stationarity-summary ${results.stationary ? 'stationary' : 'non-stationary'}`}>
        <div>
          <p className="eyebrow">STATIONARITY DECISION</p>
          <h3>{results.decision}</h3>
          <p>{results.explanation}</p>
        </div>
        <span>Why it matters<br /><b>Reliable model relationships</b></span>
      </div>
      <div className="test-grid">{tests.map((test) => <TestCard key={test.name} test={test} />)}</div>
      {!results.stationary && (
        <div className="transformations">
          <h3>Suggested transformations</h3>
          {(results.suggestions || []).map((item) => (
            <div key={item.method}>
              <b>{item.method}{item.recommended && <em>Recommended</em>}</b>
              <span>{item.description}</span>
            </div>
          ))}
        </div>
      )}
      <div className="stationarity-layout">
        <SeriesChart title="Before transformation" index={results.index} values={results.values} color="#64748b" />
        <SeriesChart title={`After first differencing${after.decision ? ` — ${after.decision}` : ''}`} index={after.index} values={after.values} color="#0b6e69" />
      </div>
      {after.tests && (
        <div className="after-tests">
          <h3>After-differencing test results</h3>
          {Object.values(after.tests).map((test) => (
            <span key={test.name}>{test.name}: <b>{test.decision}</b> (p = {format(test.p_value)})</span>
          ))}
        </div>
      )}
    </div>
  )
}

export default StationarityAnalysis
