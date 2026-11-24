"""Halaman 4 - Tariff & Reactive Energy (O5: F7 WBP/LWBP, WBP share, KVARh)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.anomaly import PF_LIMIT

res = ui.result()
ui.page_header("Tariff & Reactive Energy", "Komposisi WBP–LWBP, WBP share, KVARh, dan faktor daya indikatif.", res)
if ui.blocked_notice(res):
    st.stop()

d = ui.replay_date(res)
s = res.scored[(res.scored["DATE"] <= d) & ~res.scored["excluded"]]
w90 = s[s["DATE"] > d - pd.Timedelta(days=90)]

rate_l = (s["LWBP_PRICE"] / s["LWBP_USED"]).median()
rate_w = (s["WBP_PRICE"] / s["WBP_USED"].where(s["WBP_USED"] > 0)).median()
k = st.columns(5)
k[0].metric("Tarif LWBP / unit", f"Rp{rate_l:,.0f}", border=True)
k[1].metric("Tarif WBP / unit", f"Rp{rate_w:,.0f}", f"{rate_w / rate_l:.2f}× LWBP", delta_color="off", border=True)
k[2].metric("WBP share 90 hari", f"{w90['WBP_SHARE'].mean():.1%}",
            f"{(w90['WBP_SHARE'].mean() - s['WBP_SHARE'].mean()) * 100:+.1f} pp vs seluruh histori",
            delta_color="inverse", border=True)
k[3].metric("Porsi biaya WBP 90 hari", f"{w90['WBP_COST_SHARE'].mean():.1%}", border=True)
k[4].metric(f"Hari PF < {PF_LIMIT} (90 hari)", f"{(w90['PF_INDIKATIF'] < PF_LIMIT).sum()}", border=True)
st.caption("Tarif per unit konstan sepanjang dataset (cek K2). Karena itu, peluang efisiensi biaya terutama berasal "
           "dari volume dan pergeseran beban WBP → LWBP, bukan dari perubahan tarif.")

st.subheader("Pemakaian LWBP vs WBP per bulan")
m = s.assign(Bulan=s["DATE"].dt.to_period("M").dt.to_timestamp()).groupby("Bulan").agg(
    LWBP=("LWBP_USED", "sum"), WBP=("WBP_USED", "sum"), wbp_share=("WBP_SHARE", "mean")).reset_index()
fig = go.Figure()
fig.add_trace(go.Bar(x=m["Bulan"], y=m["LWBP"], name="LWBP", marker_color=ui.COLORS["lwbp"]))
fig.add_trace(go.Bar(x=m["Bulan"], y=m["WBP"], name="WBP", marker_color=ui.COLORS["wbp"]))
fig.add_trace(go.Scatter(x=m["Bulan"], y=m["wbp_share"], name="WBP share", yaxis="y2",
                         line=dict(color="black", width=2)))
fig.update_layout(barmode="stack", height=340, margin=dict(l=10, r=10, t=10, b=10),
                  legend=dict(orientation="h", y=-0.2), yaxis_title="Pemakaian (satuan dataset)",
                  yaxis2=dict(title="WBP share", overlaying="y", side="right", tickformat=".0%"))
st.plotly_chart(fig)

a, b = st.columns(2)
with a:
    st.subheader("WBP share harian · 90 hari")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=w90["DATE"], y=w90["WBP_SHARE"], name="Harian", line=dict(color=ui.COLORS["wbp"], width=1)))
    fig.add_trace(go.Scatter(x=w90["DATE"], y=w90["WBP_SHARE"].rolling(7, min_periods=1).mean(), name="Rata-rata 7 hari",
                             line=dict(color="black", width=2)))
    hi = w90[w90["z_wbp_share"] >= 2]
    fig.add_trace(go.Scatter(x=hi["DATE"], y=hi["WBP_SHARE"], mode="markers", name="Naik signifikan (z ≥ 2)",
                             marker=dict(color="#d62728", size=9)))
    fig.update_layout(height=320, yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig)
with b:
    st.subheader("KVARh & faktor daya indikatif · 90 hari")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=w90["DATE"], y=w90["KVARH_USED"], name="KVARh", marker_color=ui.COLORS["kvarh"]))
    fig.add_trace(go.Scatter(x=w90["DATE"], y=w90["PF_INDIKATIF"], name="PF indikatif", yaxis="y2",
                             line=dict(color="black", width=1.5)))
    fig.add_hline(y=PF_LIMIT, line_dash="dot", line_color="#d62728", yref="y2",
                  annotation_text=f"PF {PF_LIMIT}", annotation_position="bottom right")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.2),
                      yaxis_title="KVARh", yaxis2=dict(title="PF", overlaying="y", side="right", range=[0.6, 1.0]))
    st.plotly_chart(fig)
st.caption("PF indikatif = kWh/√(kWh²+kVArh²) dari agregat harian (LWBP+WBP dan KVARH). Asumsi: kedua kolom memakai "
           "skala satuan yang sama. Ini sinyal untuk pemeriksaan kapasitor bank, bukan pengukuran faktor daya.")
