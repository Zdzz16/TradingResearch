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
let lastSeries = null;

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

// The controls panel belongs to the Backtest tab, so the body carries the
// current page and the CSS decides what shows.
function setPage(page) {
  document.body.classList.toggle("page-backtest", page === "backtest");
  const titles = {
    backtest: ["Backtest", "Historical simulation across FX & gold, net of spread."],
    compare: ["Compare", "Coming next — pairs side by side."],
    tracker: ["Tracker", "Coming next — your live trades, same analytics as the backtest."],
    settings: ["Settings", "Coming next."],
  };
  const [title, sub] = titles[page] || titles.backtest;
  $("page-title").textContent = title;
  $("page-sub").textContent = sub;
}
setPage("backtest");

/* ---------- controls ---------- */
$("use-defaults").addEventListener("change", (e) => {
  $("sl").disabled = e.target.checked;
  $("tp").disabled = e.target.checked;
});

/* The strategy picker and its knobs are built from what the backend
   declares — adding a strategy in core/strategies.py is enough to make it
   appear here, with its own parameters, without touching this file. */
async function loadStrategies() {
  STRATEGIES = await (await fetch("/api/strategies")).json();
  $("strategy").innerHTML = STRATEGIES.map(
    (s) => `<option value="${s.name}">${s.label}</option>`).join("");
  $("strategy").addEventListener("change", renderStrategyParams);
  renderStrategyParams();
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
      <span>${p.label}</span>
      <input type="number" class="sparam" data-name="${p.name}"
             value="${p.default}" min="${p.min ?? ""}" max="${p.max ?? ""}"
             step="${p.step ?? 1}">
    </label>`).join("");
}

const strategyParams = () => Object.fromEntries(
  [...document.querySelectorAll(".sparam")].map((el) => [el.dataset.name, Number(el.value)]));

async function loadPairs() {
  PAIRS = await (await fetch("/api/pairs")).json();
  $("pair-list").innerHTML = PAIRS.map((p) => `
    <div class="pair-item on" data-pair="${p.name}" style="--pc:${p.color}">
      <span class="pair-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"
             stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
      </span>
      <span class="pair-dot"></span>
      <span>${p.name}</span>
    </div>`).join("");

  document.querySelectorAll(".pair-item").forEach((el) => {
    el.addEventListener("click", () => {
      el.classList.toggle("on");
      $("run").disabled = selectedPairs().length === 0;
    });
  });
}

const selectedPairs = () =>
  [...document.querySelectorAll(".pair-item.on")].map((el) => el.dataset.pair);

/* ---------- run ---------- */
$("run").addEventListener("click", run);

async function run() {
  const pairs = selectedPairs();
  if (!pairs.length) return;

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
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Backtest failed.");
    // Show first, then draw: the chart measures its container, and a
    // hidden container measures zero.
    show("results");
    render(data);
  } catch (err) {
    $("error-msg").textContent = err.message;
    show("error");
  } finally {
    $("run").disabled = false;
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
      <span class="legend-swatch" style="background:${s.color}"></span>${s.pair}
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

  const xStep = Math.max(1, Math.round(maxLen / 6));
  let xLabels = "";
  for (let i = 0; i < maxLen; i += xStep) {
    xLabels += `<text x="${X(i).toFixed(1)}" y="${height - 8}" fill="#6b7280" font-size="11"
                  text-anchor="middle">${i + 1}</text>`;
  }

  const lines = live.map((s) => {
    const d = s.points.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="1.8"
                  stroke-linejoin="round" stroke-linecap="round"/>`;
  }).join("");

  wrap.innerHTML = `<svg viewBox="0 0 ${width} ${height}" height="${height}">
    ${grid}${zero}${lines}
    <text x="${pad.l}" y="${height - 8}" fill="#6b7280" font-size="11"
          text-anchor="middle" opacity="0"></text>
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
    return `<div class="trade-row">
      <span class="trade-date">${t.entry_date}</span>
      <span class="trade-pair">
        <span class="pair-dot" style="--pc:${colors[t.pair] || "#888"}"></span>${t.pair}
      </span>
      <span class="trade-reason">${t.exit_reason.replace(/_/g, " ")}</span>
      <span class="trade-r ${r >= 0 ? "v-good" : "v-bad"}">${r >= 0 ? "+" : ""}${r.toFixed(2)}R</span>
    </div>`;
  }).join("");
}

function renderExit(reasons) {
  const entries = Object.entries(reasons).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;
  $("exit-chart").innerHTML = entries.map(([name, n]) => `
    <div class="exit-row">
      <span class="exit-name">${name.replace(/_/g, " ")}</span>
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
    <div class="mini-stat"><span>${k}</span><strong>${v}</strong></div>`).join("");
}

/* redraw the chart when the window (and so the SVG width) changes */
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (lastSeries) renderEquity(lastSeries); }, 120);
});

loadStrategies();
loadPairs();
