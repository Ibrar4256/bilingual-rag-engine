import { useState } from "react";
import { logout } from "../api.js";
import HealthStatus from "./HealthStatus.jsx";
import ProviderSettings from "./ProviderSettings.jsx";
import PromptEditor from "./PromptEditor.jsx";
import SearchTest from "./SearchTest.jsx";
import EtlProgress from "./EtlProgress.jsx";
import Analytics from "./Analytics.jsx";
import UserManagement from "./UserManagement.jsx";
import TestingGuide from "./TestingGuide.jsx";
import RAGChat from "./RAGChat.jsx";
import Evaluation from "./Evaluation.jsx";
import Observability from "./Observability.jsx";
import ChunkingComparison from "./ChunkingComparison.jsx";
import SearchAgent from "./SearchAgent.jsx";
import Logs from "./Logs.jsx";

const NAV_SECTIONS = [
  {
    label: "Main",
    items: [
      { id: "rag", label: "AI Ask (RAG)", icon: "\u{1F4AC}" },
      { id: "agent", label: "Search Agent", icon: "\u{1F916}" },
      { id: "search", label: "Search Test", icon: "\u{1F50D}" },
      { id: "analytics", label: "Analytics", icon: "\u{1F4CA}" },
      { id: "eval", label: "Evaluation", icon: "\u{1F4CF}" },
      { id: "observe", label: "Observability", icon: "\u{1F4E1}" },
      { id: "chunking", label: "Chunking Lab", icon: "\u{2702}️" },
      { id: "etl", label: "ETL Pipeline", icon: "\u{2699}️" },
      { id: "logs", label: "Application Logs", icon: "\u{1F4CB}" },
    ],
  },
  {
    label: "Configuration",
    items: [
      { id: "providers", label: "AI Providers", icon: "\u{1F916}" },
      { id: "prompts", label: "System Prompts", icon: "\u{1F4DD}" },
      { id: "users", label: "User Management", icon: "\u{1F465}" },
    ],
  },
  {
    label: "Help",
    items: [
      { id: "guide", label: "Testing Guide", icon: "\u{1F4D6}" },
    ],
  },
];

const PAGE_META = {
  rag: { title: "AI Ask (RAG)", desc: "Ask questions and get AI-generated answers with citations from your data" },
  agent: { title: "Search Agent", desc: "AI agent that plans which search tools to use and synthesizes results" },
  search: { title: "Search Test", desc: "Test bilingual search across categories and companies" },
  eval: { title: "Search Quality Evaluation", desc: "Compare retrieval modes with MRR, NDCG, and Recall metrics" },
  observe: { title: "LLM Observability", desc: "Token usage, latency, and cost tracking for every AI call" },
  chunking: { title: "Chunking Lab", desc: "Compare text splitting strategies and their impact on retrieval quality" },
  analytics: { title: "Search Analytics", desc: "Query performance and usage metrics" },
  etl: { title: "ETL Pipeline", desc: "Monitor data processing progress" },
  providers: { title: "AI Providers", desc: "Configure LLM and embedding providers" },
  prompts: { title: "System Prompts", desc: "Edit translation and enrichment prompts" },
  users: { title: "User Management", desc: "Manage admin panel access" },
  logs: { title: "Application Logs", desc: "Live server logs with level filtering and search" },
  guide: { title: "Testing Guide", desc: "How to test the search system with examples" },
};

export default function Dashboard() {
  const [tab, setTab] = useState("search");
  const meta = PAGE_META[tab] || {};

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>
            <div className="sidebar-brand-icon">B</div>
            <div>
              Bilingual Admin
              <span>bilingual search</span>
            </div>
          </h1>
        </div>

        <nav className="sidebar-nav">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label}>
              <div className="sidebar-section-label">{section.label}</div>
              {section.items.map((item) => (
                <button
                  key={item.id}
                  className={`sidebar-link ${tab === item.id ? "active" : ""}`}
                  onClick={() => setTab(item.id)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="sidebar-link" onClick={logout}>
            <span className="nav-icon">{"\u{1F6AA}"}</span>
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <HealthStatus />

        <div className="page-header">
          <h2>{meta.title}</h2>
          <p>{meta.desc}</p>
        </div>

        {tab === "rag" && <RAGChat />}
        {tab === "agent" && <SearchAgent />}
        {tab === "search" && <SearchTest />}
        {tab === "eval" && <Evaluation />}
        {tab === "observe" && <Observability />}
        {tab === "chunking" && <ChunkingComparison />}
        {tab === "providers" && <ProviderSettings />}
        {tab === "prompts" && <PromptEditor />}
        {tab === "etl" && <EtlProgress />}
        {tab === "analytics" && <Analytics />}
        {tab === "users" && <UserManagement />}
        {tab === "logs" && <Logs />}
        {tab === "guide" && <TestingGuide />}
      </main>
    </div>
  );
}
