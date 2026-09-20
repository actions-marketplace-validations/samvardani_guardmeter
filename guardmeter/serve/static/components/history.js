// Pure history model for the Try page.
//
// The 0.5.0 playground bug: history was rendered imperatively and the wrapper's
// `display` was toggled by hand, so a mistimed update could leave it hidden
// after the second evaluation. Here history is a plain value; the Try page
// renders it declaratively from state (visible whenever length > 0), so the
// "stayed hidden" failure mode cannot occur. This function is the single place
// entries are added — kept pure so it is unit-testable without a browser.

export function pushHistory(list, entry, max = 20) {
  const next = [entry, ...(list || [])];
  if (next.length > max) next.length = max;
  return next;
}

export function truncate(text, n = 80) {
  if (!text) return "";
  return text.length > n ? text.slice(0, n) + "…" : text;
}
