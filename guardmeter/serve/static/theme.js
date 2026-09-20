// Theme toggle — applies data-theme on <html> and persists to localStorage.
// Dark is the default.

const KEY = "gm_theme";

export function initTheme() {
  const saved = localStorage.getItem(KEY) || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  return saved;
}

export function currentTheme() {
  return document.documentElement.getAttribute("data-theme") || "dark";
}

export function toggleTheme() {
  const next = currentTheme() === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem(KEY, next);
  } catch (_e) {
    /* private mode / storage disabled — ignore */
  }
  return next;
}
