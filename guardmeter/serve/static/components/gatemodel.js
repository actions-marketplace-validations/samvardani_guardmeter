// Pure gate-config (de)serialisation for the editor. Kept separate so the
// round-trip (load → edit → save) is unit-testable without a browser.
//
// Every field GlobalThresholds/SliceThresholds allows is rendered and preserved
// — earlier the editor only exposed recall+fpr, so min_f1 (and latency) on a
// loaded gate.json were invisible and could be lost on a new override.

export const SLICE_FIELDS = ["min_recall", "min_f1", "max_fpr", "max_latency_p99_ms", "max_hijack_rate", "max_error_rate"];

function cleanNumbers(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj || {})) {
    if (v !== "" && v !== null && v !== undefined) out[k] = Number(v);
  }
  return out;
}

export function serializeGate(gate) {
  const g = structuredClone(gate);
  g.global_thresholds = cleanNumbers(g.global_thresholds);
  const slices = {};
  for (const [key, ov] of Object.entries(g.slices || {})) {
    if (key) slices[key] = cleanNumbers(ov);
  }
  g.slices = slices;
  return g;
}

// Any override field the editor doesn't render (so we can warn instead of drop).
export function unknownSliceFields(gate, allowed = SLICE_FIELDS) {
  const bad = new Set();
  for (const ov of Object.values((gate && gate.slices) || {})) {
    for (const k of Object.keys(ov || {})) if (!allowed.includes(k)) bad.add(k);
  }
  return [...bad];
}
