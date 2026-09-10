import { useState, useEffect, useRef } from "react";
import { searchCategories, matchCompanies, searchSingleCompany, getSuggestions } from "../api.js";

const ENDPOINTS = [
  { id: "category", label: "Categories (R15)" },
  { id: "companies", label: "Companies (R16)" },
  { id: "single", label: "Single Company (R17)" },
];

function highlightText(text, query) {
  if (!query || !text) return text;
  const words = query.split(/\s+/).filter((w) => w.length >= 2);
  if (words.length === 0) return text;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} style={{ background: "#fde68a", borderRadius: 3, padding: "0 2px" }}>{part}</mark>
    ) : (
      part
    )
  );
}

function ResultCard({ result, type, query, rank }) {
  const id = type === "category" ? result.category_id : result.company_id;
  const text = type === "category" ? result.narrative : result.content_chunk;
  return (
    <div className="result-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem", flexWrap: "wrap", gap: "0.35rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{
            width: 22, height: 22, borderRadius: "50%", background: "var(--accent-light)",
            color: "var(--accent)", fontSize: "0.7rem", fontWeight: 700,
            display: "inline-flex", alignItems: "center", justifyContent: "center",
          }}>
            {rank}
          </span>
          <strong style={{ fontSize: "0.875rem" }}>
            {type === "category" ? "Category" : "Company"} #{id}
          </strong>
          <span className={`badge ${result.language === "hu" ? "badge-info" : "badge-success"}`}>
            {result.language?.toUpperCase()}
          </span>
          {result.is_highlighted && <span className="badge badge-warning">Partner</span>}
        </div>
        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
          <span className="badge badge-neutral">RRF {result.rrf_score?.toFixed(4)}</span>
          {result.reranked_score != null && (
            <span className="badge badge-info">Re-ranked {result.reranked_score.toFixed(4)}</span>
          )}
          {result.cosine_similarity != null && (
            <span className="badge badge-success">Cos {result.cosine_similarity.toFixed(4)}</span>
          )}
        </div>
      </div>
      <p style={{ fontSize: "0.825rem", margin: 0, whiteSpace: "pre-wrap", maxHeight: 120, overflow: "auto", color: "var(--text-secondary)", lineHeight: 1.6 }}>
        {highlightText(text, query)}
      </p>
      {result.metadata && Object.keys(result.metadata).length > 0 && (
        <details style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
          <summary style={{ cursor: "pointer", color: "var(--text-muted)", fontWeight: 500 }}>Metadata</summary>
          <pre style={{
            margin: "0.25rem 0", whiteSpace: "pre-wrap", fontSize: "0.75rem",
            background: "var(--bg-input)", padding: "0.5rem", borderRadius: "var(--radius-sm)",
          }}>
            {JSON.stringify(result.metadata, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

export default function SearchTest() {
  const [endpoint, setEndpoint] = useState("category");
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [limit, setLimit] = useState(10);
  const [companyId, setCompanyId] = useState("");
  const [filterAiType, setFilterAiType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [suggestions, setSuggestions] = useState([]);
  const suggestTimer = useRef(null);
  const [rerank, setRerank] = useState(false);
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    clearTimeout(suggestTimer.current);
    if (query.length < 2) { setSuggestions([]); return; }
    suggestTimer.current = setTimeout(async () => {
      const s = await getSuggestions(query);
      setSuggestions(s);
    }, 300);
    return () => clearTimeout(suggestTimer.current);
  }, [query]);

  async function doSearch(searchOffset = 0) {
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResponse(null);
    try {
      const filters = {};
      if (filterAiType) filters.ai_type = filterAiType;
      if (filterStatus) filters.status = filterStatus;
      const hasFilters = Object.keys(filters).length > 0 ? filters : undefined;
      let data;
      if (endpoint === "category") {
        data = await searchCategories(query, language, limit, hasFilters, searchOffset, rerank);
      } else if (endpoint === "companies") {
        data = await matchCompanies(query, language, limit, hasFilters, searchOffset, rerank);
      } else {
        if (!companyId.trim()) {
          setError("Company ID is required for single-company search");
          setLoading(false);
          return;
        }
        data = await searchSingleCompany(companyId, query, language, limit, searchOffset, rerank);
      }
      if (data.detail) {
        setError(data.detail);
      } else {
        setOffset(searchOffset);
        setResponse(data);
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  function handleSearch(e) {
    e.preventDefault();
    setOffset(0);
    doSearch(0);
  }

  function exportCsv() {
    if (!response?.results?.length) return;
    const isCategory = endpoint === "category";
    const headers = isCategory
      ? ["ID", "Language", "RRF Score", "AI Type", "Status", "Narrative"]
      : ["ID", "Language", "RRF Score", "Chunk Index", "Partner", "Content"];
    const rows = response.results.map((r) =>
      isCategory
        ? [r.category_id, r.language, r.rrf_score, r.metadata?.ai_type || "", r.metadata?.status || "", `"${(r.narrative || "").replace(/"/g, '""')}"`]
        : [r.company_id, r.language, r.rrf_score, r.chunk_index, r.is_highlighted ? "Yes" : "No", `"${(r.content_chunk || "").replace(/"/g, '""')}"`]
    );
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `search-results-${endpoint}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div className="card">
        <div className="field-group">
          <label>Endpoint</label>
          <div className="chip-group">
            {ENDPOINTS.map((ep) => (
              <button
                key={ep.id}
                className={`chip ${endpoint === ep.id ? "active" : ""}`}
                onClick={() => { setEndpoint(ep.id); setResponse(null); setError(""); }}
              >
                {ep.label}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={handleSearch}>
          <div className="field-group">
            <label htmlFor="search-query">Query</label>
            <input
              id="search-query"
              type="text"
              list="query-suggestions"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={endpoint === "category"
                ? "e.g. ipari szivattyú gyártó"
                : "e.g. industrial pump manufacturer"}
              autoComplete="off"
            />
            <datalist id="query-suggestions">
              {suggestions.map((s, i) => (
                <option key={i} value={s} />
              ))}
            </datalist>
          </div>

          {endpoint === "single" && (
            <div className="field-group">
              <label htmlFor="company-id">Company ID</label>
              <input
                id="company-id"
                type="text"
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                placeholder="e.g. 65276"
              />
            </div>
          )}

          {endpoint !== "single" && (
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <div className="field-group" style={{ flex: 1, minWidth: 140 }}>
                <label htmlFor="filter-ai-type">Filter: ai_type</label>
                <select
                  id="filter-ai-type"
                  value={filterAiType}
                  onChange={(e) => setFilterAiType(e.target.value)}
                >
                  <option value="">All types</option>
                  <option value="Product">Product</option>
                  <option value="Category">Category</option>
                  <option value="Subcategory">Subcategory</option>
                  <option value="Equipment">Equipment</option>
                  <option value="Service">Service</option>
                  <option value="System">System</option>
                  <option value="Technology">Technology</option>
                  <option value="Solution">Solution</option>
                  <option value="Component">Component</option>
                  <option value="Level 3">Level 3</option>
                  <option value="Level 4">Level 4</option>
                  <option value="Level 5">Level 5</option>
                </select>
              </div>
              <div className="field-group" style={{ flex: 1, minWidth: 140 }}>
                <label htmlFor="filter-status">Filter: status</label>
                <select
                  id="filter-status"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="">All statuses</option>
                  <option value="OK">OK</option>
                  <option value="REVIEW">REVIEW</option>
                </select>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end", flexWrap: "wrap" }}>
            <div className="field-group" style={{ flex: 1, minWidth: 120 }}>
              <label htmlFor="search-lang">Language</label>
              <select
                id="search-lang"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="">Auto-detect</option>
                <option value="hu">Hungarian (hu)</option>
                <option value="en">English (en)</option>
              </select>
            </div>
            <div className="field-group" style={{ width: 80 }}>
              <label htmlFor="search-limit">Limit</label>
              <input
                id="search-limit"
                type="number"
                min={1}
                max={100}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
              />
            </div>
            <label style={{
              display: "flex", alignItems: "center", gap: "0.35rem",
              marginBottom: "0.75rem", fontSize: "0.825rem", cursor: "pointer",
              color: "var(--text-secondary)", fontWeight: 500,
            }}>
              <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} />
              Re-rank
            </label>
            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{ marginBottom: "0.75rem" }}
            >
              {loading ? "Searching..." : "Search"}
            </button>
          </div>
        </form>

        {error && <p style={{ color: "var(--danger)", fontWeight: 500, fontSize: "0.85rem" }}>{error}</p>}
      </div>

      {response && (
        <div className="card" style={{ marginTop: "0.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1rem" }}>
            <h2 style={{ margin: 0 }}>
              {response.total_count != null
                ? `${offset + 1}–${offset + (response.results?.length || 0)} of ${response.total_count}`
                : `${response.results?.length || 0} Results`}
            </h2>
            <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap" }}>
              <span className="badge badge-info">Lang: {response.detected_language}</span>
              <span className="badge badge-neutral">{response.response_time_ms?.toFixed(0)}ms</span>
              <span className="badge badge-neutral">{response.retrieval_mode}</span>
              {response.cross_language_fallback_triggered && (
                <span className="badge badge-warning">Cross-language fallback</span>
              )}
              <button className="btn-secondary btn-sm" onClick={exportCsv}>
                Export CSV
              </button>
            </div>
          </div>

          {response.results?.length === 0 && (
            <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem 0" }}>
              No results found. Try a different query or check that ETL data is loaded.
            </p>
          )}

          {response.results?.map((r, i) => (
            <ResultCard
              key={i}
              result={r}
              type={endpoint === "category" ? "category" : "company"}
              query={query}
              rank={offset + i + 1}
            />
          ))}

          {response.total_count != null && response.total_count > limit && (
            <div style={{ display: "flex", justifyContent: "center", gap: "0.75rem", marginTop: "1rem", alignItems: "center" }}>
              <button
                className="btn-secondary btn-sm"
                disabled={offset === 0 || loading}
                onClick={() => doSearch(Math.max(0, offset - limit))}
              >
                Previous
              </button>
              <span style={{ fontSize: "0.825rem", color: "var(--text-secondary)", fontWeight: 500 }}>
                Page {Math.floor(offset / limit) + 1} of {Math.ceil(response.total_count / limit)}
              </span>
              <button
                className="btn-secondary btn-sm"
                disabled={offset + limit >= response.total_count || loading}
                onClick={() => doSearch(offset + limit)}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
