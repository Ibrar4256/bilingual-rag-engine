import { useEffect, useState } from "react";
import { getHealth } from "../api.js";

export default function HealthStatus() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "unreachable" }));
  }, []);

  if (!health) return null;

  const ok = health.status === "ok";
  return (
    <div className={`status-bar ${ok ? "" : "error"}`}>
      <span className={`status-dot ${ok ? "" : "offline"}`} />
      <span style={{ fontWeight: 600 }}>API: {health.status}</span>
      {health.response_time_ms != null && (
        <span className="badge badge-neutral">{health.response_time_ms.toFixed(0)}ms</span>
      )}
      {health.checks && (
        <span style={{ marginLeft: "auto", display: "flex", gap: "0.5rem" }}>
          <span className={`badge ${health.checks.database ? "badge-success" : "badge-danger"}`}>
            DB {health.checks.database ? "OK" : "Down"}
          </span>
          <span className={`badge ${health.checks.vector_index ? "badge-success" : "badge-warning"}`}>
            Vector {health.checks.vector_index ? "OK" : "Missing"}
          </span>
          <span className={`badge ${health.checks.bm25_index ? "badge-success" : "badge-warning"}`}>
            BM25 {health.checks.bm25_index ? "OK" : "Missing"}
          </span>
        </span>
      )}
    </div>
  );
}
