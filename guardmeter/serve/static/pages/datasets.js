// Datasets page: list datasets with stat bars, browse rows with search.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, toast } from "/static/components/ui.js";

function StatBars({ title, counts }) {
  const entries = Object.entries(counts || {});
  const total = entries.reduce((a, [, n]) => a + n, 0) || 1;
  return html`<div style="margin-bottom:10px">
    <div class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:.05em">${title}</div>
    ${entries.map(([k, n]) => html`<div class="row center" style="gap:8px;margin-top:2px">
      <span style="width:110px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${k}</span>
      <div style="flex:1;height:8px;background:var(--surface-2);border-radius:999px;overflow:hidden">
        <div style=${`height:100%;width:${(n / total) * 100}%;background:var(--accent)`}></div></div>
      <span class="mono" style="font-size:12px;width:36px;text-align:right">${n}</span>
    </div>`)}
  </div>`;
}

export class DatasetsPage extends Component {
  state = { datasets: [], selected: null, stats: null, rows: [], total: 0, offset: 0, q: "", loading: true };

  async componentDidMount() {
    try {
      const d = await api.datasets();
      this.setState({ datasets: d.datasets, loading: false });
      if (d.datasets.length) this.select(d.datasets[0].name);
    } catch (e) { toast(e.message, "error"); this.setState({ loading: false }); }
  }

  async select(name) {
    this.setState({ selected: name, offset: 0, q: "", stats: null });
    try {
      const [stats] = await Promise.all([api.datasetStats(name)]);
      this.setState({ stats });
      this.loadRows(name, 0, "");
    } catch (e) { toast(e.message, "error"); }
  }

  async loadRows(name, offset, q) {
    try {
      const data = await api.datasetRows(name, { q, offset: String(offset), limit: "25" });
      this.setState({ rows: data.rows, total: data.total, offset });
    } catch (e) { toast(e.message, "error"); }
  }

  render(_, { datasets, selected, stats, rows, total, offset, q, loading }) {
    if (loading) return html`<main class="container" style="padding:24px"><div class="skeleton" style="height:120px"></div></main>`;
    if (!datasets.length) return html`<main class="container" style="padding:24px"><div class="card empty">No datasets under <code>dataset/</code>.</div></main>`;
    const cols = rows.length ? Object.keys(rows[0]) : [];
    return html`<main class="container" style="padding:24px 24px 48px">
      <h2>Datasets</h2>
      <div class="grid" style="grid-template-columns:280px 1fr;gap:24px">
        <div class="card">
          <div class="section-title" style="margin-top:0">Files</div>
          ${datasets.map((d) => html`<div key=${d.name} class=${"row between center"} style=${`padding:8px;border-radius:8px;cursor:pointer;${selected === d.name ? "background:var(--surface-2)" : ""}`}
              onClick=${() => this.select(d.name)}>
            <span>${d.name}</span><span class="muted mono" style="font-size:12px">${d.rows}</span></div>`)}
          ${stats && html`<div style="margin-top:16px">
            <${StatBars} title="Labels" counts=${stats.labels}/>
            <${StatBars} title="Categories" counts=${stats.categories}/>
            <${StatBars} title="Languages" counts=${stats.languages}/>
          </div>`}
        </div>
        <div class="card">
          <div class="row between center"><h3 style="margin:0">${selected}</h3>
            <input class="input" style="width:220px" placeholder="Search rows…" value=${q}
              onInput=${(e) => this.setState({ q: e.target.value })}
              onKeyDown=${(e) => e.key === "Enter" && this.loadRows(selected, 0, this.state.q)}/></div>
          <div class="tbl-wrap" style="margin-top:12px">
            <table class="tbl"><thead><tr>${cols.map((c) => html`<th key=${c}>${c}</th>`)}</tr></thead>
              <tbody>${rows.length ? rows.map((r, i) => html`<tr key=${i}>${cols.map((c) => html`<td key=${c}
                  style=${c === "text" ? "max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" : ""}>${String(r[c] ?? "")}</td>`)}</tr>`)
                : html`<tr><td colspan=${cols.length || 1} class="empty">No rows</td></tr>`}</tbody></table>
          </div>
          <div class="row center" style="gap:12px;margin-top:12px">
            <button class="btn secondary" disabled=${offset === 0} onClick=${() => this.loadRows(selected, Math.max(0, offset - 25), q)}>← Prev</button>
            <span class="muted">${total ? offset + 1 : 0}–${Math.min(offset + 25, total)} of ${total}</span>
            <button class="btn secondary" disabled=${offset + 25 >= total} onClick=${() => this.loadRows(selected, offset + 25, q)}>Next →</button>
          </div>
        </div>
      </div>
    </main>`;
  }
}
