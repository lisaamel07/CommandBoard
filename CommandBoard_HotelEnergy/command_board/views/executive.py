"""Halaman 1 - Executive Command Center (O2 Executive KPI + alert prioritas)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import store, ui

res = ui.result()
ui.page_header("Executive Command Center",
               "Data readiness → ekspektasi → deviasi → prioritas investigasi → keputusan.", res)
if ui.blocked_notice(res):
    st.stop()

s = res.scored.set_index("DATE")
d = ui.replay_date(res)
today = s.loc[d]
hist = s.loc[:d]
base28 = hist.iloc[-29:-1]
status_by_date = store.latest_status_by_date()

if today["day_status"] == "not-ready":
    st.error(f"Data {d:%d %b %Y} tidak layak (G1): {today['flag_reasons']}. "
             "KPI hari ini ditampilkan dari nilai interpolasi; alert dan rekomendasi diblokir.", icon=":material/block:")
elif today["day_status"] == "caution":
    st.warning(f"Data {d:%d %b %Y} berstatus caution: {today['flag_reasons'] or 'nilai hasil koreksi'}.",
               icon=":material/warning:")

# ---------------- KPI ----------------
c = st.columns(3) + st.columns(3)
act, fc = today["TOTAL_BUILDING_ELECTRICITY"], today["forecast"]
c[0].metric("Konsumsi gedung", f"{act:,.1f}",
            f"{(act - fc) / fc:+.1%} vs forecast" if pd.notna(fc) else None, delta_color="inverse", border=True,
            help="TOTAL_BUILDING_ELECTRICITY (satuan dataset).")
c[1].metric("Forecast hari ini", f"{fc:,.1f}" if pd.notna(fc) else "–",
            f"interval {today['lo']:,.0f}–{today['hi']:,.0f}" if pd.notna(fc) else None,
            delta_color="off", border=True)
cost_med = base28["TOTAL_PRICE"].median()
c[2].metric("Biaya harian", f"Rp{today['TOTAL_PRICE']/1e6:,.2f} jt",
            f"{(today['TOTAL_PRICE'] - cost_med) / cost_med:+.1%} vs median 28h", delta_color="inverse", border=True)
wbp_med = base28["WBP_SHARE"].median()
c[3].metric("WBP share", f"{today['WBP_SHARE']:.1%}",
            f"{(today['WBP_SHARE'] - wbp_med) * 100:+.1f} pp vs median 28h", delta_color="inverse", border=True)
c[4].metric("Faktor daya indikatif", f"{today['PF_INDIKATIF']:.2f}",
            "di bawah 0,85" if today["PF_INDIKATIF"] < 0.85 else "≥ 0,85", delta_color="off", border=True,
            help="kWh/√(kWh²+kVArh²) dari agregat harian LWBP+WBP dan KVARh. Indikatif, bukan pengukuran langsung.")
win = hist.iloc[-30:]
active = win[win["is_alert"] & ~win["blocked"] & win["severity"].isin(["Sedang", "Tinggi"])]
open_active = [x for x in active.index if status_by_date.get(x.strftime("%Y-%m-%d"), "proposed") not in ("closed", "rejected")]
c[5].metric("Alert prioritas 30 hari", f"{len(open_active)}",
            f"{len(win[win['is_alert']])} alert total", delta_color="off", border=True)
ui.unit_note()

# ---------------- Forecast besok ----------------
nxt = d + pd.Timedelta(days=1)
if nxt in s.index and pd.notna(s.at[nxt, "forecast"]):
    f_n, lo_n, hi_n = s.at[nxt, "forecast"], s.at[nxt, "lo"], s.at[nxt, "hi"]
    note = ""
else:
    nd = res.forecast.next_day.iloc[0]
    f_n, lo_n, hi_n, note = nd["forecast"], nd["lo"], nd["hi"], f" ({nd['catatan']})"
st.info(f"**Forecast {nxt:%A, %d %b %Y}:** {f_n:,.1f} (interval 90%: {lo_n:,.1f}–{hi_n:,.1f}) · "
        f"model {res.forecast.selected}{note}", icon=":material/insights:")

left, right = st.columns([3, 2])

# ---------------- Grafik 60 hari ----------------
with left:
    st.subheader("Aktual vs forecast · 60 hari terakhir")
    w = hist.iloc[-60:].reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pd.concat([w["DATE"], w["DATE"][::-1]]),
                             y=pd.concat([w["hi"], w["lo"][::-1]]), fill="toself",
                             fillcolor=ui.COLORS["band"], line=dict(width=0), name="Interval 90%", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w["DATE"], y=w["forecast"], name="Forecast",
                             line=dict(color=ui.COLORS["forecast"], dash="dash")))
    fig.add_trace(go.Scatter(x=w["DATE"], y=w["TOTAL_BUILDING_ELECTRICITY"], name="Aktual",
                             line=dict(color=ui.COLORS["actual"])))
    al = w[w["is_alert"]]
    fig.add_trace(go.Scatter(x=al["DATE"], y=al["TOTAL_BUILDING_ELECTRICITY"], mode="markers", name="Alert",
                             marker=dict(size=11, symbol="circle-open", line=dict(width=2),
                                         color=[{"Tinggi": "#d62728", "Sedang": "#ff7f0e", "Rendah": "#1f77b4"}[x]
                                                for x in al["severity"]]),
                             text=al["severity"], hovertemplate="%{x|%d %b}: %{y:,.1f} (%{text})<extra></extra>"))
    nr = w[w["day_status"] == "not-ready"]
    if len(nr):
        fig.add_trace(go.Scatter(x=nr["DATE"], y=nr["TOTAL_BUILDING_ELECTRICITY"], mode="markers",
                                 name="Data not-ready", marker=dict(symbol="x", size=10, color="black")))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.15),
                      hovermode="x unified")
    st.plotly_chart(fig)

# ---------------- Alert prioritas ----------------
with right:
    st.subheader("Alert prioritas")
    a = win[win["is_alert"]].reset_index().sort_values(["anomaly_score", "DATE"], ascending=False)
    if a.empty:
        st.success("Tidak ada deviasi melewati threshold dalam 30 hari terakhir.")
    else:
        a["status"] = [("diblokir (G1)" if b else status_by_date.get(x.strftime("%Y-%m-%d"), "proposed"))
                       for x, b in zip(a["DATE"], a["blocked"])]
        a["overdue"] = [(sev == "Tinggi" and stt == "proposed" and (d - x).days > 1)
                        for x, sev, stt in zip(a["DATE"], a["severity"], a["status"])]
        st.dataframe(
            a[["DATE", "severity", "confidence", "anomaly_score", "residual_pct", "status", "overdue"]],
            hide_index=True, height=340,
            column_config={
                "DATE": st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"),
                "severity": "Severity", "confidence": "Confidence",
                "anomaly_score": st.column_config.ProgressColumn("Skor", min_value=0, max_value=100, format="%d"),
                "residual_pct": st.column_config.NumberColumn("Deviasi", format="percent"),
                "status": "Status", "overdue": st.column_config.CheckboxColumn("Overdue"),
            })
        od = a[a["overdue"]]
        if len(od):
            st.warning(f"**Eskalasi:** {len(od)} alert severity tinggi belum ditinjau > 1 hari "
                       f"({', '.join(x.strftime('%d %b') for x in od['DATE'])}). Facility Manager perlu menetapkan "
                       "keputusan atau alasan penundaan.", icon=":material/priority_high:")
        if ui.role() not in ("Finance", "Manajemen"):
            st.page_link("views/anomaly_reco.py", label="Buka detail evidence & buat decision note",
                     icon=":material/arrow_forward:")

# ---------------- Ringkasan bulan berjalan ----------------
st.subheader("Bulan berjalan vs bulan sebelumnya")
mtd = hist[hist.index.to_period("M") == d.to_period("M")]
prev = hist[hist.index.to_period("M") == (d.to_period("M") - 1)]
prev_same = prev.iloc[:len(mtd)]
k = st.columns(4)
for col, (label, fn, fmt) in zip(k, [
    ("Konsumsi rata-rata/hari", lambda x: x["TOTAL_BUILDING_ELECTRICITY"].mean(), "{:,.1f}"),
    ("Biaya kumulatif", lambda x: x["TOTAL_PRICE"].sum() / 1e6, "Rp{:,.1f} jt"),
    ("WBP share rata-rata", lambda x: x["WBP_SHARE"].mean(), "{:.1%}"),
    ("Hari dengan alert", lambda x: float(x["is_alert"].sum()), "{:.0f}"),
]):
    cur, pv = fn(mtd), fn(prev_same) if len(prev_same) else np.nan
    col.metric(label, fmt.format(cur),
               None if pd.isna(pv) or pv == 0 else f"{(cur - pv) / abs(pv):+.1%} vs periode sama bln lalu",
               delta_color="inverse", border=True)
