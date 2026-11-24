"""Halaman 6 - Forecasting (O3: F4 perbandingan model, F5 actual vs forecast, F12 explainability)."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import ui
from core.forecast import MODEL_LABEL, NOT_RUN, TRAIN_END, VAL_END

res = ui.result()
ui.page_header("Forecasting", "Perbandingan model dengan split kronologis; baseline wajib: seasonal naive (G2).", res)
if ui.blocked_notice(res):
    st.stop()

fc = res.forecast
s = res.scored
d = ui.replay_date(res)

(st.success if fc.gate_g2 else st.warning)(f"**Model terpilih: {MODEL_LABEL[fc.selected]}.** {fc.gate_note}",
                                           icon=":material/model_training:")
st.caption(f"Split kronologis — train: s.d. {TRAIN_END:%d %b %Y} · validation: s.d. {VAL_END:%d %b %Y} · "
           f"test: Jan–Jun 2025. Aturan pemilihan: MAE validation terendah; bila selisih ≤ 2%, dipilih model paling "
           f"sederhana (Bab 5.5). Test dipakai hanya untuk pelaporan, bukan pemilihan.")

st.subheader("Perbandingan model")
m = fc.metrics.copy()
st.dataframe(
    m[["Model", "val_MAE", "val_RMSE", "val_sMAPE", "val_skill_vs_snaive", "test_MAE", "test_RMSE", "test_sMAPE",
       "test_skill_vs_snaive", "terpilih"]],
    hide_index=True,
    column_config={
        "val_MAE": st.column_config.NumberColumn("Val MAE", format="%.1f"),
        "val_RMSE": st.column_config.NumberColumn("Val RMSE", format="%.1f"),
        "val_sMAPE": st.column_config.NumberColumn("Val sMAPE %", format="%.1f"),
        "val_skill_vs_snaive": st.column_config.NumberColumn("Val skill vs s-naive", format="percent"),
        "test_MAE": st.column_config.NumberColumn("Test MAE", format="%.1f"),
        "test_RMSE": st.column_config.NumberColumn("Test RMSE", format="%.1f"),
        "test_sMAPE": st.column_config.NumberColumn("Test sMAPE %", format="%.1f"),
        "test_skill_vs_snaive": st.column_config.NumberColumn("Test skill vs s-naive", format="percent"),
        "terpilih": st.column_config.CheckboxColumn("Terpilih"),
    })
with st.expander("Kandidat yang belum dijalankan pada MVP"):
    for k, v in NOT_RUN.items():
        st.markdown(f"- **{k}** — {v}")

st.subheader("Validation & test: aktual vs model")
sp = fc.split_preds
pick = st.multiselect("Model ditampilkan", list(MODEL_LABEL), default=["seasonal_naive", fc.selected],
                      format_func=MODEL_LABEL.get)
act = s[s["DATE"] > TRAIN_END][["DATE", "TOTAL_BUILDING_ELECTRICITY"]]
fig = go.Figure()
fig.add_trace(go.Scatter(x=act["DATE"], y=act["TOTAL_BUILDING_ELECTRICITY"], name="Aktual",
                         line=dict(color=ui.COLORS["actual"], width=1.5)))
for name in pick:
    p = sp[sp["model"] == name]
    fig.add_trace(go.Scatter(x=p["DATE"], y=p["forecast"], name=MODEL_LABEL[name], line=dict(width=1.5, dash="dot")))
fig.add_vline(x=VAL_END, line_dash="dash", line_color="gray")
fig.add_annotation(x=VAL_END, y=1, yref="paper", text="validation | test", showarrow=False, yshift=10)
fig.update_layout(height=360, margin=dict(l=10, r=10, t=25, b=10), legend=dict(orientation="h", y=-0.15),
                  hovermode="x unified")
st.plotly_chart(fig)

st.subheader("Forecast operasional (rolling-origin, refit tiap bulan)")
st.caption("Untuk setiap bulan, model dilatih ulang hanya dengan data sebelum bulan tersebut, sehingga setiap nilai "
           "forecast bersifat out-of-sample. Interval 90% diambil dari kuantil residual validation.")
w = s[(s["DATE"] <= d) & (s["DATE"] > d - pd.Timedelta(days=120))]
fig = go.Figure()
fig.add_trace(go.Scatter(x=pd.concat([w["DATE"], w["DATE"][::-1]]), y=pd.concat([w["hi"], w["lo"][::-1]]),
                         fill="toself", fillcolor=ui.COLORS["band"], line=dict(width=0), name="Interval 90%"))
fig.add_trace(go.Scatter(x=w["DATE"], y=w["forecast"], name="Forecast", line=dict(color=ui.COLORS["forecast"], dash="dash")))
fig.add_trace(go.Scatter(x=w["DATE"], y=w["TOTAL_BUILDING_ELECTRICITY"], name="Aktual", line=dict(color=ui.COLORS["actual"])))
fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.15),
                  hovermode="x unified")
st.plotly_chart(fig)
ok = s["forecast"].notna() & ~s["excluded"] & (s["DATE"] <= d)
inside = ((s.loc[ok, "TOTAL_BUILDING_ELECTRICITY"] >= s.loc[ok, "lo"]) & (s.loc[ok, "TOTAL_BUILDING_ELECTRICITY"] <= s.loc[ok, "hi"])).mean()
k = st.columns(3)
k[0].metric("Cakupan interval 90% (s.d. replay)", f"{inside:.0%}", border=True,
            help="Persentase hari dengan aktual di dalam interval. Target ~90%.")
k[1].metric("σ residual (robust, validation)", f"{fc.sigma:,.1f}", border=True,
            help="Dipakai untuk z-score anomali: z = residual / σ.")
k[2].metric("Interval residual 5%–95%", f"{fc.q_low:,.0f} s.d. {fc.q_high:,.0f}", border=True)

a, b = st.columns(2)
with a:
    st.subheader("Distribusi residual")
    r = s.loc[ok, "residual"]
    fig = px.histogram(r, nbins=50, color_discrete_sequence=[ui.COLORS["actual"]])
    fig.update_layout(height=300, showlegend=False, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Aktual − forecast")
    st.plotly_chart(fig)
with b:
    st.subheader("Explainability (F12)")
    if fc.importance is not None:
        imp = fc.importance.head(10).iloc[::-1]
        fig = px.bar(imp, x="bobot", y="fitur", orientation="h", color_discrete_sequence=[ui.COLORS["forecast"]])
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig)
    else:
        st.info(f"Model terpilih ({MODEL_LABEL[fc.selected]}) sudah transparan dengan sendirinya: forecast = "
                + {"moving_average_7": "rata-rata konsumsi 7 hari terakhir.",
                   "seasonal_naive": "konsumsi pada hari yang sama minggu lalu.",
                   "naive": "konsumsi kemarin."}.get(fc.selected, "-")
                + " Feature importance hanya ditampilkan bila model berbasis fitur terpilih dan stabil.")
        ridge_row = fc.metrics.set_index("model").loc["ridge"]
        st.caption(f"Pembanding: Ridge val MAE {ridge_row['val_MAE']:.1f} — selisihnya di dalam toleransi 2%, "
                   "sehingga model yang lebih sederhana dipilih.")
