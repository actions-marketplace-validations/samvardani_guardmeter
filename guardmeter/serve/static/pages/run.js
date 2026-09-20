// Run page: metric cards, confusion matrices, slice heatmap, attack bar,
// threshold-sweep + latency charts, and a paginated sample explorer + drawer.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, fmt, fmtMs, fmtLatency, shortId, VerdictChip, toast } from "/static/components/ui.js";
import { computeSweep, latencyBuckets, heatColor, lineChart, barChart, downloadCanvasPng } from "/static/charts.js";
import { sliceMetricValue, naReason } from "/static/components/metrics.js";

const isSnapshot = () => !!window.__SNAPSHOT__;

// A canvas that owns a Chart.js instance for its lifetime.
class ChartCanvas extends Component {
  componentDidMount() { if (window.Chart && this.base) this.chart = this.props.make(this.base); }
  componentWillUnmount() { if (this.chart) this.chart.destroy(); }
  exportPng = () => this.base && downloadCanvasPng(this.base, (this.props.name || "chart") + ".png");
  render(props) {
    return html`<div>
      <div style=${`position:relative;height:${props.height || 220}px`}><canvas ref=${(el) => (this.base = el)}></canvas></div>
      ${!isSnapshot() && html`<button class="btn ghost" style="font-size:12px;margin-top:4px" onClick=${this.exportPng}>⬇ PNG</button>`}
    </div>`;
  }
}

function parseSlices(dict) {
  // {"[\"crime\",\"en\"]": bundle, …} → [{category, language, bundle, n}]
  return Object.entries(dict || {}).map(([k, b]) => {
    let cat = "?", lang = "?";
    try { [cat, lang] = JSON.parse(k); } catch (_e) { /* keep defaults */ }
    return { category: cat, language: lang, bundle: b, n: b.tp + b.fp + b.tn + b.fn };
  });
}

function parseAttacks(dict) {
  return Object.entries(dict || {}).map(([k, b]) => {
    let name = "?";
    try { [name] = JSON.parse(k); } catch (_e) { /* keep default */ }
    return { attack: name ?? "—", recall: sliceMetricValue(b, "recall"), n: b.tp + b.fp + b.tn + b.fn };
  });
}

function metricCard(title, m) {
  if (!m) return html`<div class="card">${title}: no data</div>`;
  const cell = (label, value) => html`<span class="muted">${label}</span><span class="mono">${value}</span>`;
  return html`<div class="card">
    <h3>${title}</h3>
    <div class="grid" style="grid-template-columns:auto 1fr;gap:4px 16px;font-size:13px">
      ${cell("Recall", `${fmt(m.recall)} (${fmt(m.recall_lo, 3)}–${fmt(m.recall_hi, 3)})`)}
      ${cell("Precision", fmt(m.precision))}
      ${cell("F1", fmt(m.f1))}
      ${cell("FPR", `${fmt(m.fpr)} (${fmt(m.fpr_lo, 3)}–${fmt(m.fpr_hi, 3)})`)}
      ${cell("FNR", fmt(m.fnr))}
      ${cell("p50/p90/p99", `${fmtMs(m.latency_p50)}/${fmtMs(m.latency_p90)}/${fmtMs(m.latency_p99)} ms`)}
    </div>
  </div>`;
}

function confusion(title, m) {
  if (!m) return null;
  const total = m.tp + m.fp + m.tn + m.fn || 1;
  const pct = (n) => `${((n / total) * 100).toFixed(1)}%`;
  const box = (n, good) => html`<td class="mono" style=${`text-align:center;background:${good ? "color-mix(in srgb,var(--ok) 16%,transparent)" : "color-mix(in srgb,var(--danger) 16%,transparent)"}`}>${n}<br/><span class="muted" style="font-size:11px">${pct(n)}</span></td>`;
  return html`<div class="card">
    <h3>${title} — confusion</h3>
    <table class="tbl"><thead><tr><th></th><th>Pred flag</th><th>Pred pass</th></tr></thead>
      <tbody>
        <tr><th>Actual unsafe</th>${box(m.tp, true)}${box(m.fn, false)}</tr>
        <tr><th>Actual benign</th>${box(m.fp, false)}${box(m.tn, true)}</tr>
      </tbody></table>
  </div>`;
}

export class RunPage extends Component {
  state = { run: null, loading: true, heatMetric: "recall",
            samples: [], total: 0, offset: 0, filter: "all", q: "",
            category: "", language: "", attack: "", drawer: null, retest: null };

  componentDidMount() { this.load(); }
  componentDidUpdate(prev) { if (prev.route.id !== this.props.route.id) this.load(); }

  async load() {
    this.setState({ loading: true });
    try {
      const run = await api.run(this.props.route.id);
      this.setState({ run, loading: false }, () => this.loadSamples());
    } catch (e) { toast(e.message, "error"); this.setState({ loading: false }); }
  }

  async loadSamples() {
    const { filter, q, offset, category, language, attack } = this.state;
    try {
      const data = await api.samples(this.props.route.id, {
        filter, q, category, language, attack, offset: String(offset), limit: "25" });
      this.setState({ samples: data.rows, total: data.total });
    } catch (e) { toast(e.message, "error"); }
  }

  setFilter(patch) { this.setState({ ...patch, offset: 0 }, () => this.loadSamples()); }

  async exportFiltered() {
    const { filter, q, category, language, attack } = this.state;
    const data = await api.samples(this.props.route.id, { filter, q, category, language, attack, offset: "0", limit: "100000" });
    const cols = ["text", "label", "category", "language", "attack_type", "baseline_pred", "candidate_pred", "baseline_score", "candidate_score"];
    const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [cols.join(",")].concat(data.rows.map((r) => cols.map((c) => esc(r[c])).join(","))).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `${this.props.route.id}-filtered.csv`;
    a.click();
  }

  async retest(text) {
    this.setState({ retest: { loading: true } });
    try {
      const res = await api.tryText(text, [this.state.run.candidate_name]);
      this.setState({ retest: { result: res[0] } });
    } catch (e) { toast(e.message, "error"); this.setState({ retest: null }); }
  }

  heatmap(run) {
    const slices = parseSlices((run.candidate_slices || {}).strict);
    if (!slices.length) return html`<div class="card empty">No slice data</div>`;
    const cats = [...new Set(slices.map((s) => s.category))].sort();
    const langs = [...new Set(slices.map((s) => s.language))].sort();
    const at = (c, l) => slices.find((s) => s.category === c && s.language === l);
    const metric = this.state.heatMetric;
    return html`<div class="card">
      <div class="row between center"><h3 style="margin:0">Slice heatmap — candidate ${metric}</h3>
        <select class="select" style="width:auto" value=${metric} onChange=${(e) => this.setState({ heatMetric: e.target.value })}>
          <option value="recall">recall</option><option value="fpr">FPR</option></select>
      </div>
      <div class="heatmap" style=${`grid-template-columns:120px repeat(${langs.length},1fr);margin-top:12px`}>
        <div class="cell hd"></div>
        ${langs.map((l) => html`<div class="cell hd">${l}</div>`)}
        ${cats.map((c) => [
          html`<div class="cell hd" style="text-align:left">${c}</div>`,
          ...langs.map((l) => {
            const s = at(c, l);
            if (!s) return html`<div class="cell" style="background:var(--surface-2)">—</div>`;
            const val = sliceMetricValue(s.bundle, metric);
            if (val === null) return html`<div class="cell" style="background:var(--surface-2);color:var(--text-muted)"
              title=${`${c}/${l} · ${naReason(metric)}`}>n/a<br/><span style="font-size:10px;opacity:.8">n=${s.n}</span></div>`;
            return html`<div class="cell" style=${`background:${heatColor(val, metric === "fpr")}`}
              title=${`${c}/${l} · n=${s.n}`}
              onClick=${() => this.setFilter({ category: c, language: l })}>${fmt(val, 2)}<br/><span style="font-size:10px;opacity:.8">n=${s.n}</span></div>`;
          }),
        ])}
      </div>
    </div>`;
  }

  render(props, { run, loading, samples, total, offset, drawer, retest }) {
    if (loading || !run) return html`<main class="container" style="padding:24px"><div class="skeleton" style="height:200px"></div></main>`;
    const cand = (run.candidate_metrics || {}).strict;
    const base = (run.baseline_metrics || {}).strict;
    const sweep = computeSweep(run.sample_results || []);
    const lat = latencyBuckets((run.sample_results || []).map((s) => s.candidate_latency_ms));
    const attacks = parseAttacks((run.candidate_attack_slices || {}).strict).filter((a) => a.recall !== null);
    const sig = run.mcnemar_p == null ? "McNemar test unavailable."
      : run.mcnemar_p < 0.05
        ? `The baseline→candidate difference is statistically significant (McNemar p = ${run.mcnemar_p < 0.001 ? "<0.001" : run.mcnemar_p.toFixed(3)}).`
        : `The baseline→candidate difference is not statistically significant (McNemar p = ${run.mcnemar_p.toFixed(3)}).`;
    const cats = [...new Set((run.sample_results || []).map((s) => s.category))].sort();
    const langs = [...new Set((run.sample_results || []).map((s) => s.language))].sort();
    const attackVals = [...new Set((run.sample_results || []).map((s) => s.attack_type).filter(Boolean))].sort();

    return html`<main class="container" style="padding:24px 24px 48px">
      <div class="row between center">
        <h2 style="margin:0">Run ${shortId(run.run_id)} · ${run.baseline_name} → ${run.candidate_name}</h2>
        <a class="btn secondary" href=${api.exportCsvUrl(run.run_id)}>Export full CSV</a>
      </div>
      <p class="muted">${sig}</p>

      <div class="grid" style="grid-template-columns:1fr 1fr;margin-top:8px">
        ${metricCard("Baseline (strict)", base)}
        ${metricCard("Candidate (strict)", cand)}
        ${confusion("Baseline", base)}
        ${confusion("Candidate", cand)}
      </div>

      <div class="grid" style="grid-template-columns:1fr 1fr;margin-top:16px">
        ${this.heatmap(run)}
        <div class="card"><h3>Attack-type recall — candidate</h3>
          ${attacks.length
            ? html`<${ChartCanvas} name="attack-recall" make=${(cv) => barChart(cv, attacks.map((a) => a.attack), attacks.map((a) => a.recall), "recall")}/>`
            : html`<div class="empty">No attack-type slices</div>`}
        </div>
      </div>

      <div class="grid" style="grid-template-columns:1fr 1fr;margin-top:16px">
        <div class="card"><h3>Candidate threshold sweep</h3>
          ${sweep ? html`<${ChartCanvas} name="threshold-sweep" make=${(cv) => lineChart(cv, sweep)}/>` : html`<div class="empty">No candidate scores</div>`}
        </div>
        <div class="card"><h3>Candidate per-sample latency (ms)</h3>
          <${ChartCanvas} name="latency-hist" make=${(cv) => barChart(cv, lat.labels, lat.counts, "count", "var(--accent)")}/>
        </div>
      </div>

      <div class="section-title">Sample explorer</div>
      <div class="row wrap center" style="gap:8px;margin-bottom:12px">
        <select class="select" style="width:auto" value=${this.state.filter} onChange=${(e) => this.setFilter({ filter: e.target.value })}>
          <option value="all">All</option><option value="fn">False negatives</option>
          <option value="fp">False positives</option><option value="mismatch">Mismatches</option>
          <option value="disagree">Judge disagreed</option>
        </select>
        <select class="select" style="width:auto" value=${this.state.category} onChange=${(e) => this.setFilter({ category: e.target.value })}>
          <option value="">category…</option>${cats.map((c) => html`<option value=${c}>${c}</option>`)}
        </select>
        <select class="select" style="width:auto" value=${this.state.language} onChange=${(e) => this.setFilter({ language: e.target.value })}>
          <option value="">lang…</option>${langs.map((l) => html`<option value=${l}>${l}</option>`)}
        </select>
        ${attackVals.length ? html`<select class="select" style="width:auto" value=${this.state.attack} onChange=${(e) => this.setFilter({ attack: e.target.value })}>
          <option value="">attack…</option>${attackVals.map((a) => html`<option value=${a}>${a}</option>`)}</select>` : ""}
        <input class="input" style="width:200px" placeholder="Search…" value=${this.state.q}
          onInput=${(e) => this.setState({ q: e.target.value })} onKeyDown=${(e) => e.key === "Enter" && this.setFilter({})}/>
        <button class="btn secondary" onClick=${() => this.exportFiltered()}>Export filtered CSV</button>
      </div>
      <div class="tbl-wrap">
        <table class="tbl"><thead><tr>
          <th>Text</th><th>Label</th><th>Category</th><th>Lang</th><th>Baseline</th><th>Candidate</th></tr></thead>
          <tbody>
            ${samples.length ? samples.map((s, i) => html`<tr key=${i} style="cursor:pointer" onClick=${() => this.setState({ drawer: s, retest: null })}>
              <td style="max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.text}</td>
              <td>${s.label}</td><td>${s.category}</td><td>${s.language}</td>
              <td><${VerdictChip} prediction=${s.baseline_pred}/></td>
              <td><${VerdictChip} prediction=${s.candidate_pred}/></td>
            </tr>`) : html`<tr><td colspan="6" class="empty">No matching samples</td></tr>`}
          </tbody></table>
      </div>
      <div class="row center" style="gap:12px;margin-top:12px">
        <button class="btn secondary" disabled=${offset === 0} onClick=${() => this.setState({ offset: Math.max(0, offset - 25) }, () => this.loadSamples())}>← Prev</button>
        <span class="muted">${total ? offset + 1 : 0}–${Math.min(offset + 25, total)} of ${total}</span>
        <button class="btn secondary" disabled=${offset + 25 >= total} onClick=${() => this.setState({ offset: offset + 25 }, () => this.loadSamples())}>Next →</button>
      </div>

      ${drawer && html`<div class="drawer-scrim" onClick=${() => this.setState({ drawer: null })}></div>
        <aside class="drawer" role="dialog" aria-label="Sample detail">
          <div class="row between center"><h3 style="margin:0">Sample</h3>
            <button class="btn ghost icon" aria-label="Close" onClick=${() => this.setState({ drawer: null })}>✕</button></div>
          <p style="white-space:pre-wrap;background:var(--surface-2);padding:12px;border-radius:8px">${drawer.text}</p>
          <div class="grid" style="grid-template-columns:auto 1fr;gap:4px 16px;font-size:13px">
            <span class="muted">Ground truth</span><span>${drawer.label} · ${drawer.category}/${drawer.language}${drawer.attack_type ? " · " + drawer.attack_type : ""}</span>
            <span class="muted">Baseline</span><span><${VerdictChip} prediction=${drawer.baseline_pred}/> score ${fmt(drawer.baseline_score, 2)} · ${fmtLatency(drawer.baseline_latency_ms)}</span>
            <span class="muted">Candidate</span><span><${VerdictChip} prediction=${drawer.candidate_pred}/> score ${fmt(drawer.candidate_score, 2)} · ${fmtLatency(drawer.candidate_latency_ms)}</span>
          </div>
          ${!isSnapshot() && html`<div style="margin-top:16px">
            <button class="btn primary" disabled=${retest && retest.loading} onClick=${() => this.retest(drawer.text)}>
              ${retest && retest.loading ? "Re-testing…" : "Re-test now"}</button>
            ${retest && retest.result && html`<p style="margin-top:8px">Now: <${VerdictChip} prediction=${retest.result.prediction} error=${retest.result.error}/> score ${fmt(retest.result.score, 2)}</p>`}
          </div>`}
        </aside>`}
    </main>`;
  }
}
