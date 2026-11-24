"""Halaman 2 - Data Quality (O1: F1 validasi + F2 trust score + quality-decision log)."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import store, ui
from core.quality import DECISIONS, TRUST_CAUTION, TRUST_READY

res = ui.result()
ui.page_header("Data Quality", "Quality gate menentukan apakah forecast dan rekomendasi boleh diterbitkan (G1).", res)

# ---------------- Trust score ----------------
sc = res.quality.scores
cols = st.columns(5)
for col, k in zip(cols, ["Total", "Kelengkapan", "Validitas", "Konsistensi", "Kewajaran pola"]):
    col.metric(f"Trust score · {k}" if k == "Total" else k, f"{sc.get(k, 0):.1f}", border=True)
st.caption(f"Ambang gate: ready ≥ {TRUST_READY:.0f} tanpa isu kritis yang belum diputuskan; "
           f"caution ≥ {TRUST_CAUTION:.0f}; di bawahnya not-ready. Bobot tiap dimensi 25%.")

t1, t2, t3, t4 = st.tabs(["Quality checks", "Baris bermasalah & keputusan", "Rekonsiliasi total vs zona", "Ingestion log"])

with t1:
    st.dataframe(res.quality.checks[["id", "dimensi", "pemeriksaan", "jumlah", "status", "detail"]],
                 hide_index=True, column_config={"jumlah": st.column_config.NumberColumn("Jumlah")})
    st.markdown("**Data mentah vs data setelah quality decision** — TOTAL_BUILDING_ELECTRICITY")
    raw = res.ingest.df
    cl = res.clean
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=raw["DATE"], y=raw["TOTAL_BUILDING_ELECTRICITY"], name="Mentah",
                             line=dict(color="#bbbbbb")))
    fig.add_trace(go.Scatter(x=cl["DATE"], y=cl["TOTAL_BUILDING_ELECTRICITY"], name="Setelah keputusan",
                             line=dict(color=ui.COLORS["actual"])))
    fl = cl[cl["flag_severity"] == "critical"]
    fig.add_trace(go.Scatter(x=fl["DATE"], y=fl["TOTAL_BUILDING_ELECTRICITY"], mode="markers", name="Baris kritis",
                             marker=dict(color="#d62728", size=9, symbol="x")))
    log_y = st.toggle("Skala logaritmik", value=True, help="Lonjakan 2023-08-01 ~30x lipat menenggelamkan pola lain.")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.15),
                      yaxis_type="log" if log_y else "linear")
    st.plotly_chart(fig)

with t2:
    rf = res.quality.row_flags.copy()
    ov = store.get_quality_overrides()
    rf["keputusan"] = [ov.get(d.strftime("%Y-%m-%d"), dd) for d, dd in zip(rf["DATE"], rf["default_decision"])]
    st.markdown(f"**{len(rf)} tanggal ditandai** "
                f"({(rf['severity'] == 'critical').sum()} kritis, {(rf['severity'] == 'warning').sum()} peringatan). "
                "Default: kritis → *correct* (interpolasi waktu), peringatan → *keep*.")
    st.caption("keep = nilai asli dipakai · correct = kolom bermasalah diinterpolasi, hari berstatus caution · "
               "exclude = hari dikeluarkan dari training/metrik/KPI, berstatus not-ready (alert diblokir).")
    edited = st.data_editor(
        rf[["DATE", "severity", "columns", "reasons", "default_decision", "keputusan"]],
        hide_index=True, disabled=not ui.can("quality"), key="qd_editor",
        column_config={
            "DATE": st.column_config.DateColumn("Tanggal", format="YYYY-MM-DD", disabled=True),
            "severity": st.column_config.TextColumn("Severity", disabled=True),
            "columns": st.column_config.TextColumn("Kolom", disabled=True, width="medium"),
            "reasons": st.column_config.TextColumn("Alasan", disabled=True, width="large"),
            "default_decision": st.column_config.TextColumn("Default", disabled=True),
            "keputusan": st.column_config.SelectboxColumn("Keputusan", options=DECISIONS, required=True),
        })
    if ui.can("quality"):
        reason = st.text_input("Alasan perubahan keputusan (wajib dicatat di quality-decision log)")
        if st.button("Simpan keputusan & jalankan ulang pipeline", type="primary", icon=":material/save:"):
            changed = edited[edited["keputusan"] != rf["keputusan"]]
            if changed.empty:
                st.info("Tidak ada perubahan.")
            elif not reason.strip():
                st.error("Isi alasan terlebih dahulu.")
            else:
                for _, r in changed.iterrows():
                    store.set_quality_decision(r["DATE"].strftime("%Y-%m-%d"), r["keputusan"], reason, ui.role())
                st.success(f"{len(changed)} keputusan disimpan.")
                st.rerun()
    else:
        st.caption(":material/lock: Hanya peran **Analis Data** yang dapat mengubah quality decision.")
    qd = store.quality_decisions_df()
    if len(qd):
        st.markdown("**Quality-decision log**")
        st.dataframe(qd, hide_index=True)

with t3:
    rc = res.quality.recon
    st.markdown("TOTAL_BUILDING_ELECTRICITY **tidak sama** dengan Zone A+B+C, dan hampir tidak berkorelasi. "
                "Sesuai Bab 3.6, gap ditampilkan apa adanya — tidak dipaksa sama — sampai satuan dan cakupan "
                "meter diverifikasi dari metadata sumber.")
    cl = res.clean
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cl["DATE"], y=cl["TOTAL_BUILDING_ELECTRICITY"], name="Total gedung"))
    fig.add_trace(go.Scatter(x=cl["DATE"], y=cl["A_ELECTRICITY_USED"] + cl["B_ELECTRICITY_USED"] + cl["C_ELECTRICITY_USED"],
                             name="Zone A+B+C"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig)
    corr = cl["TOTAL_BUILDING_ELECTRICITY"].corr(cl["LWBP_USED"] + cl["WBP_USED"])
    corr_z = cl["TOTAL_BUILDING_ELECTRICITY"].corr(cl["A_ELECTRICITY_USED"] + cl["B_ELECTRICITY_USED"] + cl["C_ELECTRICITY_USED"])
    c1, c2 = st.columns(2)
    c1.metric("Korelasi total vs LWBP+WBP", f"{corr:.2f}", border=True)
    c2.metric("Korelasi total vs Zone A+B+C", f"{corr_z:.2f}", border=True)
    st.caption("Total gedung bergerak bersama LWBP+WBP (meter utama), bukan bersama zona tenant. "
               "Zona diperlakukan sebagai sub-meter dengan cakupan tersendiri.")

with t4:
    st.dataframe(pd.DataFrame(res.ingest.log), hide_index=True)
    st.caption(f"Sumber: `{ui.data_path().name}` · checksum sha256 `{res.ingest.checksum}`")
    if ui.can("quality"):
        st.markdown("**Unggah versi dataset lain** (schema harus sama)")
        up = st.file_uploader("CSV", type="csv")
        if up is not None:
            p = Path(__file__).resolve().parent.parent / "data" / "uploaded.csv"
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(up.getvalue())
            st.session_state["use_upload"] = True
            store.audit(ui.role(), "dataset", up.name, "upload", f"{len(up.getvalue())} bytes")
            st.success("Dataset diunggah. Pipeline dijalankan ulang.")
            st.rerun()
        if st.session_state.get("use_upload") and st.button("Kembali ke DATA_170225.csv"):
            st.session_state["use_upload"] = False
            st.rerun()
