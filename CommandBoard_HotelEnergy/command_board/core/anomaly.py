"""F6 - Residual, threshold, severity, confidence, evidence (O4 Anomaly Panel).

Anomaly score menggabungkan besarnya residual (aktual - forecast) dengan
jumlah bukti kontekstual: WBP share, KVARh/faktor daya indikatif, biaya,
dan deviasi Zone A-C terhadap baseline 28 hari masing-masing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .forecast import TARGET

ZONES = {"Zone A": "A_ELECTRICITY_USED", "Zone B": "B_ELECTRICITY_USED", "Zone C": "C_ELECTRICITY_USED"}
CTX_WINDOW = 28
CTX_Z = 2.0
PF_LIMIT = 0.85
SEV_ORDER = {"Tinggi": 3, "Sedang": 2, "Rendah": 1, "Normal": 0}


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    kwh = d["LWBP_USED"] + d["WBP_USED"]
    d["ENERGY_LWBP_WBP"] = kwh
    d["WBP_SHARE"] = np.where(kwh > 0, d["WBP_USED"] / kwh, np.nan)
    d["WBP_COST_SHARE"] = np.where(d["TOTAL_PRICE"] > 0, d["WBP_PRICE"] / d["TOTAL_PRICE"], np.nan)
    d["PF_INDIKATIF"] = kwh / np.sqrt(kwh ** 2 + d["KVARH_USED"].clip(lower=0) ** 2)
    d["ZONE_SUM"] = sum(d[c] for c in ZONES.values())
    return d


def rolling_z(s: pd.Series, window: int = CTX_WINDOW) -> pd.Series:
    base = s.shift(1).rolling(window, min_periods=14)
    med = base.median()
    mad = (s.shift(1) - med).abs().rolling(window, min_periods=14).median()
    scale = (1.4826 * mad).replace(0, np.nan)
    return (s - med) / scale


def score_anomalies(df: pd.DataFrame, preds: pd.DataFrame, sigma: float, gate_g2: bool,
                    k_low: float = 2.0, k_med: float = 3.0, k_high: float = 4.0) -> pd.DataFrame:
    d = add_derived(df).merge(preds[["DATE", "forecast", "lo", "hi"]], on="DATE", how="left")
    d["residual"] = d[TARGET] - d["forecast"]
    d["residual_pct"] = d["residual"] / d["forecast"]
    d["z"] = d["residual"] / sigma
    az = d["z"].abs()
    d["severity"] = np.select([az >= k_high, az >= k_med, az >= k_low], ["Tinggi", "Sedang", "Rendah"], "Normal")
    d.loc[d["forecast"].isna(), "severity"] = "Normal"

    # ---- konteks / evidence ----
    d["z_wbp_share"] = rolling_z(d["WBP_SHARE"])
    d["z_kvarh"] = rolling_z(d["KVARH_USED"])
    d["z_cost"] = rolling_z(d["TOTAL_PRICE"])
    for zname, col in ZONES.items():
        d[f"z_{zname}"] = rolling_z(d[col])

    ev_list, top_zone = [], []
    for _, r in d.iterrows():
        ev = []
        up = (r["residual"] or 0) >= 0
        if r["z_wbp_share"] >= CTX_Z:
            ev.append(f"WBP share naik ({r['WBP_SHARE']:.1%}, z={r['z_wbp_share']:.1f})")
        if r["z_kvarh"] >= CTX_Z or (r["PF_INDIKATIF"] < PF_LIMIT):
            ev.append(f"KVARh tinggi ({r['KVARH_USED']:.2f}; PF indikatif {r['PF_INDIKATIF']:.2f})")
        if pd.notna(r["z_cost"]) and ((up and r["z_cost"] >= CTX_Z) or (not up and r["z_cost"] <= -CTX_Z)):
            ev.append(f"Biaya harian menyimpang (Rp{r['TOTAL_PRICE']:,.0f}, z={r['z_cost']:.1f})")
        zs = {z: r[f"z_{z}"] for z in ZONES if pd.notna(r[f"z_{z}"])}
        tz = max(zs, key=lambda k: abs(zs[k])) if zs else ""
        if tz and abs(zs[tz]) >= CTX_Z:
            ev.append(f"{tz} menyimpang dari baseline 28 hari (z={zs[tz]:.1f})")
        else:
            tz = ""
        ev_list.append(ev)
        top_zone.append(tz)
    d["evidence"] = ev_list
    d["n_evidence"] = d["evidence"].map(len)
    d["top_zone"] = top_zone
    d["context_calendar"] = np.select(
        [d["IS_HOLIDAY"] == 1, d["IS_WEEKEND"] == 1], ["Hari libur", "Akhir pekan"], "Hari kerja")

    # ---- confidence (G4 bukti kontekstual, G2 model, G1 data) ----
    level = np.clip(d["n_evidence"], 0, 2)            # 0 rendah, 1 sedang, 2 tinggi
    level = level - (d["day_status"] == "caution").astype(int) - int(not gate_g2)
    level = np.clip(level, 0, 2)
    d["confidence"] = np.array(["Rendah", "Sedang", "Tinggi"])[level]

    # ---- anomaly score 0-100 (prioritas) ----
    d["anomaly_score"] = np.clip(az / k_high * 70 + 10 * d["n_evidence"], 0, 100).fillna(0).round(0)
    d.loc[d["severity"] == "Normal", "anomaly_score"] = np.minimum(d["anomaly_score"], 30)

    d["is_alert"] = d["severity"] != "Normal"
    d["blocked"] = d["is_alert"] & (d["day_status"] == "not-ready")
    d["direction"] = np.where(d["residual"] >= 0, "Di atas forecast", "Di bawah forecast")
    return d


def sensitivity(d: pd.DataFrame, ks=(1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)) -> pd.DataFrame:
    """Uji sensitivitas threshold (pengganti precision/recall karena tidak ada label ground-truth)."""
    ok = d["forecast"].notna() & (d["day_status"] != "not-ready")
    n = int(ok.sum())
    rows = []
    for k in ks:
        flag = ok & (d["z"].abs() >= k)
        rows.append({"k (x sigma)": k, "jumlah alert": int(flag.sum()),
                     "alert per bulan": flag.sum() / max(n / 30.4, 1),
                     "% hari": 100 * flag.sum() / max(n, 1),
                     "dengan >=1 evidence": int((flag & (d["n_evidence"] > 0)).sum())})
    return pd.DataFrame(rows)
