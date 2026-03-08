async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Unable to load ${path}`);
  return res.json();
}

function tag(action) {
  const a = (action || "hold").toLowerCase();
  const cls = a === "buy" ? "buy" : a === "sell" ? "sell" : "hold";
  return `<span class="tag ${cls}">${a.toUpperCase()}</span>`;
}

function renderMetrics(data) {
  const stocks = data.stocks || {};
  const entries = Object.entries(stocks);
  document.getElementById("metric-tickers").textContent = entries.length;
}

function renderTickerTable(data) {
  const tbody = document.getElementById("tickerBody");
  tbody.innerHTML = "";
  const entries = Object.entries(data.stocks || {});
  const holdings = data.holdings || {};
  entries.forEach(([symbol, stock]) => {
    const ai = stock.ai_view || {};
    const holding = holdings[symbol] || {};
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${symbol}</td>
      <td>${tag(ai.action_bias)}</td>
      <td>${String(ai.sentiment || "neutral").toUpperCase()}</td>
      <td>${ai.confidence ?? 0}%</td>
      <td>${ai.current_price != null ? `$${ai.current_price}` : "--"}</td>
      <td>${holding.shares ?? 0}</td>
      <td>${holding.position_value != null ? `$${holding.position_value}` : "$0"}</td>
      <td>${ai.price_change_1d_pct ?? 0}%</td>
      <td>${String(ai.portfolio_action_plan || "hold").toUpperCase()}</td>
      <td class="summary">${ai.portfolio_justification || ""}</td>
      <td class="summary">${ai.summary || ""}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderErrors(data) {
  const list = document.getElementById("errorList");
  list.innerHTML = "";
  const errors = data.errors || {};
  const keys = Object.keys(errors);
  if (!keys.length) {
    const li = document.createElement("li");
    li.textContent = "No errors.";
    list.appendChild(li);
    return;
  }
  keys.forEach((symbol) => {
    const li = document.createElement("li");
    li.textContent = `${symbol}: ${errors[symbol]}`;
    list.appendChild(li);
  });
}

function renderOpportunities(opData) {
  const buyBody = document.getElementById("oppsBody");
  const shortBody = document.getElementById("shortOppsBody");
  buyBody.innerHTML = "";
  shortBody.innerHTML = "";
  const buyRecs = opData?.buy_ideas || [];
  const shortRecs = opData?.short_ideas || [];
  document.getElementById("metric-opps-buy").textContent = buyRecs.length;
  document.getElementById("metric-opps-short").textContent = shortRecs.length;

  if (!buyRecs.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5">No buy opportunities generated in this run.</td>`;
    buyBody.appendChild(tr);
  } else {
    buyRecs.forEach((rec) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${rec.symbol || ""}</td>
        <td>${tag("buy")}</td>
        <td>${rec.confidence ?? 0}%</td>
        <td>${rec.current_price != null ? `$${rec.current_price}` : "--"}</td>
        <td class="summary">${rec.reason || ""}</td>
      `;
      buyBody.appendChild(tr);
    });
  }

  if (!shortRecs.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5">No short opportunities generated in this run.</td>`;
    shortBody.appendChild(tr);
  } else {
    shortRecs.forEach((rec) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${rec.symbol || ""}</td>
        <td>${tag("sell")}</td>
        <td>${rec.confidence ?? 0}%</td>
        <td>${rec.current_price != null ? `$${rec.current_price}` : "--"}</td>
        <td class="summary">${rec.reason || ""}</td>
      `;
      shortBody.appendChild(tr);
    });
  }
}

function renderQuickSummary(data, opData) {
  const root = document.getElementById("quickSummary");
  const entries = Object.entries(data.stocks || {});
  const grouped = { add: [], hold: [], reduce: [], exit: [] };
  entries.forEach(([symbol, stock]) => {
    const ai = stock.ai_view || {};
    const plan = String(ai.portfolio_action_plan || "hold").toLowerCase();
    if (grouped[plan]) grouped[plan].push(symbol);
    else grouped.hold.push(symbol);
  });

  const asPills = (symbols, cls) =>
    symbols.length
      ? symbols.map((s) => `<span class="summary-pill ${cls}">${s}</span>`).join("")
      : '<span class="summary-pill none">None</span>';

  const buy = (opData?.buy_ideas || []).map((r) => r.symbol).filter(Boolean);
  const short = (opData?.short_ideas || []).map((r) => r.symbol).filter(Boolean);

  root.innerHTML = `
    <div class="summary-row">
      <div class="label">ADD to Holdings</div>
      <div class="value">${asPills(grouped.add, "add")}</div>
    </div>
    <div class="summary-row">
      <div class="label">REDUCE Holdings</div>
      <div class="value">${asPills(grouped.reduce, "reduce")}</div>
    </div>
    <div class="summary-row">
      <div class="label">EXIT Holdings</div>
      <div class="value">${asPills(grouped.exit, "exit")}</div>
    </div>
    <div class="summary-row">
      <div class="label">HOLD As-Is</div>
      <div class="value">${asPills(grouped.hold, "hold")}</div>
    </div>
    <div class="summary-row">
      <div class="label">New Buy Ideas</div>
      <div class="value">${asPills(buy, "buy")}</div>
    </div>
    <div class="summary-row">
      <div class="label">New Short Ideas</div>
      <div class="value">${asPills(short, "short")}</div>
    </div>
  `;
}

async function init() {
  try {
    const [data, opData] = await Promise.all([
      loadJson("/data/agent_market_view.json"),
      loadJson("/data/opportunity_recommendations.json").catch(() => ({ recommendations: [] })),
    ]);
    const gen = data.generated_at ? data.generated_at.replace("T", " ").slice(0, 19) : "unknown";
    const genOpp = opData.generated_at ? opData.generated_at.replace("T", " ").slice(0, 19) : "n/a";
    document.getElementById("meta").textContent = `Generated: ${gen} | Holdings source: ${data.holdings_source || "unknown"} | Opportunities: ${genOpp}`;
    renderMetrics(data);
    renderQuickSummary(data, opData);
    renderTickerTable(data);
    renderErrors(data);
    renderOpportunities(opData);
  } catch (e) {
    document.querySelector(".wrap").innerHTML = `<h1>Dashboard Error</h1><p>${e.message}</p>`;
  }
}

init();
