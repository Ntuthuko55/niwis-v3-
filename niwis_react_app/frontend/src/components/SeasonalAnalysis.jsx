import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, PolarAngleAxis,
  PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Fragment } from 'react'

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const colours = ['#0b6e69', '#16a394', '#3bb5a8', '#72c9bd', '#b9e3dc']
const numeric = (value) => Number.isFinite(value) ? value : 0
const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })

function PatternChart({ title, data, labels, type = 'bar' }) {
  const chartData = data.map((item) => ({ ...item, label: labels[item.period - (labels === days ? 0 : 1)] || item.period }))
  return <div className="seasonal-chart"><h3>{title}</h3><ResponsiveContainer width="100%" height={250}>
    {type === 'line' ? <LineChart data={chartData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="label" /><YAxis /><Tooltip formatter={format} /><Line type="monotone" dataKey="average" name="Average" stroke="#0b6e69" strokeWidth={2.5} /></LineChart>
      : <BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="label" /><YAxis /><Tooltip formatter={format} /><Bar dataKey="average" name="Average" radius={[5, 5, 0, 0]}>{chartData.map((item, index) => <Cell key={item.period} fill={colours[index % colours.length]} />)}</Bar></BarChart>}
  </ResponsiveContainer></div>
}

function CalendarHeatmap({ calendar }) {
  const years = [...new Set(calendar.map((item) => item.year))]
  const values = calendar.map((item) => item.value); const min = Math.min(...values); const max = Math.max(...values)
  const shade = (value) => { const ratio = max === min ? .5 : (value - min) / (max - min); return `rgba(11, 110, 105, ${.12 + ratio * .82})` }
  return <div className="seasonal-chart"><h3>Seasonal calendar</h3><div className="calendar-grid"><div />{months.map((month) => <span key={month}>{month}</span>)}{years.map((year) => <Fragment key={year}><strong>{year}</strong>{months.map((month, monthIndex) => { const points = calendar.filter((item) => item.year === year && item.month === monthIndex + 1); const average = points.reduce((sum, item) => sum + item.value, 0) / (points.length || 1); return <span key={`${year}-${monthIndex}`} className="calendar-cell" style={{ background: shade(average) }} title={`${month} ${year}: ${format(average)}`}>{format(average)}</span> })}</Fragment>)}</div></div>
}

function SeasonalAnalysis({ results }) {
  const { monthly_pattern: monthly = [], weekly_pattern: weekly = [], quarterly_pattern: quarterly = [], yearly_pattern: yearly = [], calendar = [], statistics = {}, explanation } = results
  const radarData = monthly.map((item) => ({ month: months[item.period - 1], average: item.average }))
  return <div className="seasonal-results">
    <div className="seasonal-summary"><div><p className="eyebrow">AUTOMATIC FINDINGS</p><h3>Seasonal analysis</h3><p>{explanation}</p></div><div className="seasonal-metrics"><span><b>{(numeric(statistics.seasonal_strength) * 100).toFixed(0)}%</b>Seasonal strength</span><span><b>{months[(statistics.peak_month || 1) - 1]}</b>Peak month</span><span><b>{months[(statistics.lowest_month || 1) - 1]}</b>Lowest month</span><span><b>{(numeric(statistics.variance_explained) * 100).toFixed(0)}%</b>Variance explained</span></div></div>
    <div className="seasonal-layout"><PatternChart title="Monthly averages" data={monthly} labels={months} /><PatternChart title="Weekly pattern" data={weekly} labels={days} /><PatternChart title="Quarterly pattern" data={quarterly} labels={['Q1', 'Q2', 'Q3', 'Q4']} /><PatternChart title="Yearly pattern" data={yearly} labels={[]} type="line" /></div>
    <div className="seasonal-layout"><CalendarHeatmap calendar={calendar} /><div className="seasonal-chart"><h3>Polar seasonal plot</h3><ResponsiveContainer width="100%" height={280}><RadarChart data={radarData}><PolarGrid /><PolarAngleAxis dataKey="month" /><Radar dataKey="average" name="Average" stroke="#0b6e69" fill="#16a394" fillOpacity={.5} /><Tooltip formatter={format} /><Legend /></RadarChart></ResponsiveContainer></div></div>
    <div className="seasonal-chart seasonal-boxplots"><h3>Seasonal boxplots</h3><p>Monthly distribution summary (min, lower quartile, median, upper quartile, max).</p><div className="boxplot-grid">{monthly.map((item) => <div className="boxplot" key={item.period}><span>{months[item.period - 1]}</span><i style={{ bottom: `${Math.max(0, Math.min(100, (item.q1 - item.min) / ((item.max - item.min) || 1) * 100))}%`, height: `${Math.max(4, (item.q3 - item.q1) / ((item.max - item.min) || 1) * 100)}%` }} title={`Median: ${format(item.median)}`} /><b style={{ bottom: `${Math.max(0, Math.min(100, (item.median - item.min) / ((item.max - item.min) || 1) * 100))}%` }} /></div>)}</div></div>
  </div>
}

export default SeasonalAnalysis
