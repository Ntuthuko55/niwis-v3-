const modelInfo = [
  ['AR', 'Date + one numeric target', 'yₜ = c + Σ φᵢyₜ₋ᵢ + εₜ', 'Captures dependence on past values.'],
  ['MA', 'Date + one numeric target', 'yₜ = μ + εₜ + Σ θᵢεₜ₋ᵢ', 'Captures dependence on past forecast errors.'],
  ['ARMA', 'Date + one stationary target', 'yₜ = c + Σ φᵢyₜ₋ᵢ + εₜ + Σ θᵢεₜ₋ᵢ', 'Combines AR and MA.'],
  ['ARIMA', 'Date + one numeric target', 'Δᵈyₜ = c + Σ φᵢΔᵈyₜ₋ᵢ + εₜ + Σ θᵢεₜ₋ᵢ', 'Uses differencing for non-stationary series.'],
  ['SARIMA', 'Date + target + seasonal period', 'Φ(Bˢ)φ(B)(1−B)ᵈ(1−Bˢ)ᴰyₜ = Θ(Bˢ)θ(B)εₜ', 'ARIMA with repeating seasonality.'],
  ['VAR', 'Date + 2 or more numeric targets', 'yₜ = c + A₁yₜ₋₁ + … + Aₚyₜ₋ₚ + εₜ', 'Models multiple series influencing one another.'],
  ['VARMAX', 'Date + 2+ targets + optional features', 'yₜ = c + Σ Aᵢyₜ₋ᵢ + Σ Bⱼεₜ₋ⱼ + βxₜ + εₜ', 'VAR with moving-average and external effects.'],
  ['GARCH', 'Date + one numeric target', 'σ²ₜ = ω + Σ αᵢε²ₜ₋ᵢ + Σ βⱼσ²ₜ₋ⱼ', 'Forecasts volatility, usually of returns.'],
  ['State space', 'Date + target; optional features', 'xₜ = Axₜ₋₁ + Buₜ + wₜ; yₜ = Cxₜ + Duₜ + vₜ', 'Flexible for trend, seasonality, and missing data.'],
  ['Prophet', 'Date + one numeric target', 'y(t) = g(t) + s(t) + h(t) + εₜ', 'Trend, seasonality, and holiday decomposition.'],
  ['LSTM', 'Date + target; optional many features', 'hₜ, cₜ = LSTM(xₜ, hₜ₋₁, cₜ₋₁)', 'Neural model for non-linear sequences.'],
  ['Transformer', 'Date + target; optional many features', 'Attention(Q,K,V) = softmax(QKᵀ/√dₖ)V', 'Attention-based model needing more data and compute.'],
]

function ModelGuide({ columns, dateColumn }) {
  return <section className="model-guide"><div className="section-heading"><div><p className="eyebrow">NEXT PHASE</p><h2>Model training guide</h2><p className="section-description">Training will be enabled after model engines are added and tested.</p></div></div>{!dateColumn && <div className="info-box">Select a valid date column before training any time-series model.</div>}<div className="model-grid">{modelInfo.map(([name, needs, equation, note]) => <article key={name} className="model-card"><h3>{name}</h3><p className="model-needs">{needs}</p><code>{equation}</code><p>{note}</p></article>)}</div><p className="model-footnote">Available numeric fields: {columns.length ? columns.join(', ') : 'upload a dataset first'}.</p></section>
}

export default ModelGuide
