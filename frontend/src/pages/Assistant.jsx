import { useState } from 'react'

const CONTEXTS = [
  { value: 'general', label: 'General' },
  { value: 'financial-services', label: 'Financial Services' },
]

export default function Assistant() {
  const [query, setQuery] = useState('')
  const [userId, setUserId] = useState('')
  const [context, setContext] = useState('general')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch('/api/v1/code-assist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, user_id: userId, context }),
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === 'string'
            ? payload.detail
            : JSON.stringify(payload.detail),
        )
      }
      setResult(payload)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const ready = query.trim() && userId.trim() && !loading

  return (
    <main className="page">
      <div className="eyebrow">Code Assistant</div>
      <h1 style={{ fontSize: 32 }}>Ask Claude, safely.</h1>
      <p className="lede" style={{ marginBottom: 28 }}>
        Your prompt is scanned for PII and redacted before it reaches the model. Every
        submission is written to the audit trail.
      </p>

      <div className="panel" style={{ marginBottom: 24 }}>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="query">Query</label>
            <textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="How do I add retry logic with exponential backoff to a Python HTTP client?"
              maxLength={8000}
            />
          </div>

          <div className="row">
            <div className="field">
              <label htmlFor="user">User ID</label>
              <input
                id="user"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="e.g. qnguyen"
                maxLength={128}
              />
            </div>
            <div className="field">
              <label htmlFor="context">Context</label>
              <select
                id="context"
                value={context}
                onChange={(e) => setContext(e.target.value)}
              >
                {CONTEXTS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button type="submit" disabled={!ready}>
            {loading ? (
              <>
                <span className="spin" />
                Running…
              </>
            ) : (
              'Submit'
            )}
          </button>
        </form>
      </div>

      {error && (
        <div className="alert error">
          <strong>Request failed.</strong> {error}
        </div>
      )}

      {result && (
        <div className="panel">
          <div className="meta-row">
            <span className="chip teal">
              audit_id <b>{result.audit_id}</b>
            </span>
            <span className="chip">
              tokens_used <b>{result.tokens_used.toLocaleString()}</b>
            </span>
            <span className="chip">
              in/out <b>{result.input_tokens}/{result.output_tokens}</b>
            </span>
            <span className={`chip ${result.pii_detected ? 'amber' : ''}`}>
              pii_detected <b>{result.pii_detected ? 'TRUE' : 'FALSE'}</b>
            </span>
            <span className="chip">
              latency <b>{result.latency_ms} ms</b>
            </span>
            <span className="chip">
              model <b>{result.model}</b>
            </span>
          </div>

          {result.pii_detected && (
            <div className="alert warn">
              <strong>PII redacted before the model call.</strong> Found{' '}
              {result.pii_matches.map((m, i) => (
                <span key={i}>
                  {i > 0 && ', '}
                  <code>{m.kind}</code> ({m.redacted})
                </span>
              ))}
              .
            </div>
          )}

          <div className="response-body">{result.response}</div>
        </div>
      )}
    </main>
  )
}
