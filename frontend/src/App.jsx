import './App.css'

export default function App() {
  return (
    <div className="frame">
      <section className="dashboard" aria-label="BusIQ public transport control room dashboard mockup">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true"></div>
            <div>
              <h1>BusIQ</h1>
              <small>AI-powered public transport control room</small>
            </div>
          </div>

          <div className="top-status">
            <div className="status-pill"><span className="status-dot green"></span>Live</div>
            <div className="status-pill"><span className="status-dot"></span>Data synced</div>
            <div className="status-pill"><span className="status-dot amber"></span>Model accuracy 94.8%</div>
            <div className="status-pill"><span className="status-dot"></span>Silk Board junction watch zone</div>
          </div>
        </header>

        <main className="main">
          <section className="panel left-panel">
            <div className="panel-header">
              <div>
                <p className="panel-title">Live Bengaluru Map</p>
                <p className="panel-subtitle">Silk Board junction congestion field with active routes</p>
              </div>
              <div className="badge">Route density 87%</div>
            </div>

            <div className="map-wrap">
              <div className="map-legend">
                <div className="legend-row">
                  <div className="swatch red"></div>
                  <span>High congestion</span>
                </div>
                <div className="legend-row">
                  <div className="swatch orange"></div>
                  <span>Medium congestion</span>
                </div>
                <div className="legend-row">
                  <div className="swatch cyan"></div>
                  <span>Active routes</span>
                </div>
              </div>
            </div>
          </section>

          <section className="panel center-panel">
            <div className="panel-header">
              <div>
                <p className="panel-title">Surge Detection</p>
                <p className="panel-subtitle">Prediction engine triggered</p>
              </div>
            </div>

            <div className="surge-card">
              <div className="surge-top">
                <div className="warning">⚠️ Critical congestion predicted</div>
              </div>
              <div className="surge-value">
                87<small>%</small>
              </div>
              <div className="surge-caption">
                Junction saturation level rising. Dynamic route optimization active. ETA adjusted for 3,247 passengers.
              </div>
            </div>
          </section>

          <section className="panel right-panel">
            <div className="panel-header">
              <div>
                <p className="panel-title">Dispatch Control</p>
              </div>
            </div>

            <div className="dispatch-body">
              <h3 className="dispatch-id">DS-8847</h3>
              <div className="action-row">
                <button className="btn primary">Activate diversion</button>
                <button className="btn secondary">View full details</button>
              </div>
            </div>
          </section>

          <section className="panel bottom-panel">
            <div className="graph-area">
              <div className="panel-header">
                <div>
                  <p className="panel-title">Traffic Flow Analysis</p>
                </div>
              </div>
              <div className="chart">
                <svg viewBox="0 0 600 200" width="100%" height="100%">
                  <polyline points="0,150 60,120 120,140 180,80 240,100 300,60 360,80 420,40 480,60 540,50 600,70" fill="none" stroke="#66b8ff" strokeWidth="3" vectorEffect="non-scaling-stroke"/>
                  <polyline points="0,180 60,160 120,170 180,130 240,150 300,110 360,130 420,90 480,110 540,100 600,120" fill="none" stroke="#60ffa0" strokeWidth="3" vectorEffect="non-scaling-stroke"/>
                </svg>
              </div>
            </div>

            <div className="timeline">
              <div className="panel-header">
                <p className="panel-title">Recent Events</p>
              </div>
              <div className="timeline-track">
                <div className="timeline-item">
                  <strong>Signal timing adjusted</strong>
                  <span>3 minutes ago</span>
                </div>
                <div className="timeline-item">
                  <strong>Route diversion activated</strong>
                  <span>8 minutes ago</span>
                </div>
                <div className="timeline-item">
                  <strong>Surge detected</strong>
                  <span>12 minutes ago</span>
                </div>
              </div>
            </div>
          </section>
        </main>
      </section>
    </div>
  )
}
