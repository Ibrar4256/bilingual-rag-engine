import { useState, useEffect, useRef } from "react";
import { getEtlProgress, startEtl, stopEtl } from "../api.js";

export default function EtlProgress() {
  const [progress, setProgress] = useState(null);
  const [action, setAction] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("success");
  const timer = useRef(null);

  useEffect(() => {
    function poll() {
      getEtlProgress().then(setProgress).catch(() => {});
    }
    poll();
    timer.current = setInterval(poll, 5000);
    return () => clearInterval(timer.current);
  }, []);

  async function handleStart(force = false) {
    setAction("starting");
    setMessage("");
    try {
      await startEtl(force);
      setMessage(force ? "ETL started (force re-enrichment)" : "ETL started");
      setMessageType("success");
    } catch (err) {
      setMessage(err.message);
      setMessageType("error");
    }
    setAction("");
  }

  async function handleStop() {
    setAction("stopping");
    setMessage("");
    try {
      await stopEtl();
      setMessage("ETL stopped");
      setMessageType("success");
    } catch (err) {
      setMessage(err.message);
      setMessageType("error");
    }
    setAction("");
  }

  if (!progress) return <div className="card"><p style={{ color: "var(--text-muted)" }}>Loading ETL status...</p></div>;

  const isRunning = progress.status === "running" || progress.subprocess_alive;
  const done = (progress.processed || 0) + (progress.skipped || 0) + (progress.failed || 0);
  const total = progress.total || 1;
  const pct = progress.status === "idle" ? 0 : Math.round((done / total) * 100);

  return (
    <>
      {message && (
        <div className="card" style={{
          background: messageType === "error" ? "var(--danger-bg)" : "var(--success-bg)",
          borderColor: messageType === "error" ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)",
          padding: "0.75rem 1rem",
        }}>
          <p style={{ color: messageType === "error" ? "var(--danger)" : "var(--success)", fontWeight: 500, margin: 0, fontSize: "0.85rem" }}>
            {message}
          </p>
        </div>
      )}

      <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.75rem 1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span className={`badge ${isRunning ? "badge-warning" : progress.status === "complete" ? "badge-success" : "badge-neutral"}`}
            style={{ fontSize: "0.85rem", padding: "0.3rem 0.7rem" }}>
            {isRunning ? "Running" : progress.status === "complete" ? "Complete" : progress.status === "failed" ? "Failed" : "Idle"}
          </span>
          {progress.phase && <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Phase: {progress.phase}</span>}
        </div>

        <div style={{ display: "flex", gap: "0.4rem" }}>
          {!isRunning && (
            <>
              <button className="btn-primary" onClick={() => handleStart(false)} disabled={!!action}
                style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}>
                {action === "starting" ? "Starting..." : "Start ETL"}
              </button>
              <button className="chip" onClick={() => handleStart(true)} disabled={!!action}
                style={{ fontSize: "0.75rem" }}>
                Force Re-enrich
              </button>
            </>
          )}
          {isRunning && (
            <button onClick={handleStop} disabled={!!action}
              style={{
                fontSize: "0.8rem", padding: "0.35rem 0.75rem", borderRadius: "var(--radius-md)",
                background: "var(--danger)", color: "#fff", border: "none", cursor: "pointer",
                opacity: action ? 0.6 : 1,
              }}>
              {action === "stopping" ? "Stopping..." : "Stop ETL"}
            </button>
          )}
        </div>
      </div>

      {progress.status !== "idle" && (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Processed</div>
            <div className="stat-value" style={{ color: "var(--success)" }}>{progress.processed || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Skipped</div>
            <div className="stat-value" style={{ color: "var(--text-muted)" }}>{progress.skipped || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value" style={{ color: progress.failed ? "var(--danger)" : "var(--text-muted)" }}>
              {progress.failed || 0}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total</div>
            <div className="stat-value">{progress.total || 0}</div>
          </div>
        </div>
      )}

      {isRunning && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "var(--text-secondary)" }}>
              Progress
            </span>
            <span style={{ fontSize: "0.825rem", fontWeight: 600, color: "var(--accent)" }}>
              {pct}% ({done}/{total})
            </span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.5rem" }}>
            Auto-refreshing every 5 seconds
          </p>
        </div>
      )}

      {progress.status === "complete" && progress.categories && (
        <div className="card">
          <h2>Run Summary</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div>
              <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Categories</h3>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <span className="badge badge-success">{progress.categories.processed} processed</span>
                <span className="badge badge-neutral">{progress.categories.skipped} skipped</span>
                <span className={`badge ${progress.categories.failed ? "badge-danger" : "badge-neutral"}`}>
                  {progress.categories.failed} failed
                </span>
              </div>
            </div>
            <div>
              <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Companies</h3>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <span className="badge badge-success">{progress.companies.processed} processed</span>
                <span className="badge badge-neutral">{progress.companies.skipped} skipped</span>
                <span className={`badge ${progress.companies.failed ? "badge-danger" : "badge-neutral"}`}>
                  {progress.companies.failed} failed
                </span>
              </div>
            </div>
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.75rem" }}>
            Finished at {new Date((progress.finished_at || 0) * 1000).toLocaleString()}
          </p>
        </div>
      )}

      {progress.status === "idle" && (
        <div className="card" style={{ textAlign: "center", padding: "2.5rem 1.5rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{2699}️"}</div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>No ETL run recorded yet.</p>
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "0.25rem" }}>
            Click "Start ETL" above or run manually:
          </p>
          <code style={{ background: "var(--bg-input)", padding: "0.3rem 0.6rem", borderRadius: "4px", fontSize: "0.8rem" }}>
            python -m bilingual_etl.scripts.main_etl
          </code>
        </div>
      )}
    </>
  );
}
