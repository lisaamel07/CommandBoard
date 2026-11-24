"""Halaman 8 - Report & Decision Note (O8: F10 ekspor ringkasan, action log, audit trail)."""
import pandas as pd
import streamlit as st

from core import store, ui

res = ui.result()
ui.page_header("Report & Decision Note", "Ringkasan mingguan/bulanan, action log tertutup (closed-loop), dan audit trail.", res)
if ui.blocked_notice(res):
    st.stop()

d = ui.replay_date(res)
s = res.scored[(res.scored["DATE"] <= d)]
dec = store.decisions_df()

t1, t2, t3, t4 = st.tabs(["Action log", "Ringkasan & ekspor", "Outcome KPI", "Audit trail"])

with t1:
    if dec.empty:
        st.info("Belum ada decision note. Buat dari halaman Anomaly & Recommendation (peran Facility Manager).")
    else:
        dec["overdue"] = (pd.to_datetime(dec["due_date"]) < d) & dec["status"].isin(["proposed", "validated"])
        st.dataframe(dec[["id", "alert_date", "severity", "confidence", "owner", "due_date", "status", "overdue",
                          "action", "note", "validation_result", "close_reason", "model_version", "updated_at"]],
                     hide_index=True, column_config={"overdue": st.column_config.CheckboxColumn("Overdue")})
        if ui.can("validate"):
            open_ = dec[~dec["status"].isin(["closed", "rejected"])]
            if len(open_):
                with st.form("update_action"):
                    st.markdown("**Perbarui action**")
                    did = st.selectbox("Action", open_["id"],
                                       format_func=lambda i: f"#{i} · {open_.set_index('id').at[i, 'alert_date']} · "
                                                             f"{open_.set_index('id').at[i, 'action'][:60]}")
                    vr = st.text_area("Hasil validasi teknis (evidence)")
                    close = st.checkbox("Tutup action", disabled=not ui.can("decide"),
                                        help="Hanya Facility Manager yang menutup action.")
                    reason = st.selectbox("Close reason", ["", "Penyebab terkonfirmasi & ditindaklanjuti",
                                                           "False alert (data/meter)", "Operasi normal (event/okupansi)",
                                                           "Tidak dapat disimpulkan"])
                    if st.form_submit_button("Simpan", type="primary"):
                        kw = {}
                        if vr.strip():
                            kw["validation_result"] = vr
                        if close:
                            if not reason or not (vr.strip() or open_.set_index("id").at[did, "validation_result"]):
                                st.error("Menutup action wajib menyertakan evidence validasi dan close reason.")
                                st.stop()
                            kw.update(status="closed", close_reason=reason)
                        if kw:
                            store.update_decision(int(did), ui.role(), **kw)
                            st.success("Action diperbarui.")
                            st.rerun()
        c = dec["status"].value_counts()
        k = st.columns(5)
        for col, stt in zip(k, store.STATUSES):
            col.metric(stt, int(c.get(stt, 0)), border=True)

with t2:
    freq = st.radio("Periode ringkasan", ["Mingguan", "Bulanan"], horizontal=True)
    rule = "W-SUN" if freq == "Mingguan" else "MS"
    g = s[~s["excluded"]].set_index("DATE")
    summ = pd.DataFrame({
        "konsumsi_total": g["TOTAL_BUILDING_ELECTRICITY"].resample(rule).sum(),
        "konsumsi_rata_hari": g["TOTAL_BUILDING_ELECTRICITY"].resample(rule).mean(),
        "forecast_total": g["forecast"].resample(rule).sum(min_count=1),
        "biaya_total_rp": g["TOTAL_PRICE"].resample(rule).sum(),
        "biaya_wbp_rp": g["WBP_PRICE"].resample(rule).sum(),
        "wbp_share": g["WBP_SHARE"].resample(rule).mean(),
        "pf_indikatif": g["PF_INDIKATIF"].resample(rule).mean(),
        "alert": g["is_alert"].resample(rule).sum(),
        "alert_tinggi_sedang": g["severity"].isin(["Tinggi", "Sedang"]).resample(rule).sum(),
        "hari_caution": (g["day_status"] == "caution").resample(rule).sum(),
    }).reset_index().rename(columns={"DATE": "periode"})
    summ["deviasi_vs_forecast"] = summ["konsumsi_total"] / summ["forecast_total"] - 1
    st.dataframe(summ.iloc[::-1], hide_index=True, column_config={
        "periode": st.column_config.DateColumn(format="YYYY-MM-DD"),
        "wbp_share": st.column_config.NumberColumn(format="percent"),
        "deviasi_vs_forecast": st.column_config.NumberColumn(format="percent"),
        "pf_indikatif": st.column_config.NumberColumn(format="%.3f"),
        "biaya_total_rp": st.column_config.NumberColumn(format="localized"),
        "biaya_wbp_rp": st.column_config.NumberColumn(format="localized")})
    c1, c2, c3 = st.columns(3)
    c1.download_button("Ekspor ringkasan (CSV)", summ.to_csv(index=False).encode("utf-8-sig"),
                       f"ringkasan_{freq.lower()}_{d:%Y%m%d}.csv", "text/csv", icon=":material/download:")
    alerts = s[s["is_alert"]][["DATE", "TOTAL_BUILDING_ELECTRICITY", "forecast", "residual", "z", "severity",
                               "confidence", "anomaly_score", "day_status", "blocked"]].copy()
    alerts["evidence"] = s.loc[alerts.index, "evidence"].map(" | ".join)
    c2.download_button("Ekspor alert log (CSV)", alerts.to_csv(index=False).encode("utf-8-sig"),
                       f"alert_log_{d:%Y%m%d}.csv", "text/csv", icon=":material/download:")
    c3.download_button("Ekspor decision log (CSV)", dec.to_csv(index=False).encode("utf-8-sig"),
                       f"decision_log_{d:%Y%m%d}.csv", "text/csv", icon=":material/download:",
                       disabled=dec.empty)

    # Decision note ringkas (markdown)
    last30 = s[s["DATE"] > d - pd.Timedelta(days=30)]
    md = [f"# Decision Note — Hotel Energy Command Board", f"Tanggal laporan: {d:%d %B %Y}",
          f"Model: {res.model_version} · Quality gate dataset: {res.gate} · Trust score: {res.quality.scores['Total']:.1f}", "",
          "## Ringkasan 30 hari", f"- Konsumsi rata-rata/hari: {last30['TOTAL_BUILDING_ELECTRICITY'].mean():,.1f}",
          f"- Biaya total: Rp{last30['TOTAL_PRICE'].sum():,.0f}", f"- WBP share rata-rata: {last30['WBP_SHARE'].mean():.1%}",
          f"- Alert: {int(last30['is_alert'].sum())} (Tinggi/Sedang: {int(last30['severity'].isin(['Tinggi', 'Sedang']).sum())})", "",
          "## Keputusan"]
    if dec.empty:
        md.append("- Belum ada keputusan tercatat.")
    for _, x in dec.iterrows():
        md.append(f"- [{x['alert_date']}] {x['status'].upper()} — {x['action']} (owner: {x['owner']}, due {x['due_date']})"
                  + (f"; ditutup: {x['close_reason']}" if x["close_reason"] else ""))
    md += ["", "## Batasan", "- Analitik harian, human-in-the-loop; bukan kontrol BAS/HVAC atau diagnosis perangkat.",
           "- Impact energi/biaya belum dapat diklaim sebelum pilot dengan data sebelum–sesudah."]
    st.download_button("Ekspor decision note (Markdown)", "\n".join(md).encode("utf-8"),
                       f"decision_note_{d:%Y%m%d}.md", "text/markdown", icon=":material/description:")

with t3:
    st.caption("Indikator output/outcome yang dapat diuji pada prototipe (Bab 3.8). Impact (kWh/hari, biaya, WBP share "
               "sebelum–sesudah) memerlukan pilot.")
    ok = s["forecast"].notna()
    alerts_ms = s[s["is_alert"] & s["severity"].isin(["Tinggi", "Sedang"]) & ~s["blocked"]]
    reviewed = dec["alert_date"].nunique() if len(dec) else 0
    closed = dec[dec["status"] == "closed"] if len(dec) else dec
    fa = (dec["close_reason"] == "False alert (data/meter)").sum() if len(dec) else 0
    rej = (dec["status"] == "rejected").sum() if len(dec) else 0
    k = st.columns(4)
    k[0].metric("Data-ready rate", f"{(s['day_status'] == 'ready').mean():.1%}", border=True)
    k[1].metric("Alert completeness", f"{(alerts_ms['forecast'].notna()).mean():.0%}" if len(alerts_ms) else "–",
                help="Alert Sedang/Tinggi yang memiliki residual, severity, confidence, evidence & rekomendasi.", border=True)
    k[2].metric("Alert Sedang/Tinggi ditinjau", f"{reviewed}/{len(alerts_ms)}", border=True)
    k[3].metric("False alert / ditolak", f"{fa + rej}", border=True,
                help="Umpan balik closed-loop untuk menilai threshold & model.")

with t4:
    au = store.audit_df()
    st.dataframe(au, hide_index=True)
    if ui.can("quality") or ui.can("decide"):
        with st.expander("Mode demo"):
            if st.button("Kosongkan decision & quality log", type="secondary"):
                store.reset_all(ui.role())
                st.rerun()
