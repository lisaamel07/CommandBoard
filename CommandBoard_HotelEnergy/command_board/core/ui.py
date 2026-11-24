"""Helper tampilan bersama untuk semua halaman Streamlit."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from . import store
from .pipeline import DEFAULT_DATA, PipelineResult, run_pipeline

ROLES = ["Facility Manager", "Staf Teknis", "Analis Data", "Finance", "Manajemen"]
STATUS_COLOR = {"ready": "green", "caution": "orange", "not-ready": "red"}
SEV_COLOR = {"Tinggi": "red", "Sedang": "orange", "Rendah": "blue", "Normal": "gray"}
CONF_COLOR = {"Tinggi": "green", "Sedang": "orange", "Rendah": "gray"}

COLORS = {"actual": "#1f3b57", "forecast": "#e07b24", "band": "rgba(224,123,36,0.15)",
          "lwbp": "#4c78a8", "wbp": "#e45756", "kvarh": "#72b7b2",
          "Zone A": "#4c78a8", "Zone B": "#f58518", "Zone C": "#54a24b"}


def role() -> str:
    return st.session_state.get("role", ROLES[0])


def can(action: str) -> bool:
    r = role()
    return {
        "decide": r == "Facility Manager",
        "validate": r in ("Facility Manager", "Staf Teknis"),
        "quality": r == "Analis Data",
        "threshold": r == "Analis Data",
    }.get(action, False)


@st.cache_data(show_spinner="Menjalankan pipeline: quality gate -> forecast -> anomaly scoring ...")
def _cached(path: str, mtime: float, overrides: tuple, k_low: float, k_med: float, k_high: float) -> PipelineResult:
    return run_pipeline(path, dict(overrides), k_low, k_med, k_high)


def data_path() -> Path:
    up = Path(__file__).resolve().parent.parent / "data" / "uploaded.csv"
    if st.session_state.get("use_upload") and up.exists():
        return up
    return DEFAULT_DATA


def result() -> PipelineResult:
    p = data_path()
    ov = tuple(sorted(store.get_quality_overrides().items()))
    k = st.session_state.get("k", (2.0, 3.0, 4.0))
    return _cached(str(p), p.stat().st_mtime, ov, *k)


def replay_date(res: PipelineResult) -> pd.Timestamp:
    d = st.session_state.get("replay_date")
    last = res.clean["DATE"].max()
    return pd.Timestamp(d) if d else last


def status_badge(status: str, prefix: str = "") -> None:
    label = {"ready": "READY", "caution": "CAUTION", "not-ready": "NOT-READY"}.get(status, status)
    st.badge(f"{prefix}{label}", color=STATUS_COLOR.get(status, "gray"),
             icon={"ready": ":material/check_circle:", "caution": ":material/warning:",
                   "not-ready": ":material/block:"}.get(status))


def blocked_notice(res: PipelineResult) -> bool:
    """Tampilkan pesan & kembalikan True bila analitik diblokir (G1 tingkat dataset)."""
    if res.gate == "not-ready" or res.scored is None:
        st.error("**Quality gate: NOT-READY.** Forecast, anomaly, dan rekomendasi tidak diterbitkan. "
                 "Analis Data perlu memeriksa schema, tanggal, satuan, dan nilai invalid pada halaman Data Quality.",
                 icon=":material/block:")
        return True
    return False


def unit_note() -> None:
    st.caption("Satuan konsumsi mengikuti dataset asli (TOTAL_BUILDING_ELECTRICITY, LWBP/WBP, Zone A-C memakai "
               "skala berbeda dan belum terverifikasi dari metadata). Biaya dalam Rupiah sesuai kolom *_PRICE.")


def page_header(title: str, subtitle: str, res: PipelineResult | None = None) -> None:
    st.title(title)
    st.caption(subtitle)
    if res is not None:
        d = replay_date(res)
        c1, c2, c3 = st.columns([2, 2, 3])
        with c1:
            status_badge(res.gate, "Dataset: ")
        if res.scored is not None and d in set(res.clean["DATE"]):
            with c2:
                status_badge(res.clean.set_index("DATE").at[d, "day_status"], f"{d:%d %b %Y}: ")
        with c3:
            st.caption(f"Model: `{res.model_version}` · Peran: **{role()}**")
