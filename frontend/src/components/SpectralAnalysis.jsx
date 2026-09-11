import { Area, AreaChart, CartesianGrid, ComposedChart, Legend, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'

const format = (value) => Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })

function downsampleArray(arr, maxPoints = 500) {
  if (!arr || arr.length <= maxPoints) return arr
  const step = Math.max(1, Math.floor(arr.length / maxPoints))
  return arr.filter((_, i) => i % step === 0 || i === arr.length - 1)
}

function SpectralAnalysis({ results }) {
  const frequencies = results.frequencies || []
  const power = results.power || []
  const peaks = results.dominant_peaks || []
  const peakSet = new Set(peaks.map((item) => item.frequency.toFixed(12)))
  const displayFreqs = downsampleArray(frequencies, 500)
  const displayPower = downsampleArray(power, 500)
  const data = displayFreqs.map((frequency, i) => ({ frequency, power: displayPower[i], peak: peakSet.has(Number(frequency).toFixed(12)) ? displayPower[i] : null }))
  const fftFreqs = downsampleArray(results.fft_frequencies || [], 500)
  const fftMag = downsampleArray(results.fft_magnitude || [], 500)
  const fftData = fftFreqs.map((frequency, i) => ({ frequency, magnitude: fftMag[i] }))
  return (
    <div className="spectral-results">
      <div className="spectral-summary">
        <div>
          <p className="eyebrow">HIDDEN PERIODICITY</p>
          <h3>{results.estimated_period ? `Dominant cycle: ${results.estimated_period.toFixed(1)} observations` : 'No dominant cycle'}</h3>
          <p>{results.explanation}</p>
        </div>
        <span><b>{results.dominant_frequency ? format(results.dominant_frequency) : '—'}</b>Dominant frequency</span>
      </div>
      <div className="spectral-layout">
        <div className="spectral-chart">
          <h3>Power spectrum / periodogram</h3>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="frequency" type="number" domain={['dataMin', 'dataMax']} />
              <YAxis />
              <Tooltip formatter={format} />
              <Legend />
              <Area dataKey="power" name="Power" stroke="#0b6e69" fill="#9dd9d1" fillOpacity={0.6} />
              <Scatter data={data.filter((item) => item.peak !== null)} dataKey="peak" fill="#e56b3f" name="Dominant peak" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="spectral-chart">
          <h3>FFT magnitude</h3>
          <p>The fast Fourier transform converts the observed sequence into frequency components.</p>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={fftData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="frequency" type="number" domain={['dataMin', 'dataMax']} />
              <YAxis />
              <Tooltip formatter={format} />
              <Area dataKey="magnitude" name="FFT magnitude" stroke="#6d4cc5" fill="#d8ccf2" fillOpacity={0.7} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="frequency-peaks">
        <h3>Dominant frequency peaks</h3>
        {peaks.length ? (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Rank</th><th>Frequency</th><th>Power</th><th>Estimated period</th></tr>
              </thead>
              <tbody>
                {peaks.map((peak) => (
                  <tr key={peak.rank}>
                    <td>{peak.rank}</td>
                    <td>{format(peak.frequency)}</td>
                    <td>{format(peak.power)}</td>
                    <td>{format(peak.estimated_period)} observations</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No distinct frequency peaks were detected.</p>
        )}
      </div>
    </div>
  )
}

export default SpectralAnalysis
