import { useState } from 'react'
import { Clock, Database, Map, Sparkles } from 'lucide-react'
import SpatialAnalysis from './components/SpatialAnalysis'
import MultivariateStatistics from './components/MultivariateStatistics'
import TimeSeriesDashboard from './components/TimeSeriesDashboard'

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState('timeseries')

  return (
    <>
      <nav className="workspace-tabs" aria-label="Analysis workspaces">
        <div className="workspace-brand">
          <span><Sparkles size={17} /></span>
          <strong>SignalLab</strong>
          <small>STUDIO</small>
        </div>
        <div className="workspace-links">
          <button
            className={activeWorkspace === 'timeseries' ? 'active' : ''}
            onClick={() => setActiveWorkspace('timeseries')}
            aria-pressed={activeWorkspace === 'timeseries'}
          >
            <Clock size={16} /> Time Series Studio
          </button>
          <button
            className={activeWorkspace === 'spatial' ? 'active' : ''}
            onClick={() => setActiveWorkspace('spatial')}
            aria-pressed={activeWorkspace === 'spatial'}
          >
            <Map size={16} /> Spatial Analysis
          </button>
          <button
            className={activeWorkspace === 'multivariate' ? 'active' : ''}
            onClick={() => setActiveWorkspace('multivariate')}
            aria-pressed={activeWorkspace === 'multivariate'}
          >
            <Database size={16} /> Multivariate Statistics
          </button>
        </div>
        <div className="workspace-actions">
          <button className="help-button">Documentation</button>
          <div className="user-avatar">DS</div>
        </div>
      </nav>

      {activeWorkspace === 'timeseries' && <TimeSeriesDashboard />}
      {activeWorkspace === 'spatial' && <SpatialAnalysis />}
      {activeWorkspace === 'multivariate' && <MultivariateStatistics />}
    </>
  )
}
