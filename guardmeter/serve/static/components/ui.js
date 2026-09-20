// Shared UI primitives. htm+preact interpolation auto-escapes text and
// attributes, so user data never becomes markup — no innerHTML anywhere.

import { h } from "/static/preact.module.js";
import htm from "/static/htm.module.js";

export const html = htm.bind(h);

export function fmt(v, dec = 4) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toFixed(dec);
}

export function fmtP(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  return n < 0.001 ? "<0.001" : n.toFixed(3);
}

export function shortId(id) {
  return id ? String(id).slice(0, 8) : "—";
}

export function GateChip({ pass }) {
  if (pass === null || pass === undefined) return html`<span class="chip neutral">—</span>`;
  return pass
    ? html`<span class="chip ok">✓ PASS</span>`
    : html`<span class="chip danger">✗ FAIL</span>`;
}

export function VerdictChip({ prediction, error }) {
  if (error) return html`<span class="chip warn">ERROR</span>`;
  return prediction === "flag"
    ? html`<span class="chip danger">FLAG</span>`
    : html`<span class="chip ok">PASS</span>`;
}

// Tiny inline-SVG sparkline (no chart lib needed for the KPI row).
export function Sparkline({ values, width = 90, height = 26, color = "var(--accent)" }) {
  const nums = (values || []).filter((v) => v !== null && v !== undefined).map(Number);
  if (nums.length < 2) return html`<svg class="spark" width=${width} height=${height} aria-hidden="true"></svg>`;
  const min = Math.min(...nums), max = Math.max(...nums);
  const span = max - min || 1;
  const step = width / (nums.length - 1);
  const pts = nums.map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / span) * (height - 4) - 2).toFixed(1)}`).join(" ");
  return html`<svg class="spark" width=${width} height=${height} viewBox=${`0 0 ${width} ${height}`} aria-hidden="true">
    <polyline points=${pts} fill="none" stroke=${color} stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

export function Delta({ value, higherBetter = true, dec = 4 }) {
  if (value === null || value === undefined || value === 0) return html`<span class="muted">—</span>`;
  const good = higherBetter ? value > 0 : value < 0;
  const arrow = value > 0 ? "▲" : "▼";
  const cls = good ? "delta up" : "delta down";
  return html`<span class=${cls}>${arrow} ${value > 0 ? "+" : ""}${Number(value).toFixed(dec)}</span>`;
}

export function KpiCard({ label, value, delta, higherBetter, spark, sparkColor }) {
  return html`<div class="card kpi">
    <span class="label">${label}</span>
    <span class="value">${value}</span>
    <div class="row center between">
      ${delta !== undefined ? html`<${Delta} value=${delta} higherBetter=${higherBetter}/>` : html`<span></span>`}
      <${Sparkline} values=${spark} color=${sparkColor || "var(--accent)"}/>
    </div>
  </div>`;
}

// Toasts — direct DOM so any code path can call it.
export function toast(message, kind = "ok", ms = 3200) {
  const host = document.getElementById("toasts");
  if (!host) return;
  const el = document.createElement("div");
  el.className = "toast " + (kind === "error" ? "err" : kind);
  el.setAttribute("role", "status");
  el.textContent = message;
  host.appendChild(el);
  setTimeout(() => el.remove(), ms);
}
