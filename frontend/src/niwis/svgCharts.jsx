import { DCLASS, GEO, LABELPOS, LESOTHO } from './demoData'

function projX(lon) { return ((lon - 16.2) / 17) * 680 }
function projY(lat) { return ((-22.0 - lat) / 13) * 560 }
function poly(pts) { return pts.map((p) => `${projX(p[0]).toFixed(1)},${projY(p[1]).toFixed(1)}`).join(' ') }

export function LineChart({ sets, labels = [], min, max, h = 190, dec = 0, split }) {
  const W = 560
  const H = h
  const P = { l: 40, r: 12, t: 12, b: 26 }
  const all = sets.flatMap((s) => s.data.filter((v) => v != null))
  let lo = min !== undefined ? min : Math.min(...all)
  let hi = max !== undefined ? max : Math.max(...all)
  if (hi === lo) hi = lo + 1
  const pad = (hi - lo) * 0.12
  if (min === undefined) lo -= pad
  if (max === undefined) hi += pad
  const n = sets[0]?.data.length || 1
  const X = (i) => P.l + (i * (W - P.l - P.r)) / Math.max(1, n - 1)
  const Y = (v) => P.t + ((hi - v) / (hi - lo)) * (H - P.t - P.b)
  const ticks = 4
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
        {Array.from({ length: ticks + 1 }, (_, t) => {
          const v = lo + ((hi - lo) * t) / ticks
          const y = Y(v)
          return (
            <g key={t}>
              <line x1={P.l} y1={y} x2={W - P.r} y2={y} stroke="#1B3A49" />
              <text x={P.l - 6} y={y + 3.5} textAnchor="end" fontSize="9.5" fill="#6A8896">{v.toFixed(dec)}</text>
            </g>
          )
        })}
        {split !== undefined && (
          <>
            <rect x={X(split)} y={P.t} width={W - P.r - X(split)} height={H - P.t - P.b} fill="#8C7BE0" opacity=".07" />
            <line x1={X(split)} y1={P.t} x2={X(split)} y2={H - P.b} stroke="#8C7BE0" strokeDasharray="3 3" />
          </>
        )}
        {sets.map((s) => {
          const d = s.data.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
          return (
            <g key={s.n}>
              {s.area && <path d={`${d} L${X(n - 1)},${Y(lo)} L${X(0)},${Y(lo)} Z`} fill={s.c} opacity=".12" />}
              <path d={d} fill="none" stroke={s.c} strokeWidth={s.w || 2} strokeDasharray={s.dash || undefined} strokeLinejoin="round" />
            </g>
          )
        })}
        {labels.map((l, i) => (n > 8 && i % 2 ? null : (
          <text key={l + i} x={X(i)} y={H - 8} textAnchor="middle" fontSize="9" fill="#6A8896">{l}</text>
        )))}
      </svg>
      {sets.length > 1 && (
        <div className="nw-legend">{sets.map((s) => <span key={s.n}><i style={{ background: s.c }} />{s.n}</span>)}</div>
      )}
    </>
  )
}

export function BarChart({ labels, vals, color = 'var(--river)', h = 190, max }) {
  const W = 560
  const H = h
  const P = { l: 38, r: 10, t: 10, b: 34 }
  const hi = max || Math.max(...vals) * 1.15
  const bw = (W - P.l - P.r) / vals.length
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
      {[0, 1, 2, 3].map((t) => {
        const y = P.t + (1 - t / 3) * (H - P.t - P.b)
        return (
          <g key={t}>
            <line x1={P.l} y1={y} x2={W - P.r} y2={y} stroke="#1B3A49" />
            <text x={P.l - 6} y={y + 3.5} textAnchor="end" fontSize="9.5" fill="#6A8896">{(hi * t / 3).toFixed(0)}</text>
          </g>
        )
      })}
      {vals.map((v, i) => {
        const height = Math.max(1, (v / hi) * (H - P.t - P.b))
        const x = P.l + i * bw + bw * 0.18
        const y = H - P.b - height
        const c = typeof color === 'function' ? color(v, i) : color
        return (
          <g key={labels[i]}>
            <rect x={x} y={y} width={bw * 0.64} height={height} rx="2" fill={c} />
            <text x={P.l + i * bw + bw / 2} y={H - 12} textAnchor="middle" fontSize="9" fill="#6A8896">{labels[i]}</text>
          </g>
        )
      })}
    </svg>
  )
}

export function BarEl({ v, color, max = 100 }) {
  return <div className="nw-bar"><i style={{ width: `${Math.max(2, Math.min(100, (v / max) * 100))}%`, background: color }} /></div>
}

export function MapSVG({ provinces, selected, onSelect, colorFn, points }) {
  return (
    <div className="nw-map">
      <svg viewBox="0 0 680 590">
        <polygon points={poly(LESOTHO)} fill="#0A1720" stroke="#2A4E5E" strokeDasharray="3 3" />
        {provinces.map((p) => {
          const g = GEO[p.id]
          if (!g) return null
          return (
            <polygon
              key={p.id}
              className={`nw-prov ${selected === p.id ? 'sel' : ''}`}
              points={poly(g)}
              fill={colorFn(p)}
              onClick={() => onSelect(p.id)}
            >
              <title>{p.name}</title>
            </polygon>
          )
        })}
        {provinces.map((p) => {
          const l = LABELPOS[p.id]
          return l ? <text key={`l${p.id}`} className="nw-mlabel" x={projX(l[0])} y={projY(l[1])} textAnchor="middle">{p.id}</text> : null
        })}
        {(points || []).map((s) => (
          <circle key={s.t} cx={projX(s.lon)} cy={projY(s.lat)} r="5" fill={s.c} stroke="#08161D" strokeWidth="1.5">
            <title>{s.t}</title>
          </circle>
        ))}
        <text x={projX(28.5)} y={projY(-29.6)} className="nw-mlabel" fill="#6A8896" textAnchor="middle">LESOTHO</text>
      </svg>
    </div>
  )
}

export function DTag({ d }) {
  const c = DCLASS[d] || DCLASS['-']
  return <span className={`nw-tag ${c.t}`}>{d === '-' ? 'No drought' : `${d} · ${c.n.split(' ')[0]}`}</span>
}
