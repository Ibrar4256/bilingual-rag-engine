import { useState } from "react";

const API_BASE = "";

export default function Evaluation() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runEval() {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const resp = await fetch(`${API_BASE}/admin/evaluation?k=10`);
      const json = await resp.json();
      if (json.detail) {
        setError(json.detail);
      } else {
        setData(json);
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  const MODES = [
    { key: "vector_only", label: "Vector Only", color: "var(--info)" },
    { key: "bm25_only", label: "BM25 Only", color: "var(--warning)" },
    { key: "hybrid_rrf", label: "Hybrid RRF", color: "var(--accent)" },
    { key: "hybrid_reranked", label: "Hybrid + Rerank", color: "var(--success)" },
  ];

  function metricBar(value, max = 1) {
    const pct = Math.round((value / max) * 100);
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <div style={{
          flex: 1, height: 8, background: "var(--bg-input)",
          borderRadius: 100, overflow: "hidden", border: "1px solid var(--border)",
        }}>
          <div style={{
            width: `${pct}%`, height: "100%",
            background: "var(--accent-gradient)", borderRadius: 100,
          }} />
        </div>
        <span style={{ fontSize: "0.8rem", fontWeight: 600, minWidth: 45, textAlign: "right" }}>
          {value.toFixed(4)}
        </span>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ margin: 0 }}>Search Quality Evaluation</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
              Compares retrieval modes on a ground-truth test set using MRR, NDCG@10, and Recall@10.
            </p>
          </div>
          <button className="btn-primary" onClick={runEval} disabled={loading}>
            {loading ? "Evaluating..." : "Run Evaluation"}
          </button>
        </div>
        {error && <p style={{ color: "var(--danger)", marginTop: "0.5rem", fontWeight: 500 }}>{error}</p>}
      </div>

      {loading && (
        <div className="card" style={{ textAlign: "center", padding: "2rem" }}>
          <p style={{ color: "var(--text-muted)" }}>Running evaluation across 4 retrieval modes... This may take 30-60 seconds.</p>
          <div className="progress-track" style={{ maxWidth: 400, margin: "1rem auto" }}>
            <div className="progress-fill" style={{ width: "60%" }} />
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="card">
            <h2>Summary (avg across {data.test_cases} queries, k={data.k})</h2>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Mode</th>
                    <th>Avg MRR</th>
                    <th>Avg NDCG@10</th>
                    <th>Avg Recall@10</th>
                    <th>Avg Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {MODES.map((m) => {
                    const s = data.summary[m.key];
                    if (!s) return null;
                    return (
                      <tr key={m.key}>
                        <td>
                          <span style={{ fontWeight: 600, color: m.color }}>{m.label}</span>
                        </td>
                        <td>{metricBar(s.avg_mrr)}</td>
                        <td>{metricBar(s["avg_ndcg@10"])}</td>
                        <td>{metricBar(s["avg_recall@10"])}</td>
                        <td><span className="badge badge-neutral">{s.avg_latency_ms}ms</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <h2>Per-Query Breakdown</h2>
            {data.per_query.map((pq, idx) => (
              <details key={idx} style={{ marginBottom: "0.75rem" }}>
                <summary style={{
                  cursor: "pointer", fontWeight: 600, fontSize: "0.875rem",
                  padding: "0.5rem 0", color: "var(--text-primary)",
                }}>
                  {pq.query}
                  <span style={{ fontWeight: 400, color: "var(--text-muted)", marginLeft: "0.5rem", fontSize: "0.8rem" }}>
                    — {pq.description} ({pq.relevant_count} relevant)
                  </span>
                </summary>
                <div className="table-wrapper" style={{ marginTop: "0.5rem" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Mode</th>
                        <th>MRR</th>
                        <th>NDCG@10</th>
                        <th>Recall@10</th>
                        <th>Latency</th>
                        <th>Retrieved IDs</th>
                      </tr>
                    </thead>
                    <tbody>
                      {MODES.map((m) => {
                        const r = pq.modes[m.key];
                        if (!r) return null;
                        return (
                          <tr key={m.key}>
                            <td style={{ fontWeight: 500, color: m.color }}>{m.label}</td>
                            <td>{r.mrr.toFixed(4)}</td>
                            <td>{r["ndcg@10"].toFixed(4)}</td>
                            <td>{r["recall@10"].toFixed(4)}</td>
                            <td><span className="badge badge-neutral">{r.latency_ms}ms</span></td>
                            <td style={{ fontSize: "0.75rem", color: "var(--text-muted)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                              {r.retrieved_ids.slice(0, 5).join(", ")}{r.retrieved_ids.length > 5 ? "..." : ""}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </div>
        </>
      )}

      {!data && !loading && (
        <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{1F4CF}"}</div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Click "Run Evaluation" to compare retrieval modes.
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
            Evaluates vector-only, BM25-only, hybrid RRF, and hybrid+rerank using MRR, NDCG@10, and Recall@10 metrics.
          </p>
        </div>
      )}
    </>
  );
}
