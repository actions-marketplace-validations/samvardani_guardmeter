// Try page: evaluate ad-hoc text against selected guards, with a live history.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, fmt, fmtLatency, VerdictChip, toast, isSnapshot } from "/static/components/ui.js";
import { pushHistory, truncate } from "/static/components/history.js";

export class TryPage extends Component {
  state = { text: "", guards: [], selected: new Set(["regex-baseline", "regex-enhanced"]),
            results: null, history: [], busy: false };

  async componentDidMount() {
    try {
      const data = await api.guards();
      this.setState({ guards: data.guards, selected: new Set(data.default || ["regex-baseline", "regex-enhanced"]) });
    } catch (e) { toast(e.message, "error"); }
    window.addEventListener("keydown", this.onKey);
  }
  componentWillUnmount() { window.removeEventListener("keydown", this.onKey); }
  onKey = (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); this.evaluate(); } };

  toggle(name) {
    const s = new Set(this.state.selected);
    s.has(name) ? s.delete(name) : s.add(name);
    this.setState({ selected: s });
  }

  async evaluate() {
    const text = this.state.text.trim();
    if (!text) return;
    this.setState({ busy: true });
    try {
      const results = await api.tryText(text, [...this.state.selected]);
      // Declarative: history is state; the panel shows whenever length > 0.
      this.setState((st) => ({ results, history: pushHistory(st.history, { text, results }), busy: false }));
    } catch (e) { toast(e.message, "error"); this.setState({ busy: false }); }
  }

  resultsTable(results) {
    if (!results) return null;
    return html`<div class="tbl-wrap" style="margin-top:16px">
      <table class="tbl"><thead><tr><th>Guard</th><th>Verdict</th><th>Score</th><th>Categories</th><th>Latency</th></tr></thead>
        <tbody>${results.map((r, i) => html`<tr key=${i}>
          <td>${r.guard}</td>
          <td><${VerdictChip} prediction=${r.prediction} error=${r.error}/></td>
          <td class="mono">${r.score === null ? "—" : fmt(r.score, 2)}</td>
          <td>${r.categories && r.categories.length ? r.categories.join(", ") : "—"}</td>
          <td class="mono">${fmtLatency(r.latency_ms)}</td>
        </tr>${r.error ? html`<tr><td></td><td colspan="4" style="color:var(--warn);font-size:12px">${r.error}</td></tr>` : ""}`)}
        </tbody></table>
    </div>`;
  }

  chip(r) {
    if (r.error) return html`<span class="chip warn">ERROR</span>`;
    return r.prediction === "flag" ? html`<span class="chip danger">FLAG</span>` : html`<span class="chip ok">PASS</span>`;
  }

  render(_, { text, guards, selected, results, history, busy }) {
    return html`<main class="container" style="padding:24px 24px 48px">
      <h2>Try a guard</h2>
      <textarea placeholder="Paste a prompt or model output…" value=${text}
        onInput=${(e) => this.setState({ text: e.target.value })}></textarea>
      <div class="row wrap center" style="gap:14px;margin:14px 0">
        ${guards.map((g) => html`<label class="check"><input type="checkbox" checked=${selected.has(g)}
          onChange=${() => this.toggle(g)}/> ${g}</label>`)}
      </div>
      <div class="row center" style="gap:12px">
        <button class="btn primary" disabled=${busy || isSnapshot()} onClick=${() => this.evaluate()}>${busy ? "Evaluating…" : "Evaluate"}</button>
        <span class="muted" style="font-size:12px">${isSnapshot() ? "Live evaluation requires guardmeter serve." : "or press ⌘/Ctrl + Enter"}</span>
      </div>
      ${this.resultsTable(results)}

      ${history.length > 0 && html`<div>
        <div class="section-title">History (last 20)</div>
        <ul style="list-style:none;margin:0;padding:0">
          ${history.map((h, i) => html`<li key=${i} class="row between center" style="padding:8px 10px;border-bottom:1px solid var(--surface-2);cursor:pointer"
              onClick=${() => this.setState({ text: h.text, results: h.results })}>
            <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${truncate(h.text)}</span>
            <span class="row" style="gap:4px">${h.results.map((r, j) => html`<span key=${j}>${this.chip(r)}</span>`)}</span>
          </li>`)}
        </ul>
      </div>`}
    </main>`;
  }
}
