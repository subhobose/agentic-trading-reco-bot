const fmtMoney = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const fmtPct = (n) => `${(n * 100).toFixed(1)}%`;

async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

function riskClass(level) {
  if (level === "high") return "sell";
  if (level === "moderate") return "hold";
  return "buy";
}

function setHeader(recData, riskData, sentData) {
  const date = (recData.generated_at || "").slice(0, 10) || "Unknown Date";
  document.getElementById("report-date").textContent = `Report ${date}`;
  const pill = document.getElementById("risk-pill");
  const level = riskData.risk_level || "unknown";
  pill.textContent = `Risk: ${level.toUpperCase()}`;
  pill.classList.add("tag", riskClass(level));
  document.getElementById("metric-model").textContent = sentData.model || "--";
}

function setMetrics(recData, riskData) {
  const recs = recData.recommendations || {};
  const values = riskData.portfolio_values || {};
  const totalValue = Object.values(values).reduce((a, b) => a + b, 0);

  document.getElementById("metric-positions").textContent = Object.keys(recs).length;
  document.getElementById("metric-value").textContent = totalValue ? fmtMoney.format(totalValue) : "--";
  document.getElementById("metric-risk").textContent = `${riskData.risk_score ?? "--"}/100`;
}

function setRecommendationTable(recData) {
  const body = document.getElementById("recommendation-body");
  body.innerHTML = "";
  const recs = recData.recommendations || {};
  Object.entries(recs).forEach(([symbol, data]) => {
    const action = (data.decision || "HOLD").toLowerCase();
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${symbol}</td>
      <td><span class="tag ${action}">${(data.decision || "HOLD").toUpperCase()}</span></td>
      <td>${data.confidence ?? "--"}%</td>
      <td>${typeof data.position_weight === "number" ? fmtPct(data.position_weight) : "--"}</td>
    `;
    body.appendChild(tr);
  });
}

function renderAllocation(riskData) {
  const values = riskData.portfolio_values || {};
  new Chart(document.getElementById("allocationChart"), {
    type: "doughnut",
    data: {
      labels: Object.keys(values),
      datasets: [
        {
          data: Object.values(values),
          backgroundColor: ["#2c78ff", "#ff5f7f", "#1ff1a2", "#ffc857", "#88a4ff"],
        },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#dce7ff" } } },
    },
  });
}

function renderRsi(techData) {
  const map = techData.analysis || {};
  const labels = Object.keys(map);
  const data = labels.map((s) => map[s]?.rsi ?? 0);
  new Chart(document.getElementById("rsiChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "RSI",
          data,
          backgroundColor: "#2c78ff",
          borderRadius: 8,
        },
      ],
    },
    options: {
      scales: {
        y: { min: 0, max: 100, ticks: { color: "#dce7ff" }, grid: { color: "rgba(255,255,255,0.08)" } },
        x: { ticks: { color: "#dce7ff" }, grid: { display: false } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

function renderSentiment(sentData) {
  const map = sentData.analysis || {};
  const labels = Object.keys(map);
  const data = labels.map((s) => map[s]?.confidence ?? 0);
  const colors = labels.map((s) => {
    const sentiment = (map[s]?.sentiment || "neutral").toLowerCase();
    if (sentiment === "bullish") return "#1ff1a2";
    if (sentiment === "bearish") return "#ff5f7f";
    return "#ffc857";
  });
  new Chart(document.getElementById("sentimentChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Sentiment Confidence",
          data,
          backgroundColor: colors,
          borderRadius: 8,
        },
      ],
    },
    options: {
      scales: {
        y: { min: 0, max: 100, ticks: { color: "#dce7ff" }, grid: { color: "rgba(255,255,255,0.08)" } },
        x: { ticks: { color: "#dce7ff" }, grid: { display: false } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

async function init() {
  try {
    const [recData, riskData, techData, sentData] = await Promise.all([
      getJson("/data/recommendations.json"),
      getJson("/data/risk_report.json"),
      getJson("/data/technical_analysis.json"),
      getJson("/data/sentiment_analysis.json"),
    ]);

    setHeader(recData, riskData, sentData);
    setMetrics(recData, riskData);
    setRecommendationTable(recData);
    renderAllocation(riskData);
    renderRsi(techData);
    renderSentiment(sentData);
  } catch (err) {
    document.body.innerHTML = `<main class="container"><h1>Dashboard Error</h1><p>${err.message}</p></main>`;
  }
}

init();

