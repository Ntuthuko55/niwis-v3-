import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 })

function downsampleMatrix(matrix, maxCols = 60, maxRows = 40) {
  if (!matrix || !matrix.length) return matrix
  const rows = matrix.length
  const cols = matrix[0]?.length || 0
  if (rows <= maxRows && cols <= maxCols) return matrix
  const rowStep = Math.max(1, Math.floor(rows / maxRows))
  const colStep = Math.max(1, Math.floor(cols / maxCols))
  return matrix.filter((_, i) => i % rowStep === 0).map(row => row.filter((_, j) => j % colStep === 0))
}

function WaveletAnalysis({ results }) {
  const scales = results.scales || []
  const matrix = results.scalogram || []
  const events = results.transient_events || []
  const displayMatrix = downsampleMatrix(matrix, 60, 40)
  const displayScales = scales.filter((_, i) => i % Math.max(1, Math.floor(scales.length / 40)) === 0)
  const allValues = displayMatrix.flat()
  const max = Math.max(...allValues, 1)
  const min = Math.min(...allValues, 0)
  const shade = (value) => {
    const ratio = (value - min) / ((max - min) || 1)
    return `hsl(${215 - ratio * 185} 72% ${95 - ratio * 52}%)`
  }
  const scaleData = displayScales.map((scale, i) => ({ scale, power: results.mean_power?.[i] }))
  return (
    <div className="wavelet-results">
      <div className="wavelet-summary">
        <div>
          <p className="eyebrow">TIME–FREQUENCY ANALYSIS</p>
          <h3>Dominant scale: {results.dominant_scale || '—'}</h3>
          <p>{results.explanation}</p>
        </div>
        <span><b>{events.length}</b>Transient events</span>
      </div>
      <div className="wavelet-scalogram">
        <h3>Wavelet scalogram</h3>
        <p>Colour intensity shows local wavelet power. Horizontal position is time; vertical position is scale. Brighter patches indicate localized cycles or transient events.</p>
        <div
          className="scalogram-grid"
          style={{
            gridTemplateColumns: `repeat(${displayMatrix[0]?.length || 1}, minmax(2px, 1fr))`,
            gridTemplateRows: `repeat(${displayMatrix.length || 1}, 5px)`,
          }}
        >
          {displayMatrix.map((row, scaleIndex) =>
            row.map((value, timeIndex) => (
              <i
                key={`${scaleIndex}-${timeIndex}`}
                style={{ background: shade(value) }}
                title={`Scale ${displayScales[scaleIndex]}, power ${format(value)}`}
              />
            ))
          )}
        </div>
        <div className="scalogram-labels">
          <span>Shorter scales / faster changes</span>
          <span>Time →</span>
          <span>Longer scales / slower changes</span>
        </div>
      </div>
      <div className="wavelet-layout">
        <div className="wavelet-chart">
          <h3>Average power by scale</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={scaleData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="scale" />
              <YAxis />
              <Tooltip formatter={format} />
              <Line dataKey="power" name="Mean power" type="monotone" stroke="#0b6e69" dot={false} strokeWidth={2.3} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="wavelet-events">
          <h3>Localized transient events</h3>
          {events.length ? (
            <ol>
              {events.slice(0, 20).map((event) => (
                <li key={`${event.index}-${event.date}`}>
                  <span>{String(event.date)}<small>Dominant scale {event.dominant_scale}</small></span>
                  <b>{format(event.power)}</b>
                </li>
              ))}
            </ol>
          ) : (
            <p>No unusually concentrated transient events were detected.</p>
          )}
          <div className="frequency-change">
            <b>Changing frequencies</b>
            <span>Dominant scale: {results.start_dominant_scale || '—'} at the start → {results.end_dominant_scale || '—'} at the end.</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default WaveletAnalysis
