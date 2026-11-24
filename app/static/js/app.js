/* Painel da Estação Meteorológica e Ambiental — consome a API REST e atualiza sem recarregar a página. */
(() => {
  "use strict";

  const METRICS = {
    temperature_c: { label: "Temperatura do ar", unit: "°C", digits: 1, color: "#f0801f" },
    humidity_pct: { label: "Umidade relativa", unit: "%", digits: 0, color: "#3f86e6" },
    pressure_hpa: { label: "Pressão atmosférica", unit: "hPa", digits: 1, color: "#8a68d8" },
    mq135_raw: { label: "Sinal do sensor de gases", unit: "pontos", digits: 0, color: "#35a56a" },
    ldr_raw: { label: "Luminosidade relativa", unit: "%", digits: 0, color: "#e8a60f" },
  };
  const ADC_MAX = 4095;
  const TREND_NOUN = { up: "Subindo", down: "Caindo", flat: "Estável" };
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const state = {
    tz: "America/Sao_Paulo", source: null, userSource: null, period: "24h", status: null, timer: null,
    table: { page: 1, size: 25, sort: "timestamp", order: "desc", period: "24h", start: "", end: "", source: "current" },
    charts: {},
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  /* ---------- formatação (pt-BR) ---------- */
  const num = (v, d = 0) => v == null ? null : new Intl.NumberFormat("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
  const dtf = (opts) => new Intl.DateTimeFormat("pt-BR", { timeZone: state.tz, ...opts });
  const fmtDateTime = (iso) => iso ? dtf({ day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso)).replace(",", "") : "—";
  const fmtSeconds = (iso) => iso ? dtf({ day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(iso)).replace(",", "") : "—";
  const ago = (minutes) => minutes == null ? "" : minutes < 1 ? "agora mesmo" : minutes < 60 ? `há ${minutes} min` : minutes < 1440 ? `há ${Math.floor(minutes / 60)} h` : `há ${Math.floor(minutes / 1440)} dia(s)`;
  const ldrPct = (raw) => raw == null ? null : (raw / ADC_MAX) * 100;

  /* ---------- API ---------- */
  async function api(path, params = {}) {
    const url = new URL(path, window.location.origin);
    for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, v);
    let res;
    try { res = await fetch(url, { headers: { Accept: "application/json" } }); }
    catch { throw new Error("Não foi possível conectar ao servidor. Verifique sua internet e tente de novo."); }
    if (!res.ok) {
      let detail = "";
      try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : ""; } catch { /* ignora */ }
      throw new Error(detail || `O servidor respondeu com erro (${res.status}).`);
    }
    return res.json();
  }
  function showError(msg) { const b = $("#error-banner"); b.textContent = msg; b.hidden = !msg; }

  /* ---------- cabeçalho / estado da estação ---------- */
  function renderStatus(st) {
    state.status = st; state.tz = st.timezone; state.source = st.data_source;
    $("#station-name").textContent = st.name;
    $("#station-location").textContent = st.location;
    const chip = $("#conn-chip");
    chip.dataset.state = st.connection;
    $("#conn-text").textContent = { online: "Estação online", offline: "Estação offline", waiting: "Aguardando primeira leitura" }[st.connection];
    const t = $("#last-updated");
    if (st.last_seen) { t.dateTime = st.last_seen; t.textContent = `${fmtDateTime(st.last_seen)} (${ago(st.minutes_since_last)})`; }
    else { t.textContent = "nenhuma leitura recebida"; }
    $("#demo-banner").hidden = !st.is_demo;
    renderMap(st);
    $("#wait-banner").hidden = st.connection !== "waiting";
    const sw = $("#source-switch");
    sw.hidden = st.available_sources.length < 2;
    $$("button", sw).forEach((b) => {
      b.hidden = !st.available_sources.includes(b.dataset.source);
      b.setAttribute("aria-pressed", String(b.dataset.source === state.source));
    });
  }

  /* ---------- cards ---------- */
  function trendHtml(tr, metric) {
    if (!tr) return { dir: "none", icon: "i-none", text: "Tendência indisponível (poucos dados)" };
    const m = METRICS[metric];
    const d = metric === "ldr_raw" ? (tr.delta / ADC_MAX) * 100 : tr.delta;
    const digits = metric === "temperature_c" || metric === "pressure_hpa" ? 1 : 0;
    const h = tr.window_minutes >= 90 ? `${num(tr.window_minutes / 60, 0)} h` : `${tr.window_minutes} min`;
    const sign = d > 0 ? "+" : "";
    const base = TREND_NOUN[tr.direction];
    return { dir: tr.direction, icon: `i-${tr.direction}`, text: tr.direction === "flat" ? `${base} em ${h}` : `${base}: ${sign}${num(d, digits)} ${m.unit} em ${h}` };
  }

  function renderLatest(data) {
    const r = data.reading;
    $$(".metric").forEach((card) => {
      const key = card.dataset.metric, m = METRICS[key];
      card.classList.remove("is-loading");
      const v = r ? r[key] : null;
      const shown = key === "ldr_raw" ? ldrPct(v) : v;
      const valEl = $('[data-role="value"]', card);
      valEl.textContent = shown == null ? "Sem leitura" : num(shown, m.digits);
      if (shown == null) valEl.classList.add("na"); else valEl.classList.remove("na");
      const whenEl = $('[data-role="when"]', card);
      whenEl.textContent = r ? fmtSeconds(r.timestamp) : "—";
      if (r) whenEl.dateTime = r.timestamp;
      const note = $('[data-role="note"]', card);
      if (key === "ldr_raw" && v != null) note.textContent = `Sensor LDR, valor relativo (leitura bruta: ${v})`;
      if (key === "mq135_raw" && shown == null) card.title = "Sem leitura do MQ-135 nesta medição.";
      const tEl = $('[data-role="trend"]', card);
      if (!r || shown == null) { tEl.textContent = ""; return; }
      const t = trendHtml(data.trends[key], key);
      tEl.dataset.dir = t.dir;
      tEl.replaceChildren();
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("aria-hidden", "true");
      const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", `#${t.icon}`);
      svg.appendChild(use);
      tEl.append(svg, document.createTextNode(t.text));
    });
  }

  /* ---------- alertas ---------- */
  function renderAlerts(list) {
    const ul = $("#alerts-list"); ul.replaceChildren();
    const st = state.status;
    if (!list.length) {
      const li = document.createElement("li"); li.className = "alert ok";
      li.innerHTML = '<svg aria-hidden="true"><use href="#i-check"/></svg>';
      const p = document.createElement("p");
      p.textContent = st && st.connection === "online" ? "Nenhum alerta no momento. Todos os valores medidos estão dentro dos limites configurados." : "Nenhum alerta ativo.";
      li.appendChild(p); ul.appendChild(li); return;
    }
    for (const a of list) {
      const li = document.createElement("li"); li.className = "alert"; li.dataset.sev = a.severity;
      li.innerHTML = `<svg aria-hidden="true"><use href="#${a.severity === "atencao" ? "i-warn" : "i-info"}"/></svg>`;
      const div = document.createElement("div");
      const h = document.createElement("h3"); h.textContent = a.title;
      const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = a.basis === "medido" ? "Medido" : "Estimado";
      h.appendChild(tag);
      const p = document.createElement("p"); p.textContent = a.message;
      div.append(h, p); li.appendChild(div); ul.appendChild(li);
    }
  }

  /* ---------- resumo ---------- */
  const PERIOD_LABEL = { "24h": "últimas 24 horas", "7d": "últimos 7 dias", "30d": "últimos 30 dias" };
  function renderStats(s) {
    const box = $("#stats-list"); box.replaceChildren();
    $("#stats-hint").textContent = `Mínimo, média e máximo nas ${PERIOD_LABEL[state.period]}. Registros no período: ${num(s.total_readings)}.`;
    if (!s.total_readings) { const p = document.createElement("p"); p.className = "empty"; p.textContent = "Sem registros neste período."; box.appendChild(p); return; }
    Object.keys(METRICS).forEach((key, i) => {
      const m = METRICS[key], st = s.metrics[key];
      const conv = key === "ldr_raw" ? ldrPct : (x) => x;
      const row = document.createElement("div"); row.className = "stat-row";
      const head = document.createElement("div"); head.className = "stat-head";
      const a = document.createElement("span"); a.textContent = m.label;
      const b = document.createElement("span");
      b.textContent = st.avg == null ? "Sem leitura" : `média ${num(conv(st.avg), m.digits)} ${m.unit}`;
      head.append(a, b);
      const bar = document.createElement("div"); bar.className = `bar bar-${i}`; bar.setAttribute("aria-hidden", "true");
      const fill = document.createElement("i");
      if (st.avg != null && st.max !== st.min) fill.style.width = `${Math.max(4, Math.min(100, ((st.avg - st.min) / (st.max - st.min)) * 100))}%`;
      else fill.style.width = st.avg != null ? "50%" : "0%";
      bar.appendChild(fill);
      const vals = document.createElement("div"); vals.className = "stat-vals";
      vals.textContent = st.avg == null ? "" : `mín. ${num(conv(st.min), m.digits)} · máx. ${num(conv(st.max), m.digits)} ${m.unit}`.replace(" · ", "  |  ");
      row.append(head, bar, vals); box.appendChild(row);
    });
  }

  /* ---------- gráficos ---------- */
  function tickLabel(iso) {
    return state.period === "24h" ? dtf({ hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : dtf({ day: "2-digit", month: "2-digit" }).format(new Date(iso));
  }
  function ensureChart(key, canvas) {
    if (state.charts[key]) return state.charts[key];
    const m = METRICS[key];
    const chart = new Chart(canvas, {
      type: "line",
      data: { labels: [], datasets: [{ data: [], borderColor: m.color, borderWidth: 3, tension: 0.4, pointRadius: 0, pointHoverRadius: 6, pointHoverBackgroundColor: "#fff", pointHoverBorderColor: m.color, pointHoverBorderWidth: 3, fill: true, spanGaps: false,
        backgroundColor: (ctx) => { const { chart: c } = ctx; if (!c.chartArea) return m.color + "22"; const g = c.ctx.createLinearGradient(0, c.chartArea.top, 0, c.chartArea.bottom); g.addColorStop(0, m.color + "40"); g.addColorStop(1, m.color + "00"); return g; } },
        { data: [], borderColor: m.color, borderDash: [8, 6], borderWidth: 2, pointRadius: 0, pointHoverRadius: 0, fill: false, tension: 0, spanGaps: true }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: REDUCED ? false : { duration: 500 },
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 7, maxRotation: 0, color: "#5f6585", callback(v) { return tickLabel(this.getLabelForValue(v)); } }, title: { display: true, text: "Data e hora", color: "#5f6585" } },
          y: { grid: { color: "#ece8f6" }, ticks: { color: "#5f6585" }, title: { display: true, text: key === "ldr_raw" ? "% da escala" : key === "mq135_raw" ? "pontos (0–4095)" : m.unit, color: "#5f6585" } },
        },
        plugins: { legend: { display: false },
          tooltip: { backgroundColor: "#fff", titleColor: "#2b3152", bodyColor: "#2b3152", borderColor: "#e9e5f4", borderWidth: 1, padding: 12, displayColors: false,
            callbacks: { title: (items) => fmtDateTime(items[0].label), label: (ctx) => ctx.datasetIndex === 1 ? `Reta de tendência: ${num(ctx.parsed.y, key === "pressure_hpa" || key === "temperature_c" ? 2 : 1)} ${key === "mq135_raw" ? "pontos" : m.unit}` : `${m.label}: ${num(ctx.parsed.y, key === "pressure_hpa" || key === "temperature_c" ? 1 : 0)} ${key === "mq135_raw" ? "pontos" : m.unit}` } } },
      },
    });
    state.charts[key] = chart; return chart;
  }
  /* Reta de tendência y = a·x + b (mínimos quadrados, calculada no servidor); x = horas desde t0. */
  const signed = (v, d) => `${v < 0 ? "−" : "+"}${num(Math.abs(v), d)}`;
  function renderTrendline(fig, chart, key, nValid, labels, tl) {
    const m = METRICS[key], eq = $('[data-role="trend-eq"]', fig);
    chart.data.datasets[1].data = [];
    eq.replaceChildren();
    if (!nValid) return;
    if (!tl) { eq.textContent = "Reta de tendência indisponível (poucos dados neste período)."; return; }
    const k = key === "ldr_raw" ? 100 / ADC_MAX : 1;           // LDR é exibido em % da escala (transformação linear)
    const a = tl.slope_per_hour * k, b = tl.intercept * k, t0 = new Date(tl.t0).getTime();
    chart.data.datasets[1].data = labels.map((t) => a * ((new Date(t).getTime() - t0) / 3.6e6) + b);
    const strong = document.createElement("strong");
    strong.textContent = `y = ${num(a, 3)}·x ${b < 0 ? "−" : "+"} ${num(Math.abs(b), 2)}`;
    eq.append("Reta de tendência (tracejada): ", strong,
      `, com x em horas desde ${fmtDateTime(tl.t0)}. R² = ${tl.r2 == null ? "n/d" : num(tl.r2, 2)}. ` +
      `Variação estimada no período: ${signed(tl.change_in_period * k, m.digits + 1)} ${m.unit}.`);
  }
  function renderSeries(data, trends) {
    $$(".chart-card").forEach((fig) => {
      const key = fig.dataset.chart, m = METRICS[key];
      const canvas = $("canvas", fig), empty = $(".chart-empty", fig), sr = $(".sr-summary", fig);
      const labels = data.points.map((p) => p.t);
      const values = data.points.map((p) => key === "ldr_raw" ? ldrPct(p[key]) : p[key]);
      const valid = values.filter((v) => v != null);
      empty.hidden = valid.length > 0;
      if (!valid.length) empty.textContent = "Ainda não há registros deste sensor neste período.";
      sr.textContent = valid.length ? `${m.label}: mínimo ${num(Math.min(...valid), m.digits)}, máximo ${num(Math.max(...valid), m.digits)} ${m.unit}, em ${PERIOD_LABEL[state.period]}.` : `${m.label}: sem registros no período.`;
      const chart = ensureChart(key, canvas);
      chart.data.labels = labels; chart.data.datasets[0].data = values;
      renderTrendline(fig, chart, key, valid.length, labels, trends && trends.metrics ? trends.metrics[key] : null);
      chart.options.scales.y.suggestedMin = key === "ldr_raw" ? 0 : undefined;
      chart.options.scales.y.suggestedMax = key === "ldr_raw" ? 100 : undefined;
      chart.update();
    });
  }

  /* ---------- histórico ---------- */
  function tableParams() {
    const t = state.table, p = { page: t.page, page_size: t.size, sort_by: t.sort, order: t.order };
    p.source = t.source === "current" ? state.source : t.source;
    if (t.period === "custom") {
      if (t.start) p.start = new Date(`${t.start}T00:00:00`).toISOString();
      if (t.end) p.end = new Date(`${t.end}T23:59:59`).toISOString();
    } else p.period = t.period;
    return p;
  }
  async function loadTable() {
    const err = $("#hist-error"); err.hidden = true;
    const t = state.table;
    if (t.period === "custom" && t.start && t.end && t.end < t.start) { err.textContent = "A data final deve ser igual ou posterior à data inicial."; err.hidden = false; return; }
    if (t.period === "custom" && !t.start) { $("#hist-body").innerHTML = '<tr><td colspan="7" class="empty">Escolha a data inicial para ver os registros.</td></tr>'; return; }
    try {
      const data = await api("/api/readings", tableParams());
      renderTable(data);
    } catch (e) { err.textContent = e.message; err.hidden = false; }
  }
  const cell = (label, text, cls) => { const td = document.createElement("td"); td.dataset.label = label; td.textContent = text ?? "Sem leitura"; if (text == null) td.className = "na"; if (cls) td.className = cls; return td; };
  function renderTable(d) {
    const body = $("#hist-body"); body.replaceChildren();
    if (!d.items.length) {
      const tr = document.createElement("tr"), td = document.createElement("td");
      td.colSpan = 7; td.className = "empty"; td.textContent = "Nenhum registro encontrado para este filtro.";
      tr.appendChild(td); body.appendChild(tr);
    }
    for (const r of d.items) {
      const tr = document.createElement("tr");
      tr.appendChild(cell("Data e horário", fmtSeconds(r.timestamp)));
      tr.appendChild(cell("Temperatura (°C)", num(r.temperature_c, 1)));
      tr.appendChild(cell("Umidade (%)", num(r.humidity_pct, 1)));
      tr.appendChild(cell("Pressão (hPa)", num(r.pressure_hpa, 1)));
      tr.appendChild(cell("MQ-135 (pontos)", num(r.mq135_raw, 0)));
      tr.appendChild(cell("LDR (pontos)", num(r.ldr_raw, 0)));
      const td = document.createElement("td"); td.dataset.label = "Origem";
      const b = document.createElement("span"); b.className = `badge ${r.source === "hardware" ? "badge-real" : "badge-sim"}`;
      b.textContent = r.source === "hardware" ? "Real" : "Simulado (demonstração)";
      td.appendChild(b); tr.appendChild(td); body.appendChild(tr);
    }
    $("#pg-info").textContent = `Página ${d.page} de ${d.pages} — ${num(d.total)} registro(s)`;
    $("#pg-prev").disabled = d.page <= 1; $("#pg-next").disabled = d.page >= d.pages;
    $$("#hist-table th[data-sort]").forEach((th) => th.setAttribute("aria-sort", th.dataset.sort === state.table.sort ? (state.table.order === "asc" ? "ascending" : "descending") : "none"));
  }

  /* ---------- limites (seção Sobre) ---------- */
  function renderLimits(s) {
    const ul = $("#limits-list"); ul.replaceChildren();
    const items = [
      `Temperatura: de ${num(s.temp_min_c, 1)} a ${num(s.temp_max_c, 1)} °C`,
      `Umidade relativa: de ${num(s.humidity_min_pct, 0)} a ${num(s.humidity_max_pct, 0)} %`,
      `Pressão: variação de ${num(s.pressure_change_hpa_3h, 1)} hPa ou mais em 3 h (alerta estimado)`,
      `Sinal do MQ-135: ${num(s.mq135_change_pct, 0)} % ou mais de diferença em relação à mediana das últimas 24 h (alerta estimado)`,
      `Falha de comunicação: sem dados há mais de ${s.offline_after_minutes} min`,
    ];
    items.forEach((t) => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
  }

  /* ---------- mapa e geolocalização (Leaflet + OpenStreetMap) ---------- */
  const geo = { map: null, group: null, bounds: null, visitor: [], key: null };
  const textEl = (t) => { const d = document.createElement("div"); d.textContent = t; return d; };  // popups sem HTML
  const geoError = (msg) => { const e = $("#geo-error"); e.textContent = msg; e.hidden = !msg; };
  const fmtKm = (km) => (km < 1 ? `${num(km * 1000, 0)} m` : `${num(km, 2)} km`);

  function renderMap(st) {
    const has = st.latitude != null && st.longitude != null;
    const key = has ? `${st.latitude},${st.longitude},${st.coverage_radius_km}` : "none";
    if (key === geo.key) return;               // só redesenha se a posição mudou
    geo.key = key;
    const btns = [$("#btn-locate"), $("#btn-calc")];
    if (!has) {
      $("#geo-station").textContent = "A localização desta estação ainda não foi configurada.";
      $("#geo-hint").textContent = "Defina STATION_LATITUDE e STATION_LONGITUDE no arquivo .env e reinicie o servidor.";
      btns.forEach((b) => (b.disabled = true)); return;
    }
    if (typeof L === "undefined") { $("#geo-station").textContent = "Não foi possível carregar a biblioteca do mapa."; return; }
    const c = [st.latitude, st.longitude];
    if (!geo.map) {
      L.Icon.Default.imagePath = "/static/vendor/leaflet/images/";
      geo.map = L.map("map", { scrollWheelZoom: false });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors", referrerPolicy: "strict-origin-when-cross-origin" }).addTo(geo.map);
      geo.group = L.layerGroup().addTo(geo.map);
    }
    geo.group.clearLayers(); geo.visitor = [];
    geo.bounds = L.latLng(c).toBounds(st.coverage_radius_km * 2000);   // quadrado que contém a circunferência (lado = 2r, em m)
    geo.map.fitBounds(geo.bounds, { padding: [20, 20] });              // define a vista antes de adicionar camadas
    // Área de cobertura = circunferência de centro na estação: (x − x₀)² + (y − y₀)² = r²
    L.circle(c, { radius: st.coverage_radius_km * 1000, color: "#8a68d8", weight: 2, fillColor: "#8a68d8", fillOpacity: 0.12 }).addTo(geo.group);
    L.marker(c, { title: st.name, alt: `Estação ${st.name}` }).bindPopup(textEl(st.name)).addTo(geo.group);
    $("#geo-station").textContent = `${st.name}: ${num(st.latitude, 5)}, ${num(st.longitude, 5)}. Área de cobertura: raio de ${num(st.coverage_radius_km, 1)} km.`;
    btns.forEach((b) => (b.disabled = false));
    setTimeout(() => geo.map.invalidateSize(), 0);
  }

  function resultRow(dl, label, value, cls) {
    const row = document.createElement("div"), dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = label; dd.textContent = value; if (cls) dd.className = cls;
    row.append(dt, dd); dl.appendChild(row);
  }
  async function showProximity(lat, lon) {
    geoError("");
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) { geoError("A latitude deve ser um número entre −90 e 90."); return; }
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) { geoError("A longitude deve ser um número entre −180 e 180."); return; }
    let d;
    try { d = await api("/api/geo/proximity", { lat, lon }); } catch (e) { geoError(e.message); return; }
    const s = [d.station.latitude, d.station.longitude], v = [lat, lon];
    geo.visitor.forEach((l) => geo.group.removeLayer(l));
    const pin = L.circleMarker(v, { radius: 8, color: "#fff", weight: 2, fillColor: d.inside_coverage ? "#35a56a" : "#c8332f", fillOpacity: 1 }).bindPopup(textEl("Sua posição"));
    const seg = L.polyline([s, v], { color: "#cf5a0c", weight: 3, dashArray: "8 8" });   // reta estação → visitante
    geo.visitor = [pin, seg]; geo.visitor.forEach((l) => l.addTo(geo.group));
    geo.map.fitBounds(L.latLngBounds(geo.bounds.getSouthWest(), geo.bounds.getNorthEast()).extend(v), { padding: [30, 30] });

    const dl = $("#geo-result"); dl.replaceChildren(); dl.hidden = false;
    const p = d.visitor_plane, r = d.station.coverage_radius_km;
    resultRow(dl, "Distância até a estação", `${fmtKm(d.distance_km)}  (conferência por Haversine: ${fmtKm(d.distance_haversine_km)})`);
    resultRow(dl, "Direção a partir da estação", d.azimuth_deg == null ? "Você está sobre a estação" : `${d.direction} (${num(d.azimuth_deg, 0)}° a partir do norte)`);
    resultRow(dl, "Área de cobertura", d.inside_coverage ? `Dentro (raio de ${num(r, 1)} km)` : `Fora (raio de ${num(r, 1)} km)`, d.inside_coverage ? "in" : "out");
    resultRow(dl, "Posição no plano (estação = origem)", `x = ${signed(p.x_km, 2)} km (leste), y = ${signed(p.y_km, 2)} km (norte)`);
    resultRow(dl, "Equação da circunferência", `x² + y² = ${num(r * r, 2)}`);
    resultRow(dl, "Reta estação–você", !d.line ? "—" : d.line.slope == null ? "x = 0 (vertical)" : `y = ${num(d.line.slope, 3)}·x`);
  }
  function locateMe() {
    geoError("");
    if (!("geolocation" in navigator)) { geoError("Seu navegador não oferece geolocalização. Informe as coordenadas manualmente."); return; }
    if (!window.isSecureContext) { geoError("A geolocalização só funciona em conexão segura (https) ou em localhost. Informe as coordenadas manualmente."); return; }
    const btn = $("#btn-locate"), label = btn.textContent;
    btn.disabled = true; btn.textContent = "Obtendo sua posição…";
    const done = () => { btn.disabled = false; btn.textContent = label; };
    navigator.geolocation.getCurrentPosition(
      (pos) => { done(); $("#geo-lat").value = pos.coords.latitude.toFixed(5); $("#geo-lon").value = pos.coords.longitude.toFixed(5); showProximity(pos.coords.latitude, pos.coords.longitude); },
      (err) => { done(); geoError({ 1: "Permissão de localização negada. Você pode informar as coordenadas manualmente.", 2: "Não foi possível determinar sua posição.", 3: "Tempo esgotado ao obter sua posição." }[err.code] || "Não foi possível obter sua posição."); },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  }
  function calcManual() {
    const la = $("#geo-lat").value.trim(), lo = $("#geo-lon").value.trim();
    if (!la || !lo) { geoError("Preencha latitude e longitude."); return; }
    showProximity(Number(la), Number(lo));
  }

  /* ---------- ciclo de atualização ---------- */
  async function refresh(first = false) {
    try {
      const st = await api("/api/station/status", { source: state.userSource });
      renderStatus(st);
      const src = state.source;
      const [latest, alerts, stats, series, trends] = await Promise.all([
        api("/api/readings/latest", { source: src }), api("/api/alerts", { source: src }),
        api("/api/statistics", { source: src, period: state.period }), api("/api/readings/series", { source: src, period: state.period }),
        api("/api/trendline", { source: src, period: state.period }).catch(() => null),
      ]);
      renderLatest(latest); renderAlerts(alerts); renderStats(stats); renderSeries(series, trends);
      showError("");
      if (first) { renderLimits(await api("/api/settings/alerts")); }
      await loadTable();
    } catch (e) {
      showError(e.message);
      const chip = $("#conn-chip");
      if (chip.dataset.state === "loading") { chip.dataset.state = "offline"; $("#conn-text").textContent = "Sem conexão com o servidor"; }
      $$(".metric.is-loading").forEach((c) => { c.classList.remove("is-loading"); $('[data-role="value"]', c).textContent = "Indisponível"; });
    }
  }

  /* ---------- eventos ---------- */
  function bind() {
    $$("#period-switch button").forEach((b) => b.addEventListener("click", () => {
      state.period = b.dataset.period;
      $$("#period-switch button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      refresh();
    }));
    $$("#source-switch button").forEach((b) => b.addEventListener("click", () => { state.userSource = b.dataset.source; state.table.page = 1; refresh(); }));
    const t = state.table;
    const on = (id, fn) => $(id).addEventListener("change", (e) => { fn(e.target.value); t.page = 1; loadTable(); });
    on("#f-period", (v) => { t.period = v; $$(".f-custom").forEach((l) => (l.hidden = v !== "custom")); });
    on("#f-start", (v) => (t.start = v)); on("#f-end", (v) => (t.end = v));
    on("#f-source", (v) => (t.source = v)); on("#f-sort", (v) => (t.sort = v));
    on("#f-order", (v) => (t.order = v)); on("#f-size", (v) => (t.size = Number(v)));
    $("#hist-filters").addEventListener("submit", (e) => e.preventDefault());
    $$("#hist-table th[data-sort]").forEach((th) => {
      th.tabIndex = 0;
      const toggle = () => { if (t.sort === th.dataset.sort) t.order = t.order === "asc" ? "desc" : "asc"; else { t.sort = th.dataset.sort; t.order = "desc"; }
        $("#f-sort").value = ["timestamp", "temperature_c", "humidity_pct", "pressure_hpa", "mq135_raw", "ldr_raw"].includes(t.sort) ? t.sort : "timestamp"; $("#f-order").value = t.order; t.page = 1; loadTable(); };
      th.addEventListener("click", toggle);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    });
    $("#pg-prev").addEventListener("click", () => { t.page = Math.max(1, t.page - 1); loadTable(); });
    $("#pg-next").addEventListener("click", () => { t.page += 1; loadTable(); });
    $("#btn-locate").addEventListener("click", locateMe);
    $("#btn-calc").addEventListener("click", calcManual);
    window.addEventListener("load", () => geo.map && geo.map.invalidateSize());
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  }

  function init() {
    $$(".metric").forEach((c) => c.classList.add("is-loading"));
    bind();
    refresh(true).then(() => {
      const secs = (state.status && state.status.refresh_seconds) || 30;
      state.timer = setInterval(() => { if (!document.hidden) refresh(); }, Math.max(10, secs) * 1000);
    });
  }
  init();
})();
