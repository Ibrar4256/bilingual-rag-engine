import { useState } from "react";

const CATEGORY_EXAMPLES = [
  {
    label: "Hungarian product search",
    query: "ipari szivattyú gyártó",
    endpoint: "category",
    lang: "hu",
    desc: "Searches for industrial pump manufacturers in Hungarian. Tests the HU BM25 + vector dual-path.",
  },
  {
    label: "English product search",
    query: "industrial pump manufacturer",
    endpoint: "category",
    lang: "en",
    desc: "Same concept in English. Compare results with the Hungarian query above to verify cross-language coverage.",
  },
  {
    label: "Cross-language fallback",
    query: "solar panel installation",
    endpoint: "category",
    lang: "",
    desc: "If fewer than 3 results in the detected language, the system falls back to the other language. Watch for the 'Cross-language fallback triggered' badge.",
  },
  {
    label: "Specific category type",
    query: "acél szerkezet",
    endpoint: "category",
    lang: "hu",
    desc: "Steel structures search. Use the ai_type filter dropdown to narrow to 'Product' or 'Service' types.",
  },
];

const COMPANY_EXAMPLES = [
  {
    label: "Company matching by capability",
    query: "CNC machining precision parts",
    endpoint: "companies",
    lang: "en",
    desc: "Finds companies whose narrative mentions CNC machining. Tests company vector search.",
  },
  {
    label: "Hungarian company search",
    query: "hegesztés és fémmegmunkálás",
    endpoint: "companies",
    lang: "hu",
    desc: "Welding and metalworking — tests Hungarian company matching.",
  },
  {
    label: "Single company deep search",
    query: "main products",
    endpoint: "single",
    companyId: "65276",
    desc: "Searches within a specific company's chunks. Enter company ID 65276 and query 'main products'.",
  },
];

const FEATURE_TESTS = [
  {
    title: "Re-ranking (semantic)",
    steps: [
      "Run a category search for 'industrial automation'",
      "Note the order and RRF scores",
      "Enable the 'Re-rank' checkbox and search again",
      "Results should show Cos (cosine similarity) and Re-ranked scores",
      "Order may differ — re-ranking blends 70% RRF + 30% cosine similarity",
    ],
  },
  {
    title: "Faceted filtering",
    steps: [
      "Search categories for 'pump'",
      "Use the 'Filter: ai_type' dropdown to select 'Product'",
      "Results should only include items classified as Product",
      "Try 'Filter: status' = 'REVIEW' to see items flagged for review",
    ],
  },
  {
    title: "Pagination",
    steps: [
      "Set Limit to 5 and search for a broad term like 'industrial'",
      "The result header shows '1-5 of N' with page controls",
      "Click Next/Previous to browse pages",
      "Total count should remain consistent across pages",
    ],
  },
  {
    title: "CSV export",
    steps: [
      "Run any search that returns results",
      "Click 'Export CSV' in the results header",
      "A .csv file downloads with all result fields",
      "Open it in Excel or Google Sheets to verify column structure",
    ],
  },
  {
    title: "Autocomplete / suggestions",
    steps: [
      "Start typing a query slowly (at least 2 characters)",
      "A suggestion dropdown should appear below the input",
      "Suggestions come from previous successful searches",
      "Select a suggestion to auto-fill the query field",
    ],
  },
  {
    title: "Query highlighting",
    steps: [
      "Search for 'industrial pump' in categories",
      "In the result text, matching words should be highlighted in yellow",
      "Highlighting works for both English and Hungarian terms",
    ],
  },
];

const API_ENDPOINTS = [
  { method: "POST", path: "/search/category", desc: "Search categories with bilingual RRF fusion" },
  { method: "POST", path: "/match/companies", desc: "Match companies by capability description" },
  { method: "POST", path: "/search/single-company", desc: "Search within one company's chunks" },
  { method: "GET", path: "/search/suggest?q=...", desc: "Autocomplete suggestions from query history" },
  { method: "GET", path: "/health", desc: "API health check with DB/vector/BM25 status" },
  { method: "POST", path: "/auth/login", desc: "Authenticate and receive JWT token" },
  { method: "GET", path: "/admin/analytics", desc: "Search usage analytics and metrics" },
  { method: "GET", path: "/admin/etl/progress", desc: "Current ETL pipeline status" },
];

function CopyableQuery({ query }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(query).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <span
      className="example-query"
      onClick={handleCopy}
      title="Click to copy"
    >
      {query} {copied ? " (copied)" : ""}
    </span>
  );
}

export default function TestingGuide() {
  const [section, setSection] = useState("quick");

  const sections = [
    { id: "quick", label: "Quick Start" },
    { id: "categories", label: "Category Search" },
    { id: "companies", label: "Company Search" },
    { id: "features", label: "Feature Tests" },
    { id: "api", label: "API Reference" },
  ];

  return (
    <>
      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        {sections.map((s) => (
          <button
            key={s.id}
            className={`chip ${section === s.id ? "active" : ""}`}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === "quick" && (
        <div className="card">
          <h2>Quick Start Guide</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1.25rem" }}>
            This admin panel lets you test the bilingual (Hungarian/English) search infrastructure
            for a Hungarian B2B platform. The system uses a hybrid retrieval approach combining BM25 (keyword) and
            vector (semantic) search, fused with Reciprocal Rank Fusion (RRF).
          </p>

          <div className="guide-section">
            <h3>How to run your first search</h3>
            <ol className="step-list">
              <li>Go to the <strong>Search Test</strong> tab in the sidebar</li>
              <li>Select an endpoint: <em>Search Categories</em>, <em>Match Companies</em>, or <em>Single Company</em></li>
              <li>Type a query in Hungarian or English (language is auto-detected)</li>
              <li>Click <strong>Search</strong> to execute the hybrid search</li>
              <li>Results show RRF scores, language, and highlighted matching text</li>
            </ol>
          </div>

          <div className="guide-section">
            <h3>Key concepts</h3>
            <div style={{ display: "grid", gap: "0.5rem" }}>
              {[
                { term: "RRF Score", def: "Reciprocal Rank Fusion — combines BM25 rank and vector rank into a single score. Higher = better match." },
                { term: "BM25", def: "Keyword-based search using lemmatized terms. Works with Hungarian (huspacy) and English (spaCy) separately." },
                { term: "Vector Search", def: "Semantic similarity using embeddings. Finds conceptually related results even if exact words differ." },
                { term: "Cross-language Fallback", def: "When the primary language yields few results, the system automatically searches in the other language too." },
                { term: "Re-ranking", def: "Optional post-processing that blends RRF scores (70%) with actual cosine similarity (30%) for better ordering." },
                { term: "Protected Terms", def: "Brand names, codes, and technical terms that are preserved during lemmatization to avoid corrupting them." },
              ].map((item) => (
                <div key={item.term} className="example-block">
                  <div className="example-label">{item.term}</div>
                  <div style={{ color: "var(--text-secondary)", fontSize: "0.825rem" }}>{item.def}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {section === "categories" && (
        <div className="card">
          <h2>Category Search Examples</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Category search (R15) searches across ~3,000 B2B categories from the platform.
            Each category has been translated, enriched with AI metadata, and indexed in both Hungarian and English.
          </p>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {CATEGORY_EXAMPLES.map((ex) => (
              <div key={ex.label} className="example-block">
                <div className="example-label">{ex.label}</div>
                <div>
                  <CopyableQuery query={ex.query} />
                  {ex.lang && (
                    <span className="badge badge-info" style={{ marginLeft: "0.5rem" }}>
                      {ex.lang.toUpperCase()}
                    </span>
                  )}
                  {!ex.lang && (
                    <span className="badge badge-neutral" style={{ marginLeft: "0.5rem" }}>
                      Auto-detect
                    </span>
                  )}
                </div>
                <div className="example-desc">{ex.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {section === "companies" && (
        <div className="card">
          <h2>Company Search Examples</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Company matching (R16) searches across ~471 companies. Single company search (R17)
            searches within one company's chunked content. Companies with empty descriptions
            use fallback fields (name, services, brands).
          </p>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {COMPANY_EXAMPLES.map((ex) => (
              <div key={ex.label} className="example-block">
                <div className="example-label">{ex.label}</div>
                <div>
                  <CopyableQuery query={ex.query} />
                  {ex.endpoint === "single" && (
                    <span className="badge badge-warning" style={{ marginLeft: "0.5rem" }}>
                      Company ID: {ex.companyId}
                    </span>
                  )}
                  {ex.lang && (
                    <span className="badge badge-info" style={{ marginLeft: "0.5rem" }}>
                      {ex.lang.toUpperCase()}
                    </span>
                  )}
                </div>
                <div className="example-desc">{ex.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {section === "features" && (
        <>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            Step-by-step instructions to verify each feature works correctly.
          </p>
          {FEATURE_TESTS.map((test) => (
            <div key={test.title} className="card">
              <h2>{test.title}</h2>
              <ol className="step-list">
                {test.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          ))}
        </>
      )}

      {section === "api" && (
        <div className="card">
          <h2>API Endpoints</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "1rem" }}>
            The backend runs on FastAPI with auto-generated Swagger docs at{" "}
            <code style={{ background: "var(--bg-input)", padding: "0.15rem 0.4rem", borderRadius: "4px", fontSize: "0.825rem" }}>
              http://localhost:8000/docs
            </code>
          </p>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Endpoint</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {API_ENDPOINTS.map((ep) => (
                  <tr key={ep.path}>
                    <td>
                      <span className={`badge ${ep.method === "POST" ? "badge-info" : "badge-success"}`}>
                        {ep.method}
                      </span>
                    </td>
                    <td style={{ fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: "0.8rem" }}>
                      {ep.path}
                    </td>
                    <td style={{ color: "var(--text-secondary)" }}>{ep.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: "1.25rem" }}>
            <h3>Example curl request</h3>
            <pre style={{
              background: "#0f172a",
              color: "#e2e8f0",
              padding: "1rem",
              borderRadius: "var(--radius-md)",
              fontSize: "0.8rem",
              overflowX: "auto",
              lineHeight: 1.7,
            }}>
{`curl -X POST http://localhost:8000/search/category \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "ipari szivattyú",
    "language": "hu",
    "limit": 5,
    "rerank": true
  }'`}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
