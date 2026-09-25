// Scenarios: suite-run history, run detail with per-scenario rows + evidence,
// and a compare that lists which scenarios changed status between two runs.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, fmt, shortId, toast } from "/static/components/ui.js";

const pct = (r) => (r === null || r === undefined) ? "n/a" : `${(r * 100).toFixed(0)}%`;
const STATUS_CLASS = { pass: "ok", fail: "bad", flaky: "warn", error: "bad" };

export class ScenariosPage extends Component {
  state = { runs: [], loading: true, a: "", b: "", diff: null };

  async componentDidMount() {
    try {
      const d = await api.scenarioRuns();
      this.setState({ runs: d.runs || [], loading: false });
    } catch (e) { toast(e.message, "error"); this.setState({ loading: false }); }
  }

  async compare() {
    const { a, b } = this.state;
    if (!a || !b) return;
    try {
      const [ra, rb] = await Promise.all([api.scenarioRun(a), api.scenarioRun(b)]);
      const sa = Object.fromEntries((ra.results || []).map((r) => [r.id, r.status]));
      const changed = (rb.results || []).filter((r) => sa[r.id] && sa[r.id] !== r.status)
        .map((r) => ({ id: r.id, category: r.category, from: sa[r.id], to: r.status }));
      this.setState({ diff: { changed, a: ra, b: rb } });
    } catch (e) { toast(e.message, "error"); }
  }

  render({ navigate }, { runs, loading, a, b, diff }) {
    if (loading) return html`<main class="container" style="padding:24px"><div class="card">Loading…</div></main>`;
    if (!runs.length) return html`<main class="container" style="padding:24px">
      <div class="card empty">No scenario runs yet. Run <code>guardmeter scenarios run SUITE --endpoint …</code>.</div></main>`;
    const opts = runs.map((r) => html`<option value=${r.run_id}>${shortId(r.run_id)} · ${r.suite_name} · ${(r.target || {}).model || ""}</option>`);
    return html`<main class="container" style="padding:24px 24px 48px">
      <h2 style="margin:0 0 12px">Scenario runs</h2>
      <div class="card" style="overflow-x:auto">
        <table><thead><tr>
          <th>When</th><th>Suite</th><th>Target</th><th class="text-right">Pass</th>
          <th class="text-right">Flaky</th><th class="text-right">Errors</th><th class="text-right">p95</th>
        </tr></thead><tbody>
        ${runs.map((r) => { const g = r.aggregate || {}; return html`<tr style="cursor:pointer"
            onClick=${() => navigate("/scenario/" + r.run_id)}>
          <td class="muted" style="white-space:nowrap">${(r.timestamp || "").replace("T", " ").slice(0, 16)}</td>
          <td>${r.suite_name} <span class="muted">v${r.suite_version}</span></td>
          <td class="mono">${(r.target || {}).model || (r.target || {}).kind || "?"}</td>
          <td class="mono text-right">${pct(g.pass_rate)}</td>
          <td class="mono text-right">${g.flaky ?? 0}</td>
          <td class="mono text-right">${g.errored ?? 0}</td>
          <td class="mono text-right">${g.latency_p95 ? g.latency_p95.toFixed(0) + "ms" : "—"}</td>
        </tr>`; })}
        </tbody></table>
      </div>

      <h3 style="margin:24px 0 8px">Compare two runs</h3>
      <div class="card">
        <div class="row center" style="gap:8px;flex-wrap:wrap">
          <select class="select" value=${a} onChange=${(e) => this.setState({ a: e.target.value })}>
            <option value="">baseline run…</option>${opts}</select>
          <span class="muted">→</span>
          <select class="select" value=${b} onChange=${(e) => this.setState({ b: e.target.value })}>
            <option value="">candidate run…</option>${opts}</select>
          <button class="btn" onClick=${() => this.compare()}>Diff</button>
        </div>
        ${diff && html`<div style="margin-top:12px">
          ${diff.changed.length === 0 ? html`<p class="muted">No scenarios changed status.</p>`
            : html`<table><thead><tr><th>Scenario</th><th>Category</th><th>From</th><th>To</th></tr></thead>
              <tbody>${diff.changed.map((c) => html`<tr>
                <td class="mono">${c.id}</td><td>${c.category}</td>
                <td><span class=${"chip " + (STATUS_CLASS[c.from] || "neutral")}>${c.from}</span></td>
                <td><span class=${"chip " + (STATUS_CLASS[c.to] || "neutral")}>${c.to}</span></td>
              </tr>`)}</tbody></table>`}
        </div>`}
      </div>
    </main>`;
  }
}

export class ScenarioRunPage extends Component {
  state = { run: null, loading: true, category: "", status: "", open: null };

  async componentDidMount() {
    try {
      this.setState({ run: await api.scenarioRun(this.props.route.id), loading: false });
    } catch (e) { toast(e.message, "error"); this.setState({ loading: false }); }
  }

  render({ navigate }, { run, loading, category, status, open }) {
    if (loading) return html`<main class="container" style="padding:24px"><div class="card">Loading…</div></main>`;
    if (!run) return html`<main class="container" style="padding:24px"><div class="card empty">Run not found.</div></main>`;
    const g = run.aggregate || {};
    const cats = [...new Set((run.results || []).map((r) => r.category))].sort();
    let rows = (run.results || []).filter((r) =>
      (!category || r.category === category) && (!status || r.status === status));
    const kpi = (label, val) => html`<div class="card kpi"><span class="label">${label}</span><span class="value">${val}</span></div>`;
    return html`<main class="container" style="padding:24px 24px 48px">
      <div class="row between center">
        <h2 style="margin:0">Scenario run ${shortId(run.run_id)} · ${run.suite_name}</h2>
        <a class="btn secondary" href="#/scenarios" onClick=${(e) => { e.preventDefault(); navigate("/scenarios"); }}>← All runs</a>
      </div>
      <p class="muted mono" style="font-size:12px">${(run.target || {}).kind} ${(run.target || {}).model || ""}
        ${(run.target || {}).endpoint ? "@ " + run.target.endpoint : ""} · ${run.timestamp}</p>

      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:12px 0">
        ${kpi("Pass rate", pct(g.pass_rate))}
        ${kpi("Passed/Failed", `${g.passed}/${g.failed}`)}
        ${kpi("Flaky", g.flaky)}
        ${kpi("Errors", g.errored)}
        ${kpi("Judge-disagree", g.judge_disagree)}
        ${kpi("p95", g.latency_p95 ? g.latency_p95.toFixed(0) + "ms" : "—")}
      </div>

      <div class="card" style="margin-bottom:12px">
        <div class="muted" style="font-size:11px;text-transform:uppercase">Pass rate by category</div>
        ${Object.entries(g.by_category || {}).map(([c, r]) => html`<div class="row center" style="gap:8px;margin-top:4px">
          <span style="width:130px;font-size:12px">${c}</span>
          <div style="flex:1;height:8px;background:var(--surface-2);border-radius:999px;overflow:hidden">
            <div style=${`height:100%;width:${(r || 0) * 100}%;background:var(--accent)`}></div></div>
          <span class="mono" style="width:40px;text-align:right;font-size:12px">${pct(r)}</span>
        </div>`)}
      </div>

      <div class="row center" style="gap:8px;margin-bottom:8px">
        <select class="select" value=${category} onChange=${(e) => this.setState({ category: e.target.value })}>
          <option value="">all categories</option>${cats.map((c) => html`<option value=${c}>${c}</option>`)}</select>
        <select class="select" value=${status} onChange=${(e) => this.setState({ status: e.target.value })}>
          <option value="">all statuses</option><option>pass</option><option>fail</option>
          <option>flaky</option><option>error</option></select>
        <span class="muted">${rows.length} scenarios</span>
      </div>

      <div class="card" style="overflow-x:auto"><table><thead><tr>
        <th>Scenario</th><th>Category</th><th>Lang</th><th>Status</th><th>Evidence</th>
      </tr></thead><tbody>
      ${rows.map((r) => html`<tr key=${r.id} style="cursor:pointer" onClick=${() => this.setState({ open: open === r.id ? null : r.id })}>
        <td class="mono">${r.id}</td><td>${r.category}</td><td>${r.language}</td>
        <td><span class=${"chip " + (STATUS_CLASS[r.status] || "neutral")}>${r.status}</span>
          ${r.judge_disagree ? html`<span class="chip neutral" title="excluded from gate">judge?</span>` : ""}</td>
        <td class="muted" style="font-size:12px">${(r.failing || []).join("; ") || "—"}</td>
      </tr>${open === r.id ? html`<tr><td colspan="5"><pre class="mono" style="white-space:pre-wrap;font-size:11px;margin:0">${
        (r.runs || []).map((run, i) => `run ${i + 1}: ${run.error ? "ERROR " + run.error : (run.passed ? "pass" : "fail")} · ${run.latency_ms}ms\n` +
          (run.outcomes || []).map((o) => `   ${o.passed ? "✓" : "✗"} ${o.type}: ${o.detail}`).join("\n") +
          (run.tool_calls && run.tool_calls.length ? "\n   tools: " + run.tool_calls.map((t) => t.name).join(",") : "")).join("\n\n")
      }</pre></td></tr>` : ""}`)}
      </tbody></table></div>
    </main>`;
  }
}
