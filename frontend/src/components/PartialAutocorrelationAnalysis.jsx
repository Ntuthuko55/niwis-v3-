import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 })

function PartialAutocorrelationAnalysis({ results }) {
  const values = results.pacf || []; const intervals = results.confidence_intervals || []; const significant = results.significant_lags || []
  const data = values.map((value, lag) => ({ lag, correlation: value, lower: intervals[lag]?.lower, upper: intervals[lag]?.upper, significant: significant.includes(lag) }))
  const order = results.suggested_ar_order || 0
  return <div className="pacf-results"><div className="pacf-summary"><div><p className="eyebrow">AR ORDER GUIDANCE</p><h3>{order ? `Suggested AR(${order})` : 'No clear AR order'}</h3><p>{results.interpretation}</p></div><span><b>{significant.length}</b>Significant lags</span></div><div className="pacf-chart"><h3>Partial autocorrelation plot</h3><p>Bars outside the dashed 95% confidence bounds are highlighted. Each bar shows a lag’s direct relationship after accounting for the preceding lags.</p><ResponsiveContainer width="100%" height={350}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="lag" /><YAxis domain={[-1, 1]} /><Tooltip formatter={format} /><ReferenceLine y={0} stroke="#64748b" /><ReferenceLine y={data[1]?.upper} stroke="#94a3b8" strokeDasharray="4 4" /><ReferenceLine y={data[1]?.lower} stroke="#94a3b8" strokeDasharray="4 4" /><Bar dataKey="correlation" name="Partial correlation">{data.map((item) => <Cell key={item.lag} fill={item.significant ? '#6d4cc5' : '#c7b9e9'} />)}</Bar></BarChart></ResponsiveContainer></div><div className="pacf-guidance"><div><h3>Suggested AR model</h3><strong>{order ? `AR(${order})` : 'AR(0)'}</strong><p>{order ? `Start model comparison with ${order} autoregressive lag${order === 1 ? '' : 's'}. Confirm the choice using information criteria and residual diagnostics.` : 'Start with no autoregressive lag, then compare alternatives only if model diagnostics suggest remaining structure.'}</p></div><div><h3>Significant direct lags</h3><div className="lag-pills">{significant.length ? significant.map((lag) => <span key={lag}>Lag {lag}</span>) : <span>None detected</span>}</div></div></div></div>
}

export default PartialAutocorrelationAnalysis
