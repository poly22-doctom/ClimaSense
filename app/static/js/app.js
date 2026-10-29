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
        backgroundColor: (ctx) => { const { chart: c } = ctx; if (!c.chartArea) return m.color + "22"; const g = c.ctx.createLinearGradient(0, c.chartArea.top, 0, c.chartArea.bottom); g.addColorStop(0, m.color + "40"); g.addColorStop(1, m.color + "00"); return g; } }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: REDUCED ? false : { duration: 500 },
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 7, maxRotation: 0, color: "#5f6585", callback(v) { return tickLabel(this.getLabelForValue(v)); } }, title: { display: true, text: "Data e hora", color: "#5f6585" } },
          y: { grid: { color: "#ece8f6" }, ticks: { color: "#5f6585" }, title: { display: true, text: key === "ldr_raw" ? "% da escala" : key === "mq135_raw" ? "pontos (0–4095)" : m.unit, color: "#5f6585" } },
        },
        plugins: { legend: { display: false },
          tooltip: { backgroundColor: "#fff", titleColor: "#2b3152", bodyColor: "#2b3152", borderColor: "#e9e5f4", borderWidth: 1, padding: 12, displayColors: false,
            callbacks: { title: (items) => fmtDateTime(items[0].label), label: (ctx) => `${m.label}: ${num(ctx.parsed.y, key === "pressure_hpa" || key === "temperature_c" ? 1 : 0)} ${key === "mq135_raw" ? "pontos" : m.unit}` } } },
      },
    });
    state.charts[key] = chart; return chart;
  }
  function renderSeries(data) {
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

  /* ---------- ciclo de atualização ---------- */
  async function refresh(first = false) {
    try {
      const st = await api("/api/station/status", { source: state.userSource });
      renderStatus(st);
      const src = state.source;
      const [latest, alerts, stats, series] = await Promise.all([
        api("/api/readings/latest", { source: src }), api("/api/alerts", { source: src }),
        api("/api/statistics", { source: src, period: state.period }), api("/api/readings/series", { source: src, period: state.period }),
      ]);
      renderLatest(latest); renderAlerts(alerts); renderStats(stats); renderSeries(series);
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
