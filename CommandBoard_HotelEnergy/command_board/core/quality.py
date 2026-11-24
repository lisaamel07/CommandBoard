"""F1-F2 - Quality checks, trust score, quality gate (O1 Data Quality Panel).

Empat dimensi trust score sesuai laporan: kelengkapan, validitas, konsistensi,
dan kewajaran pola. Hasil per baris dipakai untuk gate harian
(ready / caution / not-ready) dan quality-decision log (keep/correct/exclude).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .ingest import NUMERIC_COLS

USAGE_COLS = ["LWBP_USED", "WBP_USED", "KVARH_USED", "TOTAL_BUILDING_ELECTRICITY",
              "A_ELECTRICITY_USED", "B_ELECTRICITY_USED", "C_ELECTRICITY_USED"]
PRICE_PAIRS = {  # harga : pemakaian -> cek tarif per unit konstan
    "LWBP_PRICE": "LWBP_USED", "WBP_PRICE": "WBP_USED",
    "A_ELECTRICITY_PRICE": "A_ELECTRICITY_USED",
    "B_ELECTRICITY_PRICE": "B_ELECTRICITY_USED",
    "C_ELECTRICITY_PRICE": "C_ELECTRICITY_USED",
}

Z_SUSPICIOUS = 6.0   # robust z > 6  -> warning (dicurigai, tetap dipakai)
Z_EXTREME = 20.0     # robust z > 20 -> kritis (artefak meter / akumulasi)

TRUST_READY = 95.0
TRUST_CAUTION = 85.0
DECISIONS = ["keep", "correct", "exclude"]


@dataclass
class QualityResult:
    checks: pd.DataFrame          # ringkasan pemeriksaan
    row_flags: pd.DataFrame       # baris bermasalah
    scores: dict                  # trust score per dimensi + total
    gate: str                     # ready / caution / not-ready (dataset)
    recon: pd.DataFrame           # gap rekonsiliasi total vs zona


def robust_z(s: pd.Series) -> pd.Series:
    med = s.median()
    mad = (s - med).abs().median()
    scale = 1.4826 * mad if mad > 0 else (s.std() or 1.0)
    return (s - med) / scale


def run_quality(df: pd.DataFrame, critical_ingest: bool = False) -> QualityResult:
    n = len(df)
    checks: list[dict] = []
    flags: dict[pd.Timestamp, dict] = {}

    def flag(date, sev, col, reason):
        f = flags.setdefault(date, {"severity": "warning", "columns": set(), "reasons": []})
        if sev == "critical":
            f["severity"] = "critical"
        f["columns"].add(col)
        f["reasons"].append(reason)

    # ---------- Kelengkapan ----------
    full = pd.date_range(df["DATE"].min(), df["DATE"].max(), freq="D")
    missing_dates = len(full.difference(df["DATE"]))
    dup = int(df["DATE"].duplicated().sum())
    nan_cells = int(df[NUMERIC_COLS].isna().sum().sum())
    checks += [
        dict(id="C1", dimensi="Kelengkapan", pemeriksaan="Tanggal kontinu (tanpa hari hilang)",
             jumlah=missing_dates, kritis=missing_dates > 0.05 * len(full),
             detail=f"{len(full)} hari diharapkan, {missing_dates} hilang"),
        dict(id="C2", dimensi="Kelengkapan", pemeriksaan="Missing value pada kolom numerik",
             jumlah=nan_cells, kritis=False, detail=f"{nan_cells} sel kosong"),
        dict(id="C3", dimensi="Kelengkapan", pemeriksaan="Duplikasi tanggal",
             jumlah=dup, kritis=dup > 0, detail=f"{dup} tanggal ganda"),
    ]

    # ---------- Validitas ----------
    neg_rows = 0
    for c in NUMERIC_COLS:
        bad = df[c] < 0
        for d, v in zip(df.loc[bad, "DATE"], df.loc[bad, c]):
            flag(d, "critical", c, f"{c} bernilai negatif ({v:,.2f})")
        neg_rows += int(bad.sum())
    dow = df["DATE"].dt.dayofweek + 1
    cal_bad = (df["DAY_OF_WEEK"] != dow) | (df["IS_WEEKEND"] != (dow >= 6).astype(int)) | \
              (df["MONTH"] != df["DATE"].dt.month)
    for d in df.loc[cal_bad, "DATE"]:
        flag(d, "critical", "DAY_OF_WEEK", "Fitur kalender tidak sesuai tanggal")
    checks += [
        dict(id="V1", dimensi="Validitas", pemeriksaan="Nilai negatif pada pemakaian/harga",
             jumlah=neg_rows, kritis=False, detail=f"{neg_rows} nilai negatif"),
        dict(id="V2", dimensi="Validitas", pemeriksaan="Konsistensi fitur kalender vs DATE",
             jumlah=int(cal_bad.sum()), kritis=False,
             detail="DAY_OF_WEEK (Senin=1), IS_WEEKEND, MONTH dicocokkan dengan tanggal"),
    ]

    # ---------- Konsistensi ----------
    psum = df["LWBP_PRICE"] + df["WBP_PRICE"]
    price_bad = (psum - df["TOTAL_PRICE"]).abs() > (1 + 0.001 * df["TOTAL_PRICE"].abs())
    for d in df.loc[price_bad, "DATE"]:
        flag(d, "critical", "TOTAL_PRICE", "TOTAL_PRICE != LWBP_PRICE + WBP_PRICE")
    checks.append(dict(id="K1", dimensi="Konsistensi", pemeriksaan="TOTAL_PRICE = LWBP_PRICE + WBP_PRICE",
                       jumlah=int(price_bad.sum()), kritis=False,
                       detail="Toleransi Rp1 + 0,1%"))

    tariff_rows = 0
    tariff_info = []
    for pc, uc in PRICE_PAIRS.items():
        ok = df[uc].abs() > 1e-9
        rate = df.loc[ok, pc] / df.loc[ok, uc]
        med = rate.median()
        bad = ok & ((df[pc] / df[uc].where(ok) - med).abs() > 0.01 * abs(med))
        for d in df.loc[bad, "DATE"]:
            flag(d, "warning", pc, f"Tarif per unit {pc} menyimpang dari median")
        tariff_rows += int(bad.sum())
        tariff_info.append(f"{pc.replace('_PRICE','')}: Rp{med:,.1f}/unit")
    checks.append(dict(id="K2", dimensi="Konsistensi", pemeriksaan="Tarif per unit konstan",
                       jumlah=tariff_rows, kritis=False, detail="; ".join(tariff_info)))

    zsum = df["A_ELECTRICITY_USED"] + df["B_ELECTRICITY_USED"] + df["C_ELECTRICITY_USED"]
    recon = pd.DataFrame({"DATE": df["DATE"], "TOTAL": df["TOTAL_BUILDING_ELECTRICITY"],
                          "ZONA_ABC": zsum, "GAP": df["TOTAL_BUILDING_ELECTRICITY"] - zsum})
    corr = df["TOTAL_BUILDING_ELECTRICITY"].corr(zsum, method="spearman")
    checks.append(dict(id="K3", dimensi="Konsistensi (info)",
                       pemeriksaan="Rekonsiliasi TOTAL_BUILDING vs Zone A+B+C",
                       jumlah=int((recon["GAP"].abs() > 0.05 * recon["TOTAL"].abs()).sum()), kritis=False,
                       detail=f"Median gap {recon['GAP'].median():,.1f}; korelasi Spearman {corr:.2f}. "
                              "Tidak dipaksa sama: satuan/cakupan perlu diverifikasi dari metadata."))

    # ---------- Kewajaran pola ----------
    ext_n, sus_n = 0, 0
    for c in NUMERIC_COLS:
        z = robust_z(df[c])
        ext = z.abs() > Z_EXTREME
        sus = (z.abs() > Z_SUSPICIOUS) & ~ext
        for d, zz, v in zip(df.loc[ext, "DATE"], z[ext], df.loc[ext, c]):
            flag(d, "critical", c, f"{c} ekstrem ({v:,.2f}; robust z={zz:,.0f})")
        for d, zz, v in zip(df.loc[sus, "DATE"], z[sus], df.loc[sus, c]):
            flag(d, "warning", c, f"{c} tidak wajar ({v:,.2f}; robust z={zz:,.1f})")
        ext_n += int(ext.sum())
        sus_n += int(sus.sum())
    checks += [
        dict(id="P1", dimensi="Kewajaran pola", pemeriksaan=f"Nilai ekstrem (robust z > {Z_EXTREME:.0f})",
             jumlah=ext_n, kritis=False, detail="Pola khas akumulasi/reset meter"),
        dict(id="P2", dimensi="Kewajaran pola",
             pemeriksaan=f"Nilai mencurigakan ({Z_SUSPICIOUS:.0f} < robust z <= {Z_EXTREME:.0f})",
             jumlah=sus_n, kritis=False, detail="Tetap dipakai, ditandai caution"),
    ]

    # pasangan lonjakan berlawanan (indikasi reset meter)
    pair_n = 0
    for c in USAGE_COLS:
        z = robust_z(df[c])
        for i in range(n - 1):
            if abs(z[i]) > Z_EXTREME and abs(z[i + 1]) > Z_EXTREME and np.sign(z[i]) != np.sign(z[i + 1]):
                pair_n += 1
                for j in (i, i + 1):
                    flag(df.at[j, "DATE"], "critical", c, f"{c}: lonjakan berpasangan +/- (indikasi reset meter)")
    checks.append(dict(id="P3", dimensi="Kewajaran pola", pemeriksaan="Lonjakan berpasangan +/- (reset meter)",
                       jumlah=pair_n, kritis=False, detail="Hari t dan t+1 ekstrem dengan tanda berlawanan"))

    checks_df = pd.DataFrame(checks)
    checks_df["status"] = np.where(checks_df["jumlah"] == 0, "Lolos",
                                   np.where(checks_df["kritis"], "Gagal (kritis)", "Ditandai"))
    checks_df.loc[checks_df["id"] == "K3", "status"] = np.where(
        checks_df.loc[checks_df["id"] == "K3", "jumlah"] > 0, "Gap dicatat", "Lolos")

    # ---------- Row flags ----------
    rows = []
    for d, f in sorted(flags.items()):
        rows.append(dict(DATE=d, severity=f["severity"], columns=", ".join(sorted(f["columns"])),
                         reasons="; ".join(dict.fromkeys(f["reasons"])),
                         default_decision="correct" if f["severity"] == "critical" else "keep"))
    row_flags = pd.DataFrame(rows, columns=["DATE", "severity", "columns", "reasons", "default_decision"])

    # ---------- Trust score ----------
    crit_rows = set(row_flags.loc[row_flags["severity"] == "critical", "DATE"])
    warn_rows = set(row_flags.loc[row_flags["severity"] == "warning", "DATE"])
    n_cells = n * len(NUMERIC_COLS)
    invalid_rows = df.loc[(df[NUMERIC_COLS] < 0).any(axis=1) | cal_bad, "DATE"].nunique()
    completeness = 100 * (1 - missing_dates / len(full)) * (1 - nan_cells / n_cells) * (1 - dup / n)
    validity = 100 * (1 - invalid_rows / n)
    consistency = 100 * (1 - (int(price_bad.sum()) + 0.5 * tariff_rows) / n)
    pattern_crit = len(crit_rows)
    pattern = 100 * (1 - (pattern_crit + 0.5 * len(warn_rows)) / n)
    total = 0.25 * (completeness + validity + consistency + pattern)
    scores = dict(Kelengkapan=completeness, Validitas=validity, Konsistensi=consistency,
                  **{"Kewajaran pola": pattern}, Total=total)

    critical_check_failed = critical_ingest or bool((checks_df["kritis"] & (checks_df["jumlah"] > 0)).any())
    # gate awal (sebelum quality decision); gate final dihitung ulang di pipeline
    gate = gate_from_score(total, critical_check_failed)
    if gate == "ready" and crit_rows:
        gate = "caution"

    return QualityResult(checks_df, row_flags, scores, gate, recon)


def apply_decisions(df: pd.DataFrame, row_flags: pd.DataFrame, overrides: dict[str, str]) -> pd.DataFrame:
    """Terapkan quality decision per tanggal, hasilkan data bersih + status gate harian.

    keep    : nilai asli dipakai; hari berstatus caution bila baris ditandai.
    correct : kolom bermasalah diinterpolasi waktu; hari berstatus caution (nilai hasil koreksi).
    exclude : kolom diinterpolasi hanya untuk kontinuitas fitur; hari dikeluarkan dari
              training/metrik/KPI dan berstatus not-ready (alert diblokir).
    """
    out = df.copy().set_index("DATE")
    out["flag_severity"] = ""
    out["flag_reasons"] = ""
    out["decision"] = ""
    out["excluded"] = False
    out["corrected"] = False

    for _, r in row_flags.iterrows():
        d = r["DATE"]
        dec = overrides.get(d.strftime("%Y-%m-%d"), r["default_decision"])
        out.at[d, "flag_severity"] = r["severity"]
        out.at[d, "flag_reasons"] = r["reasons"]
        out.at[d, "decision"] = dec
        if dec in ("correct", "exclude"):
            cols = [c for c in r["columns"].split(", ") if c in NUMERIC_COLS]
            # bila pemakaian dikoreksi, koreksi juga harga terkait agar tetap konsisten
            for pc, uc in PRICE_PAIRS.items():
                if uc in cols and pc not in cols:
                    cols.append(pc)
            if ("LWBP_PRICE" in cols or "WBP_PRICE" in cols) and "TOTAL_PRICE" not in cols:
                cols.append("TOTAL_PRICE")
            out.loc[d, cols] = np.nan
            out.at[d, "corrected"] = dec == "correct"
            out.at[d, "excluded"] = dec == "exclude"

    out[NUMERIC_COLS] = out[NUMERIC_COLS].interpolate(method="time", limit_direction="both")

    # gate harian
    out["day_status"] = "ready"
    out["day_trust"] = 100.0
    warn = (out["flag_severity"] != "") & (out["decision"] == "keep")
    crit_keep = (out["flag_severity"] == "critical") & (out["decision"] == "keep")
    out.loc[warn, ["day_status", "day_trust"]] = ["caution", 80.0]
    out.loc[out["corrected"], ["day_status", "day_trust"]] = ["caution", 75.0]
    out.loc[crit_keep | out["excluded"], ["day_status", "day_trust"]] = ["not-ready", 30.0]
    return out.reset_index()


def gate_from_score(score: float, has_unresolved_critical: bool) -> str:
    if has_unresolved_critical:
        return "not-ready"
    if score >= TRUST_READY:
        return "ready"
    if score >= TRUST_CAUTION:
        return "caution"
    return "not-ready"
