import { useState, useEffect } from "react";
import { listUsers, createUser, deleteUser } from "../api.js";

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("admin");
  const [confirmDelete, setConfirmDelete] = useState(null);

  async function load() {
    setLoading(true);
    try {
      setUsers(await listUsers());
      setError("");
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    try {
      await createUser(username, password, role);
      setUsername("");
      setPassword("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDelete(name) {
    if (confirmDelete !== name) {
      setConfirmDelete(name);
      return;
    }
    setConfirmDelete(null);
    try {
      await deleteUser(name);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="card">
        <h2>Add New User</h2>
        {error && (
          <div style={{ background: "var(--danger-bg)", padding: "0.5rem 0.75rem", borderRadius: "var(--radius-sm)", marginBottom: "0.75rem" }}>
            <p style={{ color: "var(--danger)", fontWeight: 500, margin: 0, fontSize: "0.825rem" }}>{error}</p>
          </div>
        )}
        <form onSubmit={handleCreate} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field-group" style={{ flex: 1, minWidth: 140 }}>
            <label htmlFor="new-username">Username</label>
            <input id="new-username" type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="new-user" />
          </div>
          <div className="field-group" style={{ flex: 1, minWidth: 140 }}>
            <label htmlFor="new-password">Password</label>
            <input id="new-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
          </div>
          <div className="field-group" style={{ minWidth: 100 }}>
            <label htmlFor="new-role">Role</label>
            <select id="new-role" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
          <button type="submit" className="btn-primary" style={{ marginBottom: "0.75rem" }}>Add User</button>
        </form>
      </div>

      <div className="card">
        <h2>Users</h2>
        {loading ? (
          <p style={{ color: "var(--text-muted)" }}>Loading users...</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Created</th>
                  <th style={{ width: 80 }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ color: "var(--text-muted)" }}>{u.id}</td>
                    <td style={{ fontWeight: 500 }}>{u.username}</td>
                    <td>
                      <span className={`badge ${u.role === "admin" ? "badge-info" : "badge-neutral"}`}>
                        {u.role}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>{u.created_at}</td>
                    <td>
                      <button
                        className={confirmDelete === u.username ? "btn-danger btn-sm" : "btn-secondary btn-sm"}
                        onClick={() => handleDelete(u.username)}
                      >
                        {confirmDelete === u.username ? "Confirm?" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={5} style={{ padding: "1rem", color: "var(--text-muted)", textAlign: "center" }}>No users found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
