import { useState, useEffect, useRef } from "react";
import { getLogs } from "../api.js";

const LEVEL_COLORS = {
  DEBUG: "#9ca3af",
  INFO: "#3b82f6",
  WARNING: "#f59e0b",
  ERROR: "#ef4444",
  CRITICAL: "#dc2626",
};

export default function Logs() {
  const [entries, setEntries] = useState([]);
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef(null);

  async function fetchLogs() {
    try {
      const data = await getLogs(300, level || null, search || null);
      setEntries(data);
    } catch { /* auth redirect handled */ }
    setLoading(false);
  }

  useEffect(() => {
    fetchLogs();
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [level, search, autoRefresh]);

  useEffect(() => {
    if (autoRefresh && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [entries]);

  if (loading) return <div className="card"><p style={{ color: "var(--text-muted)" }}>Loading logs...</p></div>;

  return (
    <>
      <div className="card" style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          style={{
            padding: "0.4rem 0.6rem",
            borderRadius: "6px",
            border: "1px solid var(--border)",
            background: "var(--bg-card)",
            color: "var(--text)",
            fontSize: "0.8rem",
          }}
        >
          <option value="">All levels</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>

        <input
          type="text"
          placeholder="Search logs..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "0.4rem 0.6rem",
            borderRadius: "6px",
            border: "1px solid var(--border)",
            background: "var(--bg-card)",
            color: "var(--text)",
            fontSize: "0.8rem",
            flex: 1,
            minWidth: "150px",
          }}
        />

        <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.3rem" }}>
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          Auto-refresh (5s)
        </label>

        <button
          onClick={fetchLogs}
          className="chip"
          style={{ fontSize: "0.75rem", padding: "0.3rem 0.7rem" }}
        >
          Refresh
        </button>

        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          {entries.length} entries
        </span>
      </div>

      <div
        className="card"
        style={{
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          fontSize: "0.72rem",
          lineHeight: "1.6",
          maxHeight: "65vh",
          overflowY: "auto",
          padding: "0.75rem",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {entries.length === 0 ? (
          <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem" }}>
            No log entries{level ? ` at ${level} level` : ""}{search ? ` matching "${search}"` : ""}.
          </p>
        ) : (
          entries.map((e, i) => (
            <div
              key={i}
              style={{
                padding: "0.15rem 0",
                borderBottom: "1px solid var(--border)",
                opacity: e.level === "DEBUG" ? 0.6 : 1,
              }}
            >
              <span style={{ color: "var(--text-muted)" }}>{e.timestamp.split(" ")[1]}</span>
              {" "}
              <span
                style={{
                  color: LEVEL_COLORS[e.level] || "var(--text)",
                  fontWeight: e.level === "ERROR" || e.level === "WARNING" ? 600 : 400,
                  display: "inline-block",
                  width: "5.5ch",
                }}
              >
                {e.level.padEnd(5)}
              </span>
              {" "}
              <span style={{ color: "var(--primary)", opacity: 0.7 }}>{e.module}:{e.function}:{e.line}</span>
              {" "}
              <span style={{ color: e.level === "ERROR" ? LEVEL_COLORS.ERROR : "var(--text)" }}>
                {e.message}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </>
  );
}
