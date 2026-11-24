"""Halaman 5 - Zone Analysis (O6: F8 kontribusi & deviasi Zone A-C)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.anomaly import ZONES

res = ui.result()
ui.page_header("Zone Analysis", "Kontribusi dan deviasi Zone A–C tanpa menebak identitas tenant.", res)
if ui.blocked_notice(res):
    st.stop()

d = ui.replay_date(res)
s = res.scored[(res.scored["DATE"] <= d) & ~res.scored["excluded"]]
days = st.select_slider("Periode", [30, 60, 90, 180, 365], value=90, format_func=lambda x: f"{x} hari")
w = s[s["DATE"] > d - pd.Timedelta(days=days)]

st.info("Zone A–C adalah sub-meter dengan cakupan sendiri: jumlahnya **tidak** sama dengan total gedung (lihat cek K3). "
        "Kontribusi di bawah ini dihitung terhadap **jumlah ketiga zona**, dan deviasi tiap zona dibandingkan dengan "
        "baseline 28 hari zona itu sendiri.", icon=":material/info:")

k = st.columns(3)
tot = sum(w[c].sum() for c in ZONES.values())
for col, (z, c) in zip(k, ZONES.items()):
    today_z = res.scored.set_index("DATE").at[d, f"z_{z}"]
    col.metric(z, f"{w[c].sum() / tot:.1%} kontribusi",
               f"hari ini z = {today_z:+.1f}" if pd.notna(today_z) else None,
               delta_color="inverse", border=True,
               help=f"Rata-rata {w[c].mean():,.1f}/hari; biaya Rp{w[c.replace('USED', 'PRICE')].sum() / 1e6:,.1f} jt pada periode ini.")

a, b = st.columns([3, 2])
with a:
    st.subheader("Konsumsi harian per zona")
    fig = go.Figure()
    for z, c in ZONES.items():
        fig.add_trace(go.Scatter(x=w["DATE"], y=w[c], name=z, line=dict(color=ui.COLORS[z], width=1.5)))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.15),
                      hovermode="x unified")
    st.plotly_chart(fig)
with b:
    st.subheader("Komposisi bulanan")
    m = w.assign(Bulan=w["DATE"].dt.to_period("M").astype(str)).groupby("Bulan")[list(ZONES.values())].sum()
    m.columns = list(ZONES)
    mm = (m.div(m.sum(axis=1), axis=0)).reset_index().melt(id_vars="Bulan", var_name="Zona", value_name="Porsi")
    fig = px.bar(mm, x="Bulan", y="Porsi", color="Zona", color_discrete_map=ui.COLORS)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), yaxis_tickformat=".0%",
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig)

st.subheader("Peta deviasi zona (robust z terhadap baseline 28 hari)")
hz = w.set_index("DATE")[[f"z_{z}" for z in ZONES]].iloc[-60:].T
hz.index = list(ZONES)
fig = px.imshow(hz.clip(-5, 5), aspect="auto", color_continuous_scale="RdBu_r", zmin=-5, zmax=5,
                labels=dict(color="z"))
fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig)
st.caption("Merah = di atas baseline zona, biru = di bawah. |z| ≥ 2 dipakai sebagai evidence pada anomaly scoring. "
           "60 hari terakhir dari periode terpilih.")

top = w.loc[w["top_zone"] != "", ["DATE", "top_zone", "severity", "residual_pct"]].tail(15).iloc[::-1]
if len(top):
    st.markdown("**Hari dengan deviasi zona signifikan (terbaru)**")
    st.dataframe(top, hide_index=True, column_config={
        "DATE": st.column_config.DateColumn("Tanggal", format="DD MMM YYYY"), "top_zone": "Zona",
        "severity": "Severity total gedung",
        "residual_pct": st.column_config.NumberColumn("Deviasi total vs forecast", format="percent")})
