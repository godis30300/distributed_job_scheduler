import { useState } from "react";
import { apiFetch } from "../api/client.js";

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [role, setRole] = useState("admin");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");

    try {
      if (mode === "register") {
        await apiFetch("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ username, password, role })
        });
      }

      const auth = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });
      onLogin(auth);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="login-page">
      <form className="card login-card" onSubmit={submit}>
        <h1>Distributed Job Scheduler</h1>
        <p className="muted">Login or register an account.</p>

        {error && <div className="alert">{error}</div>}

        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} />

        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />

        {mode === "register" && (
          <>
            <label>Role</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </>
        )}

        <button type="submit">{mode === "login" ? "Login" : "Register and Login"}</button>
        <button type="button" className="secondary" onClick={() => setMode(mode === "login" ? "register" : "login")}>
          Switch to {mode === "login" ? "Register" : "Login"}
        </button>
      </form>
    </div>
  );
}
