// TradingResearch dashboard — page logic.
// Everything here is presentation: it asks the Flask API for results and
// draws them. No trading maths lives in this file.

const REASON_COLORS = {
  stop_loss: "#ef4444",
  take_profit: "#22c55e",
  time_exit: "#94a3b8",
  break_even: "#eab308",
  trailing_stop: "#38bdf8",
  exit_signal: "#a78bfa",
  end_of_data: "#64748b",
};

const $ = (id) => document.getElementById(id);
let PAIRS = [];
let STRATEGIES = [];
let STRATEGY_ERRORS = [];
let lastSeries = null;

// Escape anything before it goes into innerHTML. Today these strings come
// from local files you write and from the engine, so it's not a live attack
// vector — but the Tracker page will soon show broker data, and a stray
// "<" in a note shouldn't be able to break (or rewrite) the page.
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// One fetch path that always yields a useful Error instead of a silent blank
// page or a cryptic JSON.parse failure.
async function fetchJSON(url, opts) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch {
    throw new Error(`Couldn't reach ${url} — is the server running?`);
  }
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`${url} returned a non-JSON response (HTTP ${res.status}).`);
  }
  if (!res.ok) throw new Error(data.error || `${url} failed (HTTP ${res.status}).`);
  return data;
}

/* ---------- sidebar ---------- */
$("toggle").addEventListener("click", () => {
  const collapsed = document.body.classList.toggle("collapsed");
  localStorage.setItem("sidebar-collapsed", collapsed ? "1" : "0");
  if (lastSeries) renderEquity(lastSeries);
});

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((i) => i.classList.remove("active"));
    item.classList.add("active");
    setPage(item.dataset.page);
  });
});

const PAGE_META = {
  backtest: ["Backtest", "Test strategies against historical price data."],
  compare: ["Compare", "Strategies side by side."],
  tracker: ["Tracker", "Your live trades, measured like the backtest."],
  settings: ["Settings", "Preferences and defaults."],
};

// The controls panel belongs to the Backtest tab, so the body carries the
// current page and the CSS decides what shows. Every other tab is a blank
// page with its name on it until we build it.
function setPage(page) {
  const isBacktest = page === "backtest";
  document.body.classList.toggle("page-backtest", isBacktest);
  $("page-backtest").hidden = !isBacktest;
  $("page-blank").hidden = isBacktest;

  const [title, sub] = PAGE_META[page] || PAGE_META.backtest;
  $("page-title").textContent = title;
  $("page-sub").textContent = sub;

  if (isBacktest) {
    // the chart couldn't measure itself while the page was hidden
    if (lastSeries) renderEquity(lastSeries);
  } else {
    $("blank-label").textContent = `${title} — nothing here yet.`;
  }
}
setPage("backtest");

/* ---------- controls ---------- */
$("use-defaults").addEventListener("change", (e) => {
  $("sl").disabled = e.target.checked;
  $("tp").disabled = e.target.checked;
});

// Whether the app is usable at all — false when no strategy files loaded, so
// the Run button's finally clause can't wrongly re-enable it.
let ready = false;

function refreshRunButton() {
  $("run").disabled = !ready || selectedPairs().length === 0;
}

/* The strategy picker and its knobs are built from what the backend
   declares — dropping a file in /strategies is enough to make it appear
   here, with its own parameters, without touching this file. */
async function loadStrategies() {
  const data = await fetchJSON("/api/strategies");
  STRATEGIES = data.strategies || [];
  STRATEGY_ERRORS = data.errors || [];

  $("strategy").innerHTML = STRATEGIES.map(
    (s) => `<option value="${esc(s.name)}">${esc(s.label)}</option>`).join("");
  $("strategy").addEventListener("change", renderStrategyParams);
  renderStrategyParams();

  // A strategy file that won't import is worth saying out loud — otherwise
  // it just isn't in the list and you're left wondering why.
  const box = $("strategy-errors");
  if (STRATEGY_ERRORS.length) {
    box.innerHTML = STRATEGY_ERRORS.map(
      (e) => `<div><strong>${esc(e.name)}.py</strong> failed to load — ${esc(e.error)}</div>`).join("");
    box.hidden = false;
  } else {
    box.hidden = true;
  }

  if (!STRATEGIES.length) {
    $("strategy-desc").textContent = "No strategy files found in /strategies.";
  }
}

function currentStrategy() {
  return STRATEGIES.find((s) => s.name === $("strategy").value) || STRATEGIES[0];
}

function renderStrategyParams() {
  const s = currentStrategy();
  if (!s) return;
  $("strategy-desc").textContent = s.description || "";
  $("strategy-params").innerHTML = s.params.map((p) => `
    <label class="field">
      <span>${esc(p.label)}</span>
      <input type="number" class="sparam" data-name="${esc(p.name)}"
             value="${esc(p.default)}" min="${esc(p.min ?? "")}" max="${esc(p.max ?? "")}"
             step="${esc(p.step ?? 1)}">
    </label>`).join("");
}

const strategyParams = () => Object.fromEntries(
  [...document.querySelectorAll(".sparam")].map((el) => [el.dataset.name, Number(el.value)]));

async function loadPairs() {
  PAIRS = await fetchJSON("/api/pairs");
  $("pair-list").innerHTML = PAIRS.map((p) => `
    <div class="pair-item on" data-pair="${esc(p.name)}" style="--pc:${esc(p.color)}">
      <span class="pair-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"
             stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
      </span>
      <span class="pair-dot"></span>
      <span>${esc(p.name)}</span>
    </div>`).join("");

  document.querySelectorAll(".pair-item").forEach((el) => {
    el.addEventListener("click", () => {
      el.classList.toggle("on");
      refreshRunButton();
    });
  });
}

const selectedPairs = () =>
  [...document.querySelectorAll(".pair-item.on")].map((el) => el.dataset.pair);

/* ---------- startup ---------- */
async function init() {
  try {
    await Promise.all([loadStrategies(), loadPairs()]);
    ready = STRATEGIES.length > 0;
  } catch (err) {
    // A failed load used to leave the sidebar mysteriously empty. Say so.
    $("error-msg").textContent = err.message;
    show("error");
    ready = false;
  }
  refreshRunButton();
}

/* ---------- run ---------- */
$("run").addEventListener("click", run);

async function run() {
  const pairs = selectedPairs();
  if (!pairs.length || !ready) return;

  show("loading");
  $("run").disabled = true;

  const useDefaults = $("use-defaults").checked;
  const body = {
    pairs,
    strategy: $("strategy").value,
    params: strategyParams(),
    max_hold_days: Number($("max-hold").value),
    sl_pips: useDefaults ? null : Number($("sl").value),
    tp_pips: useDefaults ? null : Number($("tp").value),
  };

  try {
    const data = await fetchJSON("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    // Show first, then draw: the chart measures its container, and a hidden
    // container measures zero.
    show("results");
    render(data);
  } catch (err) {
    $("error-msg").textContent = err.message;
    show("error");
  } finally {
    // Only re-enable if the app is actually usable — never resurrect a
    // button that was disabled because there are no strategies.
    refreshRunButton();
  }
}

function show(which) {
  ["empty", "loading", "error", "results"].forEach((id) => {
    $(id).hidden = id !== which;
  });
}

/* ---------- render ---------- */
function render(data) {
  const c = data.combined;

  // A win rate is only good or bad relative to the win rate this strategy
  // needs to break even — which depends on how big its wins are versus its
  // losses. So we colour it against that, and show the bar it has to clear.
  const wr = c.win_rate ?? 0;
  const be = c.breakeven_win_rate;
  const wrEl = $("c-winrate");
  wrEl.textContent = `${wr.toFixed(1)}%`;
  if (be == null) {
    wrEl.className = "card-value";
    $("c-winrate-note").textContent = "";
  } else {
    const edge = wr - be;
    wrEl.className = "card-value " +
      (edge > 0.5 ? "v-good" : edge < -0.5 ? "v-bad" : "v-warn");
    $("c-winrate-note").textContent = `needs ${be.toFixed(1)}% to break even`;
  }

  // Expectancy: green when it makes money, red when it loses. This and the
  // win-rate colour are two views of the same truth, so they always agree.
  const exp = c.expectancy_r ?? 0;
  const expEl = $("c-expectancy");
  expEl.textContent = `${exp > 0 ? "+" : ""}${exp.toFixed(3)} R`;
  expEl.className = "card-value " +
    (exp > 0.005 ? "v-good" : exp < -0.005 ? "v-bad" : "v-warn");

  // Drawdown gets no colour: every strategy has one, and there's no honest
  // threshold that says which number is "bad" — it's context, not a verdict.
  $("c-drawdown").textContent = `${(c.max_drawdown_r ?? 0).toFixed(2)} R`;

  lastSeries = data.series;
  renderLegend(data.series);
  renderEquity(data.series);
  renderTrades(data.trades);
  renderExit(c.exit_reasons || {});
  renderMini(c);
}

function renderLegend(series) {
  $("legend").innerHTML = series.map((s) => `
    <span class="legend-item">
      <span class="legend-swatch" style="background:${esc(s.color)}"></span>${esc(s.pair)}
    </span>`).join("");
}

/* Hand-drawn SVG so the chart is exactly as clean as we want it — no
   charting library, no CDN, nothing to break offline. */
function renderEquity(series) {
  const wrap = $("equity-wrap");
  const width = wrap.clientWidth || 760;
  const height = 320;
  const pad = { l: 46, r: 14, t: 12, b: 28 };

  const live = series.filter((s) => s.points.length);
  if (!live.length) { wrap.innerHTML = ""; return; }

  const maxLen = Math.max(...live.map((s) => s.points.length));
  const vals = live.flatMap((s) => s.points);
  let lo = Math.min(0, ...vals), hi = Math.max(0, ...vals);
  if (lo === hi) { lo -= 1; hi += 1; }
  const room = (hi - lo) * 0.08;
  lo -= room; hi += room;

  const X = (i) => pad.l + (i / Math.max(1, maxLen - 1)) * (width - pad.l - pad.r);
  const Y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (height - pad.t - pad.b);

  const ticks = niceTicks(lo, hi, 5);
  const grid = ticks.map((t) => `
    <line x1="${pad.l}" y1="${Y(t).toFixed(1)}" x2="${width - pad.r}" y2="${Y(t).toFixed(1)}"
          stroke="#262a33" stroke-width="1"/>
    <text x="${pad.l - 10}" y="${(Y(t) + 3.5).toFixed(1)}" fill="#6b7280" font-size="11"
          text-anchor="end">${fmtTick(t)}</text>`).join("");

  const zero = (lo <= 0 && hi >= 0) ? `
    <line x1="${pad.l}" y1="${Y(0).toFixed(1)}" x2="${width - pad.r}" y2="${Y(0).toFixed(1)}"
          stroke="#4b5563" stroke-width="1" stroke-dasharray="4 4"/>` : "";

  // x-axis: trade number, a handful of evenly-spaced ticks
  const xStep = Math.max(1, Math.round(maxLen / 6));
  let xLabels = "";
  for (let i = 0; i < maxLen; i += xStep) {
    xLabels += `<text x="${X(i).toFixed(1)}" y="${height - 8}" fill="#6b7280" font-size="11"
                  text-anchor="middle">${i + 1}</text>`;
  }

  const lines = live.map((s) => {
    const d = s.points.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
    return `<path d="${d}" fill="none" stroke="${esc(s.color)}" stroke-width="1.8"
                  stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");

  wrap.innerHTML = `<svg viewBox="0 0 ${width} ${height}" height="${height}">
    ${grid}${zero}${lines}${xLabels}
  </svg>`;
}

function niceTicks(min, max, count) {
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(Math.abs(raw) || 1)));
  const norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(v);
  return out;
}
const fmtTick = (t) => (Math.abs(t) < 1e-9 ? "0" : t.toFixed(Math.abs(t) < 10 ? 1 : 0));

function renderTrades(trades) {
  $("t-total").textContent = trades.length;
  const colors = Object.fromEntries(PAIRS.map((p) => [p.name, p.color]));
  $("trades-scroll").innerHTML = trades.map((t) => {
    const r = t.r_multiple ?? 0;
    // exit_reason is always set by the engine today, but guarding it means an
    // API change (or a live trade with no reason) can't blank the whole list.
    const reason = (t.exit_reason || "—").replace(/_/g, " ");
    return `<div class="trade-row">
      <span class="trade-date">${esc(t.entry_date)}</span>
      <span class="trade-pair">
        <span class="pair-dot" style="--pc:${esc(colors[t.pair] || "#888")}"></span>${esc(t.pair)}
      </span>
      <span class="trade-reason">${esc(reason)}</span>
      <span class="trade-r ${r >= 0 ? "v-good" : "v-bad"}">${r >= 0 ? "+" : ""}${r.toFixed(2)}R</span>
    </div>`;
  }).join("");
}

function renderExit(reasons) {
  const entries = Object.entries(reasons).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;
  $("exit-chart").innerHTML = entries.map(([name, n]) => `
    <div class="exit-row">
      <span class="exit-name">${esc(name.replace(/_/g, " "))}</span>
      <span class="exit-bar-bg">
        <span class="exit-bar" style="width:${(n / total * 100).toFixed(1)}%;
              background:${REASON_COLORS[name] || "#64748b"}; display:block"></span>
      </span>
      <span class="exit-count">${n}</span>
    </div>`).join("");
}

// Only what earns its place — the rest of the stats stay out of the way.
// Wins/losses are in R, not price units: averaging gold's dollars with
// EURUSD's pips would produce a number that means nothing.
function renderMini(c) {
  const rows = [
    ["Total R", `${c.total_r > 0 ? "+" : ""}${(c.total_r ?? 0).toFixed(2)}`],
    ["Avg win", `+${(c.avg_win_r ?? 0).toFixed(2)}R`],
    ["Avg loss", `${(c.avg_loss_r ?? 0).toFixed(2)}R`],
    ["Ambiguous", c.ambiguous_exits ?? 0],
  ];
  $("mini-stats").innerHTML = rows.map(([k, v]) => `
    <div class="mini-stat"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join("");
}

/* redraw the chart when the window (and so the SVG width) changes */
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (lastSeries) renderEquity(lastSeries); }, 120);
});

init();
