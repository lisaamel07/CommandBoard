/* =========================================================
   Hotel Energy Command Board — frontend
   Lenis (smooth scroll) · GSAP + ScrollTrigger · Motion (hover) · ECharts
   ========================================================= */
(() => {
  "use strict";

  // ---------------------------------------------------------------- utils
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const nf = (d) => new Intl.NumberFormat("id-ID", { minimumFractionDigits: d, maximumFractionDigits: d });
  const NF = [nf(0), nf(1), nf(2), nf(3)];
  const num = (v, d = 1) => (v == null || isNaN(v) ? "–" : NF[d].format(v));
  const pct = (v, d = 1) => (v == null || isNaN(v) ? "–" : NF[d].format(v * 100) + "%");
  const spct = (v, d = 1) => (v == null || isNaN(v) ? "–" : (v >= 0 ? "+" : "") + pct(v, d));
  const rp = (v) => (v == null ? "–" : "Rp" + NF[0].format(v));
  const rpJt = (v) => (v == null ? "–" : "Rp" + NF[2].format(v / 1e6) + " jt");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dt = (s, o) => new Date(s + "T00:00:00").toLocaleDateString("id-ID", o || { day: "2-digit", month: "short", year: "numeric" });
  const dtShort = (s) => dt(s, { day: "2-digit", month: "short" });
  const dtLong = (s) => dt(s, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const addDays = (s, n) => { const d = new Date(s + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
  const diffDays = (a, b) => Math.round((new Date(a + "T00:00:00Z") - new Date(b + "T00:00:00Z")) / 864e5);
  const clean = (a) => a.filter((x) => x != null && !isNaN(x));
  const mean = (a) => { const b = clean(a); return b.length ? b.reduce((x, y) => x + y, 0) / b.length : null; };
  const sum = (a) => clean(a).reduce((x, y) => x + y, 0);
  const quant = (a, q) => { const b = clean(a).sort((x, y) => x - y); if (!b.length) return null; const p = (b.length - 1) * q, i = Math.floor(p); return b[i] + (b[Math.min(i + 1, b.length - 1)] - b[i]) * (p - i); };
  const median = (a) => quant(a, 0.5);
  const corr = (x, y) => { const mx = mean(x), my = mean(y); let a = 0, b = 0, c = 0; x.forEach((v, i) => { a += (v - mx) * (y[i] - my); b += (v - mx) ** 2; c += (y[i] - my) ** 2; }); return a / Math.sqrt(b * c); };
  const monthKey = (d) => d.slice(0, 7);
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const ICON = {
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    wallet: '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="M16 13h2M3 10h18"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    gauge: '<path d="M4 16a8 8 0 1 1 16 0"/><path d="m12 16 4-5"/>',
    bell: '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    spark: '<path d="M3 17l5-6 4 4 8-9"/><path d="M14 6h6v6"/>',
    dl: '<path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16"/>',
    save: '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v5h7M8 21v-7h8v7"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  };
  const ico = (k) => `<svg viewBox="0 0 24 24">${ICON[k]}</svg>`;

  // ---------------------------------------------------------------- state
  const ACCESS = {
    "Facility Manager": ["exec", "dq", "cons", "tariff", "zone", "fc", "anom", "report"],
    "Analis Data": ["exec", "dq", "cons", "tariff", "zone", "fc", "anom", "report"],
    "Staf Teknis": ["exec", "cons", "tariff", "zone", "anom", "report"],
    Finance: ["exec", "cons", "tariff", "report"],
    Manajemen: ["exec", "report"],
  };
  const PERM = {
    decide: ["Facility Manager"], validate: ["Facility Manager", "Staf Teknis"],
    quality: ["Analis Data"], threshold: ["Analis Data"],
  };
  const store = {
    get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  const S = {
    data: null, ser: [], byDate: new Map(), idx: new Map(), alerts: new Map(),
    D: null, role: store.get("hecb-role", "Facility Manager"),
    consDays: 180, consCal: new Set(["Hari kerja", "Akhir pekan", "Hari libur"]), zoneDays: 90,
    fcModels: null, sel: null, sumFreq: "W",
    af: { days: 90, sev: new Set(["Tinggi", "Sedang", "Rendah"]), conf: new Set(["Tinggi", "Sedang", "Rendah"]),
          st: new Set(["proposed", "validated", "monitor", "rejected", "closed", "diblokir"]) },
    chartFns: {}, seen: new Set(), first: true,
  };
  const can = (a) => PERM[a].includes(S.role);

  // ---------------------------------------------------------------- api
  async function api(path, body) {
    const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || r.statusText);
    return j;
  }
  async function load() {
    S.data = await api("/api/data");
    S.ser = S.data.series || [];
    S.byDate = new Map(S.ser.map((r) => [r.d, r]));
    S.idx = new Map(S.ser.map((r, i) => [r.d, i]));
    S.alerts = new Map((S.data.alerts || []).map((a) => [a.d, a]));
    if (!S.D) S.D = S.data.meta.date_max;
  }
  const upto = () => S.ser.slice(0, (S.idx.get(S.D) ?? S.ser.length - 1) + 1);
  const today = () => S.byDate.get(S.D);

  function toast(msg, type = "ok") {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    $("#toasts").appendChild(el);
    gsap.fromTo(el, { x: 40, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, ease: "back.out(1.6)" });
    gsap.to(el, { x: 40, opacity: 0, delay: 4, duration: 0.4, onComplete: () => el.remove() });
  }

  // ---------------------------------------------------------------- theme
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  function C() {
    return {
      text: css("--text"), muted: css("--muted"), line: css("--line"), actual: css("--c-actual"), fc: css("--c-fc"),
      band: css("--c-band"), lwbp: css("--c-lwbp"), wbp: css("--c-wbp"), kv: css("--c-kv"),
      za: css("--c-za"), zb: css("--c-zb"), zc: css("--c-zc"), ok: css("--ok"), warn: css("--warn"), danger: css("--danger"),
      info: css("--info"), accent: css("--accent"), accent2: css("--accent-2"), accent3: css("--accent-3"), tip: css("--glass-strong"),
      dark: document.documentElement.dataset.theme === "dark",
    };
  }
  const SEVC = () => { const c = C(); return { Tinggi: c.danger, Sedang: c.warn, Rendah: c.info }; };

  function setTheme(t, ev) {
    const apply = () => {
      document.documentElement.dataset.theme = t;
      store.set("hecb-theme", t);
      [...S.seen].forEach(draw);
    };
    if (document.startViewTransition && !reduceMotion && ev) {
      const x = ev.clientX, y = ev.clientY, r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
      const tr = document.startViewTransition(apply);
      tr.ready.then(() => document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 750, easing: "cubic-bezier(.7,0,.25,1)", pseudoElement: "::view-transition-new(root)" }));
    } else apply();
  }

  // ---------------------------------------------------------------- charts
  function chart(id, fn) { S.chartFns[id] = fn; if (S.seen.has(id)) draw(id); }
  function draw(id) {
    const el = document.getElementById(id);
    if (!el || !S.chartFns[id]) return;
    el.style.height = (el.dataset.h || 300) + "px";
    if (!el.offsetWidth) return;                       // panel tersembunyi -> digambar saat tab dibuka
    const inst = echarts.getInstanceByDom(el) || echarts.init(el, null, { renderer: "canvas" });
    const opt = S.chartFns[id]();
    if (opt.legend && opt.series) opt.legend.data = opt.series.filter((x) => x.name && !x.name.startsWith("_")).map((x) => x.name);
    inst.setOption(opt, true);
  }
  function observeCharts(root = document) {
    $$(".chart", root).forEach((el) => {
      if (el._obs) return;
      el._obs = true;
      el.style.height = (el.dataset.h || 300) + "px";
      ScrollTrigger.create({ trigger: el, start: "top 92%", once: true, onEnter: () => { S.seen.add(el.id); draw(el.id); } });
    });
  }
  addEventListener("resize", () => $$(".chart").forEach((el) => echarts.getInstanceByDom(el)?.resize()));

  function base(o = {}) {
    const c = C();
    return {
      animationDuration: 1100, animationEasing: "cubicOut", animationDurationUpdate: 700,
      textStyle: { fontFamily: "Plus Jakarta Sans", color: c.muted },
      grid: { left: 52, right: 20, top: 22, bottom: 56, ...(o.grid || {}) },
      tooltip: {
        trigger: "axis", backgroundColor: c.tip, borderColor: c.line, borderWidth: 1, padding: [8, 12],
        textStyle: { color: c.text, fontSize: 12, fontFamily: "Plus Jakarta Sans" },
        extraCssText: "backdrop-filter:blur(14px);border-radius:12px;box-shadow:0 12px 32px -12px rgba(15,23,42,.35)",
        valueFormatter: (v) => (typeof v === "number" ? num(v, 1) : v), ...(o.tooltip || {}),
      },
      legend: { bottom: 0, icon: "roundRect", itemWidth: 12, itemHeight: 6, textStyle: { color: c.muted, fontSize: 11 }, ...(o.legend || {}) },
    };
  }
  const xCat = (data, o = {}) => ({
    type: "category", data, boundaryGap: false, axisLine: { lineStyle: { color: C().line } }, axisTick: { show: false },
    axisLabel: { color: C().muted, fontSize: 11, formatter: (v) => (/^\d{4}-\d{2}-\d{2}$/.test(v) ? dtShort(v) : v), hideOverlap: true }, ...o,
  });
  const yVal = (o = {}) => ({
    type: "value", scale: true, axisLabel: { color: C().muted, fontSize: 11 }, splitLine: { lineStyle: { color: C().line } }, ...o,
  });
  function bandSeries(lo, hi, name = "Interval 90%") {
    const c = C();
    return [
      { name: "_lo", type: "line", data: lo, stack: "band", symbol: "none", lineStyle: { opacity: 0 }, tooltip: { show: false }, silent: true },
      { name, type: "line", data: hi.map((h, i) => (h == null || lo[i] == null ? null : h - lo[i])), stack: "band", symbol: "none",
        lineStyle: { opacity: 0 }, areaStyle: { color: c.band }, tooltip: { show: false }, silent: true },
    ];
  }
  const DZ = undefined; // zoom di dalam grafik dimatikan agar wheel tidak memblokir smooth scroll
  const lineS = (name, data, color, o = {}) => ({ name, type: "line", data, symbol: "none", smooth: 0.25, lineStyle: { color, width: 2 }, itemStyle: { color }, ...o });

  // ---------------------------------------------------------------- micro UI
  function spark(vals, color) {
    const v = vals.map((x) => (x == null ? null : x));
    const ok = clean(v);
    if (ok.length < 2) return "";
    const mn = Math.min(...ok), mx = Math.max(...ok), W = 110, H = 40;
    const pts = v.map((y, i) => [(i / (v.length - 1)) * W, y == null ? null : H - 4 - ((y - mn) / (mx - mn || 1)) * (H - 8)]).filter((p) => p[1] != null);
    const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const id = "sg" + Math.random().toString(36).slice(2, 8);
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="${line} L${W} ${H} L0 ${H} Z" fill="url(#${id})"/><path class="spark-line" d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round"/></svg>`;
  }
  const deltaChip = (v, txt, inverse = true) => {
    if (v == null || isNaN(v)) return `<span class="delta flat">${esc(txt || "–")}</span>`;
    const cls = Math.abs(v) < 1e-9 ? "flat" : (v > 0) === inverse ? "up" : "down";
    return `<span class="delta ${cls}">${v > 0 ? "▲" : v < 0 ? "▼" : "•"} ${esc(txt)}</span>`;
  };
  const statusChip = (st, prefix = "") => {
    const m = { ready: ["ok", "READY"], caution: ["warn", "CAUTION"], "not-ready": ["danger", "NOT-READY"] }[st] || ["neutral", st];
    return `<span class="chip ${m[0]}"><span class="dot" style="background:currentColor"></span>${esc(prefix)}${m[1]}</span>`;
  };
  const sevChip = (s) => `<span class="chip ${{ Tinggi: "danger", Sedang: "warn", Rendah: "info" }[s] || "neutral"}">${esc(s)}</span>`;
  const confChip = (s) => `<span class="chip ${{ Tinggi: "ok", Sedang: "warn", Rendah: "neutral" }[s] || "neutral"}">conf. ${esc(s)}</span>`;
  const lockNote = (txt) => `<div class="lock">${ico("lock").replace("<svg", '<svg style="width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2"')} ${txt}</div>`;

  const FMT = { n0: (v) => num(v, 0), n1: (v) => num(v, 1), n2: (v) => num(v, 2), pct: (v) => pct(v, 1), jt: (v) => NF[2].format(v), int: (v) => NF[0].format(Math.round(v)) };
  const cnt = (v, f = "n1") => (v == null || isNaN(v) ? "–" : `<span class="count" data-to="${v}" data-fmt="${f}">${FMT[f](S.first ? 0 : v)}</span>`);
  function runCounts(root = document) {
    $$(".count", root).forEach((el) => {
      if (el._done) return;
      const to = +el.dataset.to, f = FMT[el.dataset.fmt];
      const go = () => {
        el._done = true;
        const o = { v: el._from ?? 0 };
        gsap.to(o, { v: to, duration: reduceMotion ? 0 : 1.4, ease: "power3.out", onUpdate: () => (el.textContent = f(o.v)) });
      };
      if (S.first) ScrollTrigger.create({ trigger: el, start: "top 95%", once: true, onEnter: go });
      else { el.textContent = f(to); el._done = true; }
    });
  }

  function hoverFx(root = document) {
    const M = window.Motion;
    $$(".card, .kpi, .mini, .ring-card, .alert-item, .rec, .banner", root).forEach((el) => {
      if (el._hover) return;
      el._hover = true;
      const big = el.classList.contains("card");
      const lift = el.classList.contains("alert-item") ? { x: 4 } : big ? { y: -3 } : { y: -6, scale: 1.02 };
      const rest = el.classList.contains("alert-item") ? { x: 0 } : big ? { y: 0 } : { y: 0, scale: 1 };
      const spring = { type: "spring", stiffness: 320, damping: 22 };
      el.addEventListener("pointermove", (e) => {
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", e.clientX - r.left + "px");
        el.style.setProperty("--my", e.clientY - r.top + "px");
      });
      if (reduceMotion) return;
      el.addEventListener("mouseenter", () => {
        if (M?.animate) M.animate(el, lift, spring);
        el.style.boxShadow = "var(--shadow-hover)";
      });
      el.addEventListener("mouseleave", () => {
        if (M?.animate) M.animate(el, rest, spring);
        el.style.boxShadow = "";
      });
    });
  }

  function tabs(group, onShow) {
    const btns = $$(`[data-tabs="${group}"] button`);
    btns.forEach((b) => b.addEventListener("click", () => {
      btns.forEach((x) => x.classList.toggle("on", x === b));
      const panels = $$(`[data-panels="${group}"] > .panel`);
      panels.forEach((p) => p.classList.toggle("on", p.dataset.panel === b.dataset.tab));
      const p = panels.find((x) => x.dataset.panel === b.dataset.tab);
      if (p) {
        gsap.fromTo(p, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.45, ease: "power2.out", clearProps: "transform" });
        $$(".chart", p).forEach((c) => { S.seen.add(c.id); draw(c.id); });
        onShow?.(b.dataset.tab);
      }
      ScrollTrigger.refresh();
    }));
  }

  function download(name, text, type = "text/csv") {
    const blob = new Blob([type === "text/csv" ? "﻿" + text : text], { type: type + ";charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  const toCSV = (rows, cols) => [cols.join(","), ...rows.map((r) => cols.map((c) => {
    const v = r[c] ?? ""; const s = Array.isArray(v) ? v.join(" | ") : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(","))].join("\n");

  function table(cols, rows, o = {}) {
    const th = cols.map((c) => `<th class="${c.num ? "num" : ""}">${esc(c.h)}</th>`).join("");
    const tr = rows.map((r, i) => `<tr class="${o.hl?.(r) ? "hl" : ""}">${cols.map((c) =>
      `<td class="${c.num ? "num" : ""}">${c.f ? c.f(r[c.k], r, i) : esc(r[c.k] ?? "")}</td>`).join("")}</tr>`).join("");
    return `<table><thead><tr>${th}</tr></thead><tbody>${tr || `<tr><td colspan="${cols.length}" class="muted">Tidak ada data.</td></tr>`}</tbody></table>`;
  }

  // ================================================================= 01 EXECUTIVE
  function renderExec() {
    const m = S.data.meta, t = today(), U = upto();
    const prev28 = U.slice(-29, -1);
    $("#fileName").textContent = m.file;
    $("#heroChips").innerHTML = [
      statusChip(m.gate, "Dataset: "), statusChip(t.st, dt(S.D) + ": "),
      `<span class="chip neutral">Model: <span class="mono">${esc(m.model_version)}</span></span>`,
      `<span class="chip info">Trust score ${num(m.trust.Total, 1)}</span>`,
      `<span class="chip neutral">Peran: ${esc(S.role)}</span>`,
    ].join("");

    $("#dayBanner").innerHTML = t.st === "not-ready"
      ? `<div class="alert-banner danger"><b>G1 · Data ${dt(S.D)} tidak layak.</b>&nbsp;${esc(t.fr)} — KPI memakai nilai interpolasi; alert &amp; rekomendasi diblokir.</div>`
      : t.st === "caution" ? `<div class="alert-banner warn"><b>Caution · ${dt(S.D)}:</b>&nbsp;${esc(t.fr || "nilai hasil koreksi")}</div>` : "";

    const last30 = U.slice(-30);
    const win = last30.filter((r) => r.alert);
    const decided = statusByDate();
    const active = win.filter((r) => !r.blocked && ["Sedang", "Tinggi"].includes(r.sev) && !["closed", "rejected"].includes(decided[r.d]));
    const costMed = median(prev28.map((r) => r.cost)), wsMed = median(prev28.map((r) => r.ws));
    const c = C();
    const K = [
      { ico: "bolt", lbl: "Konsumsi gedung", val: cnt(t.total, "n1"), d: deltaChip(t.fc ? (t.total - t.fc) / t.fc : null, t.fc ? spct((t.total - t.fc) / t.fc) + " vs forecast" : "forecast belum tersedia"), sp: spark(last30.map((r) => r.total), c.accent) },
      { ico: "target", lbl: "Forecast hari ini", val: cnt(t.fc, "n1"), d: `<span class="delta flat">interval ${num(t.lo, 0)}–${num(t.hi, 0)}</span>`, sp: spark(last30.map((r) => r.fc), c.fc) },
      { ico: "wallet", lbl: "Biaya harian", val: `Rp${cnt(t.cost / 1e6, "jt")}<small>jt</small>`, d: deltaChip((t.cost - costMed) / costMed, spct((t.cost - costMed) / costMed) + " vs median 28 hari"), sp: spark(last30.map((r) => r.cost), c.accent2) },
      { ico: "clock", lbl: "WBP share", val: cnt(t.ws, "pct"), d: deltaChip(t.ws - wsMed, `${(t.ws - wsMed) >= 0 ? "+" : ""}${num((t.ws - wsMed) * 100, 1)} pp vs median 28 hari`), sp: spark(last30.map((r) => r.ws), c.wbp) },
      { ico: "gauge", lbl: "Faktor daya indikatif", val: cnt(t.pf, "n2"), d: `<span class="delta ${t.pf < 0.85 ? "up" : "down"}">${t.pf < 0.85 ? "di bawah 0,85" : "≥ 0,85"}</span>`, sp: spark(last30.map((r) => r.pf), c.kv) },
      { ico: "bell", lbl: "Alert prioritas 30 hari", val: cnt(active.length, "int"), d: `<span class="delta flat">${win.length} alert total</span>`, sp: spark(last30.map((r) => Math.abs(r.z ?? 0)), c.danger) },
    ];
    $("#kpis").innerHTML = K.map((k) => `<div class="kpi glass">${k.sp}<div class="lbl"><span class="ico">${ico(k.ico)}</span>${k.lbl}</div>
      <div class="val">${k.val}</div>${k.d}</div>`).join("");

    const nxt = addDays(S.D, 1), nr = S.byDate.get(nxt);
    let f, lo, hi, note = "";
    if (nr && nr.fc != null) ({ fc: f, lo, hi } = nr);
    else { const n = S.data.forecast.next_day; f = n.forecast; lo = n.lo; hi = n.hi; note = ` · ${n.catatan}`; }
    $("#nextDay").innerHTML = `<span class="b-ico">${ico("spark")}</span><p><b>Forecast ${dtLong(nxt)}:</b> ${num(f, 1)}
      <span class="muted">(interval 90%: ${num(lo, 1)}–${num(hi, 1)}) · model ${esc(S.data.forecast.label)}${esc(note)}</span></p>`;

    const w = U.slice(-60);
    chart("chExec", () => {
      const c = C(), sc = SEVC();
      return {
        ...base(),
        xAxis: xCat(w.map((r) => r.d)), yAxis: yVal(),
        series: [
          ...bandSeries(w.map((r) => r.lo), w.map((r) => r.hi)),
          lineS("Forecast", w.map((r) => r.fc), c.fc, { lineStyle: { color: c.fc, width: 2, type: "dashed" } }),
          lineS("Aktual", w.map((r) => r.total), c.actual, { lineStyle: { color: c.actual, width: 2.4 },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: c.accent + "33" }, { offset: 1, color: c.accent + "00" }]) } }),
          { name: "Alert", type: "scatter", symbolSize: 13, z: 5,
            data: w.map((r) => (r.alert ? { value: r.total, itemStyle: { color: sc[r.sev], borderColor: "#fff", borderWidth: 2 } } : null)) },
          { name: "Data not-ready", type: "scatter", symbol: "path://M2 2L22 22M22 2L2 22", symbolSize: 10,
            itemStyle: { color: c.text, borderColor: c.text, borderWidth: 2 }, data: w.map((r) => (r.st === "not-ready" ? r.total : null)) },
        ],
      };
    });

    const list = win.map((r) => ({ ...r, status: r.blocked ? "diblokir" : decided[r.d] || "proposed" })).sort((a, b) => b.score - a.score);
    $("#execAlerts").innerHTML = list.length ? list.map((r) => alertItem(r)).join("")
      : `<div class="alert-banner ok">Tidak ada deviasi melewati threshold dalam 30 hari terakhir.</div>`;
    $$("#execAlerts .alert-item").forEach((el) => el.addEventListener("click", () => {
      if (!ACCESS[S.role].includes("anom")) return toast("Peran ini tidak memiliki akses ke panel Anomali.", "err");
      S.sel = el.dataset.d; S.af.days = 10000; renderAnomaly(); lenis.scrollTo("#anomaly", { offset: -90, duration: 1.6 });
    }));
    const od = list.filter((r) => r.sev === "Tinggi" && r.status === "proposed" && diffDays(S.D, r.d) > 1);
    $("#escalation").innerHTML = od.length ? `<div class="alert-banner warn" style="margin:12px 0 0"><b>Eskalasi:</b>&nbsp;${od.length} alert severity tinggi belum ditinjau &gt; 1 hari (${od.map((r) => dtShort(r.d)).join(", ")}).</div>` : "";

    const ym = S.D.slice(0, 7), mtd = U.filter((r) => monthKey(r.d) === ym && !r.ex);
    const pm = new Date(S.D + "T00:00:00Z"); pm.setUTCMonth(pm.getUTCMonth() - 1);
    const pkey = pm.toISOString().slice(0, 7);
    const prev = U.filter((r) => monthKey(r.d) === pkey && !r.ex).slice(0, mtd.length);
    const M = [
      ["Konsumsi rata-rata/hari", (a) => mean(a.map((r) => r.total)), "n1"],
      ["Biaya kumulatif (Rp jt)", (a) => sum(a.map((r) => r.cost)) / 1e6, "n1"],
      ["WBP share rata-rata", (a) => mean(a.map((r) => r.ws)), "pct"],
      ["Hari dengan alert", (a) => a.filter((r) => r.alert).length, "int"],
    ];
    $("#monthCmp").innerHTML = M.map(([l, fn, f]) => {
      const cur = fn(mtd), pv = prev.length ? fn(prev) : null;
      const dl = pv ? (cur - pv) / Math.abs(pv) : null;
      return `<div class="mini glass reveal"><div class="lbl">${l}</div><div class="val">${cnt(cur, f)}</div>${deltaChip(dl, dl == null ? "tidak ada pembanding" : spct(dl) + " vs bln lalu")}</div>`;
    }).join("");
  }

  function statusByDate() {
    const o = {};
    [...(S.data.decisions || [])].sort((a, b) => a.id - b.id).forEach((d) => (o[d.alert_date] = d.status));
    return o;
  }
  function alertItem(r) {
    return `<div class="alert-item ${S.sel === r.d ? "sel" : ""}" data-d="${r.d}">
      <span class="sev sev-${r.sev}"></span>
      <div><div class="t">${dt(r.d)} · ${r.sev} <span class="muted">· conf. ${r.conf}</span></div>
      <div class="s">${spct(r.rp)} vs forecast · ${esc(r.cal)} · <b>${esc(r.status)}</b></div></div>
      <div class="score"><b>${num(r.score, 0)}</b><span class="bar"><i style="width:${r.score}%"></i></span></div></div>`;
  }

  // ================================================================= 02 DATA QUALITY
  function renderQuality() {
    const tr = S.data.meta.trust;
    const R = 50, CIRC = 2 * Math.PI * R;
    $("#rings").innerHTML = ["Total", "Kelengkapan", "Validitas", "Konsistensi", "Kewajaran pola"].map((k) =>
      `<div class="ring-card glass reveal"><div class="ring-wrap"><svg viewBox="0 0 120 120">
        <circle class="track" cx="60" cy="60" r="${R}" fill="none" stroke-width="10"/>
        <circle class="val-ring" cx="60" cy="60" r="${R}" fill="none" stroke-width="10" stroke-dasharray="${CIRC}" stroke-dashoffset="${CIRC}" data-off="${CIRC * (1 - tr[k] / 100)}"/></svg>
        <div class="num">${cnt(tr[k], "n1")}</div></div><div class="lbl">${k === "Total" ? "Trust score" : k}</div></div>`).join("");
    $$("#rings .val-ring").forEach((c) => ScrollTrigger.create({ trigger: c, start: "top 92%", once: true,
      onEnter: () => gsap.to(c, { strokeDashoffset: +c.dataset.off, duration: 1.6, ease: "power3.out" }) }));

    const stCls = { Lolos: "ok", Ditandai: "warn", "Gap dicatat": "info" };
    $("#checksTbl").innerHTML = table([
      { h: "ID", k: "id", f: (v) => `<b>${esc(v)}</b>` }, { h: "Dimensi", k: "dimensi" }, { h: "Pemeriksaan", k: "pemeriksaan" },
      { h: "Jumlah", k: "jumlah", num: true }, { h: "Status", k: "status", f: (v) => `<span class="chip ${stCls[v] || "danger"}">${esc(v)}</span>` },
      { h: "Detail", k: "detail" }], S.data.checks);

    chart("chRawClean", () => {
      const c = C(), log = $("#logToggle").checked;
      return {
        ...base(), xAxis: xCat(S.ser.map((r) => r.d)), yAxis: yVal({ type: log ? "log" : "value", scale: !log }),
        dataZoom: DZ,
        series: [
          lineS("Mentah", S.ser.map((r) => r.raw), c.warn, { smooth: false, z: 3, lineStyle: { color: c.warn, width: 1.4 } }),
          lineS("Setelah keputusan", S.ser.map((r) => r.total), c.accent, { smooth: false, z: 4, lineStyle: { color: c.accent, width: 1.4 } }),
          { name: "Baris kritis", type: "scatter", symbolSize: 11, itemStyle: { color: c.danger }, data: S.ser.map((r) => (r.fs === "critical" ? r.raw : null)) },
        ],
      };
    });

    const ov = Object.fromEntries((S.data.quality_decisions || []).map((q) => [q.date, q.decision]));
    const flags = S.data.flags.map((f) => ({ ...f, cur: ov[f.DATE] || f.default_decision }));
    const nc = flags.filter((f) => f.severity === "critical").length;
    $("#flagsInfo").innerHTML = `<b>${flags.length} tanggal ditandai</b> (${nc} kritis, ${flags.length - nc} peringatan). Default: kritis → <i>correct</i> (interpolasi waktu), peringatan → <i>keep</i>.
      <br>keep = nilai asli · correct = diinterpolasi, hari caution · exclude = dikeluarkan dari training/metrik/KPI, hari not-ready (alert diblokir).`;
    const editable = can("quality");
    $("#flagsTbl").innerHTML = table([
      { h: "Tanggal", k: "DATE", f: (v) => `<b>${v}</b>` },
      { h: "Severity", k: "severity", f: (v) => `<span class="chip ${v === "critical" ? "danger" : "warn"}">${v}</span>` },
      { h: "Kolom", k: "columns", f: (v) => `<span class="muted">${esc(v)}</span>` }, { h: "Alasan", k: "reasons" },
      { h: "Default", k: "default_decision" },
      { h: "Keputusan", k: "cur", f: (v, r) => editable
        ? `<select data-date="${r.DATE}" data-orig="${v}">${S.data.meta.decisions_allowed.map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select>`
        : `<b>${v}</b>` }], flags);
    $("#flagsForm").innerHTML = editable
      ? `<input id="qReason" placeholder="Alasan perubahan (wajib, dicatat di quality-decision log)" style="flex:1;min-width:260px">
         <button class="btn" id="qSave">${ico("save")} Simpan &amp; jalankan ulang pipeline</button>`
      : lockNote("Hanya peran <b>Analis Data</b> yang dapat mengubah quality decision.");
    $("#qSave")?.addEventListener("click", async () => {
      const items = $$("#flagsTbl select").filter((s) => s.value !== s.dataset.orig).map((s) => ({ date: s.dataset.date, decision: s.value }));
      if (!items.length) return toast("Tidak ada perubahan.", "err");
      try { await api("/api/quality-decisions", { role: S.role, items, reason: $("#qReason").value }); toast(`${items.length} keputusan disimpan. Pipeline dijalankan ulang.`); await refresh(); }
      catch (e) { toast(e.message, "err"); }
    });

    chart("chRecon", () => {
      const c = C();
      return { ...base(), xAxis: xCat(S.ser.map((r) => r.d)), yAxis: yVal(), dataZoom: DZ,
        series: [lineS("Total gedung", S.ser.map((r) => r.total), c.accent, { smooth: false, lineStyle: { width: 1.2, color: c.accent } }),
                 lineS("Zone A+B+C", S.ser.map((r) => r.A + r.B + r.C), c.zb, { smooth: false, lineStyle: { width: 1.2, color: c.zb } })] };
    });
    const tot = S.ser.map((r) => r.total);
    $("#reconStats").innerHTML = `<div class="mini glass"><div class="lbl">Korelasi total vs LWBP+WBP</div><div class="val">${num(corr(tot, S.ser.map((r) => r.lwbp + r.wbp)), 2)}</div><span class="muted">bergerak bersama meter utama</span></div>
      <div class="mini glass"><div class="lbl">Korelasi total vs Zone A+B+C</div><div class="val">${num(corr(tot, S.ser.map((r) => r.A + r.B + r.C)), 2)}</div><span class="muted">sub-meter dengan cakupan sendiri</span></div>`;

    $("#ingestTbl").innerHTML = table([{ h: "Langkah", k: "langkah" }, { h: "Status", k: "status", f: (v) => `<span class="chip ${v === "OK" ? "ok" : "warn"}">${v}</span>` }, { h: "Detail", k: "detail" }], S.data.ingest_log);
    $("#ingestNote").innerHTML = `Sumber: <b>${esc(S.data.meta.file)}</b> · checksum sha256 <span class="mono">${esc(S.data.meta.checksum)}</span>`;
  }

  // ================================================================= 03 CONSUMPTION
  function segment(el, opts, cur, onPick) {
    el.innerHTML = opts.map(([v, l]) => `<button data-v="${v}" class="${v == cur ? "on" : ""}">${l}</button>`).join("");
    $$("button", el).forEach((b) => b.addEventListener("click", () => onPick(+b.dataset.v || b.dataset.v)));
  }
  function renderCons() {
    segment($("#consPeriod"), [[30, "30 hari"], [90, "90 hari"], [180, "180 hari"], [365, "1 tahun"], [100000, "Semua"]], S.consDays,
      (v) => { S.consDays = v; renderCons(); });
    const cals = ["Hari kerja", "Akhir pekan", "Hari libur"];
    $("#consCal").innerHTML = `<span class="lbl">Kalender</span>` + cals.map((c) => `<button class="tog ${S.consCal.has(c) ? "on" : ""}" data-c="${c}">${c}</button>`).join("");
    $$("#consCal .tog").forEach((b) => b.addEventListener("click", () => {
      S.consCal.has(b.dataset.c) ? S.consCal.delete(b.dataset.c) : S.consCal.add(b.dataset.c);
      if (!S.consCal.size) S.consCal.add(b.dataset.c);
      renderCons();
    }));
    const U = upto().filter((r) => !r.ex);
    const from = addDays(S.D, -S.consDays);
    const w = U.filter((r) => r.d > from && S.consCal.has(r.cal));
    $("#consKpi").innerHTML = [
      ["Rata-rata konsumsi/hari", cnt(mean(w.map((r) => r.total)), "n1")],
      ["Total biaya periode", `Rp${cnt(sum(w.map((r) => r.cost)) / 1e6, "n1")} jt`],
      ["Rata-rata biaya/hari", `Rp${cnt(mean(w.map((r) => r.cost)) / 1e6, "jt")} jt`],
      ["Hari dianalisis", cnt(w.length, "int")],
    ].map(([l, v]) => `<div class="mini glass"><div class="lbl">${l}</div><div class="val">${v}</div></div>`).join("");

    chart("chCons", () => {
      const c = C(); const ma = w.map((_, i) => mean(w.slice(Math.max(0, i - 6), i + 1).map((r) => r.total)));
      return { ...base(), xAxis: xCat(w.map((r) => r.d)), yAxis: yVal(), dataZoom: DZ,
        series: [
          lineS("Konsumsi", w.map((r) => r.total), c.actual, { smooth: false, lineStyle: { color: c.actual, width: 1, opacity: 0.55 } }),
          lineS("Rata-rata 7 hari", ma, c.accent, { lineStyle: { color: c.accent, width: 3 },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: c.accent + "30" }, { offset: 1, color: c.accent + "00" }]) } }),
          { name: "Hari libur", type: "scatter", symbolSize: 10, itemStyle: { color: c.accent3 || "#ec4899" }, data: w.map((r) => (r.hol ? r.total : null)) },
        ] };
    });
    chart("chCost", () => {
      const c = C();
      return { ...base(), xAxis: xCat(w.map((r) => r.d), { boundaryGap: true }), yAxis: yVal({ scale: false }),
        tooltip: { valueFormatter: (v) => num(v, 2) + " jt" },
        series: [{ name: "LWBP", type: "bar", stack: "c", data: w.map((r) => r.lp / 1e6), itemStyle: { color: c.lwbp } },
                 { name: "WBP", type: "bar", stack: "c", data: w.map((r) => r.wp / 1e6), itemStyle: { color: c.wbp, borderRadius: [3, 3, 0, 0] } }] };
    });
    chart("chDow", () => {
      const c = C(), names = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
      const box = names.map((_, i) => {
        const v = w.filter((r) => r.dow === i + 1).map((r) => r.total);
        const q1 = quant(v, 0.25), q3 = quant(v, 0.75), iqr = q3 - q1;
        const inl = v.filter((x) => x >= q1 - 1.5 * iqr && x <= q3 + 1.5 * iqr);
        return [Math.min(...inl), q1, median(v), q3, Math.max(...inl)];
      });
      return { ...base({ tooltip: { trigger: "item", valueFormatter: (v) => num(v, 1) } }),
        xAxis: { type: "category", data: names, axisLabel: { color: c.muted }, axisLine: { lineStyle: { color: c.line } } }, yAxis: yVal(),
        series: [{ name: "Konsumsi", type: "boxplot", data: box, itemStyle: { color: c.accent + "33", borderColor: c.accent, borderWidth: 1.6 } }] };
    });
    const months = groupMonths(U);
    chart("chMonthly", () => {
      const c = C();
      return { ...base({ grid: { right: 56 } }), xAxis: xCat(months.map((m) => m.k), { boundaryGap: true }),
        yAxis: [yVal({ name: "Rp juta", scale: false, nameTextStyle: { color: c.muted } }), yVal({ name: "Konsumsi", splitLine: { show: false }, nameTextStyle: { color: c.muted } })],
        series: [{ name: "Biaya total (Rp juta)", type: "bar", data: months.map((m) => m.cost / 1e6), itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: c.accent2 }, { offset: 1, color: c.accent2 + "44" }]), borderRadius: [6, 6, 0, 0] } },
                 lineS("Konsumsi rata-rata/hari", months.map((m) => m.avg), c.accent, { yAxisIndex: 1, symbol: "circle", symbolSize: 6, lineStyle: { color: c.accent, width: 3 } })] };
    });
  }
  function groupMonths(rows) {
    const g = new Map();
    rows.forEach((r) => { const k = monthKey(r.d); if (!g.has(k)) g.set(k, []); g.get(k).push(r); });
    return [...g].map(([k, a]) => ({ k, avg: mean(a.map((r) => r.total)), cost: sum(a.map((r) => r.cost)), lwbp: sum(a.map((r) => r.lwbp)),
      wbp: sum(a.map((r) => r.wbp)), ws: mean(a.map((r) => r.ws)), A: sum(a.map((r) => r.A)), B: sum(a.map((r) => r.B)), C: sum(a.map((r) => r.C)) }));
  }

  // ================================================================= 04 TARIFF
  function renderTariff() {
    const U = upto().filter((r) => !r.ex), w90 = U.filter((r) => r.d > addDays(S.D, -90));
    const rl = median(U.map((r) => r.lp / r.lwbp)), rw = median(U.filter((r) => r.wbp > 0).map((r) => r.wp / r.wbp));
    const ws90 = mean(w90.map((r) => r.ws)), wsAll = mean(U.map((r) => r.ws));
    $("#tariffKpi").innerHTML = [
      ["Tarif LWBP / unit", `Rp${cnt(rl, "n0")}`, ""],
      ["Tarif WBP / unit", `Rp${cnt(rw, "n0")}`, `<span class="delta flat">${num(rw / rl, 2)}× LWBP</span>`],
      ["WBP share 90 hari", cnt(ws90, "pct"), deltaChip(ws90 - wsAll, `${ws90 - wsAll >= 0 ? "+" : ""}${num((ws90 - wsAll) * 100, 1)} pp vs histori`)],
      ["Porsi biaya WBP 90 hari", cnt(mean(w90.map((r) => r.wcs)), "pct"), ""],
      ["Hari PF < 0,85 (90 hari)", cnt(w90.filter((r) => r.pf < 0.85).length, "int"), ""],
    ].map(([l, v, d]) => `<div class="mini glass"><div class="lbl">${l}</div><div class="val">${v}</div>${d}</div>`).join("");
    const months = groupMonths(U);
    chart("chTariffM", () => {
      const c = C();
      return { ...base({ grid: { right: 56 } }), xAxis: xCat(months.map((m) => m.k), { boundaryGap: true }),
        yAxis: [yVal({ scale: false }), yVal({ splitLine: { show: false }, axisLabel: { color: c.muted, formatter: (v) => pct(v, 0) } })],
        series: [{ name: "LWBP", type: "bar", stack: "t", data: months.map((m) => m.lwbp), itemStyle: { color: c.lwbp } },
                 { name: "WBP", type: "bar", stack: "t", data: months.map((m) => m.wbp), itemStyle: { color: c.wbp, borderRadius: [6, 6, 0, 0] } },
                 lineS("WBP share", months.map((m) => m.ws), c.text, { yAxisIndex: 1, symbol: "circle", symbolSize: 6, tooltip: { valueFormatter: (v) => pct(v) } })] };
    });
    chart("chWbp", () => {
      const c = C(); const ma = w90.map((_, i) => mean(w90.slice(Math.max(0, i - 6), i + 1).map((r) => r.ws)));
      return { ...base({ tooltip: { valueFormatter: (v) => pct(v) } }), xAxis: xCat(w90.map((r) => r.d)),
        yAxis: yVal({ axisLabel: { color: c.muted, formatter: (v) => pct(v, 0) } }),
        series: [lineS("Harian", w90.map((r) => r.ws), c.wbp, { smooth: false, lineStyle: { color: c.wbp, width: 1.2, opacity: 0.7 } }),
                 lineS("Rata-rata 7 hari", ma, c.text, { lineStyle: { color: c.text, width: 2.5 } }),
                 { name: "Naik signifikan (z ≥ 2)", type: "scatter", symbolSize: 11, itemStyle: { color: c.danger, borderColor: "#fff", borderWidth: 2 }, data: w90.map((r) => (r.zw >= 2 ? r.ws : null)) }] };
    });
    chart("chKv", () => {
      const c = C();
      return { ...base({ grid: { right: 48 } }), xAxis: xCat(w90.map((r) => r.d), { boundaryGap: true }),
        yAxis: [yVal({ scale: false }), yVal({ min: 0.6, max: 1, splitLine: { show: false } })],
        series: [{ name: "KVARh", type: "bar", data: w90.map((r) => r.kv), itemStyle: { color: c.kv + "aa", borderRadius: [4, 4, 0, 0] } },
                 lineS("PF indikatif", w90.map((r) => r.pf), c.text, { yAxisIndex: 1, tooltip: { valueFormatter: (v) => num(v, 3) },
                   markLine: { symbol: "none", lineStyle: { color: c.danger, type: "dashed" }, label: { color: c.danger, formatter: "PF 0,85" }, data: [{ yAxis: 0.85 }] } })] };
    });
  }

  // ================================================================= 05 ZONE
  const ZONES = [["Zone A", "A", "zA", "za"], ["Zone B", "B", "zB", "zb"], ["Zone C", "C", "zC", "zc"]];
  function renderZone() {
    segment($("#zonePeriod"), [[30, "30 hari"], [60, "60 hari"], [90, "90 hari"], [180, "180 hari"], [365, "1 tahun"]], S.zoneDays,
      (v) => { S.zoneDays = v; renderZone(); });
    const U = upto().filter((r) => !r.ex), w = U.filter((r) => r.d > addDays(S.D, -S.zoneDays)), t = today(), c = C();
    const tot = sum(w.map((r) => r.A + r.B + r.C));
    $("#zoneKpi").innerHTML = ZONES.map(([n, k, z, col]) => {
      const zz = t[z];
      return `<div class="mini glass"><div class="lbl" style="display:flex;gap:8px;align-items:center"><span class="dot" style="background:${c[col]}"></span>${n}</div>
        <div class="val">${cnt(sum(w.map((r) => r[k])) / tot, "pct")} <small class="muted">kontribusi</small></div>
        ${deltaChip(zz, zz == null ? "–" : `hari ini z = ${zz >= 0 ? "+" : ""}${num(zz, 1)}`)}
        <div class="muted" style="margin-top:6px">rata-rata ${num(mean(w.map((r) => r[k])), 1)}/hari · ${rpJt(sum(w.map((r) => r[k + "p"])))}</div></div>`;
    }).join("");
    chart("chZone", () => {
      const c = C();
      return { ...base(), xAxis: xCat(w.map((r) => r.d)), yAxis: yVal(), dataZoom: DZ,
        series: ZONES.map(([n, k, , col]) => lineS(n, w.map((r) => r[k]), c[col], { lineStyle: { color: c[col], width: 2 } })) };
    });
    const ms = groupMonths(w);
    chart("chZoneMix", () => {
      const c = C();
      return { ...base({ tooltip: { valueFormatter: (v) => pct(v) } }), xAxis: xCat(ms.map((m) => m.k), { boundaryGap: true }),
        yAxis: yVal({ max: 1, scale: false, axisLabel: { color: c.muted, formatter: (v) => pct(v, 0) } }),
        series: ZONES.map(([n, k, , col], i) => ({ name: n, type: "bar", stack: "z", data: ms.map((m) => m[k] / (m.A + m.B + m.C)),
          itemStyle: { color: c[col], borderRadius: i === 2 ? [6, 6, 0, 0] : 0 } })) };
    });
    const h = w.slice(-60);
    chart("chZoneHeat", () => {
      const c = C(), data = [];
      h.forEach((r, i) => ZONES.forEach(([, , z], j) => data.push([i, j, r[z] == null ? "-" : Math.max(-5, Math.min(5, r[z]))])));
      return { ...base({ tooltip: { trigger: "item", formatter: (p) => `${dt(h[p.value[0]].d)}<br>${ZONES[p.value[1]][0]}: z = ${num(p.value[2], 2)}` }, grid: { left: 70, bottom: 70 } }),
        xAxis: { type: "category", data: h.map((r) => r.d), axisLabel: { color: c.muted, formatter: dtShort, hideOverlap: true }, axisLine: { show: false }, axisTick: { show: false } },
        yAxis: { type: "category", data: ZONES.map((z) => z[0]), axisLabel: { color: c.text, fontWeight: 600 }, axisLine: { show: false }, axisTick: { show: false } },
        visualMap: { min: -5, max: 5, calculable: true, orient: "horizontal", left: "center", bottom: 0, itemHeight: 220, itemWidth: 10,
          textStyle: { color: c.muted }, inRange: { color: ["#2563eb", "#93c5fd", c.dark ? "#1e293b" : "#f8fafc", "#fca5a5", "#dc2626"] } },
        series: [{ type: "heatmap", data, itemStyle: { borderRadius: 4, borderColor: c.dark ? "#0b1022" : "#fff", borderWidth: 2 } }] };
    });
  }

  // ================================================================= 06 FORECAST
  function renderForecast() {
    const F = S.data.forecast, m = S.data.meta, c = C();
    $("#fcBanner").innerHTML = `<span class="b-ico">${ico("target")}</span><p><b>Model terpilih: ${esc(F.label)}.</b> ${esc(F.note)}</p>`;
    $("#fcBanner").style.borderColor = F.g2 ? "rgba(16,185,129,.4)" : "rgba(245,158,11,.5)";
    $("#fcSplit").textContent = `train ≤ ${dt(m.train_end)} · validation ≤ ${dt(m.val_end)} · test Jan–Jun 2025`;
    const maxSkill = Math.max(...F.metrics.map((r) => Math.max(0, r.val_skill_vs_snaive)));
    const sk = (v) => `<span class="skill" style="width:${Math.max(2, (Math.max(0, v) / (maxSkill || 1)) * 60)}px"></span>${pct(v, 1)}`;
    $("#fcTbl").innerHTML = table([
      { h: "Model", k: "Model", f: (v, r) => `${r.terpilih ? "★ " : ""}${esc(v)}` },
      { h: "Val MAE", k: "val_MAE", num: true, f: (v) => num(v, 1) }, { h: "Val RMSE", k: "val_RMSE", num: true, f: (v) => num(v, 1) },
      { h: "Val sMAPE", k: "val_sMAPE", num: true, f: (v) => num(v, 1) + "%" }, { h: "Skill vs s-naive (val)", k: "val_skill_vs_snaive", f: sk },
      { h: "Test MAE", k: "test_MAE", num: true, f: (v) => num(v, 1) }, { h: "Test sMAPE", k: "test_sMAPE", num: true, f: (v) => num(v, 1) + "%" },
      { h: "Skill (test)", k: "test_skill_vs_snaive", num: true, f: (v) => pct(v, 1) }], F.metrics, { hl: (r) => r.terpilih });
    $("#fcNotRun").innerHTML = Object.entries(F.not_run).map(([k, v]) => `<li><b>${esc(k)}</b> — ${esc(v)}</li>`).join("");

    if (!S.fcModels) S.fcModels = new Set(["seasonal_naive", F.selected]);
    $("#fcModels").innerHTML = Object.entries(F.labels).map(([k, l]) => `<button class="tog ${S.fcModels.has(k) ? "on" : ""}" data-m="${k}">${esc(l.split(" (")[0])}</button>`).join("");
    $$("#fcModels .tog").forEach((b) => b.addEventListener("click", () => {
      S.fcModels.has(b.dataset.m) ? S.fcModels.delete(b.dataset.m) : S.fcModels.add(b.dataset.m);
      b.classList.toggle("on"); draw("chSplit");
    }));
    const pal = [c.accent, c.danger, c.warn, c.ok, c.accent2];
    chart("chSplit", () => {
      const c = C(), dates = S.ser.filter((r) => r.d > m.train_end).map((r) => r.d);
      const series = [lineS("Aktual", dates.map((d) => S.byDate.get(d).total), c.actual, { smooth: false, lineStyle: { color: c.actual, width: 1.6 } })];
      Object.keys(F.labels).forEach((k, i) => {
        if (!S.fcModels.has(k)) return;
        const mp = new Map(F.split[k] || []);
        series.push(lineS(F.labels[k], dates.map((d) => mp.get(d) ?? null), pal[i], { lineStyle: { color: pal[i], width: 2, type: k === F.selected ? "solid" : "dashed" } }));
      });
      series[0].markLine = { symbol: "none", lineStyle: { color: c.muted, type: "dashed" }, label: { formatter: "validation | test", color: c.muted }, data: [{ xAxis: dates.find((d) => d > m.val_end) }] };
      return { ...base(), xAxis: xCat(dates), yAxis: yVal(), dataZoom: DZ, series };
    });

    const U = upto(), w = U.slice(-120);
    chart("chRolling", () => {
      const c = C();
      return { ...base(), xAxis: xCat(w.map((r) => r.d)), yAxis: yVal(),
        series: [...bandSeries(w.map((r) => r.lo), w.map((r) => r.hi)),
          lineS("Forecast", w.map((r) => r.fc), c.fc, { lineStyle: { color: c.fc, width: 2, type: "dashed" } }),
          lineS("Aktual", w.map((r) => r.total), c.actual, { lineStyle: { color: c.actual, width: 2 } })] };
    });
    const ok = U.filter((r) => r.fc != null && !r.ex);
    const inside = ok.filter((r) => r.total >= r.lo && r.total <= r.hi).length / (ok.length || 1);
    $("#fcStats").innerHTML = [
      ["Cakupan interval 90%", cnt(inside, "pct"), "target ± 90%"],
      ["σ residual (robust, validation)", cnt(F.sigma, "n1"), "z = residual / σ"],
      ["Interval residual 5%–95%", `${num(F.q_low, 0)} s.d. ${num(F.q_high, 0)}`, "dari residual validation"],
    ].map(([l, v, s]) => `<div class="mini glass"><div class="lbl">${l}</div><div class="val">${v}</div><span class="muted">${s}</span></div>`).join("");

    chart("chResid", () => {
      const c = C(), r = clean(ok.map((x) => x.resid)), mn = Math.min(...r), mx = Math.max(...r), nb = 40, bw = (mx - mn) / nb;
      const bins = Array.from({ length: nb }, (_, i) => [mn + bw * (i + 0.5), 0]);
      r.forEach((v) => bins[Math.min(nb - 1, Math.floor((v - mn) / bw))][1]++);
      return { ...base({ tooltip: { trigger: "item", formatter: (p) => `residual ≈ ${num(p.value[0], 0)}<br>${p.value[1]} hari` } }),
        xAxis: { type: "value", scale: true, axisLabel: { color: c.muted }, splitLine: { show: false } }, yAxis: yVal({ scale: false }),
        series: [{ type: "bar", data: bins, barWidth: "90%", itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: c.accent }, { offset: 1, color: c.accent2 }]), borderRadius: [4, 4, 0, 0] } }] };
    });
    const ex = { moving_average_7: "rata-rata konsumsi 7 hari terakhir.", seasonal_naive: "konsumsi pada hari yang sama minggu lalu.", naive: "konsumsi kemarin." };
    if (F.importance) {
      $("#fcExplain").innerHTML = `<div class="chart" id="chImp" data-h="270"></div>`;
      observeCharts($("#fcExplain"));
      chart("chImp", () => ({ ...base({ grid: { left: 90 }, tooltip: { trigger: "item" } }), xAxis: yVal({ scale: false }),
        yAxis: { type: "category", data: F.importance.map((r) => r.fitur).reverse(), axisLabel: { color: C().text } },
        series: [{ type: "bar", data: F.importance.map((r) => r.bobot).reverse(), itemStyle: { color: C().accent, borderRadius: [0, 6, 6, 0] } }] }));
    } else {
      const ridge = F.metrics.find((r) => r.model === "ridge");
      $("#fcExplain").innerHTML = `<div class="note glass" style="margin-top:8px">Model terpilih (<b>${esc(F.label)}</b>) transparan dengan sendirinya: forecast = ${ex[F.selected] || "-"}
        <br><br>Feature importance hanya ditampilkan bila model berbasis fitur terpilih dan stabil.</div>
        <p class="caption">Pembanding: Ridge val MAE ${num(ridge.val_MAE, 1)} — selisihnya di dalam toleransi 2%, sehingga model yang lebih sederhana dipilih (Bab 5.5).</p>`;
    }
  }

  // ================================================================= 07 ANOMALY
  function renderAnomaly() {
    const k = S.data.meta.k, U = upto();
    // threshold & sensitivitas
    const ed = can("threshold");
    $("#thrCtl").innerHTML = `<p class="caption">Tidak ada label ground-truth, sehingga threshold dievaluasi lewat sensitivitas jumlah alert. z = (aktual − forecast) / σ.</p>
      ${[["Rendah ≥", 0], ["Sedang (G3 material) ≥", 1], ["Tinggi ≥", 2]].map(([l, i]) => `<div class="field" style="margin-bottom:10px">
        <label>${l} <b id="kv${i}">${k[i]}</b> σ</label><input type="range" min="1" max="6" step="0.5" value="${k[i]}" data-i="${i}" ${ed ? "" : "disabled"}></div>`).join("")}
      ${ed ? `<button class="btn" id="kApply">${ico("save")} Terapkan threshold</button>` : lockNote("Hanya Analis Data yang dapat mengubah threshold.")}`;
    $$("#thrCtl input[type=range]").forEach((r) => r.addEventListener("input", () => ($("#kv" + r.dataset.i).textContent = r.value)));
    $("#kApply")?.addEventListener("click", async () => {
      const kk = $$("#thrCtl input[type=range]").map((r) => +r.value);
      try { await api("/api/threshold", { role: S.role, k: kk }); toast("Threshold diterapkan; anomaly scoring dijalankan ulang."); await refresh(); }
      catch (e) { toast(e.message, "err"); }
    });
    const okRows = U.filter((r) => r.fc != null && r.st !== "not-ready"), n = okRows.length;
    const sens = [1.5, 2, 2.5, 3, 3.5, 4, 5].map((kk) => { const f = okRows.filter((r) => Math.abs(r.z) >= kk);
      return { k: kk, n: f.length, pm: f.length / Math.max(n / 30.4, 1), pd: f.length / Math.max(n, 1), ev: f.filter((r) => r.nev > 0).length }; });
    $("#sensTbl").innerHTML = table([{ h: "k (× σ)", k: "k", num: true }, { h: "Jumlah alert", k: "n", num: true },
      { h: "Alert / bulan", k: "pm", num: true, f: (v) => num(v, 1) }, { h: "% hari", k: "pd", num: true, f: (v) => pct(v, 1) },
      { h: "Dengan ≥1 evidence", k: "ev", num: true }], sens, { hl: (r) => k.includes(r.k) });

    // filter
    const A = S.af;
    const tg = (set, vals, key) => vals.map((v) => `<button class="tog ${set.has(v) ? "on" : ""}" data-k="${key}" data-v="${v}">${v}</button>`).join("");
    $("#anomFilters").innerHTML = `<div class="filter-group"><span class="muted">Periode</span><select id="afDays">${[[30, "30 hari"], [90, "90 hari"], [180, "180 hari"], [365, "1 tahun"], [10000, "Semua"]]
        .map(([v, l]) => `<option value="${v}" ${v == A.days ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="chip-set"><span class="lbl">Severity</span>${tg(A.sev, ["Tinggi", "Sedang", "Rendah"], "sev")}</div>
      <div class="chip-set"><span class="lbl">Confidence</span>${tg(A.conf, ["Tinggi", "Sedang", "Rendah"], "conf")}</div>
      <div class="chip-set"><span class="lbl">Status</span>${tg(A.st, ["proposed", "validated", "monitor", "rejected", "closed", "diblokir"], "st")}</div>`;
    $("#afDays").addEventListener("change", (e) => { A.days = +e.target.value; renderAnomaly(); });
    $$("#anomFilters .tog").forEach((b) => b.addEventListener("click", () => { const s = A[b.dataset.k]; s.has(b.dataset.v) ? s.delete(b.dataset.v) : s.add(b.dataset.v); renderAnomaly(); }));

    const st = statusByDate();
    const list = U.filter((r) => r.alert && r.d > addDays(S.D, -A.days))
      .map((r) => ({ ...r, status: r.blocked ? "diblokir" : st[r.d] || "proposed" }))
      .filter((r) => A.sev.has(r.sev) && A.conf.has(r.conf) && A.st.has(r.status)).reverse();
    $("#alertCount").textContent = `Alert (${list.length})`;
    if (!list.length) { $("#alertList").innerHTML = `<div class="alert-banner ok">Tidak ada alert pada filter ini.</div>`; $("#alertDetail").innerHTML = ""; return; }
    if (!S.sel || !list.find((r) => r.d === S.sel)) S.sel = [...list].sort((a, b) => b.score - a.score)[0].d;
    $("#alertList").innerHTML = list.map(alertItem).join("");
    $$("#alertList .alert-item").forEach((el) => el.addEventListener("click", () => {
      S.sel = el.dataset.d;
      $$("#alertList .alert-item").forEach((x) => x.classList.toggle("sel", x === el));
      renderDetail(list.find((r) => r.d === S.sel));
    }));
    hoverFx($("#alertList"));
    renderDetail(list.find((r) => r.d === S.sel));
  }

  function renderDetail(r) {
    const a = S.alerts.get(r.d) || { evidence: [], recs: [], gates: [] };
    const el = $("#alertDetail");
    const hist = (S.data.decisions || []).filter((d) => d.alert_date === r.d);
    el.innerHTML = `<header class="card-h"><h3>Detail · ${dtLong(r.d)}</h3><div class="chips">${sevChip(r.sev)} ${confChip(r.conf)}</div></header>
      <div class="d-stats">
        <div class="mini"><div class="lbl">Aktual</div><div class="val">${num(r.total, 1)}</div></div>
        <div class="mini"><div class="lbl">Forecast</div><div class="val">${num(r.fc, 1)}</div></div>
        <div class="mini"><div class="lbl">Residual</div><div class="val">${r.resid >= 0 ? "+" : ""}${num(r.resid, 1)}</div>${deltaChip(r.rp, spct(r.rp) + " · z " + num(r.z, 2))}</div>
        <div class="mini"><div class="lbl">Skor anomali</div><div class="val">${num(r.score, 0)}</div><span class="bar" style="width:100%"><i style="width:${r.score}%"></i></span></div>
      </div>
      <p class="caption">Konteks kalender: <b>${esc(r.cal)}</b> · status data: <b>${esc(r.st)}</b>${r.fr ? " (" + esc(r.fr) + ")" : ""}</p>
      <div class="tabs" data-tabs="ad"><button class="on" data-tab="ev">Evidence</button><button data-tab="g">Evidence gate G1–G6</button>
        <button data-tab="rec">Rekomendasi</button><button data-tab="dn">Decision note</button></div>
      <div class="tab-panels" data-panels="ad">
        <div class="panel on" data-panel="ev">
          ${a.evidence.length ? `<ul class="ev-list">${a.evidence.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>` : `<p class="caption"><i>Tidak ada bukti kontekstual yang mendukung (confidence rendah, G4).</i></p>`}
          <div class="chart" id="chAlert" data-h="230"></div>
          <div class="table-wrap">${table([{ h: "Indikator", k: "i" }, { h: "Nilai", k: "v", num: true }, { h: "z vs baseline 28 hari", k: "z", num: true, f: (v) => (v == null ? "–" : (v >= 0 ? "+" : "") + num(v, 2)) }], [
            { i: "WBP share", v: pct(r.ws), z: r.zw }, { i: "KVARh", v: num(r.kv, 2), z: r.zk }, { i: "Biaya", v: rp(r.cost), z: r.zc },
            { i: "Zone A", v: num(r.A, 1), z: r.zA }, { i: "Zone B", v: num(r.B, 1), z: r.zB }, { i: "Zone C", v: num(r.C, 1), z: r.zC }])}</div>
        </div>
        <div class="panel" data-panel="g">${a.gates.map((g) => `<div class="gate"><span class="ic ${g.lolos ? "pass" : "fail"}">${g.lolos ? "✓" : "✕"}</span><b>${esc(g.gate)}</b><span>${esc(g.respon)}</span></div>`).join("")}</div>
        <div class="panel" data-panel="rec">${r.blocked ? `<div class="alert-banner danger">Diblokir oleh G1: data hari ini tidak layak. Rekomendasi tidak diterbitkan.</div>`
          : a.recs.map((x, i) => `<div class="rec"><b>${i + 1}. ${esc(x.aksi)}</b><p>Alasan: ${esc(x.alasan)}</p><p>Batasan: ${esc(x.batasan)}</p></div>`).join("")}</div>
        <div class="panel" data-panel="dn">
          ${hist.length ? `<div class="table-wrap" style="margin-bottom:12px">${table([{ h: "#", k: "id" }, { h: "Diperbarui", k: "updated_at" }, { h: "Owner", k: "owner" }, { h: "Due", k: "due_date" },
            { h: "Status", k: "status", f: (v) => `<span class="chip info">${esc(v)}</span>` }, { h: "Tindakan", k: "action" }, { h: "Validasi", k: "validation_result" }], hist)}</div>` : ""}
          ${r.blocked ? `<div class="alert-banner info">Alert diblokir — decision note tidak dapat dibuat sampai data diperbaiki.</div>`
            : can("decide") ? decisionForm(r, a) : lockNote("Hanya Facility Manager yang membuat decision note. Staf Teknis mengisi hasil validasi di panel Laporan.")}
        </div>
      </div>`;
    tabs("ad");
    observeCharts(el);
    hoverFx(el);
    gsap.fromTo(el.children, { opacity: 0, y: 12 }, { opacity: 1, y: 0, stagger: 0.04, duration: 0.45, ease: "power2.out", clearProps: "transform" });
    const w = S.ser.filter((x) => x.d >= addDays(r.d, -21) && x.d <= addDays(r.d, 7));
    chart("chAlert", () => {
      const c = C();
      return { ...base({ grid: { top: 16, bottom: 46 } }), xAxis: xCat(w.map((x) => x.d)), yAxis: yVal(),
        series: [...bandSeries(w.map((x) => x.lo), w.map((x) => x.hi)),
          lineS("Forecast", w.map((x) => x.fc), c.fc, { lineStyle: { color: c.fc, type: "dashed", width: 2 } }),
          lineS("Aktual", w.map((x) => x.total), c.actual, { lineStyle: { color: c.actual, width: 2.2 },
            markLine: { symbol: "none", lineStyle: { color: c.danger, type: "dotted", width: 2 }, label: { show: false }, data: [{ xAxis: r.d }] } })] };
    });
    S.seen.add("chAlert"); draw("chAlert");
    $("#dnForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      try {
        await api("/api/decisions", { role: S.role, alert_date: r.d, owner: f.get("owner"), due_date: f.get("due"), priority: f.get("prio"),
          status: f.get("status"), action: f.get("action"), note: f.get("note") });
        toast("Decision note tersimpan dan tercatat di audit trail."); await refresh();
      } catch (err) { toast(err.message, "err"); }
    });
  }
  function decisionForm(r, a) {
    const acts = a.recs.map((x) => x.aksi).concat(["Lainnya (tulis di catatan)"]);
    return `<form id="dnForm"><p class="caption"><b>Buat decision note</b> (G6 – human approval)</p>
      <div class="form-row">
        <div class="field"><label>Owner</label><input name="owner" placeholder="mis. Supervisor ME"></div>
        <div class="field"><label>Due date</label><input name="due" type="date" value="${addDays(r.d, 1)}"></div>
        <div class="field"><label>Prioritas</label><select name="prio">${["Tinggi", "Sedang", "Rendah"].map((p) => `<option ${p === r.sev ? "selected" : ""}>${p}</option>`).join("")}</select></div>
      </div>
      <div class="form-row"><div class="field"><label>Tindakan</label><select name="action">${acts.map((x) => `<option>${esc(x)}</option>`).join("")}</select></div></div>
      <div class="form-row radios">${[["validated", "tindak lanjut"], ["monitor", "pantau"], ["rejected", "tolak (false alert)"]].map(([v, l], i) =>
        `<label><input type="radio" name="status" value="${v}" ${i ? "" : "checked"}> <b>${v}</b> <span class="muted">${l}</span></label>`).join("")}</div>
      <div class="form-row"><div class="field"><label>Catatan / alasan keputusan</label><textarea name="note"></textarea></div></div>
      <div class="form-row"><button class="btn" type="submit">${ico("save")} Simpan decision note</button></div></form>`;
  }

  // ================================================================= 08 REPORT
  function renderReport() {
    const dec = (S.data.decisions || []).map((d) => ({ ...d, overdue: d.due_date < S.D && ["proposed", "validated"].includes(d.status) }));
    const open = dec.filter((d) => !["closed", "rejected"].includes(d.status));
    const counts = ["proposed", "validated", "monitor", "rejected", "closed"].map((s) => [s, dec.filter((d) => d.status === s).length]);
    $("#actionsBox").innerHTML = (dec.length ? `<div class="table-wrap">${table([
        { h: "#", k: "id" }, { h: "Alert", k: "alert_date", f: (v) => `<b>${v}</b>` }, { h: "Severity", k: "severity", f: (v) => sevChip(v) },
        { h: "Owner", k: "owner" }, { h: "Due", k: "due_date" }, { h: "Status", k: "status", f: (v) => `<span class="chip info">${esc(v)}</span>` },
        { h: "Overdue", k: "overdue", f: (v) => (v ? `<span class="chip danger">overdue</span>` : "") }, { h: "Tindakan", k: "action" },
        { h: "Catatan", k: "note" }, { h: "Validasi", k: "validation_result" }, { h: "Close reason", k: "close_reason" }, { h: "Model", k: "model_version", f: (v) => `<span class="mono muted">${esc(v)}</span>` }], dec)}</div>`
      : `<div class="alert-banner info">Belum ada decision note. Buat dari panel Anomali (peran Facility Manager).</div>`)
      + `<div class="mini-grid five">${counts.map(([s, n]) => `<div class="mini glass"><div class="lbl">${s}</div><div class="val">${n}</div></div>`).join("")}</div>`
      + (can("validate") && open.length ? `<form id="upForm" style="margin-top:16px"><p class="caption"><b>Perbarui action</b> — closed-loop: tutup dengan evidence &amp; close reason</p>
          <div class="form-row"><div class="field"><label>Action</label><select name="id">${open.map((d) => `<option value="${d.id}">#${d.id} · ${d.alert_date} · ${esc(d.action.slice(0, 60))}</option>`).join("")}</select></div>
          <div class="field"><label>Close reason</label><select name="reason" ${can("decide") ? "" : "disabled"}>${["", "Penyebab terkonfirmasi & ditindaklanjuti", "False alert (data/meter)", "Operasi normal (event/okupansi)", "Tidak dapat disimpulkan"].map((x) => `<option>${x}</option>`).join("")}</select></div></div>
          <div class="form-row"><div class="field"><label>Hasil validasi teknis (evidence)</label><textarea name="vr"></textarea></div></div>
          <div class="form-row"><label class="switch"><input type="checkbox" name="close" ${can("decide") ? "" : "disabled"}><span></span> Tutup action ${can("decide") ? "" : "(hanya Facility Manager)"}</label>
          <button class="btn" type="submit">${ico("save")} Simpan</button></div></form>` : "");
    $("#upForm")?.addEventListener("submit", async (e) => {
      e.preventDefault(); const f = new FormData(e.target);
      try { await api(`/api/decisions/${f.get("id")}`, { role: S.role, validation_result: f.get("vr") || "", close: f.get("close") === "on", close_reason: f.get("reason") || "" });
        toast("Action diperbarui."); await refresh(); } catch (err) { toast(err.message, "err"); }
    });

    // ringkasan
    const U = upto().filter((r) => !r.ex);
    const key = (d) => { if (S.sumFreq === "M") return d.slice(0, 7); const x = new Date(d + "T00:00:00Z"); x.setUTCDate(x.getUTCDate() + ((7 - x.getUTCDay()) % 7)); return x.toISOString().slice(0, 10); };
    const g = new Map(); U.forEach((r) => { const k = key(r.d); if (!g.has(k)) g.set(k, []); g.get(k).push(r); });
    const summ = [...g].map(([k, a]) => { const ft = sum(a.map((r) => r.fc)); return { periode: k, konsumsi_total: sum(a.map((r) => r.total)), konsumsi_rata_hari: mean(a.map((r) => r.total)),
      forecast_total: ft || null, deviasi_vs_forecast: ft ? sum(a.map((r) => r.total)) / ft - 1 : null, biaya_total_rp: sum(a.map((r) => r.cost)), biaya_wbp_rp: sum(a.map((r) => r.wp)),
      wbp_share: mean(a.map((r) => r.ws)), pf_indikatif: mean(a.map((r) => r.pf)), alert: a.filter((r) => r.alert).length,
      alert_tinggi_sedang: a.filter((r) => ["Tinggi", "Sedang"].includes(r.sev)).length, hari_caution: a.filter((r) => r.st === "caution").length }; }).reverse();
    $("#summaryBox").innerHTML = `<div class="toolbar"><div class="seg" id="sumSeg"></div>
        <div class="chip-set"><button class="btn ghost" id="exSum">${ico("dl")} Ringkasan CSV</button><button class="btn ghost" id="exAl">${ico("dl")} Alert log CSV</button>
        <button class="btn ghost" id="exDec" ${dec.length ? "" : "disabled"}>${ico("dl")} Decision log CSV</button><button class="btn" id="exMd">${ico("dl")} Decision note (.md)</button></div></div>
      <div class="table-wrap" style="margin-top:12px" data-lenis-prevent>${table([
        { h: "Periode", k: "periode", f: (v) => `<b>${v}</b>` }, { h: "Konsumsi total", k: "konsumsi_total", num: true, f: (v) => num(v, 0) },
        { h: "Rata-rata/hari", k: "konsumsi_rata_hari", num: true, f: (v) => num(v, 1) }, { h: "Deviasi vs forecast", k: "deviasi_vs_forecast", num: true, f: (v) => spct(v) },
        { h: "Biaya total", k: "biaya_total_rp", num: true, f: rp }, { h: "Biaya WBP", k: "biaya_wbp_rp", num: true, f: rp },
        { h: "WBP share", k: "wbp_share", num: true, f: (v) => pct(v) }, { h: "PF", k: "pf_indikatif", num: true, f: (v) => num(v, 3) },
        { h: "Alert", k: "alert", num: true }, { h: "Tinggi/Sedang", k: "alert_tinggi_sedang", num: true }, { h: "Hari caution", k: "hari_caution", num: true }], summ)}</div>`;
    segment($("#sumSeg"), [["W", "Mingguan"], ["M", "Bulanan"]], S.sumFreq, (v) => { S.sumFreq = v; renderReport(); });
    const tag = S.D.replace(/-/g, "");
    $("#exSum").onclick = () => download(`ringkasan_${S.sumFreq === "W" ? "mingguan" : "bulanan"}_${tag}.csv`, toCSV(summ, Object.keys(summ[0] || {})));
    $("#exAl").onclick = () => { const rows = upto().filter((r) => r.alert).map((r) => ({ tanggal: r.d, aktual: r.total, forecast: r.fc, residual: r.resid, z: r.z, severity: r.sev,
      confidence: r.conf, skor: r.score, status_data: r.st, diblokir: r.blocked, evidence: (S.alerts.get(r.d)?.evidence || []).join(" | ") }));
      download(`alert_log_${tag}.csv`, toCSV(rows, Object.keys(rows[0] || {}))); };
    $("#exDec").onclick = () => download(`decision_log_${tag}.csv`, toCSV(dec, Object.keys(dec[0] || {})));
    $("#exMd").onclick = () => {
      const l30 = upto().filter((r) => r.d > addDays(S.D, -30)), m = S.data.meta;
      const md = [`# Decision Note — Hotel Energy Command Board`, `Tanggal laporan: ${dtLong(S.D)}`,
        `Model: ${m.model_version} · Quality gate dataset: ${m.gate} · Trust score: ${num(m.trust.Total, 1)}`, "", "## Ringkasan 30 hari",
        `- Konsumsi rata-rata/hari: ${num(mean(l30.map((r) => r.total)), 1)}`, `- Biaya total: ${rp(sum(l30.map((r) => r.cost)))}`,
        `- WBP share rata-rata: ${pct(mean(l30.map((r) => r.ws)))}`, `- Alert: ${l30.filter((r) => r.alert).length} (Tinggi/Sedang: ${l30.filter((r) => ["Tinggi", "Sedang"].includes(r.sev)).length})`,
        "", "## Keputusan", ...(dec.length ? dec.map((x) => `- [${x.alert_date}] ${x.status.toUpperCase()} — ${x.action} (owner: ${x.owner}, due ${x.due_date})${x.close_reason ? "; ditutup: " + x.close_reason : ""}`) : ["- Belum ada keputusan tercatat."]),
        "", "## Batasan", "- Analitik harian, human-in-the-loop; bukan kontrol BAS/HVAC atau diagnosis perangkat.", "- Impact energi/biaya belum dapat diklaim sebelum pilot dengan data sebelum–sesudah."];
      download(`decision_note_${tag}.md`, md.join("\n"), "text/markdown");
    };

    // outcome
    const Ux = upto(), ms = Ux.filter((r) => r.alert && ["Tinggi", "Sedang"].includes(r.sev) && !r.blocked);
    const reviewed = new Set(dec.map((d) => d.alert_date)).size;
    const fa = dec.filter((d) => d.close_reason === "False alert (data/meter)" || d.status === "rejected").length;
    $("#outcomeBox").innerHTML = `<p class="caption">Indikator output/outcome yang dapat diuji pada prototipe (Bab 3.8). Impact (kWh/hari, biaya, WBP share sebelum–sesudah) memerlukan pilot.</p>
      <div class="mini-grid">${[["Data-ready rate", pct(Ux.filter((r) => r.st === "ready").length / Ux.length)],
        ["Alert completeness", ms.length ? pct(ms.filter((r) => r.fc != null).length / ms.length, 0) : "–"],
        ["Alert Sedang/Tinggi ditinjau", `${reviewed}/${ms.length}`], ["False alert / ditolak", String(fa)]]
        .map(([l, v]) => `<div class="mini glass"><div class="lbl">${l}</div><div class="val">${v}</div></div>`).join("")}</div>`;

    // audit
    $("#auditBox").innerHTML = `<div class="table-wrap" data-lenis-prevent>${table([{ h: "Waktu", k: "ts" }, { h: "Peran", k: "role" }, { h: "Entitas", k: "entity" },
        { h: "ID", k: "entity_id" }, { h: "Aksi", k: "action", f: (v) => `<span class="chip neutral">${esc(v)}</span>` }, { h: "Detail", k: "detail" }], S.data.audit || [])}</div>
      ${can("decide") || can("quality") ? `<details class="more" style="margin-top:12px"><summary>Mode demo</summary><p class="caption">Mengosongkan decision &amp; quality log, dan mengembalikan threshold default.</p>
        <button class="btn ghost" id="resetBtn">Kosongkan log</button></details>` : ""}`;
    $("#resetBtn")?.addEventListener("click", async () => {
      if (!confirm("Kosongkan semua decision log dan quality decision? Tindakan ini tidak dapat dibatalkan.")) return;
      try { await api("/api/reset", { role: S.role }); toast("Log dikosongkan."); S.sel = null; await refresh(); } catch (e) { toast(e.message, "err"); }
    });
  }

  // ================================================================= orkestrasi
  function applyRole() {
    const ok = ACCESS[S.role];
    $$(".section").forEach((s) => (s.hidden = !ok.includes(s.dataset.key)));
    $$("#links a").forEach((a) => (a.hidden = !ok.includes(a.dataset.key)));
    requestAnimationFrame(movePill);
  }
  function renderAll() {
    renderExec();
    if (!S.data.series?.length) return;
    renderQuality(); renderCons(); renderTariff(); renderZone(); renderForecast(); renderAnomaly(); renderReport();
    applyRole();
    observeCharts(); hoverFx(); runCounts(); setupReveal();
    $("#footMeta").innerHTML = `Sumber ${esc(S.data.meta.file)} · checksum <span class="mono">${esc(S.data.meta.checksum)}</span> · model ${esc(S.data.meta.model_version)} · threshold k = ${S.data.meta.k.join(" / ")}`;
    ScrollTrigger.refresh();
  }
  async function refresh() {
    await load();
    S.first = false;
    renderAll();
  }

  // reveal on scroll
  function setupReveal() {
    const els = $$(".reveal, .kpi, .mini, .ring-card").filter((e) => !e._rev && !e.closest(".panel:not(.on)"));
    els.forEach((e) => (e._rev = true));
    if (reduceMotion || !S.first) return;
    gsap.set(els, { opacity: 0, y: 40 });
    ScrollTrigger.batch(els, {
      start: "top 92%", once: true,
      onEnter: (b) => gsap.to(b, { opacity: 1, y: 0, duration: 0.9, ease: "power3.out", stagger: 0.08, clearProps: "transform" }),
    });
  }

  // ---------------------------------------------------------------- nav: Lenis + scrollspy + pill
  let lenis;
  function movePill() {
    const a = $("#links a.active:not([hidden])"), pill = $("#pill");
    if (!a) return gsap.to(pill, { opacity: 0, duration: 0.2 });
    gsap.to(pill, { x: a.offsetLeft, width: a.offsetWidth, opacity: 1, duration: 0.55, ease: "elastic.out(1, 0.75)" });
  }
  function setupScroll() {
    lenis = new Lenis({ lerp: 0.09, wheelMultiplier: 1, smoothWheel: !reduceMotion });
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);

    $$('a[href^="#"]').forEach((a) => a.addEventListener("click", (e) => {
      e.preventDefault(); lenis.scrollTo(a.getAttribute("href"), { offset: -90, duration: 1.6, easing: (t) => 1 - Math.pow(1 - t, 4) });
    }));
    $$(".section").forEach((s) => ScrollTrigger.create({
      trigger: s, start: "top 45%", end: "bottom 45%",
      onToggle: (st) => { if (st.isActive) { $$("#links a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === "#" + s.id)); movePill(); } },
    }));
    gsap.to(".progress span", { scaleX: 1, ease: "none", scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 0.3 } });
    $$(".sec-num").forEach((n) => gsap.fromTo(n, { yPercent: 45, opacity: 0.2 }, { yPercent: -10, opacity: 0.9, ease: "none",
      scrollTrigger: { trigger: n, start: "top bottom", end: "top 35%", scrub: true } }));
    $$(".sec-head h2").forEach((h) => gsap.from(h, { x: -30, opacity: 0, duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: h, start: "top 88%" } }));
    // parallax blob
    gsap.to(".b1", { yPercent: 30, ease: "none", scrollTrigger: { scrub: 1 } });
    gsap.to(".b3", { yPercent: -40, ease: "none", scrollTrigger: { scrub: 1 } });
  }

  function intro() {
    $$(".split").forEach((el) => {
      el.innerHTML = [...el.textContent].map((ch) => `<span class="ch">${ch === " " ? "&nbsp;" : ch}</span>`).join("");
    });
    $$(".grad .ch").forEach((c, i, all) => (c.style.backgroundPosition = `${(i / (all.length - 1)) * 100}% 0`));
    if (reduceMotion) return;
    const tl = gsap.timeline({ defaults: { ease: "power4.out" } });
    tl.from(".nav", { y: -80, opacity: 0, duration: 1 })
      .from(".eyebrow", { y: 20, opacity: 0, duration: 0.6 }, "-=0.6")
      .from(".hero-title .ch", { yPercent: 110, rotate: 8, opacity: 0, duration: 1, stagger: 0.025 }, "-=0.4")
      .from(".hero-sub", { y: 20, opacity: 0, duration: 0.7 }, "-=0.6")
      .from("#heroChips .chip", { scale: 0.6, opacity: 0, duration: 0.5, stagger: 0.06, ease: "back.out(2)" }, "-=0.4");
    // blob mengambang terus-menerus
    $$(".blob").forEach((b, i) => gsap.to(b, { x: `random(-80, 80)`, y: `random(-60, 60)`, scale: `random(0.85, 1.2)`,
      duration: 9 + i * 2, repeat: -1, yoyo: true, ease: "sine.inOut" }));
  }

  // ---------------------------------------------------------------- boot
  async function boot() {
    gsap.registerPlugin(ScrollTrigger);
    if (!$("#ringGradDefs")) document.body.insertAdjacentHTML("beforeend",
      `<svg id="ringGradDefs" width="0" height="0" style="position:absolute"><defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#6366f1"/><stop offset=".5" stop-color="#8b5cf6"/><stop offset="1" stop-color="#06b6d4"/></linearGradient></defs></svg>`);
    $("#role").value = S.role;
    try { await load(); }
    catch (e) { $("#loader").innerHTML = `<p style="color:var(--danger)">Gagal memuat data: ${esc(e.message)}</p>`; return; }
    const rp = $("#replay");
    rp.min = S.data.meta.date_min; rp.max = S.data.meta.date_max; rp.value = S.D;
    rp.addEventListener("change", () => {
      if (!rp.value || !S.byDate.has(rp.value)) { rp.value = S.D; return; }
      S.D = rp.value; S.first = false; S.sel = null; renderAll();
      gsap.fromTo("#kpis .kpi", { scale: 0.96, opacity: 0.4 }, { scale: 1, opacity: 1, duration: 0.6, stagger: 0.05, ease: "back.out(1.7)", clearProps: "transform" });
      toast(`Replay: ${dtLong(S.D)}`);
    });
    $("#role").addEventListener("change", (e) => { S.role = e.target.value; store.set("hecb-role", S.role); S.first = false; renderAll(); toast(`Peran: ${S.role}`); });
    $("#themeBtn").addEventListener("click", (e) => {
      setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", e);
      gsap.fromTo("#themeBtn", { rotate: -25, scale: 0.85 }, { rotate: 0, scale: 1, duration: 0.6, ease: "back.out(3)" });
    });
    $("#logToggle").addEventListener("change", () => draw("chRawClean"));
    tabs("dq"); tabs("rep");

    setupScroll();
    renderAll();
    S.first = false;
    gsap.to("#loader", { opacity: 0, duration: 0.5, onComplete: () => $("#loader").remove() });
    intro();
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
