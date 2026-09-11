import { useEffect, useState } from 'react'
import { BarChart3, MapPin, Sparkles, TrendingUp } from 'lucide-react'
import { loadProvince } from '../services/api'
import ModelTraining from './ModelTraining'

const PROVINCES = [
  ['gauteng', 'Gauteng'],
  ['western-cape', 'Western Cape'],
  ['kwa-zulu-natal', 'KwaZulu-Natal'],
  ['eastern-cape', 'Eastern Cape'],
  ['limpopo', 'Limpopo'],
  ['mpumalanga', 'Mpumalanga'],
  ['north-west', 'North West'],
  ['free-state', 'Free State'],
  ['northern-cape', 'Northern Cape'],
]

const PROVINCE_PATHS = {
  'western-cape': 'M70,225 L128,185 L188,194 L215,245 L198,316 L136,342 L88,303 L60,266 Z',
  'northern-cape': 'M132,186 L218,145 L318,118 L390,150 L392,218 L314,250 L236,260 L171,246 L128,212 Z',
  'north-west': 'M302,118 L392,144 L432,198 L406,238 L338,244 L286,200 L274,154 Z',
  'free-state': 'M292,244 L388,218 L430,244 L460,304 L404,346 L331,331 L282,276 Z',
  'gauteng': 'M406,240 L462,230 L498,250 L492,289 L438,299 L404,274 Z',
  'limpopo': 'M392,146 L490,116 L557,128 L584,176 L570,222 L516,240 L468,226 L424,196 Z',
  'mpumalanga': 'M460,244 L528,230 L586,252 L600,310 L560,344 L498,332 L454,292 Z',
  'eastern-cape': 'M286,276 L368,328 L418,364 L454,396 L462,430 L402,442 L338,420 L286,376 L248,332 Z',
  'kwa-zulu-natal': 'M462,298 L514,312 L560,348 L592,390 L578,430 L522,438 L474,420 L448,366 Z',
}

const PROVINCE_CENTROIDS = {
  'western-cape': '148,260',
  'northern-cape': '250,190',
  'north-west': '338,180',
  'free-state': '364,286',
  'gauteng': '448,264',
  'limpopo': '486,176',
  'mpumalanga': '536,286',
  'eastern-cape': '360,382',
  'kwa-zulu-natal': '520,374',
}

const provinceName = (id) => PROVINCES.find(([key]) => key === id)?.[1]

export default function ForecastingWorkspace() {
  const [selectedProvince, setSelectedProvince] = useState('gauteng')
  const [dataset, setDataset] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('Select a province to load its climate data and fit the monthly forecasting models.')

  // Auto-load on mount
  useEffect(() => {
    onSelectProvince('gauteng')
  }, [])

  const onSelectProvince = async (id) => {
    setSelectedProvince(id)
    setLoading(true)
    setMessage('Loading provincial series…')
    try {
      const loaded = await loadProvince(id)
      setDataset(loaded)
      setMessage(`${provinceName(id)} loaded. Select a model below to train and generate future forecasts.`)
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Unable to load this province.')
    } finally {
      setLoading(false)
    }
  }

  const dateColumn = dataset?.index_column || dataset?.inferred_time_columns?.[0] || 'date'
  const numericColumns = dataset?.dataset_summary?.numeric_columns || []

  return (
    <div className="fc-workspace">
      <header className="fc-header">
        <div className="fc-badge-pill">
          <Sparkles size={14} />
          <span>MULTI-HORIZON FORECASTING STUDIO</span>
        </div>
        <h1>Predictive Climate & Time Series Forecasting</h1>
        <p>
          Select a province from the map to load historical observations, then select from 17 statistical, machine learning, deep learning, and auto-tuning models to forecast future climate trajectories.
        </p>
      </header>

      <div className="fc-map-card">
        <div className="fc-map-head">
          <div className="fc-title-wrap">
            <MapPin size={16} className="text-teal" />
            <h3>South African Provincial Climate Explorer</h3>
          </div>
          <span className="fc-status-pill">{loading ? 'Loading province data…' : `${provinceName(selectedProvince)} Active`}</span>
        </div>

        <svg className="sa-map" viewBox="0 0 620 420" role="img" aria-label="South African provinces map">
          <defs>
            <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#0f172a" floodOpacity="0.14" />
            </filter>
            <linearGradient id="mapGlow" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#e7f8f5" />
              <stop offset="100%" stopColor="#dfeef4" />
            </linearGradient>
          </defs>

          <rect width="620" height="420" fill="url(#mapGlow)" rx="12" />

          <path d="M40,50 L120,30 L200,44 L240,80 L260,130 L230,184 L146,206 L82,188 L30,140 Z" fill="#edf6f7" opacity="0.4" />
          <path d="M520,78 L600,118 L606,170 L570,220 L520,200 L478,146 Z" fill="#edf6f7" opacity="0.28" />

          {PROVINCES.map(([id]) => (
            <path
              key={id}
              d={PROVINCE_PATHS[id]}
              className={selectedProvince === id ? 'selected' : ''}
              onClick={() => onSelectProvince(id)}
              filter="url(#shadow)"
            >
              <title>{provinceName(id)}</title>
            </path>
          ))}
          {PROVINCES.map(([id]) => (
            <text
              key={`label-${id}`}
              x={PROVINCE_CENTROIDS[id]?.split(',')[0]}
              y={PROVINCE_CENTROIDS[id]?.split(',')[1]}
              textAnchor="middle"
              dominantBaseline="middle"
              className={`province-label ${selectedProvince === id ? 'selected' : ''}`}
              onClick={() => onSelectProvince(id)}
            >
              {provinceName(id)}
            </text>
          ))}
        </svg>

        <div className="fc-province-buttons">
          {PROVINCES.map(([id, label]) => (
            <button
              key={id}
              className={`fc-prov-btn ${selectedProvince === id ? 'active' : ''}`}
              onClick={() => onSelectProvince(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {dataset && (
        <div style={{ marginTop: 24 }}>
          <ModelTraining
            datasetId={dataset.dataset_id}
            dateColumn={dateColumn}
            numericColumns={numericColumns}
            allColumns={dataset.columns || []}
          />
        </div>
      )}

      <style>{`
        .fc-workspace {
          max-width: 1280px;
          margin: 0 auto;
          padding: 28px 24px 72px;
          font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: #162b31;
        }

        .fc-header {
          margin-bottom: 24px;
          padding: 32px 36px;
          background: linear-gradient(120deg, #0a333c 0%, #0d5659 60%, #0b6e69 100%);
          border-radius: 20px;
          color: #fff;
          box-shadow: 0 16px 40px rgba(10, 51, 60, 0.16);
        }

        .fc-badge-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 999px;
          background: rgba(162, 236, 217, 0.18);
          border: 1px solid rgba(162, 236, 217, 0.3);
          color: #a2ecd9;
          font-size: 0.72rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          margin-bottom: 12px;
        }

        .fc-header h1 {
          margin: 0 0 8px;
          font-size: 2.1rem;
          letter-spacing: -0.03em;
          color: #ffffff;
        }

        .fc-header p {
          margin: 0;
          color: #d1eae4;
          font-size: 0.95rem;
          line-height: 1.55;
          max-width: 760px;
        }

        .fc-map-card {
          background: #ffffff;
          border: 1px solid #dce8e4;
          border-radius: 18px;
          padding: 24px;
          box-shadow: 0 8px 28px rgba(22, 43, 49, 0.04);
        }

        .fc-map-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 18px;
        }

        .fc-title-wrap {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .fc-title-wrap h3 {
          margin: 0;
          font-size: 1.1rem;
          color: #0f172a;
        }

        .fc-status-pill {
          padding: 4px 12px;
          border-radius: 999px;
          background: #ecfdf5;
          color: #065f46;
          border: 1px solid #a7f3d0;
          font-size: 0.78rem;
          font-weight: 700;
        }

        .sa-map {
          display: block;
          width: 100%;
          max-height: 420px;
          background: linear-gradient(135deg, #effaf7 0%, #f7fbff 100%);
          border-radius: 12px;
          border: 1px solid #dfeaf2;
        }

        .sa-map path {
          fill: #cfe3dd;
          stroke: rgba(15, 23, 42, 0.38);
          stroke-width: 1.8;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .sa-map path:hover {
          fill: #9ad1c2;
          stroke: rgba(15, 23, 42, 0.6);
        }

        .sa-map path.selected {
          fill: #e47738;
          stroke: #b85720;
          stroke-width: 2.4;
          filter: drop-shadow(0 8px 18px rgba(228, 119, 56, 0.25));
        }

        .province-label {
          font-size: 10px;
          font-weight: 800;
          fill: #1e293b;
          pointer-events: none;
          text-shadow: 0 1px 3px rgba(255, 255, 255, 0.85);
          cursor: pointer;
        }

        .province-label.selected {
          fill: #ffffff;
          font-size: 11px;
          text-shadow: 0 1px 6px rgba(0, 0, 0, 0.55);
        }

        .fc-province-buttons {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 18px;
        }

        .fc-prov-btn {
          padding: 8px 14px;
          border-radius: 8px;
          border: 1px solid #dce8e4;
          background: #f8fafc;
          color: #334155;
          font-size: 0.82rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .fc-prov-btn:hover {
          background: #f1f5f9;
          border-color: #cbd5e1;
        }

        .fc-prov-btn.active {
          background: #0b6e69;
          color: #ffffff;
          border-color: #0b6e69;
          box-shadow: 0 2px 8px rgba(11, 110, 105, 0.25);
        }
      `}</style>
    </div>
  )
}
