// "New evaluation" modal: pick guards + dataset, run a background compare with
// a live progress bar, then navigate to the new run.
import { Component } from "/static/preact.module.js";
import { api } from "/static/api.js";
import { html, toast } from "/static/components/ui.js";
import { navigate } from "/static/app.js";

export class NewEvalModal extends Component {
  state = { guards: [], datasets: [], baseline: "regex-baseline", candidate: "regex-enhanced",
            dataset: "", progress: null, error: null };

  async componentDidMount() {
    try {
      const [g, d] = await Promise.all([api.guards(), api.datasets()]);
      this.setState({ guards: g.guards, datasets: d.datasets,
                      dataset: d.datasets.length ? d.datasets[0].name : "" });
    } catch (e) { this.setState({ error: e.message }); }
  }

  async run() {
    this.setState({ progress: 0, error: null });
    try {
      const { job_id } = await api.compare({
        baseline: this.state.baseline, candidate: this.state.candidate,
        dataset: "dataset/" + this.state.dataset });
      for (let i = 0; i < 600; i++) {
        const job = await api.job(job_id);
        this.setState({ progress: Math.round((job.progress || 0) * 100) });
        if (job.status === "done") { this.props.onClose(); navigate("/run/" + job.run_id); return; }
        if (job.status === "error") { this.setState({ error: job.error || "evaluation failed", progress: null }); return; }
        await new Promise((r) => setTimeout(r, 250));
      }
    } catch (e) { toast(e.message, "error"); this.setState({ progress: null, error: e.message }); }
  }

  render(props, { guards, datasets, baseline, candidate, dataset, progress, error }) {
    const running = progress !== null;
    return html`<div class="modal-scrim" onClick=${() => !running && props.onClose()}>
      <div class="modal" onClick=${(e) => e.stopPropagation()}>
        <h3>New evaluation</h3>
        <div class="grid" style="gap:12px">
          <label>Baseline
            <select class="select" value=${baseline} onChange=${(e) => this.setState({ baseline: e.target.value })}>
              ${guards.map((g) => html`<option value=${g}>${g}</option>`)}</select></label>
          <label>Candidate
            <select class="select" value=${candidate} onChange=${(e) => this.setState({ candidate: e.target.value })}>
              ${guards.map((g) => html`<option value=${g}>${g}</option>`)}</select></label>
          <label>Dataset
            <select class="select" value=${dataset} onChange=${(e) => this.setState({ dataset: e.target.value })}>
              ${datasets.map((d) => html`<option value=${d.name}>${d.name} (${d.rows} rows)</option>`)}</select></label>
        </div>
        ${error && html`<p style="color:var(--danger);margin-top:12px">${error}</p>`}
        ${running && html`<div style="margin-top:16px">
          <div style="height:8px;background:var(--surface-2);border-radius:999px;overflow:hidden">
            <div style=${`height:100%;width:${progress}%;background:var(--accent-2);transition:width .2s`}></div></div>
          <p class="muted" style="font-size:12px;margin-top:6px">Running… ${progress}%</p>
        </div>`}
        <div class="row" style="justify-content:flex-end;gap:8px;margin-top:16px">
          <button class="btn secondary" disabled=${running} onClick=${() => props.onClose()}>Cancel</button>
          <button class="btn primary" disabled=${running || !dataset} onClick=${() => this.run()}>Run</button>
        </div>
      </div>
    </div>`;
  }
}
