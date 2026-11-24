"""Halaman 3 - Consumption & Cost (tren konsumsi, biaya, kalender)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import ui

res = ui.result()
ui.page_header("Consumption & Cost", "Tren konsumsi dan biaya harian, dibaca bersama konteks kalender.", res)
if ui.blocked_notice(res):
    st.stop()

s = res.scored
d = ui.replay_date(res)
s = s[(s["DATE"] <= d) & ~s["excluded"]]

c1, c2 = st.columns([3, 2])
period = c1.select_slider("Periode", ["30 hari", "90 hari", "180 hari", "1 tahun", "Semua"], value="180 hari")
days = {"30 hari": 30, "90 hari": 90, "180 hari": 180, "1 tahun": 365, "Semua": 10_000}[period]
cal = c2.multiselect("Filter kalender", ["Hari kerja", "Akhir pekan", "Hari libur"],
                     default=["Hari kerja", "Akhir pekan", "Hari libur"])
w = s[s["DATE"] > d - pd.Timedelta(days=days)]
w = w[w["context_calendar"].isin(cal)]

k = st.columns(4)
k[0].metric("Rata-rata konsumsi/hari", f"{w['TOTAL_BUILDING_ELECTRICITY'].mean():,.1f}", border=True)
k[1].metric("Total biaya periode", f"Rp{w['TOTAL_PRICE'].sum() / 1e6:,.1f} jt", border=True)
k[2].metric("Rata-rata biaya/hari", f"Rp{w['TOTAL_PRICE'].mean() / 1e6:,.2f} jt", border=True)
k[3].metric("Hari dianalisis", f"{len(w)}", border=True)

st.subheader("Konsumsi harian")
fig = go.Figure()
fig.add_trace(go.Scatter(x=w["DATE"], y=w["TOTAL_BUILDING_ELECTRICITY"], mode="lines", name="Konsumsi",
                         line=dict(color=ui.COLORS["actual"], width=1)))
fig.add_trace(go.Scatter(x=w["DATE"], y=w["TOTAL_BUILDING_ELECTRICITY"].rolling(7, min_periods=1).mean(),
                         name="Rata-rata 7 hari", line=dict(color=ui.COLORS["forecast"], width=2.5)))
hol = w[w["IS_HOLIDAY"] == 1]
fig.add_trace(go.Scatter(x=hol["DATE"], y=hol["TOTAL_BUILDING_ELECTRICITY"], mode="markers", name="Hari libur",
                         marker=dict(color="#9467bd", size=8)))
fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.15),
                  hovermode="x unified")
st.plotly_chart(fig)

a, b = st.columns(2)
with a:
    st.subheader("Biaya harian (LWBP + WBP)")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=w["DATE"], y=w["LWBP_PRICE"] / 1e6, name="LWBP", marker_color=ui.COLORS["lwbp"]))
    fig.add_trace(go.Bar(x=w["DATE"], y=w["WBP_PRICE"] / 1e6, name="WBP", marker_color=ui.COLORS["wbp"]))
    fig.update_layout(barmode="stack", height=320, yaxis_title="Rp juta", margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig)
with b:
    st.subheader("Pola per hari dalam minggu")
    names = {1: "Sen", 2: "Sel", 3: "Rab", 4: "Kam", 5: "Jum", 6: "Sab", 7: "Min"}
    ww = w.assign(Hari=w["DAY_OF_WEEK"].map(names))
    fig = px.box(ww, x="Hari", y="TOTAL_BUILDING_ELECTRICITY", category_orders={"Hari": list(names.values())},
                 color_discrete_sequence=[ui.COLORS["actual"]])
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Konsumsi")
    st.plotly_chart(fig)

st.subheader("Ringkasan bulanan")
m = s.assign(Bulan=s["DATE"].dt.to_period("M").dt.to_timestamp()).groupby("Bulan").agg(
    konsumsi_rata=("TOTAL_BUILDING_ELECTRICITY", "mean"), biaya_total=("TOTAL_PRICE", "sum"),
    wbp_share=("WBP_SHARE", "mean"), hari=("DATE", "count")).reset_index()
fig = go.Figure()
fig.add_trace(go.Bar(x=m["Bulan"], y=m["biaya_total"] / 1e6, name="Biaya total (Rp juta)", marker_color="#9ecae1"))
fig.add_trace(go.Scatter(x=m["Bulan"], y=m["konsumsi_rata"], name="Konsumsi rata-rata/hari", yaxis="y2",
                         line=dict(color=ui.COLORS["actual"], width=2.5)))
fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.2),
                  yaxis=dict(title="Rp juta"), yaxis2=dict(title="Konsumsi", overlaying="y", side="right"))
st.plotly_chart(fig)
st.caption("Hari berstatus *exclude* tidak dihitung. Bulan berjalan dihitung sampai tanggal replay.")
ui.unit_note()
