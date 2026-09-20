// Overview page: KPI row (latest run) + filterable, sortable runs table.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, fmt, fmtP, fmtLatency, shortId, GateChip, KpiCard, toast, isSnapshot } from "/static/components/ui.js";

export class OverviewPage extends Component {
  state = { runs: [], loading: true, q: "", guard: "", sortKey: "timestamp", sortDir: "desc",
            editing: null, confirmDelete: null, demoBusy: false };

  componentDidMount() {
    const params = new URLSearchParams(location.search);
    this.setState({ q: params.get("q") || "" });
    this.load();
  }

  async load() {
    this.setState({ loading: true });
    try {
      const runs = await api.runs({ limit: "100" });
      this.setState({ runs, loading: false });
    } catch (e) {
      toast(e.message, "error");
      this.setState({ loading: false });
    }
  }

  sortedFiltered() {
    const { runs, q, guard, sortKey, sortDir } = this.state;
    let rows = runs.slice();
    if (guard) rows = rows.filter((r) => r.baseline === guard || r.candidate === guard);
    if (q) {
      const ql = q.toLowerCase();
      rows = rows.filter((r) => [r.run_id, r.tag, r.baseline, r.candidate, r.note]
        .some((v) => (v || "").toLowerCase().includes(ql)));
    }
    const dir = sortDir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (va === vb) return 0;
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      return (va > vb ? 1 : -1) * dir;
    });
    return rows;
  }

  setSort(key) {
    this.setState((s) => ({ sortKey: key, sortDir: s.sortKey === key && s.sortDir === "asc" ? "desc" : "asc" }));
  }

  ariaSort(key) {
    if (this.state.sortKey !== key) return "none";
    return this.state.sortDir === "asc" ? "ascending" : "descending";
  }

  async saveTag(id, value) {
    this.setState({ editing: null });
    try {
      await api.patchRun(id, { tag: value });
      this.setState((s) => ({ runs: s.runs.map((r) => (r.run_id === id ? { ...r, tag: value } : r)) }));
    } catch (e) { toast(e.message, "error"); }
  }

  async doDelete(id) {
    this.setState({ confirmDelete: null });
    try {
      await api.deleteRun(id);
      this.setState((s) => ({ runs: s.runs.filter((r) => r.run_id !== id) }));
      toast("Run deleted", "ok");
    } catch (e) { toast(e.message, "error"); }
  }

  async runDemo() {
    this.setState({ demoBusy: true });
    try {
      const { job_id } = await api.compare({ baseline: "regex-baseline", candidate: "regex-enhanced", dataset: "dataset/sample.csv" });
      for (let i = 0; i < 100; i++) {
        const job = await api.job(job_id);
        if (job.status === "done") { this.props.navigate("/run/" + job.run_id); return; }
        if (job.status === "error") { toast(job.error || "demo failed", "error"); break; }
        await new Promise((r) => setTimeout(r, 200));
      }
    } catch (e) { toast(e.message, "error"); }
    this.setState({ demoBusy: false });
  }

  kpiRow() {
    const rows = this.state.runs;
    if (!rows.length) return null;
    const latest = rows[0], prev = rows[1] || {};
    const hist = (key) => rows.slice(0, 10).reverse().map((r) => r[key]);
    const d = (key) => (latest[key] != null && prev[key] != null ? latest[key] - prev[key] : undefined);
    return html`<div class="grid" style="grid-template-columns:repeat(5,1fr);margin-bottom:24px">
      <${KpiCard} label="Candidate F1" value=${fmt(latest.f1)} delta=${d("f1")} higherBetter=${true} spark=${hist("f1")} sparkColor="var(--ok)"/>
      <${KpiCard} label="Recall" value=${fmt(latest.recall)} delta=${d("recall")} higherBetter=${true} spark=${hist("recall")}/>
      <${KpiCard} label="FPR" value=${fmt(latest.fpr)} delta=${d("fpr")} higherBetter=${false} spark=${hist("fpr")} sparkColor="var(--danger)"/>
      <${KpiCard} label="Latency p99" value=${fmtLatency(latest.latency_p99)} spark=${hist("latency_p99")} sparkColor="var(--warn)"/>
      <div class="card kpi"><span class="label">Gate</span><span class="value"><${GateChip} pass=${latest.gate_pass}/></span></div>
    </div>`;
  }

  guardChips() {
    const guards = [...new Set(this.state.runs.flatMap((r) => [r.baseline, r.candidate]).filter(Boolean))];
    return html`<div class="row wrap center" style="gap:6px">
      <button class=${"chip " + (this.state.guard === "" ? "ok" : "neutral")} onClick=${() => this.setState({ guard: "" })}>all</button>
      ${guards.map((g) => html`<button class=${"chip " + (this.state.guard === g ? "ok" : "neutral")}
          onClick=${() => this.setState({ guard: g })}>${g}</button>`)}
    </div>`;
  }

  header(key, label, cls = "") {
    return html`<th class=${"sortable " + cls} aria-sort=${this.ariaSort(key)} tabindex="0"
      onClick=${() => this.setSort(key)} onKeyDown=${(e) => e.key === "Enter" && this.setSort(key)}>${label}</th>`;
  }

  render(props, { loading, editing, confirmDelete, demoBusy }) {
    if (loading) return html`<main class="container" style="padding:24px"><div class="skeleton" style="height:120px"></div></main>`;
    const rows = this.sortedFiltered();

    if (!this.state.runs.length) {
      return html`<main class="container" style="padding:24px 24px 48px">
        <div class="card empty">
          <h2>No runs yet</h2>
          <p class="muted">Get started from the command line:</p>
          <pre class="mono" style="text-align:left;display:inline-block;background:var(--surface-2);padding:12px;border-radius:8px">guardmeter init
guardmeter compare --baseline regex-baseline --candidate regex-enhanced --dataset dataset/sample.csv
guardmeter serve --open</pre>
          <p style="margin-top:16px"><button class="btn primary" disabled=${demoBusy} onClick=${() => this.runDemo()}>
            ${demoBusy ? "Running demo…" : "Run demo evaluation"}</button></p>
        </div>
      </main>`;
    }

    return html`<main class="container" style="padding:24px 24px 48px">
      ${this.kpiRow()}
      <div class="row between center" style="margin-bottom:12px">
        <h2 style="margin:0">Runs</h2>
        <input class="input" style="width:260px" placeholder="Search…" value=${this.state.q}
          onInput=${(e) => this.setState({ q: e.target.value })} aria-label="Search runs"/>
      </div>
      <div style="margin-bottom:12px">${this.guardChips()}</div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead><tr>
            ${this.header("timestamp", "Date")}
            <th>Tag</th>
            ${this.header("baseline", "Baseline")}
            ${this.header("candidate", "Candidate")}
            ${this.header("f1", "F1", "text-right")}
            ${this.header("recall", "Recall", "text-right")}
            ${this.header("fpr", "FPR", "text-right")}
            ${this.header("mcnemar_p", "McNemar p", "text-right")}
            <th>Gate</th><th aria-label="Actions"></th>
          </tr></thead>
          <tbody>
            ${rows.map((r) => html`<tr key=${r.run_id} style="cursor:pointer"
                onClick=${(e) => { if (!e.target.closest(".rowactions,.tagcell")) props.navigate("/run/" + r.run_id); }}>
              <td class="muted" style="white-space:nowrap">${(r.timestamp || "").replace("T", " ").slice(0, 16)}</td>
              <td class="tagcell">${isSnapshot()
                ? html`<span class="chip neutral">${r.tag || "—"}</span>`
                : editing === r.run_id
                ? html`<input class="input" style="width:110px" autofocus value=${r.tag || ""}
                    onBlur=${(e) => this.saveTag(r.run_id, e.target.value)}
                    onKeyDown=${(e) => e.key === "Enter" && this.saveTag(r.run_id, e.target.value)}/>`
                : html`<span onClick=${() => this.setState({ editing: r.run_id })}
                    class="chip neutral" title="Click to edit">${r.tag || "＋ tag"}</span>`}</td>
              <td>${r.baseline}</td><td>${r.candidate}</td>
              <td class="mono text-right">${fmt(r.f1)}</td>
              <td class="mono text-right">${fmt(r.recall)}</td>
              <td class="mono text-right">${fmt(r.fpr)}</td>
              <td class="mono text-right">${fmtP(r.mcnemar_p)}</td>
              <td><${GateChip} pass=${r.gate_pass}/></td>
              <td class="rowactions" style="white-space:nowrap">
                <button class="btn ghost icon" title="Compare" aria-label="Compare with"
                  onClick=${() => props.navigate("/compare?a=" + r.run_id)}>⇄</button>
                ${!isSnapshot() && html`<a class="btn ghost icon" title="Export CSV" href=${api.exportCsvUrl(r.run_id)}>⬇</a>`}
                ${!isSnapshot() && html`<button class="btn ghost icon" title="Delete" aria-label="Delete run"
                  onClick=${() => this.setState({ confirmDelete: r.run_id })}>🗑</button>`}
              </td>
            </tr>`)}
          </tbody>
        </table>
      </div>
      <p class="muted" style="font-size:12px;margin-top:8px">Click a row to open the run.</p>

      ${confirmDelete && html`<div class="modal-scrim" onClick=${() => this.setState({ confirmDelete: null })}>
        <div class="modal" onClick=${(e) => e.stopPropagation()}>
          <h3>Delete run?</h3>
          <p class="muted">Run <code>${shortId(confirmDelete)}</code> and its samples will be removed.</p>
          <div class="row" style="justify-content:flex-end;margin-top:16px">
            <button class="btn secondary" onClick=${() => this.setState({ confirmDelete: null })}>Cancel</button>
            <button class="btn danger" onClick=${() => this.doDelete(confirmDelete)}>Delete</button>
          </div>
        </div>
      </div>`}
    </main>`;
  }
}
