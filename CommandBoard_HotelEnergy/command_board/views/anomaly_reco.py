"""Halaman 7 - Anomaly & Recommendation (O4 + O7: F6 scoring, F9 bounded recommendation, G1-G6)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import store, ui
from core.anomaly import SEV_ORDER, sensitivity
from core.reco import evidence_gates, recommend

res = ui.result()
ui.page_header("Anomaly & Recommendation",
               "Residual + konteks → severity, confidence, evidence → rekomendasi investigatif → keputusan manusia.", res)
if ui.blocked_notice(res):
    st.stop()

k_low, k_med, k_high = st.session_state.get("k", (2.0, 3.0, 4.0))
s = res.scored
d = ui.replay_date(res)
status_by_date = store.latest_status_by_date()

# ---------------- Threshold & sensitivitas ----------------
with st.expander("Threshold & uji sensitivitas", expanded=False):
    st.caption("Tidak ada label ground-truth anomali, sehingga threshold dievaluasi lewat sensitivitas jumlah alert "
               "(Bab 5.4). z = (aktual − forecast) / σ residual validation.")
    c1, c2 = st.columns([2, 3])
    with c1:
        lo, hi = st.slider("Rendah ≥ k · Tinggi ≥ k", 1.0, 6.0, (k_low, k_high), 0.5, disabled=not ui.can("threshold"))
        med = st.slider("Sedang (= threshold material G3) ≥ k", 1.0, 6.0, k_med, 0.5, disabled=not ui.can("threshold"))
        if ui.can("threshold"):
            if st.button("Terapkan threshold", icon=":material/tune:"):
                if not lo <= med <= hi:
                    st.error("Harus Rendah ≤ Sedang ≤ Tinggi.")
                else:
                    st.session_state["k"] = (lo, med, hi)
                    store.audit(ui.role(), "threshold", "-", "update", f"k={lo}/{med}/{hi}")
                    st.rerun()
        else:
            st.caption(":material/lock: Hanya Analis Data yang dapat mengubah threshold.")
    with c2:
        st.dataframe(sensitivity(s[s["DATE"] <= d]), hide_index=True,
                     column_config={"alert per bulan": st.column_config.NumberColumn(format="%.1f"),
                                    "% hari": st.column_config.NumberColumn(format="%.1f")})

# ---------------- Daftar alert ----------------
a = s[(s["DATE"] <= d) & s["is_alert"]].copy()
a["status"] = [("diblokir" if b else status_by_date.get(x.strftime("%Y-%m-%d"), "proposed"))
               for x, b in zip(a["DATE"], a["blocked"])]
f1, f2, f3, f4 = st.columns(4)
days = f1.selectbox("Periode", [30, 90, 180, 365, 10_000], index=1,
                    format_func=lambda x: "Semua" if x > 1000 else f"{x} hari")
sev = f2.multiselect("Severity", ["Tinggi", "Sedang", "Rendah"], default=["Tinggi", "Sedang", "Rendah"])
conf = f3.multiselect("Confidence", ["Tinggi", "Sedang", "Rendah"], default=["Tinggi", "Sedang", "Rendah"])
stt = f4.multiselect("Status review", store.STATUSES + ["diblokir"], default=store.STATUSES + ["diblokir"])
a = a[(a["DATE"] > d - pd.Timedelta(days=days)) & a["severity"].isin(sev) & a["confidence"].isin(conf)
      & a["status"].isin(stt)]
a = a.assign(sev_rank=a["severity"].map(SEV_ORDER)).sort_values(["DATE"], ascending=False)

left, right = st.columns([2, 3])
with left:
    st.subheader(f"Alert ({len(a)})")
    if a.empty:
        st.success("Tidak ada alert pada filter ini.")
        st.stop()
    event = st.dataframe(
        a[["DATE", "severity", "confidence", "anomaly_score", "residual_pct", "status"]],
        hide_index=True, height=520, on_select="rerun", selection_mode="single-row", key="alert_table",
        column_config={
            "DATE": st.column_config.DateColumn("Tanggal", format="DD MMM YY"),
            "severity": "Severity", "confidence": "Conf.",
            "anomaly_score": st.column_config.ProgressColumn("Skor", min_value=0, max_value=100, format="%d"),
            "residual_pct": st.column_config.NumberColumn("Deviasi", format="percent"),
            "status": "Status"})
    sel = event.selection.rows
    r = a.iloc[sel[0]] if sel else a.sort_values(["anomaly_score"], ascending=False).iloc[0]
    if not sel:
        st.caption("Pilih baris untuk melihat detail. Default: skor tertinggi.")

# ---------------- Detail alert ----------------
with right:
    ds = r["DATE"].strftime("%Y-%m-%d")
    st.subheader(f"Detail · {r['DATE']:%A, %d %B %Y}")
    b = st.columns(4)
    b[0].metric("Aktual", f"{r['TOTAL_BUILDING_ELECTRICITY']:,.1f}", border=True)
    b[1].metric("Forecast", f"{r['forecast']:,.1f}", border=True)
    b[2].metric("Residual", f"{r['residual']:+,.1f}", f"{r['residual_pct']:+.1%} · z {r['z']:+.2f}",
                delta_color="inverse", border=True)
    b[3].metric("Skor anomali", f"{r['anomaly_score']:.0f}", f"{r['severity']} · conf. {r['confidence']}",
                delta_color="off", border=True)
    st.caption(f"Konteks kalender: {r['context_calendar']} · status data: {r['day_status']}"
               + (f" ({r['flag_reasons']})" if r["flag_reasons"] else ""))

    t1, t2, t3, t4 = st.tabs(["Evidence", "Evidence gate G1–G6", "Rekomendasi", "Decision note"])
    with t1:
        if r["evidence"]:
            for e in r["evidence"]:
                st.markdown(f"- {e}")
        else:
            st.markdown("_Tidak ada bukti kontekstual yang mendukung (confidence rendah)._")
        w = s[(s["DATE"] >= r["DATE"] - pd.Timedelta(days=21)) & (s["DATE"] <= r["DATE"] + pd.Timedelta(days=7))]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pd.concat([w["DATE"], w["DATE"][::-1]]), y=pd.concat([w["hi"], w["lo"][::-1]]),
                                 fill="toself", fillcolor=ui.COLORS["band"], line=dict(width=0), name="Interval"))
        fig.add_trace(go.Scatter(x=w["DATE"], y=w["forecast"], name="Forecast", line=dict(color=ui.COLORS["forecast"], dash="dash")))
        fig.add_trace(go.Scatter(x=w["DATE"], y=w["TOTAL_BUILDING_ELECTRICITY"], name="Aktual", line=dict(color=ui.COLORS["actual"])))
        fig.add_vline(x=r["DATE"], line_color="#d62728", line_dash="dot")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig)
        ctx = pd.DataFrame({
            "Indikator": ["WBP share", "KVARh", "Biaya", "Zone A", "Zone B", "Zone C"],
            "Nilai": [f"{r['WBP_SHARE']:.1%}", f"{r['KVARH_USED']:.2f}", f"Rp{r['TOTAL_PRICE']:,.0f}",
                      f"{r['A_ELECTRICITY_USED']:,.1f}", f"{r['B_ELECTRICITY_USED']:,.1f}", f"{r['C_ELECTRICITY_USED']:,.1f}"],
            "z vs baseline 28 hari": [r["z_wbp_share"], r["z_kvarh"], r["z_cost"], r["z_Zone A"], r["z_Zone B"], r["z_Zone C"]]})
        st.dataframe(ctx, hide_index=True, column_config={
            "z vs baseline 28 hari": st.column_config.NumberColumn(format="%+.2f")})

    with t2:
        gates = pd.DataFrame(evidence_gates(r, res.forecast.gate_g2, k_med, status_by_date.get(ds)))
        gates["lolos"] = gates["lolos"].map({True: "✅", False: "⛔"})
        st.dataframe(gates, hide_index=True, column_config={"lolos": "Status", "respon": st.column_config.TextColumn("Respons sistem", width="large")})

    recs = recommend(r)
    with t3:
        if r["blocked"]:
            st.error("Diblokir oleh G1: data hari ini tidak layak. Rekomendasi tidak diterbitkan.", icon=":material/block:")
        else:
            for i, rc in enumerate(recs, 1):
                with st.container(border=True):
                    st.markdown(f"**{i}. {rc['aksi']}**")
                    st.caption(f"Alasan: {rc['alasan']}  \nBatasan: {rc['batasan']}")

    with t4:
        hist = store.decisions_df()
        hist = hist[hist["alert_date"] == ds]
        if len(hist):
            st.dataframe(hist[["id", "updated_at", "owner", "due_date", "status", "action", "validation_result", "close_reason"]],
                         hide_index=True)
        if r["blocked"]:
            st.info("Alert diblokir — decision note tidak dapat dibuat sampai data diperbaiki.")
        elif ui.can("decide"):
            with st.form(f"dn_{ds}", clear_on_submit=True):
                st.markdown("**Buat decision note** (G6 – human approval)")
                c1, c2, c3 = st.columns(3)
                owner = c1.text_input("Owner", placeholder="mis. Supervisor ME")
                due = c2.date_input("Due date", value=r["DATE"] + pd.Timedelta(days=1))
                prio = c3.selectbox("Prioritas", ["Tinggi", "Sedang", "Rendah"],
                                    index=["Tinggi", "Sedang", "Rendah"].index(r["severity"]))
                action = st.selectbox("Tindakan", [rc["aksi"] for rc in recs] + ["Lainnya (tulis di catatan)"])
                status = st.radio("Keputusan", ["validated", "monitor", "rejected"], horizontal=True,
                                  captions=["tindak lanjut", "pantau", "tolak (false alert)"])
                note = st.text_area("Catatan / alasan keputusan")
                if st.form_submit_button("Simpan decision note", type="primary", icon=":material/save:"):
                    if not owner.strip() or not note.strip():
                        st.error("Owner dan catatan wajib diisi (accountability).")
                    else:
                        store.add_decision(alert_date=ds, role=ui.role(), owner=owner, due_date=str(due), priority=prio,
                                           status=status, action=action, note=note, severity=r["severity"],
                                           confidence=r["confidence"], model_version=res.model_version,
                                           trust_status=r["day_status"])
                        st.success("Decision note tersimpan dan tercatat di audit trail.")
                        st.rerun()
        else:
            st.caption(":material/lock: Hanya Facility Manager yang membuat decision note. "
                       "Staf Teknis mengisi hasil validasi di halaman Report & Decision Note.")
