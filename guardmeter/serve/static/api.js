// API client. Against a live server it talks to /api/*; inside a static
// snapshot (window.__SNAPSHOT__) it reads embedded data and filters in-browser,
// so the exported dashboard works from disk with no network.

function authHeaders(base) {
  const h = base || {};
  const t = sessionStorage.getItem("gm_token");
  if (t) h["Authorization"] = "Bearer " + t;
  return h;
}

async function request(method, url, body) {
  const opts = { method, headers: authHeaders(body ? { "Content-Type": "application/json" } : {}) };
  if (body !== undefined) opts.body = JSON.stringify(body);
  let resp = await fetch(url, opts);
  if (resp.status === 401) {
    const t = window.prompt("This app requires a token (GUARDMETER_TOKEN):");
    if (t) {
      sessionStorage.setItem("gm_token", t);
      resp = await fetch(url, { method, headers: authHeaders(body ? { "Content-Type": "application/json" } : {}),
                               body: body !== undefined ? JSON.stringify(body) : undefined });
    }
  }
  return resp;
}

async function json(method, url, body) {
  const resp = await request(method, url, body);
  const data = resp.status === 204 ? null : await resp.json().catch(() => null);
  if (!resp.ok) throw new Error((data && data.error) || `${resp.status} ${resp.statusText}`);
  return data;
}

// ── snapshot (offline) data access ─────────────────────────────────────────
const SNAP = () => window.__SNAPSHOT_DATA__ || {};
const isSnap = () => !!window.__SNAPSHOT__;
const isPositive = (label) => label !== "benign";

function snapRuns(params = {}) {
  let rows = (SNAP().runs || []).slice();
  if (params.guard) rows = rows.filter((r) => r.baseline === params.guard || r.candidate === params.guard);
  if (params.q) {
    const ql = params.q.toLowerCase();
    rows = rows.filter((r) => [r.run_id, r.tag, r.baseline, r.candidate, r.note].some((v) => (v || "").toLowerCase().includes(ql)));
  }
  return rows;
}

function snapSamples(id, params = {}) {
  const run = (SNAP().runDetail || {})[id] || {};
  const filt = params.filter || "all";
  let rows = (run.sample_results || []).filter((s) => {
    if (filt === "fn" && !(isPositive(s.label) && s.candidate_pred === "pass")) return false;
    if (filt === "fp" && !(s.label === "benign" && s.candidate_pred === "flag")) return false;
    if (filt === "mismatch" && s.baseline_pred === s.candidate_pred) return false;
    if (filt === "disagree" && s.judge_verdict !== "disagree") return false;
    if (params.category && s.category !== params.category) return false;
    if (params.language && s.language !== params.language) return false;
    if (params.attack && (s.attack_type || "") !== params.attack) return false;
    if (params.q && !JSON.stringify(s).toLowerCase().includes(params.q.toLowerCase())) return false;
    return true;
  });
  const offset = Number(params.offset || 0), limit = Number(params.limit || 100);
  return { total: rows.length, offset, limit, rows: rows.slice(offset, offset + limit) };
}

function snapDatasetRows(name, params = {}) {
  const d = (SNAP().datasetRows || {})[name] || [];
  let rows = d;
  if (params.q) rows = rows.filter((r) => JSON.stringify(r).toLowerCase().includes(params.q.toLowerCase()));
  const offset = Number(params.offset || 0), limit = Number(params.limit || 100);
  return { total: rows.length, offset, limit, rows: rows.slice(offset, offset + limit) };
}

export const api = {
  guards: () => isSnap() ? Promise.resolve(SNAP().guardsInfo || { guards: [], default: [] }) : json("GET", "/api/guards"),
  runs: (params = {}) => isSnap() ? Promise.resolve(snapRuns(params)) : json("GET", "/api/runs?" + new URLSearchParams(params)),
  run: (id) => isSnap() ? Promise.resolve((SNAP().runDetail || {})[id]) : json("GET", `/api/runs/${encodeURIComponent(id)}`),
  deleteRun: (id) => json("DELETE", `/api/runs/${encodeURIComponent(id)}`),
  patchRun: (id, body) => json("PATCH", `/api/runs/${encodeURIComponent(id)}`, body),
  samples: (id, params = {}) => isSnap() ? Promise.resolve(snapSamples(id, params)) : json("GET", `/api/runs/${encodeURIComponent(id)}/samples?` + new URLSearchParams(params)),
  exportCsvUrl: (id) => `/api/runs/${encodeURIComponent(id)}/export.csv`,
  gate: () => isSnap() ? Promise.resolve(SNAP().gate || {}) : json("GET", "/api/gate"),
  putGate: (gate) => json("PUT", "/api/gate", { gate }),
  evaluateGate: (gate, run_id) => json("POST", "/api/gate/evaluate", { gate, run_id }),
  datasets: () => isSnap() ? Promise.resolve({ datasets: SNAP().datasets || [] }) : json("GET", "/api/datasets"),
  datasetStats: (name) => isSnap() ? Promise.resolve((SNAP().datasetStats || {})[name]) : json("GET", `/api/datasets/${encodeURIComponent(name)}/stats`),
  datasetRows: (name, params = {}) => isSnap() ? Promise.resolve(snapDatasetRows(name, params)) : json("GET", `/api/datasets/${encodeURIComponent(name)}/rows?` + new URLSearchParams(params)),
  tryText: (text, guards) => json("POST", "/api/try", { text, guards }),
  compare: (body) => json("POST", "/api/compare", body),
  job: (id) => json("GET", `/api/jobs/${encodeURIComponent(id)}`),
};
