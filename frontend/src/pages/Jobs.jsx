import { useEffect, useState } from "react";
import { apiFetch } from "../api/client.js";

const defaultPayload = JSON.stringify({
  method: "GET",
  url: "https://example.com",
  headers: {},
  body: null
}, null, 2);

export default function Jobs({ onOpenRun }) {
  const [jobs, setJobs] = useState([]);
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    task_name: "sample-api-job",
    action_type: "api_call",
    action_payload: defaultPayload,
    schedule_rule: "every:5m",
    timeout_seconds: 60,
    max_retry: 3
  });

  async function load() {
    try {
      setJobs(await apiFetch("/api/jobs"));
      setRuns(await apiFetch("/api/job-runs"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createJob(event) {
    event.preventDefault();
    setError("");
    try {
      await apiFetch("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          timeout_seconds: Number(form.timeout_seconds),
          max_retry: Number(form.max_retry),
          action_payload: JSON.parse(form.action_payload)
        })
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function triggerJob(jobId) {
    try {
      await apiFetch(`/api/jobs/${jobId}/trigger`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function scanScheduler() {
    try {
      await apiFetch("/api/scheduler/scan", { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function retryRun(runId) {
    try {
      await apiFetch(`/api/job-runs/${runId}/retry`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <div className="page-header">
        <h2>Jobs</h2>
        <div className="row">
          <button onClick={scanScheduler}>Scan Scheduler</button>
          <button className="secondary" onClick={load}>Refresh</button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      <form className="card form-grid" onSubmit={createJob}>
        <h3>Create Job</h3>

        <label>Task Name</label>
        <input value={form.task_name} onChange={(e) => setForm({ ...form, task_name: e.target.value })} />

        <label>Action Type</label>
        <select value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
          <option value="api_call">api_call</option>
          <option value="shell">shell</option>
          <option value="backup">backup</option>
        </select>

        <label>Schedule Rule</label>
        <input value={form.schedule_rule} onChange={(e) => setForm({ ...form, schedule_rule: e.target.value })} />

        <label>Timeout Seconds</label>
        <input type="number" value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: e.target.value })} />

        <label>Max Retry</label>
        <input type="number" value={form.max_retry} onChange={(e) => setForm({ ...form, max_retry: e.target.value })} />

        <label>Action Payload JSON</label>
        <textarea rows="8" value={form.action_payload} onChange={(e) => setForm({ ...form, action_payload: e.target.value })} />

        <button type="submit">Create Job</button>
      </form>

      <div className="card">
        <h3>Job List</h3>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Action</th>
              <th>Schedule</th>
              <th>Enabled</th>
              <th>Next Run</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.task_name}</td>
                <td>{job.action_type}</td>
                <td>{job.schedule_rule}</td>
                <td>{String(job.enabled)}</td>
                <td>{job.next_run_at || "-"}</td>
                <td><button onClick={() => triggerJob(job.id)}>Trigger</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Recent Runs</h3>
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Job ID</th>
              <th>Status</th>
              <th>Worker</th>
              <th>Created At</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td>{run.id.slice(0, 8)}</td>
                <td>{run.job_id.slice(0, 8)}</td>
                <td><span className={`badge ${run.status}`}>{run.status}</span></td>
                <td>{run.worker_id || "-"}</td>
                <td>{run.created_at}</td>
                <td className="row">
                  <button onClick={() => onOpenRun(run.id)}>Logs</button>
                  {(run.status === "failed" || run.status === "canceled") && (
                    <button className="secondary" onClick={() => retryRun(run.id)}>Retry</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
