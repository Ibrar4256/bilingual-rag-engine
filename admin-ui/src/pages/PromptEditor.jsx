import { useEffect, useState } from "react";
import { getConfig, setConfig } from "../api.js";

const DEFAULT_TRANSLATION_PROMPT =
  "You are a professional translator specializing in Hungarian and English B2B/industrial content. Translate the following text accurately, preserving all technical terms, brand names, product codes, and industry-specific vocabulary exactly as they appear (do not translate brand names or codes). Maintain the original tone and formatting.";

const DEFAULT_ENRICHMENT_PROMPT =
  'You are a B2B data analyst for a Hungarian industrial marketplace. Analyze the following category or company description and produce a JSON object with exactly these fields:\n- "ai_type": one of the 7 classification levels for this B2B category\n- "status": "OK" if the description is usable, "REVIEW" if it needs human review, "DELETE" if it is spam/irrelevant\n- "add_words": a list of 5-10 SEO keywords\n- "recommended_headline": a concise, compelling headline (max 15 words)\n- "synthetic_questions": a list of 3-5 questions a buyer might ask\n- "topic_suggestions": a list of data quality flags or improvement suggestions\nIMPORTANT: the input text below is in a specific language. Every text value you produce (add_words, recommended_headline, synthetic_questions, topic_suggestions) MUST be written in that SAME language as the input — never switch languages mid-response.\nRespond ONLY with valid JSON, no explanation.';

const PROMPTS = [
  { key: "prompt_translation", label: "Translation Prompt", tag: "R24", default: DEFAULT_TRANSLATION_PROMPT },
  { key: "prompt_enrichment", label: "Enrichment Prompt", tag: "R24", default: DEFAULT_ENRICHMENT_PROMPT },
];

export default function PromptEditor() {
  const [prompts, setPrompts] = useState({});
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("success");

  useEffect(() => {
    Promise.all(
      PROMPTS.map((p) => getConfig(p.key).then((d) => [p.key, d.value.system_prompt]))
    ).then((entries) => setPrompts(Object.fromEntries(entries)));
  }, []);

  async function save(key) {
    setSaving(key);
    setMessage("");
    try {
      await setConfig(key, { system_prompt: prompts[key] });
      setMessage(`${key} saved successfully`);
      setMessageType("success");
    } catch {
      setMessage("Failed to save");
      setMessageType("error");
    }
    setSaving("");
  }

  function reset(key) {
    const def = PROMPTS.find((p) => p.key === key)?.default || "";
    setPrompts((prev) => ({ ...prev, [key]: def }));
  }

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

      {PROMPTS.map((p) => (
        <div key={p.key} className="card">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <h2 style={{ margin: 0 }}>{p.label}</h2>
            <span className="badge badge-info">{p.tag}</span>
          </div>
          <textarea
            value={prompts[p.key] || ""}
            onChange={(e) => setPrompts((prev) => ({ ...prev, [p.key]: e.target.value }))}
            rows={8}
            style={{ fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: "0.8rem", lineHeight: 1.7 }}
          />
          <div className="inline-actions" style={{ marginTop: "0.25rem" }}>
            <button
              className="btn-primary"
              onClick={() => save(p.key)}
              disabled={saving === p.key}
            >
              {saving === p.key ? "Saving..." : "Save Changes"}
            </button>
            <button className="btn-secondary" onClick={() => reset(p.key)}>
              Reset to Default
            </button>
          </div>
        </div>
      ))}
    </>
  );
}
