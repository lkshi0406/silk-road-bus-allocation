const state = {
  dayIndex: 12,
  hour: 8,
  waitChart: null,
  learningChart: null,
  candidates: [],
};

const dayIndex = document.getElementById("dayIndex");
const dayLabel = document.getElementById("dayLabel");
const hourSelect = document.getElementById("hourSelect");
const refreshBtn = document.getElementById("refreshBtn");
const approveBtn = document.getElementById("approveBtn");
const overrideBtn = document.getElementById("overrideBtn");
const overrideSelect = document.getElementById("overrideSelect");
const overrideReason = document.getElementById("overrideReason");
const smsBtn = document.getElementById("smsBtn");
const smsPhone = document.getElementById("smsPhone");
const smsMessage = document.getElementById("smsMessage");
const toast = document.getElementById("toast");

function notify(msg, isError = false) {
  toast.style.color = isError ? "#ff96a7" : "#9df9be";
  toast.textContent = msg;
}

async function apiGet(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return await res.json();
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} failed: ${text}`);
  }
  return await res.json();
}

function renderMap(mapData) {
  const svg = document.getElementById("corridorMap");
  svg.innerHTML = "";

  mapData.heat.forEach((h) => {
    const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    c.setAttribute("cx", h.x);
    c.setAttribute("cy", h.y);
    c.setAttribute("r", h.r);
    c.setAttribute("fill", "rgba(255,95,122,0.28)");
    svg.appendChild(c);
  });

  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", mapData.corridor.map((p) => `${p.x},${p.y}`).join(" "));
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#45f2ff");
  line.setAttribute("stroke-width", "2.8");
  svg.appendChild(line);

  mapData.buses.forEach((b) => {
    const bus = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    bus.setAttribute("cx", b.x);
    bus.setAttribute("cy", b.y);
    bus.setAttribute("r", 1.8);
    bus.setAttribute("fill", b.color);
    svg.appendChild(bus);
  });
}

function updateWaitChart(series) {
  const ctx = document.getElementById("waitChart");
  if (state.waitChart) state.waitChart.destroy();
  state.waitChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: series.hours,
      datasets: [
        { label: "Baseline", data: series.baseline, borderColor: "#66b8ff", tension: 0.25 },
        { label: "BusIQ", data: series.busiq, borderColor: "#61ff8f", tension: 0.25 },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#dce8ff" } } },
      scales: {
        x: { ticks: { color: "#b9cae8" }, grid: { color: "rgba(148,197,255,0.12)" } },
        y: { ticks: { color: "#b9cae8" }, grid: { color: "rgba(148,197,255,0.12)" } },
      },
    },
  });
}

function updateLearningChart(metrics) {
  const ctx = document.getElementById("learningChart");
  if (state.learningChart) state.learningChart.destroy();
  state.learningChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: metrics.rolling_mae.map((x) => x.date),
      datasets: [{ label: "MAE", data: metrics.rolling_mae.map((x) => x.mae), borderColor: "#ffba5c", tension: 0.25 }],
    },
    options: {
      plugins: { legend: { labels: { color: "#dce8ff" } } },
      scales: {
        x: { ticks: { color: "#b9cae8", maxTicksLimit: 5 }, grid: { color: "rgba(148,197,255,0.12)" } },
        y: { ticks: { color: "#b9cae8" }, grid: { color: "rgba(148,197,255,0.12)" } },
      },
    },
  });
}

function renderLogs(id, rows, pick) {
  const tbody = document.querySelector(`#${id} tbody`);
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    const vals = pick(r);
    vals.forEach((v) => {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function renderDispatch(dispatch) {
  const box = document.getElementById("dispatchCard");
  const rec = dispatch.recommended;
  box.innerHTML = `
    <div><strong>Bus:</strong> ${rec.bus_id}</div>
    <div><strong>ETA:</strong> ${rec.eta_min} min</div>
    <div><strong>Capacity:</strong> ${rec.capacity}</div>
    <div><strong>Utilization:</strong> ${rec.utilization_pct}%</div>
    <div><strong>Shift Remaining:</strong> ${Math.floor(rec.shift_remaining_min / 60)}h ${String(rec.shift_remaining_min % 60).padStart(2, "0")}m</div>
    <div><strong>Expected Wait After Dispatch:</strong> ${rec.est_wait_after_dispatch} min</div>
  `;

  state.candidates = dispatch.candidates;
  overrideSelect.innerHTML = "";
  dispatch.candidates.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.bus_id;
    opt.textContent = `${c.bus_id} (score ${c.score})`;
    overrideSelect.appendChild(opt);
  });
}

function renderForecast(data) {
  document.getElementById("scopeText").textContent = `${data.scope.corridor} | Route ${data.scope.route} | ${data.scope.day} ${data.scope.hour}`;
  document.getElementById("acc").textContent = data.status.model_accuracy;
  document.getElementById("predictionValue").textContent = `${Math.round(data.forecast.prediction)} passengers`;
  document.getElementById("predictionBand").textContent = `Band: ${Math.round(data.forecast.lower)} - ${Math.round(data.forecast.upper)} | Trigger: ${data.forecast.trigger ? "Fired" : "Not fired"}`;
  document.getElementById("rainTag").textContent = `Rain +${data.forecast.rain_mm}mm`;
  document.getElementById("metroTag").textContent = `Metro Delay +${data.forecast.metro_delay_min}m`;
  document.getElementById("odTag").textContent = `OD ${Math.round(data.forecast.od_index)}`;

  const featureList = document.getElementById("featureList");
  featureList.innerHTML = "";
  data.features.forEach((f) => {
    const li = document.createElement("li");
    li.textContent = `${f.name}: ${f.value > 0 ? "+" : ""}${f.value}`;
    featureList.appendChild(li);
  });

  smsMessage.value = `BusIQ alert: ${data.dispatch.recommended.bus_id} dispatched to Silk Board. Forecast ${Math.round(data.forecast.prediction)} passengers in 20 min.`;
}

async function loadState() {
  try {
    const data = await apiGet(`/api/state?day_index=${state.dayIndex}&hour=${state.hour}`);
    renderForecast(data);
    renderDispatch(data.dispatch);
    renderMap(data.map);
    updateWaitChart(data.series);
    updateLearningChart(data.metrics);
    renderLogs("overrideTable", data.override_log, (r) => [r.ts, r.operator_action, r.outcome]);
    renderLogs("smsTable", data.sms_log, (r) => [r.ts, r.phone, r.status]);
    notify("Dashboard refreshed.");
  } catch (err) {
    notify(err.message, true);
  }
}

refreshBtn.addEventListener("click", loadState);
dayIndex.addEventListener("input", () => {
  state.dayIndex = Number(dayIndex.value);
  dayLabel.textContent = String(state.dayIndex);
});
hourSelect.addEventListener("change", () => {
  state.hour = Number(hourSelect.value);
});

approveBtn.addEventListener("click", async () => {
  try {
    const res = await apiPost("/api/approve", { day_index: state.dayIndex, hour: state.hour });
    renderLogs("overrideTable", res.override_log, (r) => [r.ts, r.operator_action, r.outcome]);
    notify(res.message);
  } catch (err) {
    notify(err.message, true);
  }
});

overrideBtn.addEventListener("click", async () => {
  try {
    const res = await apiPost("/api/override", {
      day_index: state.dayIndex,
      hour: state.hour,
      bus_id: overrideSelect.value,
      reason: overrideReason.value,
    });
    renderLogs("overrideTable", res.override_log, (r) => [r.ts, r.operator_action, r.outcome]);
    notify(`${res.message} (${res.outcome})`);
  } catch (err) {
    notify(err.message, true);
  }
});

smsBtn.addEventListener("click", async () => {
  try {
    const res = await apiPost("/api/sms", { phone: smsPhone.value, message: smsMessage.value });
    renderLogs("smsTable", res.sms_log, (r) => [r.ts, r.phone, r.status]);
    notify(res.message);
  } catch (err) {
    notify(err.message, true);
  }
});

loadState();
