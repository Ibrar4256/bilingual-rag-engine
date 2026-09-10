import { useState, useRef, useEffect, useCallback } from "react";
import { listConversations, getConversation, saveConversation, deleteConversation } from "../api.js";

function CitationBadge({ c }) {
  return (
    <span className="badge badge-info" style={{ marginRight: "0.3rem", cursor: "default" }}
      title={`${c.type} #${c.id} (${c.language}) — RRF ${c.rrf_score.toFixed(4)}`}>
      [{c.ref}] {c.type} #{c.id}
    </span>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "0.75rem",
    }}>
      <div style={{
        maxWidth: "80%",
        padding: "0.85rem 1.1rem",
        borderRadius: isUser ? "var(--radius-lg) var(--radius-lg) 4px var(--radius-lg)" : "var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px",
        background: isUser ? "var(--accent-gradient)" : "var(--bg-card)",
        color: isUser ? "#fff" : "var(--text-primary)",
        border: isUser ? "none" : "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
        fontSize: "0.875rem",
        lineHeight: 1.65,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}>
        {msg.text}
        {msg.citations && msg.citations.length > 0 && (
          <div style={{ marginTop: "0.6rem", paddingTop: "0.5rem", borderTop: "1px solid rgba(255,255,255,0.15)" }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.3rem", opacity: 0.7 }}>
              Sources
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
              {msg.citations.map((c) => <CitationBadge key={c.ref} c={c} />)}
            </div>
          </div>
        )}
        {msg.meta && (
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
            <span className="badge badge-neutral">{msg.meta.retrieval_mode}</span>
            <span className="badge badge-neutral">{msg.meta.response_time_ms?.toFixed(0)}ms</span>
            <span className={`badge ${msg.meta.detected_language === "hu" ? "badge-info" : "badge-success"}`}>
              {msg.meta.detected_language?.toUpperCase()}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationList({ conversations, activeId, onSelect, onDelete, onNew }) {
  return (
    <div style={{
      width: 220, borderRight: "1px solid var(--border)", background: "var(--bg-card)",
      display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0,
    }}>
      <div style={{ padding: "0.6rem", borderBottom: "1px solid var(--border)" }}>
        <button className="btn-primary" onClick={onNew}
          style={{ width: "100%", fontSize: "0.8rem", padding: "0.4rem 0.6rem" }}>
          + New Chat
        </button>
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "0.3rem" }}>
        {conversations.length === 0 && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", textAlign: "center", padding: "1rem 0.5rem" }}>
            No saved conversations yet
          </p>
        )}
        {conversations.map((c) => (
          <div key={c.id}
            onClick={() => onSelect(c.id)}
            style={{
              padding: "0.5rem 0.6rem", borderRadius: "var(--radius-md)", cursor: "pointer",
              marginBottom: "0.2rem", fontSize: "0.8rem",
              background: c.id === activeId ? "var(--accent-muted)" : "transparent",
              color: c.id === activeId ? "var(--accent)" : "var(--text-secondary)",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
            <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
              {c.title}
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                {c.message_count} msgs
              </div>
            </div>
            <button onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
              style={{
                background: "none", border: "none", cursor: "pointer", padding: "0.15rem 0.3rem",
                color: "var(--text-muted)", fontSize: "0.7rem", borderRadius: "var(--radius-sm)",
                flexShrink: 0, opacity: 0.5,
              }}
              onMouseEnter={(e) => e.target.style.opacity = 1}
              onMouseLeave={(e) => e.target.style.opacity = 0.5}
              title="Delete conversation">
              x
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RAGChat() {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [table, setTable] = useState("category_vectors");
  const [limit, setLimit] = useState(5);
  const [loading, setLoading] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const chatEnd = useRef(null);
  const saveTimer = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    loadConversations();
  }, []);

  async function loadConversations() {
    try {
      const list = await listConversations();
      setConversations(list);
    } catch {
      /* auth redirect handled by apiFetch */
    }
  }

  const autoSave = useCallback((msgs, convId) => {
    clearTimeout(saveTimer.current);
    if (msgs.length < 2) return;
    saveTimer.current = setTimeout(async () => {
      try {
        const firstUserMsg = msgs.find((m) => m.role === "user");
        const title = firstUserMsg ? firstUserMsg.text.slice(0, 60) : "Untitled";
        const saved = await saveConversation(convId, title, msgs);
        setActiveConvId(saved.id);
        loadConversations();
      } catch { /* silent */ }
    }, 1500);
  }, []);

  async function handleSelectConversation(id) {
    clearTimeout(saveTimer.current);
    if (messages.length >= 2 && activeConvId !== id) {
      try {
        const firstUserMsg = messages.find((m) => m.role === "user");
        const title = firstUserMsg ? firstUserMsg.text.slice(0, 60) : "Untitled";
        await saveConversation(activeConvId, title, messages);
      } catch { /* silent */ }
    }
    try {
      const conv = await getConversation(id);
      setMessages(conv.messages);
      setActiveConvId(id);
    } catch { /* silent */ }
  }

  async function handleDeleteConversation(id) {
    try {
      await deleteConversation(id);
      if (activeConvId === id) {
        setMessages([]);
        setActiveConvId(null);
      }
      loadConversations();
    } catch { /* silent */ }
  }

  async function handleNewChat() {
    clearTimeout(saveTimer.current);
    if (messages.length >= 2) {
      try {
        const firstUserMsg = messages.find((m) => m.role === "user");
        const title = firstUserMsg ? firstUserMsg.text.slice(0, 60) : "Untitled";
        await saveConversation(activeConvId, title, messages);
        loadConversations();
      } catch { /* silent */ }
    }
    setMessages([]);
    setActiveConvId(null);
    setQuery("");
  }

  async function handleSend(e) {
    e.preventDefault();
    if (!query.trim() || loading) return;
    const q = query.trim();
    setQuery("");
    const newMsgs = [...messages, { role: "user", text: q }];
    setMessages(newMsgs);
    setLoading(true);

    const assistantIdx = newMsgs.length;
    setMessages((prev) => [...prev, { role: "assistant", text: "", streaming: true }]);

    try {
      const resp = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, table, limit, stream: true }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        setMessages((prev) => {
          const updated = [...prev];
          updated[assistantIdx] = { role: "assistant", text: `Error: ${err.detail || resp.statusText}` };
          return updated;
        });
        setLoading(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let meta = {};
      let fullText = "";
      let finalMessages = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventType) {
            const payload = JSON.parse(line.slice(6));
            if (eventType === "metadata") {
              meta = payload;
            } else if (eventType === "token") {
              fullText += payload.text;
              setMessages((prev) => {
                const updated = [...prev];
                updated[assistantIdx] = {
                  role: "assistant",
                  text: fullText,
                  citations: meta.citations,
                  streaming: true,
                };
                return updated;
              });
            } else if (eventType === "done") {
              const assistantMsg = {
                role: "assistant",
                text: fullText,
                citations: meta.citations,
                meta: {
                  detected_language: meta.detected_language,
                  retrieval_mode: meta.retrieval_mode,
                  response_time_ms: payload.response_time_ms,
                },
                streaming: false,
              };
              setMessages((prev) => {
                const updated = [...prev];
                updated[assistantIdx] = assistantMsg;
                finalMessages = updated;
                return updated;
              });
            }
            eventType = "";
          }
        }
      }

      if (finalMessages) {
        autoSave(finalMessages, activeConvId);
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[assistantIdx] = { role: "assistant", text: `Error: ${err.message}` };
        return updated;
      });
    }
    setLoading(false);
  }

  return (
    <>
      <div className="card" style={{ padding: "0.75rem 1rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <button className="chip" onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}>
            {sidebarOpen ? "Hide History" : "Show History"}
          </button>
          <label style={{ margin: 0, fontSize: "0.8rem", fontWeight: 600 }}>Search in:</label>
          <div className="chip-group">
            <button className={`chip ${table === "category_vectors" ? "active" : ""}`}
              onClick={() => setTable("category_vectors")}>Categories</button>
            <button className={`chip ${table === "company_vectors" ? "active" : ""}`}
              onClick={() => setTable("company_vectors")}>Companies</button>
          </div>
          <label style={{ margin: 0, fontSize: "0.8rem", fontWeight: 600 }}>Context docs:</label>
          <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}
            style={{ width: 60, marginBottom: 0, padding: "0.3rem 0.4rem", fontSize: "0.8rem" }}>
            {[3, 5, 8, 10].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>

      <div className="card" style={{
        flex: 1,
        display: "flex",
        minHeight: 400,
        padding: 0,
        overflow: "hidden",
      }}>
        {sidebarOpen && (
          <ConversationList
            conversations={conversations}
            activeId={activeConvId}
            onSelect={handleSelectConversation}
            onDelete={handleDeleteConversation}
            onNew={handleNewChat}
          />
        )}

        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{
            flex: 1,
            overflowY: "auto",
            padding: "1.25rem",
            background: "var(--bg-body)",
          }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
                <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem", opacity: 0.4 }}>{"\u{1F4AC}"}</div>
                <p style={{ fontSize: "0.95rem", fontWeight: 500 }}>Ask anything about the indexed data</p>
                <p style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
                  The system retrieves relevant documents and generates an answer with citations.
                </p>
                <p style={{ fontSize: "0.75rem", marginTop: "0.5rem", color: "var(--text-muted)" }}>
                  Conversations are saved automatically so you can continue later.
                </p>
                <div style={{ marginTop: "1rem", display: "flex", flexWrap: "wrap", gap: "0.4rem", justifyContent: "center" }}>
                  {[
                    "What types of industrial pumps are available?",
                    "Milyen hegesztési szolgáltatások léteznek?",
                    "Find CNC machining companies",
                  ].map((q) => (
                    <button key={q} className="chip" onClick={() => { setQuery(q); }}
                      style={{ fontSize: "0.75rem" }}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}

            {loading && messages[messages.length - 1]?.text === "" && (
              <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "0.75rem" }}>
                <div style={{
                  padding: "0.85rem 1.1rem", borderRadius: "var(--radius-lg)",
                  background: "var(--bg-card)", border: "1px solid var(--border)",
                  fontSize: "0.875rem", color: "var(--text-muted)",
                }}>
                  Retrieving documents & generating answer...
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
              placeholder="Ask a question about categories or companies..."
              style={{ flex: 1, marginBottom: 0 }}
              disabled={loading}
              autoFocus
            />
            <button type="submit" className="btn-primary" disabled={loading || !query.trim()}>
              {loading ? "..." : "Ask"}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}
