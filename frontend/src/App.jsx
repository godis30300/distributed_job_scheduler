import { useEffect, useState } from "react";
import { apiFetch, clearToken, getToken, setToken } from "./api/client.js";
import Dashboard from "./pages/Dashboard.jsx";
import Jobs from "./pages/Jobs.jsx";
import JobDetail from "./pages/JobDetail.jsx";
import Login from "./pages/Login.jsx";

export default function App() {
  const [token, setTokenState] = useState(getToken());
  const [page, setPage] = useState("dashboard");
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [user, setUser] = useState(null);

  async function loadMe() {
    if (!getToken()) return;
    try {
      const me = await apiFetch("/api/auth/me");
      setUser(me);
    } catch {
      clearToken();
      setTokenState(null);
    }
  }

  useEffect(() => {
    loadMe();
  }, [token]);

  function handleLogin(auth) {
    setToken(auth.access_token);
    setTokenState(auth.access_token);
    setUser(auth.user);
  }

  function logout() {
    clearToken();
    setTokenState(null);
    setUser(null);
  }

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Kube Scheduler</h1>
        <p className="muted">Distributed Async Job Scheduler</p>
        <nav>
          <button onClick={() => setPage("dashboard")}>Dashboard</button>
          <button onClick={() => setPage("jobs")}>Jobs</button>
        </nav>
        <div className="user-box">
          <span>{user?.username}</span>
          <small>{user?.role}</small>
          <button className="secondary" onClick={logout}>Logout</button>
        </div>
      </aside>

      <main className="content">
        {page === "dashboard" && <Dashboard />}
        {page === "jobs" && (
          <Jobs
            onOpenRun={(runId) => {
              setSelectedRunId(runId);
              setPage("run-detail");
            }}
          />
        )}
        {page === "run-detail" && (
          <JobDetail runId={selectedRunId} onBack={() => setPage("jobs")} />
        )}
      </main>
    </div>
  );
}
