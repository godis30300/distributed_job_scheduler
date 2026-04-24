import { useEffect, useState } from "react";
import { apiFetch } from "../api/client.js";

export default function JobDetail({ runId, onBack }) {
  const [run, setRun] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setRun(await apiFetch(`/api/job-runs/${runId}`));
      setLogs(await apiFetch(`/api/job-runs/${runId}/logs`));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, [runId]);

  return (
    <section>
      <div className="page-header">
        <h2>Run Detail</h2>
        <div className="row">
          <button className="secondary" onClick={onBack}>Back</button>
          <button onClick={load}>Refresh</button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      <div className="card">
        <h3>Run</h3>
        <pre>{JSON.stringify(run, null, 2)}</pre>
      </div>

      <div className="card">
        <h3>Logs</h3>
        <div className="log-viewer">
          {logs.map((log) => (
            <div key={log.id} className="log-line">
              <span>{log.created_at}</span>
              <strong>{log.log_level}</strong>
              <code>{log.message}</code>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
