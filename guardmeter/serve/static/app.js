// GuardMeter single-page app shell + client-side router (Preact + htm, no build).
import { render, Component } from "/static/preact.module.js";
import { html, toast } from "/static/components/ui.js";
import { initTheme, toggleTheme, currentTheme } from "/static/theme.js";
import { OverviewPage } from "/static/pages/overview.js";
import { RunPage } from "/static/pages/run.js";
import { GatePage } from "/static/pages/gate.js";
import { TryPage } from "/static/pages/try.js";
import { DatasetsPage } from "/static/pages/datasets.js";
import { ComparePage } from "/static/pages/compare.js";
import { ScenariosPage, ScenarioRunPage } from "/static/pages/scenarios.js";
import { NewEvalModal } from "/static/components/neweval.js";

initTheme();

// ── routing ──────────────────────────────────────────────────────────────
export function navigate(path) {
  // In the offline snapshot (file://) pushState throws, so use hash routing.
  if (window.__SNAPSHOT__) {
    if ("#" + path !== location.hash) location.hash = path;      // fires hashchange → re-route
    else window.dispatchEvent(new Event("gm:navigate"));
    return;
  }
  try {
    if (path !== location.pathname + location.search) history.pushState({}, "", path);
  } catch (_e) { /* non-http origin — fall back to a plain re-render */ }
  window.dispatchEvent(new Event("gm:navigate"));
}

function parseRoute() {
  // Honour a hash route first so the offline snapshot (opened from file://)
  // is deep-linkable, e.g. snap.html#/run/<id>. Live serve uses the pathname.
  const hash = location.hash && location.hash.length > 1 ? location.hash.slice(1) : "";
  const path = (hash ? hash.split("?")[0] : location.pathname);
  const run = path.match(/^\/run\/(.+)$/);
  if (run) return { name: "run", id: decodeURIComponent(run[1]) };
  const scn = path.match(/^\/scenario\/(.+)$/);
  if (scn) return { name: "scenario", id: decodeURIComponent(scn[1]) };
  if (path === "/scenarios") return { name: "scenarios" };
  if (path === "/gate") return { name: "gate" };
  if (path === "/compare") return { name: "compare" };
  if (path === "/try") return { name: "try" };
  if (path === "/datasets") return { name: "datasets" };
  return { name: "overview" };
}

// Registry filled in by later page modules; overview is built in.
export const PAGES = { overview: OverviewPage, run: RunPage, gate: GatePage, try: TryPage, datasets: DatasetsPage, compare: ComparePage, scenarios: ScenariosPage, scenario: ScenarioRunPage };

function Stub({ title }) {
  return html`<main class="container" style="padding:24px 24px 48px">
    <div class="card empty">${title} — available in this build once its section lands.</div>
  </main>`;
}

const NAV = [
  { name: "overview", href: "/", label: "Overview" },
  { name: "gate", href: "/gate", label: "Gate" },
  { name: "compare", href: "/compare", label: "Compare" },
  { name: "scenarios", href: "/scenarios", label: "Scenarios" },
  { name: "try", href: "/try", label: "Try" },
  { name: "datasets", href: "/datasets", label: "Datasets" },
];

function Shield() {
  return html`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="28" height="28" aria-hidden="true">
    <path d="M60 8 L100 24 L100 62 Q100 90 60 112 Q20 90 20 62 L20 24 Z" fill="#121814" stroke="#c8f4ad" stroke-width="2.5" stroke-linejoin="round"/>
    <polyline points="44,60 56,72 76,48" fill="none" stroke="#c8f4ad" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

class Header extends Component {
  onNav = (e, href) => { e.preventDefault(); navigate(href); };
  onSearch = (e) => {
    if (e.key === "Enter" && e.target.value.trim()) {
      navigate("/?q=" + encodeURIComponent(e.target.value.trim()));
    }
  };
  render({ route, snapshot }) {
    return html`<header class="app-header">
      <div class="brand">
        <${Shield}/>
        <span class="wm"><span style="color:var(--text)">Guard</span><span style="color:var(--accent)">Meter</span></span>
        ${!snapshot && html`<nav class="nav">
          ${NAV.map((n) => html`<a href=${n.href} class=${route.name === n.name ? "active" : ""}
             onClick=${(e) => this.onNav(e, n.href)}>${n.label}</a>`)}
        </nav>`}
      </div>
      <div class="row center" style="gap:12px">
        ${snapshot
          ? html`<span class="snapshot-badge">Read-only snapshot · generated ${window.__SNAPSHOT_AT__ || ""}</span>`
          : html`<input class="input" style="width:220px" placeholder="Search runs (⌘K)…"
                    id="global-search" aria-label="Search runs" onKeyDown=${this.onSearch}/>`}
        <button class="btn secondary" aria-label="Toggle colour theme"
          onClick=${() => { toggleTheme(); this.forceUpdate(); }}>
          ${currentTheme() === "light" ? "🌙" : "☀️"}
        </button>
        ${!snapshot && html`<button class="btn primary" onClick=${() => window.dispatchEvent(new Event("gm:newEval"))}>New evaluation</button>`}
      </div>
    </header>`;
  }
}

class App extends Component {
  state = { route: parseRoute(), newEval: false };
  onRoute = () => this.setState({ route: parseRoute() });
  onNewEval = () => this.setState({ newEval: true });
  onKey = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const el = document.getElementById("global-search");
      if (el) el.focus();
    }
  };
  componentDidMount() {
    window.addEventListener("popstate", this.onRoute);
    window.addEventListener("hashchange", this.onRoute);
    window.addEventListener("gm:navigate", this.onRoute);
    window.addEventListener("gm:newEval", this.onNewEval);
    window.addEventListener("keydown", this.onKey);
  }
  componentWillUnmount() {
    window.removeEventListener("popstate", this.onRoute);
    window.removeEventListener("hashchange", this.onRoute);
    window.removeEventListener("gm:navigate", this.onRoute);
    window.removeEventListener("gm:newEval", this.onNewEval);
    window.removeEventListener("keydown", this.onKey);
  }
  render(_, { route, newEval }) {
    const snapshot = !!window.__SNAPSHOT__;
    const Page = PAGES[route.name];
    return html`<div>
      <${Header} route=${route} snapshot=${snapshot}/>
      ${Page ? html`<${Page} route=${route} navigate=${navigate}/>` : html`<${Stub} title=${route.name}/>`}
      ${newEval && html`<${NewEvalModal} onClose=${() => this.setState({ newEval: false })}/>`}
    </div>`;
  }
}

window.gmToast = toast;
render(html`<${App}/>`, document.getElementById("app"));
