// Chart helpers built on the globally-loaded Chart.js (window.Chart) plus a
// couple of pure data transforms. Charts render into a <canvas> ref.

function themeColors() {
  const css = getComputedStyle(document.documentElement);
  return {
    grid: css.getPropertyValue("--border").trim() || "#334155",
    text: css.getPropertyValue("--text-muted").trim() || "#94a3b8",
    accent: css.getPropertyValue("--accent-2").trim() || "#818cf8",
    ok: css.getPropertyValue("--ok").trim() || "#4ade80",
    danger: css.getPropertyValue("--danger").trim() || "#f87171",
  };
}

// Threshold sweep from candidate scores + labels (strict policy positives).
export function computeSweep(samples) {
  const scored = samples.filter((s) => s.candidate_score !== null && s.candidate_score !== undefined);
  if (!scored.length) return null;
  const pos = (s) => s.label !== "benign";
  const P = scored.filter(pos).length, N = scored.length - P;
  const thresholds = [], precision = [], recall = [], fpr = [];
  for (let t = 0; t <= 1.0001; t += 0.05) {
    let tp = 0, fp = 0, fn = 0, tn = 0;
    for (const s of scored) {
      const flag = s.candidate_score >= t;
      if (pos(s)) (flag ? tp++ : fn++); else (flag ? fp++ : tn++);
    }
    thresholds.push(t.toFixed(2));
    precision.push(tp + fp ? tp / (tp + fp) : 1);
    recall.push(P ? tp / P : 0);
    fpr.push(N ? fp / N : 0);
  }
  return { thresholds, precision, recall, fpr };
}

export function latencyBuckets(values, buckets = 12) {
  const nums = values.filter((v) => v !== null && v !== undefined).map(Number);
  if (!nums.length) return { labels: [], counts: [] };
  const max = Math.max(...nums, 1);
  const size = Math.max(1, Math.ceil(max / buckets));
  const counts = new Array(buckets).fill(0);
  for (const v of nums) counts[Math.min(Math.floor(v / size), buckets - 1)]++;
  const labels = counts.map((_, i) => `${i * size}–${(i + 1) * size}`);
  return { labels, counts };
}

// Diverging heat colour for a 0..1 metric (green good … red bad).
export function heatColor(value, invert = false) {
  if (value === null || value === undefined) return "var(--surface-2)";
  let v = Math.max(0, Math.min(1, value));
  if (invert) v = 1 - v;
  const hue = v * 130; // 0=red → 130=green
  return `hsl(${hue}, 62%, 55%)`;
}

export function lineChart(canvas, sweep) {
  const c = themeColors();
  return new window.Chart(canvas, {
    type: "line",
    data: {
      labels: sweep.thresholds,
      datasets: [
        { label: "Precision", data: sweep.precision, borderColor: c.accent, fill: false, tension: 0.25, pointRadius: 2 },
        { label: "Recall", data: sweep.recall, borderColor: c.ok, fill: false, tension: 0.25, pointRadius: 2 },
        { label: "FPR", data: sweep.fpr, borderColor: c.danger, fill: false, tension: 0.25, pointRadius: 2 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: c.text } } },
      scales: {
        x: { title: { display: true, text: "Threshold", color: c.text }, ticks: { color: c.text }, grid: { color: c.grid } },
        y: { min: 0, max: 1, title: { display: true, text: "Rate", color: c.text }, ticks: { color: c.text }, grid: { color: c.grid } },
      },
    },
  });
}

export function barChart(canvas, labels, data, label, color) {
  const c = themeColors();
  return new window.Chart(canvas, {
    type: "bar",
    data: { labels, datasets: [{ label, data, backgroundColor: color || c.accent }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: c.text }, grid: { color: c.grid } },
        y: { beginAtZero: true, ticks: { color: c.text }, grid: { color: c.grid } },
      },
    },
  });
}

export function downloadCanvasPng(canvas, name) {
  const a = document.createElement("a");
  a.href = canvas.toDataURL("image/png");
  a.download = name;
  a.click();
}
