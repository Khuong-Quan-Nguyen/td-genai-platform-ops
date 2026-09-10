import { Link } from 'react-router-dom'

const CAPABILITIES = [
  {
    icon: '🛡️',
    title: 'PII guardrail',
    body: 'Every prompt is scanned for SINs, card numbers, bank accounts, emails and phone numbers before it leaves the process. Matches are replaced with typed placeholders — raw identifiers never reach the model.',
  },
  {
    icon: '📋',
    title: 'Append-only audit trail',
    body: 'Each request writes exactly one record — success, blocked or error — capturing the user, PII classes found, token spend and latency. Records carry PII kinds, never PII values.',
  },
  {
    icon: '⚡',
    title: 'Claude agentic layer',
    body: 'Requests run against Claude Opus 5 with adaptive thinking and a financial-services system context that accounts for OSFI and PIPEDA obligations.',
  },
]

const ENDPOINTS = [
  ['POST', '/api/v1/code-assist', 'Redact, run, and audit one prompt'],
  ['GET', '/api/v1/audit-trail', 'Recent audit records, newest first'],
  ['GET', '/api/v1/health', 'Liveness plus model and key status'],
]

export default function Home() {
  return (
    <main className="page">
      <div className="eyebrow">Internal Platform · MVP</div>
      <h1>
        Governed Claude access
        <br />
        for TD engineering.
      </h1>
      <p className="lede">
        A single service that puts a PII guardrail and a complete audit trail in front of
        every model call — so teams can use frontier AI without routing customer data
        through it.
      </p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 44, flexWrap: 'wrap' }}>
        <Link to="/assistant">
          <button>Open Code Assistant</button>
        </Link>
        <Link to="/audit">
          <button
            style={{ background: 'var(--bg-raised)', color: 'var(--text)' }}
          >
            View Audit Logs
          </button>
        </Link>
      </div>

      <div className="grid-3" style={{ marginBottom: 44 }}>
        {CAPABILITIES.map((c) => (
          <div className="card" key={c.title}>
            <div className="card-icon">{c.icon}</div>
            <h2>{c.title}</h2>
            <p>{c.body}</p>
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="eyebrow" style={{ marginBottom: 18 }}>API Surface</div>
        <div className="table-wrap" style={{ border: 'none' }}>
          <table>
            <thead>
              <tr>
                <th>Method</th>
                <th>Path</th>
                <th>Purpose</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map(([method, path, purpose]) => (
                <tr key={path}>
                  <td>
                    <span className={`badge ${method === 'POST' ? 'yes' : 'no'}`}>
                      {method}
                    </span>
                  </td>
                  <td className="id">{path}</td>
                  <td>{purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  )
}
