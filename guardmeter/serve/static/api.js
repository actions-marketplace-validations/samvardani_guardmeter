// Minimal API client. Token (if the server requires one) lives only in
// sessionStorage and is sent as a Bearer header — never in the URL.

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
  if (!resp.ok) {
    const msg = (data && data.error) || `${resp.status} ${resp.statusText}`;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  guards: () => json("GET", "/api/guards"),
  runs: (params = {}) => json("GET", "/api/runs?" + new URLSearchParams(params)),
  run: (id) => json("GET", `/api/runs/${encodeURIComponent(id)}`),
  deleteRun: (id) => json("DELETE", `/api/runs/${encodeURIComponent(id)}`),
  patchRun: (id, body) => json("PATCH", `/api/runs/${encodeURIComponent(id)}`, body),
  samples: (id, params = {}) => json("GET", `/api/runs/${encodeURIComponent(id)}/samples?` + new URLSearchParams(params)),
  exportCsvUrl: (id) => `/api/runs/${encodeURIComponent(id)}/export.csv`,
  gate: () => json("GET", "/api/gate"),
  putGate: (gate) => json("PUT", "/api/gate", { gate }),
  evaluateGate: (gate, run_id) => json("POST", "/api/gate/evaluate", { gate, run_id }),
  datasets: () => json("GET", "/api/datasets"),
  datasetStats: (name) => json("GET", `/api/datasets/${encodeURIComponent(name)}/stats`),
  datasetRows: (name, params = {}) => json("GET", `/api/datasets/${encodeURIComponent(name)}/rows?` + new URLSearchParams(params)),
  tryText: (text, guards) => json("POST", "/api/try", { text, guards }),
  compare: (body) => json("POST", "/api/compare", body),
  job: (id) => json("GET", `/api/jobs/${encodeURIComponent(id)}`),
};
