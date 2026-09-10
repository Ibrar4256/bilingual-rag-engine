import { useEffect, useState } from "react";
import { getConfig, setConfig, getProviderAvailability } from "../api.js";

const LLM_OPTIONS = ["groq", "openrouter", "gemini", "9router", "cerebras", "sambanova", "custom_openai"];
const EMBEDDING_OPTIONS = ["gemini", "jina", "9router", "local_bge_m3"];

export default function ProviderSettings() {
  const [llm, setLlm] = useState("");
  const [embedding, setEmbedding] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("success");
  const [availability, setAvailability] = useState({});

  useEffect(() => {
    getConfig("llm_provider").then((d) => setLlm(d.value.active));
    getConfig("embedding_provider").then((d) => setEmbedding(d.value.active));
    getProviderAvailability().then((items) => {
      const map = {};
      for (const item of items) {
        map[item.provider] = item;
      }
      setAvailability(map);
    });
  }, []);

  function isAvailable(type, name) {
    const key = `${type}:${name}`;
    const entry = availability[key];
    return entry ? entry.available : true;
  }

  function unavailableReason(type, name) {
    const key = `${type}:${name}`;
    const entry = availability[key];
    return entry && !entry.available ? entry.reason : null;
  }

  async function saveLlm(value) {
    setSaving(true);
    setMessage("");
    try {
      await setConfig("llm_provider", { active: value });
      setLlm(value);
      setMessage("LLM provider saved");
      setMessageType("success");
    } catch (err) {
      setMessage(err.message);
      setMessageType("error");
    }
    setSaving(false);
  }

  async function saveEmbedding(value) {
    setSaving(true);
    setMessage("");
    try {
      const current = await getConfig("embedding_provider");
      await setConfig("embedding_provider", { ...current.value, active: value });
      setEmbedding(value);
      setMessage("Embedding provider saved");
      setMessageType("success");
    } catch (err) {
      setMessage(err.message);
      setMessageType("error");
    }
    setSaving(false);
  }

  return (
    <>
      {message && (
        <div className={`card`} style={{
          background: messageType === "error" ? "var(--danger-bg)" : "var(--success-bg)",
          borderColor: messageType === "error" ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)",
          padding: "0.75rem 1rem",
        }}>
          <p style={{ color: messageType === "error" ? "var(--danger)" : "var(--success)", fontWeight: 500, margin: 0, fontSize: "0.85rem" }}>
            {message}
          </p>
        </div>
      )}

      <div className="card">
        <h2>LLM Provider (R22)</h2>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
          Used for translation and AI enrichment during ETL runs. Changes take effect on the next ETL run.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {LLM_OPTIONS.filter((o) => isAvailable("llm", o)).map((o) => (
              <button
                key={o}
                className={`chip ${llm === o ? "active" : ""}`}
                onClick={() => saveLlm(o)}
                disabled={saving}
                style={{ textTransform: "capitalize" }}
              >
                {o}
              </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Embedding Provider (R23)</h2>
        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
          Generates vector embeddings for semantic search. Changing this requires a full ETL re-run to regenerate all embeddings.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {EMBEDDING_OPTIONS.filter((o) => isAvailable("embedding", o)).map((o) => (
              <button
                key={o}
                className={`chip ${embedding === o ? "active" : ""}`}
                onClick={() => saveEmbedding(o)}
                disabled={saving}
              >
                {o}
              </button>
          ))}
        </div>
        {unavailableReason("embedding", embedding) && (
          <p style={{ fontSize: "0.8rem", color: "var(--danger)", marginTop: "0.5rem" }}>
            Warning: current provider may not work — {unavailableReason("embedding", embedding)}
          </p>
        )}
      </div>
    </>
  );
}
