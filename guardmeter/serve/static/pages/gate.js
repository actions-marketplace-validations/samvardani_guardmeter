// Gate editor: edit thresholds on the left, live pass/fail preview on the right.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, fmt, shortId, GateChip, toast } from "/static/components/ui.js";

const DEFAULT_GATE = {
  mode: "strict",
  global_thresholds: { min_recall: 0.55, max_fpr: 0.05, min_f1: 0.8, max_latency_p99_ms: 500 },
  slices: {},
  on_failure: "block",
};

export class GatePage extends Component {
  state = { gate: null, original: null, runs: [], runId: "", sliceKeys: [], evalResult: null, showDiff: false, saving: false };
  _timer = null;

  async componentDidMount() {
    try {
      const [gate, runs] = await Promise.all([api.gate(), api.runs({ limit: "100" })]);
      const g = gate && gate.global_thresholds ? gate : DEFAULT_GATE;
      const runId = runs.length ? runs[0].run_id : "";
      this.setState({ gate: structuredClone(g), original: structuredClone(g), runs, runId },
        () => { this.loadSliceKeys(); this.evaluate(); });
    } catch (e) { toast(e.message, "error"); }
  }

  async loadSliceKeys() {
    if (!this.state.runId) return;
    try {
      const run = await api.run(this.state.runId);
      const keys = Object.keys((run.candidate_slices || {}).strict || {}).map((k) => {
        try { const [c, l] = JSON.parse(k); return `${c}/${l}`; } catch (_e) { return k; }
      });
      const attacks = Object.keys((run.candidate_attack_slices || {}).strict || {}).map((k) => {
        try { return "attack:" + JSON.parse(k)[0]; } catch (_e) { return k; }
      });
      this.setState({ sliceKeys: [...keys, ...attacks] });
    } catch (_e) { /* non-fatal */ }
  }

  changed() { this.setState({}, () => this.scheduleEval()); }
  scheduleEval() {
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.evaluate(), 300);
  }

  async evaluate() {
    if (!this.state.runId || !this.state.gate) return;
    try {
      const evalResult = await api.evaluateGate(this.cleanGate(), this.state.runId);
      this.setState({ evalResult });
    } catch (e) { this.setState({ evalResult: { error: e.message } }); }
  }

  cleanGate() {
    // Drop empty slice-override fields before sending.
    const g = structuredClone(this.state.gate);
    const slices = {};
    for (const [key, ov] of Object.entries(g.slices || {})) {
      const kept = {};
      for (const [k, v] of Object.entries(ov)) if (v !== "" && v !== null && v !== undefined) kept[k] = Number(v);
      if (key) slices[key] = kept;
    }
    g.slices = slices;
    return g;
  }

  setGlobal(field, value) { this.state.gate.global_thresholds[field] = value === "" ? "" : Number(value); this.changed(); }
  setMeta(field, value) { this.state.gate[field] = value; this.changed(); }
  addSlice() { this.state.gate.slices[""] = { min_recall: "", max_fpr: "" }; this.changed(); }
  renameSlice(oldKey, newKey) {
    const s = this.state.gate.slices; const v = s[oldKey]; delete s[oldKey]; s[newKey] = v; this.changed();
  }
  setSliceField(key, field, value) { this.state.gate.slices[key][field] = value; this.changed(); }
  removeSlice(key) { delete this.state.gate.slices[key]; this.changed(); }

  async suggestFromRun() {
    try {
      const run = await api.run(this.state.runId);
      const m = (run.candidate_metrics || {}).strict;
      if (!m) return;
      this.state.gate.global_thresholds = {
        min_recall: Math.max(0, +(m.recall - 0.05).toFixed(3)),
        max_fpr: +(m.fpr + 0.01).toFixed(3),
        min_f1: Math.max(0, +(m.f1 - 0.05).toFixed(3)),
        max_latency_p99_ms: Math.ceil((m.latency_p99 || 0) + 5),
      };
      this.changed();
      toast("Suggested a starting point from this run — review before saving", "ok");
    } catch (e) { toast(e.message, "error"); }
  }

  async save() {
    this.setState({ saving: true });
    try {
      await api.putGate(this.cleanGate());
      this.setState({ original: structuredClone(this.state.gate), showDiff: false, saving: false });
      toast("gate.json saved (previous backed up to gate.json.bak)", "ok");
    } catch (e) { toast(e.message, "error"); this.setState({ saving: false }); }
  }

  numRow(label, field, max = 1, step = 0.01, slider = true) {
    const v = this.state.gate.global_thresholds[field];
    return html`<div style="margin-bottom:12px">
      <label class="muted" style="display:block;font-size:12px;margin-bottom:4px">${label}</label>
      <div class="row center" style="gap:10px">
        <input class="input" style="width:100px" type="number" step=${step} value=${v}
          onInput=${(e) => this.setGlobal(field, e.target.value)}/>
        ${slider && html`<input type="range" min="0" max=${max} step=${step} value=${v || 0}
          aria-label=${label} onInput=${(e) => this.setGlobal(field, e.target.value)}/>`}
      </div>
    </div>`;
  }

  render(_, { gate, runs, runId, sliceKeys, evalResult, showDiff, saving }) {
    if (!gate) return html`<main class="container" style="padding:24px"><div class="skeleton" style="height:200px"></div></main>`;
    const snapshot = !!window.__SNAPSHOT__;
    const failures = (evalResult && evalResult.failures) || [];
    const wouldPass = evalResult && !evalResult.error ? evalResult.passed : null;

    return html`<main class="container" style="padding:24px 24px 48px">
      <h2>Gate editor</h2>
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:24px">
        <div class="card">
          <div class="row between center"><h3 style="margin:0">Policy</h3>
            <button class="btn secondary" onClick=${() => this.suggestFromRun()} disabled=${!runId}>Suggest from run</button></div>

          <div class="row" style="gap:12px;margin:12px 0">
            <div><label class="muted" style="font-size:12px">Mode</label>
              <select class="select" value=${gate.mode} onChange=${(e) => this.setMeta("mode", e.target.value)}>
                <option value="strict">strict</option><option value="lenient">lenient</option></select></div>
            <div><label class="muted" style="font-size:12px">On failure</label>
              <select class="select" value=${gate.on_failure} onChange=${(e) => this.setMeta("on_failure", e.target.value)}>
                <option value="block">block</option><option value="warn">warn</option></select></div>
          </div>

          <div class="section-title">Global thresholds</div>
          ${this.numRow("min_recall", "min_recall")}
          ${this.numRow("max_fpr", "max_fpr", 0.2, 0.005)}
          ${this.numRow("min_f1", "min_f1")}
          ${this.numRow("max_latency_p99_ms", "max_latency_p99_ms", 1000, 1, false)}

          <div class="section-title">Per-slice overrides</div>
          <datalist id="slice-keys">${sliceKeys.map((k) => html`<option value=${k}></option>`)}</datalist>
          ${Object.entries(gate.slices).map(([key, ov]) => html`<div class="row center" style="gap:6px;margin-bottom:6px">
            <input class="input" list="slice-keys" style="width:150px" placeholder="category/lang" value=${key}
              onChange=${(e) => this.renameSlice(key, e.target.value)}/>
            <input class="input" style="width:90px" type="number" step="0.01" placeholder="recall" value=${ov.min_recall ?? ""}
              onInput=${(e) => this.setSliceField(key, "min_recall", e.target.value)}/>
            <input class="input" style="width:90px" type="number" step="0.01" placeholder="fpr" value=${ov.max_fpr ?? ""}
              onInput=${(e) => this.setSliceField(key, "max_fpr", e.target.value)}/>
            <button class="btn ghost icon" aria-label="Remove override" onClick=${() => this.removeSlice(key)}>✕</button>
          </div>`)}
          <button class="btn ghost" onClick=${() => this.addSlice()}>＋ Add override</button>
        </div>

        <div class="card">
          <div class="row between center"><h3 style="margin:0">Live preview</h3>
            <select class="select" style="width:auto" value=${runId}
              onChange=${(e) => this.setState({ runId: e.target.value }, () => { this.loadSliceKeys(); this.evaluate(); })}>
              ${runs.map((r) => html`<option value=${r.run_id}>${shortId(r.run_id)} · ${r.candidate}</option>`)}
            </select></div>
          ${!runId ? html`<div class="empty">No runs to preview against.</div>` : evalResult && evalResult.error
            ? html`<div class="empty">${evalResult.error}</div>`
            : html`<div>
              <p style="margin:12px 0">${wouldPass === null ? html`<span class="chip neutral">…</span>`
                : wouldPass ? html`<span class="chip ok">Would PASS</span>`
                : html`<span class="chip danger">Would FAIL (${failures.length})</span>`}</p>
              <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Scope</th><th>Metric</th><th>Value</th><th>Threshold</th></tr></thead>
                <tbody>${failures.length ? failures.map((f, i) => html`<tr key=${i}>
                  <td>${f.scope}</td><td>${f.metric}</td><td class="mono">${fmt(f.value)}</td><td class="mono">${fmt(f.threshold)}</td></tr>`)
                  : html`<tr><td colspan="4" class="empty">All checked scopes pass 🎉</td></tr>`}</tbody></table></div>
            </div>`}
          ${!snapshot && html`<div class="row" style="justify-content:flex-end;margin-top:16px">
            <button class="btn primary" onClick=${() => this.setState({ showDiff: true })}>Save gate.json…</button></div>`}
        </div>
      </div>

      ${showDiff && html`<div class="modal-scrim" onClick=${() => this.setState({ showDiff: false })}>
        <div class="modal" onClick=${(e) => e.stopPropagation()}>
          <h3>Save gate.json</h3>
          <p class="muted">Review the change (previous file is backed up to <code>gate.json.bak</code>):</p>
          <pre class="mono" style="background:var(--surface-2);padding:12px;border-radius:8px;max-height:300px;overflow:auto">${JSON.stringify(this.cleanGate(), null, 2)}</pre>
          <div class="row" style="justify-content:flex-end;gap:8px;margin-top:12px">
            <button class="btn secondary" onClick=${() => this.setState({ showDiff: false })}>Cancel</button>
            <button class="btn primary" disabled=${saving} onClick=${() => this.save()}>${saving ? "Saving…" : "Save"}</button>
          </div>
        </div>
      </div>`}
    </main>`;
  }
}
