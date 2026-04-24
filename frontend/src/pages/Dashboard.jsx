import { useEffect, useState } from "react";
import { apiFetch } from "../api/client.js";

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setSummary(await apiFetch("/api/dashboard/summary"));
      setHealth(await apiFetch("/api/system/health"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section>
      <div className="page-header">
        <h2>Dashboard</h2>
        <button onClick={load}>Refresh</button>
      </div>

      {error && <div className="alert">{error}</div>}

      <div className="grid">
        <Metric title="Total Jobs" value={summary?.total_jobs ?? "-"} />
        <Metric title="Enabled Jobs" value={summary?.enabled_jobs ?? "-"} />
        <Metric title="Pending Runs" value={summary?.pending_runs ?? "-"} />
        <Metric title="Running Runs" value={summary?.running_runs ?? "-"} />
        <Metric title="Success Today" value={summary?.success_today ?? "-"} />
        <Metric title="Failed Today" value={summary?.failed_today ?? "-"} />
      </div>

      <div className="card">
        <h3>System Health</h3>
        <pre>{JSON.stringify(health, null, 2)}</pre>
      </div>
    </section>
  );
}

function Metric({ title, value }) {
  return (
    <div className="card metric">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}
