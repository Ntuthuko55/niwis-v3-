import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
const colours = { observed: '#64748b', trend: '#f97316', seasonal: '#0b6e69', resid: '#9b5de5' }

function ComponentChart({ title, field, data, explanation }) {
  return (
    <div className="decomposition-chart">
      <h3>{title}</h3>
      <p>{explanation}</p>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" minTickGap={35} />
          <YAxis />
          <Tooltip formatter={format} />
          <Legend />
          <Line type="monotone" dataKey={field} name={title} stroke={colours[field]} dot={false} strokeWidth={2.3} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function DecompositionAnalysis({ results }) {
  const index = results.index || []
  const observed = results.observed || []
  const trend = results.trend || []
  const seasonal = results.seasonal || []
  const resid = results.resid || []
  const step = Math.max(1, Math.floor(index.length / 800))
  const data = index.map((date, i) => i % step === 0 || i === index.length - 1 ? { date, observed: observed[i], trend: trend[i], seasonal: seasonal[i], resid: resid[i] } : null).filter(Boolean)
  const copy = results.component_explanations || {}
  return (
    <div className="decomposition-results">
      <div className="decomposition-summary">
        <div>
          <p className="eyebrow">TIME SERIES DECOMPOSITION</p>
          <h3>{results.method_name || 'Decomposition'}</h3>
          <p>The series is separated into four components so you can distinguish its overall movement, recurring pattern, and unexplained variation.</p>
        </div>
        <span><b>{results.period}</b>Seasonal period</span>
      </div>
      <div className="decomposition-layout">
        <ComponentChart title="Observed" field="observed" data={data} explanation={copy.observed} />
        <ComponentChart title="Trend" field="trend" data={data} explanation={copy.trend} />
        <ComponentChart title="Seasonal" field="seasonal" data={data} explanation={copy.seasonal} />
        <ComponentChart title="Residual" field="resid" data={data} explanation={copy.residual} />
      </div>
    </div>
  )
}

export default DecompositionAnalysis
