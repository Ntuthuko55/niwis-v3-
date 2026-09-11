import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 })

function downsample(arr, maxPoints = 800) {
  if (!arr || arr.length <= maxPoints) return arr
  const step = Math.max(1, Math.floor(arr.length / maxPoints))
  return arr.filter((_, i) => i % step === 0 || i === arr.length - 1)
}

function AutocorrelationAnalysis({ results }) {
  const acf = results.acf || []
  const intervals = results.confidence_intervals || []
  const plotData = acf.map((value, lag) => ({ lag, correlation: value, lower: intervals[lag]?.lower, upper: intervals[lag]?.upper, significant: (results.significant_lags || []).includes(lag) }))
  const rolling = results.rolling_correlation || {}
  const rollingIndex = downsample(rolling.index || [])
  const rollingValues = downsample(rolling.values || [])
  const step = rollingIndex.length ? Math.max(1, Math.floor((rolling.index || []).length / rollingIndex.length)) : 1
  const rollingData = rollingIndex.map((date, i) => ({ date, correlation: rollingValues[i] }))
  const table = results.lag_table || []
  return (
    <div className="autocorrelation-results">
      <div className="autocorrelation-summary">
        <div>
          <p className="eyebrow">PERSISTENCE ANALYSIS</p>
          <h3>{results.persistence || 'Autocorrelation analysis'}</h3>
          <p>{results.explanation}</p>
        </div>
        <span><b>{(results.significant_lags || []).length}</b>Significant lags</span>
      </div>
      <div className="autocorrelation-layout">
        <div className="autocorrelation-chart">
          <h3>ACF plot with 95% confidence intervals</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={plotData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="lag" />
              <YAxis domain={[-1, 1]} />
              <Tooltip formatter={format} />
              <ReferenceLine y={0} stroke="#64748b" />
              <ReferenceLine y={plotData[1]?.upper} stroke="#94a3b8" strokeDasharray="4 4" />
              <ReferenceLine y={plotData[1]?.lower} stroke="#94a3b8" strokeDasharray="4 4" />
              <Bar dataKey="correlation" name="Correlation">
                {plotData.map((item) => (
                  <Cell key={item.lag} fill={item.significant ? '#0b6e69' : '#9dd9d1'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="autocorrelation-chart">
          <h3>Rolling lag-one correlation</h3>
          <p>Correlation between each value and its preceding observation, calculated across a {rolling.window || '—'}-point window.</p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={rollingData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" minTickGap={35} />
              <YAxis domain={[-1, 1]} />
              <Tooltip formatter={format} />
              <ReferenceLine y={0} stroke="#64748b" />
              <Line dataKey="correlation" name="Rolling correlation" type="monotone" stroke="#f97316" dot={false} strokeWidth={2.3} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="lag-table">
        <h3>Lag correlation table</h3>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr><th>Lag</th><th>Correlation</th><th>95% confidence interval</th><th>Significant</th></tr>
            </thead>
            <tbody>
              {table.map((item) => (
                <tr key={item.lag}>
                  <td>{item.lag}</td>
                  <td>{format(item.correlation)}</td>
                  <td>{format(item.lower_confidence)} to {format(item.upper_confidence)}</td>
                  <td><span className={item.significant ? 'significant' : 'not-significant'}>{item.significant ? 'Yes' : 'No'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default AutocorrelationAnalysis
