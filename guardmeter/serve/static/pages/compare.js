// Compare page: two runs side by side — metric deltas, a delta heatmap, and
// the samples whose candidate verdict changed. Deep-linkable: /compare?a=&b=.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, fmt, shortId, VerdictChip, toast } from "/static/components/ui.js";
import { sliceMetricValue } from "/static/components/metrics.js";

function deltaColor(d) {
  if (d === null || d === undefined || Math.abs(d) < 1e-9) return "var(--surface-2)";
  const mag = Math.min(1, Math.abs(d) * 4); // amplify small deltas for visibility
  const hue = d > 0 ? 130 : 0; // green up, red down
  return `hsla(${hue}, 62%, 50%, ${0.25 + mag * 0.6})`;
}

function parseSlices(dict) {
  const out = {};
  for (const [k, b] of Object.entries(dict || {})) {
    let cat = "?", lang = "?";
    try { [cat, lang] = JSON.parse(k); } catch (_e) { /* keep */ }
    // null recall when the slice has no positives — excluded from the delta scale.
    out[`${cat}/${lang}`] = { category: cat, language: lang, recall: sliceMetricValue(b, "recall") };
  }
  return out;
}

const FIELDS = [
  ["Recall", "recall", true], ["Precision", "precision", true], ["F1", "f1", true],
  ["FPR", "fpr", false], ["FNR", "fnr", false],
  ["Latency p50", "latency_p50", false], ["Latency p90", "latency_p90", false], ["Latency p99", "latency_p99", false],
];

export class ComparePage extends Component {
  state = { runs: [], aId: "", bId: "", a: null, b: null, drawer: null };

  async componentDidMount() {
    const params = new URLSearchParams(location.search);
    try {
      const runs = await api.runs({ limit: "100" });
      const aId = params.get("a") || (runs[0] && runs[0].run_id) || "";
      const bId = params.get("b") || (runs[1] && runs[1].run_id) || (runs[0] && runs[0].run_id) || "";
      this.setState({ runs, aId, bId }, () => this.loadBoth());
    } catch (e) { toast(e.message, "error"); }
  }

  async loadBoth() {
    const { aId, bId } = this.state;
    if (!aId || !bId) return;
    this.props.navigate(`/compare?a=${encodeURIComponent(aId)}&b=${encodeURIComponent(bId)}`);
    try {
      const [a, b] = await Promise.all([api.run(aId), api.run(bId)]);
      this.setState({ a, b });
    } catch (e) { toast(e.message, "error"); }
  }

  pick(which, id) { this.setState({ [which]: id }, () => this.loadBoth()); }

  changedSamples(a, b) {
    const sa = a.sample_results || [], sb = b.sample_results || [];
    const n = Math.min(sa.length, sb.length);
    const out = [];
    for (let i = 0; i < n; i++) {
      if (sa[i].candidate_pred !== sb[i].candidate_pred && sa[i].text === sb[i].text) {
        out.push({ text: sa[i].text, label: sa[i].label, category: sa[i].category,
                   language: sa[i].language, a: sa[i].candidate_pred, b: sb[i].candidate_pred });
      }
    }
    return out;
  }

  render(props, { runs, aId, bId, a, b, drawer }) {
    const picker = (which, val) => html`<select class="select" style="width:auto" value=${val}
      onChange=${(e) => this.pick(which, e.target.value)}>
      ${runs.map((r) => html`<option value=${r.run_id}>${shortId(r.run_id)} · ${r.candidate}</option>`)}</select>`;

    if (!a || !b) return html`<main class="container" style="padding:24px 24px 48px">
      <h2>Compare</h2><div class="row center" style="gap:12px">A ${picker("aId", aId)} B ${picker("bId", bId)}</div>
      <div class="skeleton" style="height:160px;margin-top:16px"></div></main>`;

    const ma = (a.candidate_metrics || {}).strict || {};
    const mb = (b.candidate_metrics || {}).strict || {};
    const sa = parseSlices((a.candidate_slices || {}).strict);
    const sb = parseSlices((b.candidate_slices || {}).strict);
    const keys = [...new Set([...Object.keys(sa), ...Object.keys(sb)])].sort();
    const cats = [...new Set(keys.map((k) => k.split("/")[0]))].sort();
    const langs = [...new Set(keys.map((k) => k.split("/")[1]))].sort();
    const changed = this.changedSamples(a, b);

    return html`<main class="container" style="padding:24px 24px 48px">
      <h2>Compare</h2>
      <div class="row center" style="gap:12px;margin-bottom:16px">
        A ${picker("aId", aId)} B ${picker("bId", bId)}
        <span class="muted">${a.candidate_name} vs ${b.candidate_name}</span>
      </div>

      <div class="grid" style="grid-template-columns:1fr 1fr;gap:24px">
        <div class="card"><h3>Metric deltas (B − A)</h3>
          <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Metric</th><th class="text-right">A</th><th class="text-right">B</th><th class="text-right">Δ</th></tr></thead>
            <tbody>${FIELDS.map(([label, key, higher]) => {
              const va = ma[key], vb = mb[key], d = (va != null && vb != null) ? vb - va : null;
              const good = d != null && (higher ? d > 0 : d < 0);
              const bad = d != null && (higher ? d < 0 : d > 0);
              const color = good ? "var(--ok)" : bad ? "var(--danger)" : "var(--text-muted)";
              const arrow = d == null || d === 0 ? "" : d > 0 ? " ▲" : " ▼";
              return html`<tr key=${key}><td>${label}</td>
                <td class="mono text-right">${fmt(va)}</td><td class="mono text-right">${fmt(vb)}</td>
                <td class="mono text-right" style=${`color:${color}`}>${d == null ? "—" : (d > 0 ? "+" : "") + fmt(d)}${arrow}</td></tr>`;
            })}</tbody></table></div>
        </div>

        <div class="card"><h3>Slice recall Δ (B − A)</h3>
          ${keys.length ? html`<div class="heatmap" style=${`grid-template-columns:120px repeat(${langs.length},1fr);margin-top:12px`}>
            <div class="cell hd"></div>${langs.map((l) => html`<div class="cell hd">${l}</div>`)}
            ${cats.map((c) => [
              html`<div class="cell hd" style="text-align:left">${c}</div>`,
              ...langs.map((l) => {
                const key = `${c}/${l}`;
                const ra = sa[key] && sa[key].recall, rb = sb[key] && sb[key].recall;
                if (ra == null || rb == null) return html`<div class="cell" style="background:var(--surface-2);color:var(--text-muted)"
                  title=${`${key} · recall undefined in one run (no positives)`}>n/a</div>`;
                const d = rb - ra;
                return html`<div class="cell" style=${`background:${deltaColor(d)};color:var(--text)`} title=${key}>${(d > 0 ? "+" : "") + fmt(d, 2)}</div>`;
              }),
            ])}
          </div>` : html`<div class="empty">No comparable slices</div>`}
        </div>
      </div>

      ${(() => {
        const langRecall = (run) => {
          const out = {};
          for (const [k, b] of Object.entries((run.candidate_language_slices || {}).strict || {})) {
            try { out[JSON.parse(k)[0]] = (b.tp + b.fn) ? b.recall : null; } catch (_e) { /* skip */ }
          }
          return out;
        };
        const la = langRecall(a), lb = langRecall(b);
        const codes = [...new Set([...Object.keys(la), ...Object.keys(lb)])].sort();
        if (!codes.length) return "";
        return html`<div class="section-title">Recall by language Δ (B − A)</div>
          <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Language</th><th class="text-right">A</th><th class="text-right">B</th><th class="text-right">Δ</th></tr></thead>
          <tbody>${codes.map((c) => {
            const ra = la[c], rb = lb[c], d = (ra != null && rb != null) ? rb - ra : null;
            const color = d == null ? "var(--text-muted)" : d < 0 ? "var(--danger)" : d > 0 ? "var(--ok)" : "var(--text-muted)";
            return html`<tr key=${c}><td>${c}</td><td class="mono text-right">${fmt(ra)}</td>
              <td class="mono text-right">${fmt(rb)}</td>
              <td class="mono text-right" style=${`color:${color}`}>${d == null ? "—" : (d > 0 ? "+" : "") + fmt(d)}</td></tr>`;
          })}</tbody></table></div>`;
      })()}

      <div class="section-title">Samples that changed (${changed.length})</div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Text</th><th>Label</th><th>A</th><th></th><th>B</th></tr></thead>
        <tbody>${changed.length ? changed.map((s, i) => html`<tr key=${i} style="cursor:pointer" onClick=${() => this.setState({ drawer: s })}>
          <td style="max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.text}</td>
          <td>${s.label}</td><td><${VerdictChip} prediction=${s.a}/></td><td class="muted">→</td><td><${VerdictChip} prediction=${s.b}/></td>
        </tr>`) : html`<tr><td colspan="5" class="empty">No candidate verdicts changed between these runs.</td></tr>`}</tbody></table></div>

      ${drawer && html`<div class="drawer-scrim" onClick=${() => this.setState({ drawer: null })}></div>
        <aside class="drawer" role="dialog" aria-label="Changed sample">
          <div class="row between center"><h3 style="margin:0">Changed sample</h3>
            <button class="btn ghost icon" aria-label="Close" onClick=${() => this.setState({ drawer: null })}>✕</button></div>
          <p style="white-space:pre-wrap;background:var(--surface-2);padding:12px;border-radius:8px">${drawer.text}</p>
          <div class="grid" style="grid-template-columns:auto 1fr;gap:4px 16px;font-size:13px">
            <span class="muted">Ground truth</span><span>${drawer.label} · ${drawer.category}/${drawer.language}</span>
            <span class="muted">Run A</span><span><${VerdictChip} prediction=${drawer.a}/></span>
            <span class="muted">Run B</span><span><${VerdictChip} prediction=${drawer.b}/></span>
          </div>
        </aside>`}
    </main>`;
  }
}
