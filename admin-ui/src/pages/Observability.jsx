import { useState } from "react";

const API_BASE = "";

export default function Observability() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hours, setHours] = useState(24);

  async function fetchStats() {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${API_BASE}/admin/observability?hours=${hours}`);
      const json = await resp.json();
      if (json.detail) setError(json.detail);
      else setData(json);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  function formatNumber(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
  }

  const s = data?.summary;

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
          <div>
            <h2 style={{ margin: 0 }}>LLM Observability</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
              Token usage, latency, and cost tracking for every LLM and embedding call.
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <select
              value={hours}
              onChange={e => setHours(Number(e.target.value))}
              style={{
                padding: "0.4rem 0.6rem", borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)", background: "var(--bg-input)",
                color: "var(--text-primary)", fontSize: "0.8rem",
              }}
            >
              <option value={1}>Last 1h</option>
              <option value={6}>Last 6h</option>
              <option value={24}>Last 24h</option>
              <option value={72}>Last 3 days</option>
              <option value={168}>Last 7 days</option>
            </select>
            <button className="btn-primary" onClick={fetchStats} disabled={loading}>
              {loading ? "Loading..." : "Load Traces"}
            </button>
          </div>
        </div>
        {error && <p style={{ color: "var(--danger)", marginTop: "0.5rem", fontWeight: 500 }}>{error}</p>}
      </div>

      {s && (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-value">{formatNumber(s.total_calls)}</div>
            <div className="stat-label">Total Calls</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{formatNumber(s.total_input_tokens)}</div>
            <div className="stat-label">Input Tokens</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{formatNumber(s.total_output_tokens)}</div>
            <div className="stat-label">Output Tokens</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{s.avg_latency_ms.toFixed(0)}ms</div>
            <div className="stat-label">Avg Latency</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: s.error_count > 0 ? "var(--danger)" : "var(--success)" }}>
              {s.error_count}
            </div>
            <div className="stat-label">Errors</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">${s.total_cost.toFixed(4)}</div>
            <div className="stat-label">Est. Cost</div>
          </div>
        </div>
      )}

      {data?.by_provider?.length > 0 && (
        <div className="card">
          <h2>Usage by Provider</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Operation</th>
                  <th>Calls</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Avg Latency</th>
                  <th>Max Latency</th>
                  <th>Errors</th>
                </tr>
              </thead>
              <tbody>
                {data.by_provider.map((r, i) => (
                  <tr key={i}>
                    <td><span style={{ fontWeight: 600 }}>{r.provider}</span></td>
                    <td><span className="badge badge-neutral">{r.model}</span></td>
                    <td>
                      <span className={`badge ${r.operation === "generate" ? "badge-info" : "badge-success"}`}>
                        {r.operation}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{r.calls}</td>
                    <td>{formatNumber(r.input_tokens)}</td>
                    <td>{formatNumber(r.output_tokens)}</td>
                    <td>{r.avg_latency_ms.toFixed(0)}ms</td>
                    <td>{r.max_latency_ms.toFixed(0)}ms</td>
                    <td style={{ color: r.errors > 0 ? "var(--danger)" : "var(--text-muted)" }}>
                      {r.errors}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data?.recent_traces?.length > 0 && (
        <div className="card">
          <h2>Recent Traces</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Provider</th>
                  <th>Op</th>
                  <th>In Tokens</th>
                  <th>Out Tokens</th>
                  <th>Latency</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_traces.map((t, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: "0.75rem", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                      {t.created_at ? new Date(t.created_at).toLocaleTimeString() : "—"}
                    </td>
                    <td>
                      <span style={{ fontWeight: 500 }}>{t.provider}</span>
                      <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginLeft: 4 }}>
                        {t.model}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${t.operation === "generate" ? "badge-info" : "badge-success"}`}>
                        {t.operation}
                      </span>
                    </td>
                    <td>{formatNumber(t.input_tokens)}</td>
                    <td>{formatNumber(t.output_tokens)}</td>
                    <td>{t.latency_ms}ms</td>
                    <td>
                      {t.status === "error" ? (
                        <span className="badge badge-danger" title={t.error || ""}>error</span>
                      ) : (
                        <span className="badge badge-success">ok</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!data && !loading && (
        <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{1F50D}"}</div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Click "Load Traces" to view LLM call history and token usage.
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
            Every LLM generation and embedding call is traced with provider, model, tokens, and latency.
          </p>
        </div>
      )}
    </>
  );
}
