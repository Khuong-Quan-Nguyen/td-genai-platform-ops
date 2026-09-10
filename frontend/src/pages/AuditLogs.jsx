import { useCallback, useEffect, useState } from 'react'

const REFRESH_MS = 5000

function formatTime(iso) {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

export default function AuditLogs() {
  const [records, setRecords] = useState([])
  const [error, setError] = useState(null)
  const [lastSync, setLastSync] = useState(null)

  const load = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/audit-trail?limit=200')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const payload = await response.json()
      setRecords(payload.records)
      setError(null)
      setLastSync(new Date())
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  const flagged = records.filter((r) => r.pii_detected).length
  const failed = records.filter((r) => r.status !== 'success').length
  const tokens = records.reduce((sum, r) => sum + r.tokens_used, 0)

  return (
    <main className="page">
      <div className="table-head">
        <div>
          <div className="eyebrow">Audit Logs</div>
          <h1 style={{ fontSize: 32, margin: 0 }}>Request trail</h1>
        </div>
        <div className="refresh">
          <span className="pulse" />
          auto-refresh 5s
          {lastSync && ` · synced ${lastSync.toLocaleTimeString()}`}
        </div>
      </div>

      <div className="stat-row">
        <div className="stat">
          <div className="stat-label">Records</div>
          <div className="stat-value">{records.length}</div>
        </div>
        <div className="stat">
          <div className="stat-label">PII flagged</div>
          <div className="stat-value amber">{flagged}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Non-success</div>
          <div className="stat-value">{failed}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Tokens</div>
          <div className="stat-value teal">{tokens.toLocaleString()}</div>
        </div>
      </div>

      {error && (
        <div className="alert error">
          <strong>Could not reach the audit API.</strong> {error}
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>audit_id</th>
              <th>user_id</th>
              <th>status</th>
              <th>pii_detected</th>
              <th>timestamp</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.audit_id}>
                <td className="id">{r.audit_id}</td>
                <td className="user">{r.user_id}</td>
                <td>
                  <span className={`badge ${r.status}`}>{r.status}</span>
                </td>
                <td>
                  <span className={`badge ${r.pii_detected ? 'yes' : 'no'}`}>
                    {r.pii_detected ? `yes · ${r.pii_kinds.join(', ')}` : 'no'}
                  </span>
                </td>
                <td>{formatTime(r.timestamp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {records.length === 0 && !error && (
          <div className="empty">
            No audit records yet. Submit a query from the Code Assistant.
          </div>
        )}
      </div>
    </main>
  )
}
