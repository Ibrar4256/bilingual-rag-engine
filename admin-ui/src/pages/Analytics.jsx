import { useState, useEffect } from "react";
import { getAnalytics } from "../api.js";

export default function Analytics() {
  const [data, setData] = useState(null);

  useEffect(() => {
    getAnalytics().then(setData).catch(() => {});
  }, []);

  if (!data) return <div className="card"><p style={{ color: "var(--text-muted)" }}>Loading analytics...</p></div>;

  if (data.total_queries === 0) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
        <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{1F4CA}"}</div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No searches recorded yet.</p>
        <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
          Run some searches from the Search Test tab to see analytics here.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Queries</div>
          <div className="stat-value">{data.total_queries}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Top Queries</div>
          <div className="stat-value">{data.top_queries.length}</div>
          <div className="stat-sub">unique popular terms</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Zero Results</div>
          <div className="stat-value" style={{ color: data.zero_result_queries.length ? "var(--danger)" : "var(--success)" }}>
            {data.zero_result_queries.length}
          </div>
          <div className="stat-sub">queries with no matches</div>
        </div>
      </div>

      {data.top_queries.length > 0 && (
        <div className="card">
          <h2>Top Queries</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Count</th>
                  <th>Avg Time</th>
                </tr>
              </thead>
              <tbody>
                {data.top_queries.map((q, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{q.query}</td>
                    <td><span className="badge badge-info">{q.count}</span></td>
                    <td><span className="badge badge-neutral">{q.avg_ms}ms</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.zero_result_queries.length > 0 && (
        <div className="card">
          <h2 style={{ color: "var(--danger)" }}>Zero-Result Queries</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Times</th>
                </tr>
              </thead>
              <tbody>
                {data.zero_result_queries.map((q, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{q.query}</td>
                    <td><span className="badge badge-danger">{q.count}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Recent Searches</h2>
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Query</th>
                <th>Endpoint</th>
                <th>Lang</th>
                <th>Results</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {data.recent.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500 }}>{r.query}</td>
                  <td><span className="badge badge-neutral">{r.endpoint}</span></td>
                  <td><span className={`badge ${r.language === "hu" ? "badge-info" : "badge-success"}`}>{r.language}</span></td>
                  <td>
                    <span className={`badge ${r.result_count === 0 ? "badge-danger" : "badge-neutral"}`}>
                      {r.result_count}
                    </span>
                  </td>
                  <td><span className="badge badge-neutral">{r.response_time_ms}ms</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
