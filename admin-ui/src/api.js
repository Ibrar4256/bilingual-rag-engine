const API_BASE = "";

function getToken() {
  return localStorage.getItem("token");
}

function setToken(token) {
  localStorage.setItem("token", token);
}

function clearToken() {
  localStorage.removeItem("token");
}

function isLoggedIn() {
  return !!getToken();
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (resp.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error("Session expired");
  }
  return resp;
}

async function login(username, password) {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Login failed");
  }
  const data = await resp.json();
  setToken(data.access_token);
  return data;
}

function logout() {
  clearToken();
  window.location.reload();
}

async function getHealth() {
  const resp = await fetch(`${API_BASE}/health`);
  return resp.json();
}

async function listConfig() {
  const resp = await apiFetch("/admin/config/");
  return resp.json();
}

async function getConfig(key) {
  const resp = await apiFetch(`/admin/config/${key}`);
  return resp.json();
}

async function setConfig(key, value) {
  const resp = await apiFetch(`/admin/config/${key}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to save config");
  }
  return resp.json();
}

async function getProviderAvailability() {
  const resp = await apiFetch("/admin/config/providers/availability");
  return resp.json();
}

async function searchCategories(query, language, limit = 10, filters, offset = 0, rerank = false) {
  const resp = await fetch(`${API_BASE}/search/category`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, language: language || undefined, limit, offset, filters: filters || undefined, rerank }),
  });
  return resp.json();
}

async function matchCompanies(query, language, limit = 10, filters, offset = 0, rerank = false) {
  const resp = await fetch(`${API_BASE}/match/companies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, language: language || undefined, limit, offset, filters: filters || undefined, rerank }),
  });
  return resp.json();
}

async function searchSingleCompany(companyId, query, language, limit = 10, offset = 0, rerank = false) {
  const resp = await fetch(`${API_BASE}/search/single-company`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_id: companyId, query, language: language || undefined, limit, offset, rerank }),
  });
  return resp.json();
}

async function getEtlProgress() {
  const resp = await apiFetch("/admin/etl/progress");
  return resp.json();
}

async function getAnalytics() {
  const resp = await apiFetch("/admin/analytics");
  return resp.json();
}

async function getLogs(limit = 200, level = null, search = null) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) params.set("level", level);
  if (search) params.set("search", search);
  const resp = await apiFetch(`/admin/logs?${params}`);
  return resp.json();
}

async function getSuggestions(q) {
  if (!q || q.length < 2) return [];
  const resp = await fetch(`${API_BASE}/search/suggest?q=${encodeURIComponent(q)}&limit=8`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.suggestions || [];
}

async function listUsers() {
  const resp = await apiFetch("/auth/users");
  if (!resp.ok) throw new Error("Failed to load users");
  return resp.json();
}

async function createUser(username, password, role = "admin") {
  const resp = await apiFetch("/auth/users", {
    method: "POST",
    body: JSON.stringify({ username, password, role }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to create user");
  }
  return resp.json();
}

async function deleteUser(username) {
  const resp = await apiFetch(`/auth/users/${encodeURIComponent(username)}`, {
    method: "DELETE",
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to delete user");
  }
}

async function startEtl(forceEnrichment = false) {
  const resp = await apiFetch(`/admin/etl/start?force_enrichment=${forceEnrichment}`, { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to start ETL");
  }
  return resp.json();
}

async function stopEtl() {
  const resp = await apiFetch("/admin/etl/stop", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to stop ETL");
  }
  return resp.json();
}

async function askRAG(query, table = "category_vectors", limit = 5, language) {
  const resp = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, table, limit, language: language || undefined }),
  });
  return resp.json();
}

async function listConversations(limit = 20) {
  const resp = await apiFetch(`/admin/conversations/?limit=${limit}`);
  return resp.json();
}

async function getConversation(id) {
  const resp = await apiFetch(`/admin/conversations/${id}`);
  if (!resp.ok) throw new Error("Conversation not found");
  return resp.json();
}

async function saveConversation(id, title, messages) {
  const resp = await apiFetch("/admin/conversations/", {
    method: "POST",
    body: JSON.stringify({ id: id || undefined, title, messages }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to save conversation");
  }
  return resp.json();
}

async function deleteConversation(id) {
  const resp = await apiFetch(`/admin/conversations/${id}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Failed to delete conversation");
}

export {
  login,
  logout,
  isLoggedIn,
  getHealth,
  listConfig,
  getConfig,
  setConfig,
  getProviderAvailability,
  searchCategories,
  matchCompanies,
  searchSingleCompany,
  getSuggestions,
  getEtlProgress,
  listUsers,
  createUser,
  deleteUser,
  askRAG,
  startEtl,
  stopEtl,
  listConversations,
  getConversation,
  saveConversation,
  deleteConversation,
  getAnalytics,
  getLogs,
};
