// Pure metric-cell model. Recall is undefined for a slice with no positive
// examples; FPR is undefined for a slice with no negatives. Undefined must
// render as "n/a" (neutral, excluded from the colour scale), never as 0.

export function sliceMetricValue(b, metric) {
  const hasPositives = ((b.tp || 0) + (b.fn || 0)) > 0;
  const hasNegatives = ((b.fp || 0) + (b.tn || 0)) > 0;
  if (metric === "recall") return hasPositives ? b.recall : null;
  if (metric === "fpr") return hasNegatives ? b.fpr : null;
  const v = b[metric];
  return v === undefined ? null : v;
}

export function naReason(metric) {
  return metric === "fpr" ? "no negatives in this slice" : "no positives in this slice";
}
