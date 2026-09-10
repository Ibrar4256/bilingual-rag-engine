import { useState, useRef, useEffect } from "react";

const API_BASE = "";

export default function SearchAgent() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEnd = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!query.trim() || loading) return;
    const q = query.trim();
    setQuery("");
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setLoading(true);

    try {
      const resp = await fetch(`${API_BASE}/agent/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      const data = await resp.json();

      if (data.detail) {
        setMessages((prev) => [...prev, { role: "assistant", text: `Error: ${data.detail}` }]);
      } else {
        setMessages((prev) => [...prev, {
          role: "assistant",
          text: data.answer,
          plan: data.plan,
          toolResults: data.tool_results,
          timing: data.timing,
        }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Error: ${err.message}` }]);
    }
    setLoading(false);
  }

  function AgentBubble({ msg }) {
    return (
      <div style={{ marginBottom: "1rem" }}>
        <div style={{
          padding: "0.85rem 1.1rem",
          borderRadius: "var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px",
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          boxShadow: "var(--shadow-sm)",
          fontSize: "0.875rem",
          lineHeight: 1.65,
          whiteSpace: "pre-wrap",
        }}>
          {msg.text}

          {msg.plan && (
            <details style={{ marginTop: "0.75rem" }}>
              <summary style={{
                cursor: "pointer", fontWeight: 600, fontSize: "0.8rem",
                color: "var(--accent)", display: "flex", alignItems: "center", gap: "0.3rem",
              }}>
                {"\u{1F9E0}"} Agent Reasoning
              </summary>

              <div style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
                <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Plan:</div>
                <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
                  {msg.plan.map((t, i) => (
                    <span key={i} className="badge badge-info">{t.name}({t.args?.query})</span>
                  ))}
                </div>

                <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Execution:</div>
                {msg.toolResults?.map((tr, i) => (
                  <div key={i} style={{ marginBottom: "0.25rem" }}>
                    <span className={`badge ${tr.error ? "badge-danger" : "badge-success"}`} style={{ marginRight: "0.3rem" }}>
                      {tr.tool}
                    </span>
                    {tr.error
                      ? <span style={{ color: "var(--danger)", fontSize: "0.75rem" }}>{tr.error}</span>
                      : <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                          {tr.result_count} results for "{tr.query}"
                        </span>
                    }
                  </div>
                ))}

                {msg.timing && (
                  <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                    <span className="badge badge-neutral">Plan: {msg.timing.plan_ms}ms</span>
                    <span className="badge badge-neutral">Search: {msg.timing.execution_ms}ms</span>
                    <span className="badge badge-neutral">Synthesis: {msg.timing.synthesis_ms}ms</span>
                    <span className="badge badge-neutral">Total: {msg.timing.total_ms}ms</span>
                  </div>
                )}
              </div>
            </details>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="card" style={{ padding: "0.75rem 1rem" }}>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-muted)" }}>
          The search agent uses an LLM to plan which search tools to call,
          executes them, and synthesizes results. Expand "Agent Reasoning" to see the plan.
        </p>
      </div>

      <div className="card" style={{
        flex: 1, display: "flex", flexDirection: "column",
        minHeight: 400, padding: 0, overflow: "hidden",
      }}>
        <div style={{
          flex: 1, overflowY: "auto", padding: "1.25rem",
          background: "var(--bg-body)",
        }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{1F916}"}</div>
              <p style={{ fontSize: "0.95rem", fontWeight: 500 }}>AI Search Agent</p>
              <p style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                Ask a question — the agent decides which search tools to use.
              </p>
              <div style={{ marginTop: "1rem", display: "flex", flexWrap: "wrap", gap: "0.4rem", justifyContent: "center" }}>
                {[
                  "Find companies that make industrial pumps",
                  "What welding categories exist?",
                  "Which companies offer CNC machining services?",
                ].map((q) => (
                  <button key={q} className="chip" onClick={() => setQuery(q)}
                    style={{ fontSize: "0.75rem" }}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            msg.role === "user" ? (
              <div key={i} style={{ display: "flex", justifyContent: "flex-end", marginBottom: "0.75rem" }}>
                <div style={{
                  maxWidth: "80%", padding: "0.85rem 1.1rem",
                  borderRadius: "var(--radius-lg) var(--radius-lg) 4px var(--radius-lg)",
                  background: "var(--accent-gradient)", color: "#fff",
                  boxShadow: "var(--shadow-sm)", fontSize: "0.875rem",
                }}>
                  {msg.text}
                </div>
              </div>
            ) : (
              <AgentBubble key={i} msg={msg} />
            )
          ))}

          {loading && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "0.75rem" }}>
              <div style={{
                padding: "0.85rem 1.1rem", borderRadius: "var(--radius-lg)",
                background: "var(--bg-card)", border: "1px solid var(--border)",
                fontSize: "0.875rem", color: "var(--text-muted)",
              }}>
                Agent thinking... planning tools...
              </div>
            </div>
          )}
          <div ref={chatEnd} />
        </div>

        <form onSubmit={handleSend} style={{
          display: "flex", gap: "0.5rem", padding: "0.75rem 1rem",
          borderTop: "1px solid var(--border)", background: "var(--bg-card)",
        }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask the search agent a question..."
            style={{ flex: 1, marginBottom: 0 }}
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="btn-primary" disabled={loading || !query.trim()}>
            {loading ? "..." : "Ask"}
          </button>
        </form>
      </div>
    </>
  );
}
