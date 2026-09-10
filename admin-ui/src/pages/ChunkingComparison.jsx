import { useState } from "react";

const API_BASE = "";

export default function ChunkingComparison() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runComparison() {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const resp = await fetch(`${API_BASE}/admin/chunking-comparison?sample_size=10`);
      const json = await resp.json();
      if (json.detail) setError(json.detail);
      else setData(json);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  function scoreBar(value, max = 1) {
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
        <span style={{ fontSize: "0.8rem", fontWeight: 600, minWidth: 50, textAlign: "right" }}>
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
            <h2 style={{ margin: 0 }}>Chunking Strategy Comparison</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
              Compare how different text splitting strategies affect retrieval quality.
            </p>
          </div>
          <button className="btn-primary" onClick={runComparison} disabled={loading}>
            {loading ? "Running..." : "Run Comparison"}
          </button>
        </div>
        {error && <p style={{ color: "var(--danger)", marginTop: "0.5rem" }}>{error}</p>}
      </div>

      {loading && (
        <div className="card" style={{ textAlign: "center", padding: "2rem" }}>
          <p style={{ color: "var(--text-muted)" }}>
            Chunking and embedding documents with 4 strategies... This may take 1-2 minutes.
          </p>
          <div className="progress-track" style={{ maxWidth: 400, margin: "1rem auto" }}>
            <div className="progress-fill" style={{ width: "50%" }} />
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-value">{data.documents_sampled}</div>
              <div className="stat-label">Docs Sampled</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{data.test_queries}</div>
              <div className="stat-label">Test Queries</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{data.strategies.length}</div>
              <div className="stat-label">Strategies</div>
            </div>
          </div>

          <div className="card">
            <h2>Strategy Summary</h2>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Total Chunks</th>
                    <th>Avg Words/Chunk</th>
                    <th>Min/Max Words</th>
                    <th>Avg Top Score</th>
                    <th>Avg Doc Diversity</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {data.strategies.map((s) => (
                    <tr key={s.strategy}>
                      <td style={{ fontWeight: 600 }}>{s.label}</td>
                      <td>{s.chunk_stats.total_chunks}</td>
                      <td>{s.chunk_stats.avg_chunk_words}</td>
                      <td>
                        <span className="badge badge-neutral">
                          {s.chunk_stats.min_words}–{s.chunk_stats.max_words}
                        </span>
                      </td>
                      <td>{scoreBar(s.avg_top_score)}</td>
                      <td>
                        <span style={{ fontWeight: 600 }}>{s.avg_diversity}</span>
                        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}> docs</span>
                      </td>
                      <td><span className="badge badge-neutral">{s.processing_time_ms}ms</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {data.strategies.map((s) => (
            <div className="card" key={s.strategy}>
              <details>
                <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: "0.9rem" }}>
                  {s.label} — Per-Query Results
                </summary>
                <div className="table-wrapper" style={{ marginTop: "0.75rem" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Query</th>
                        <th>Best Score</th>
                        <th>Avg Top-5</th>
                        <th>Unique Docs (Top 5)</th>
                        <th>Unique Docs (Top 10)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.query_results.map((qr, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 500 }}>{qr.query}</td>
                          <td>{qr.top_5_score.toFixed(4)}</td>
                          <td>{qr.avg_top5_score.toFixed(4)}</td>
                          <td>{qr.unique_docs_in_top5}</td>
                          <td>{qr.unique_docs_in_top10}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          ))}
        </>
      )}

      {!data && !loading && (
        <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{2702}️"}</div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Click "Run Comparison" to evaluate chunking strategies.
          </p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
            Compares fixed-size (200/500/800 words) and paragraph-based chunking
            on retrieval quality metrics.
          </p>
        </div>
      )}
    </>
  );
}
