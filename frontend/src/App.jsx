import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Assistant from './pages/Assistant.jsx'
import AuditLogs from './pages/AuditLogs.jsx'

function StatusPill() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    let alive = true
    fetch('/api/v1/health')
      .then((r) => r.json())
      .then((d) => alive && setHealth(d))
      .catch(() => alive && setHealth({ status: 'down' }))
    return () => {
      alive = false
    }
  }, [])

  if (!health) return null
  const tone = health.status === 'ok' ? 'ok' : health.status === 'degraded' ? 'warn' : 'err'
  const label =
    health.status === 'ok'
      ? health.model
      : health.status === 'degraded'
        ? 'no api key'
        : 'offline'

  return (
    <div className="nav-status">
      <span className={`dot ${tone}`} />
      <span>{label}</span>
    </div>
  )
}

export default function App() {
  return (
    <div className="shell">
      <nav className="nav">
        <NavLink to="/" className="brand">
          <span className="brand-mark">TD</span>
          <span className="brand-text">
            GenAI <span>Platform</span>
          </span>
        </NavLink>
        <NavLink to="/" className="nav-link" end>
          Home
        </NavLink>
        <NavLink to="/assistant" className="nav-link">
          Code Assistant
        </NavLink>
        <NavLink to="/audit" className="nav-link">
          Audit Logs
        </NavLink>
        <StatusPill />
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/audit" element={<AuditLogs />} />
        <Route path="*" element={<Home />} />
      </Routes>
    </div>
  )
}
