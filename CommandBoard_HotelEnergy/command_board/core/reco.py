"""F9 - Bounded recommendation + Evidence Gate G1-G6 (O7 Recommendation Panel).

Rekomendasi hanya memakai kata kerja investigatif: periksa, validasi,
bandingkan, monitor, eskalasi. Sistem tidak mengubah korelasi menjadi diagnosis.
"""
from __future__ import annotations

import pandas as pd

LIMIT_DAILY = "Data harian tidak menunjukkan jam terjadinya beban; perlu log operasional untuk memastikan penyebab."


def recommend(r: pd.Series) -> list[dict]:
    recs: list[dict] = []
    ev = " | ".join(r["evidence"])
    if r["severity"] == "Rendah":
        recs.append(dict(aksi="Monitor 3 hari berikutnya",
                         alasan=f"Deviasi {r['residual_pct']:+.1%} masih di bawah threshold material (G3).",
                         batasan="Belum cukup untuk membuat action prioritas."))
        if r["n_evidence"] == 0:
            return recs

    if r["residual"] < 0:
        recs.append(dict(aksi="Validasi pembacaan meter dan kelengkapan pencatatan hari ini",
                         alasan=f"Konsumsi {r['residual_pct']:+.1%} di bawah forecast; bisa berupa data kurang tercatat.",
                         batasan="Penurunan juga dapat berasal dari operasi yang memang berkurang (area tutup, okupansi rendah) — okupansi tidak tersedia."))
    for e in r["evidence"]:
        if e.startswith("WBP share"):
            recs.append(dict(aksi="Bandingkan aktivitas fleksibel pada periode WBP dengan 4 minggu sebelumnya; "
                                  "validasi apakah ada beban yang dapat digeser ke LWBP",
                             alasan=e + "; tarif WBP 1,5x LWBP.",
                             batasan=LIMIT_DAILY))
        elif e.startswith("KVARh"):
            recs.append(dict(aksi="Periksa status kapasitor bank / koreksi faktor daya bersama staf teknis",
                             alasan=e,
                             batasan="Faktor daya indikatif dihitung dari agregat harian, bukan pengukuran langsung."))
        elif e.startswith("Biaya"):
            recs.append(dict(aksi="Eskalasi ke Finance bila deviasi biaya berulang >=3 hari dalam 7 hari",
                             alasan=e,
                             batasan="Tarif per unit konstan pada dataset; biaya mengikuti pemakaian."))
        elif e.startswith("Zone"):
            z = r["top_zone"]
            recs.append(dict(aksi=f"Validasi perubahan operasi {z} dengan pengelola zona; bandingkan dengan hari sejenis",
                             alasan=e,
                             batasan="Zona tidak terekonsiliasi dengan total gedung; identitas/fungsi tenant tidak diketahui."))
    if r["n_evidence"] == 0 and r["residual"] >= 0:
        recs.append(dict(aksi="Monitor dan minta konteks operasional (event, okupansi, perawatan)",
                         alasan=f"Deviasi {r['residual_pct']:+.1%} tanpa bukti kontekstual (confidence rendah, G4).",
                         batasan="Tidak dapat disimpulkan dari dataset saja."))
    if r["context_calendar"] != "Hari kerja":
        recs.append(dict(aksi=f"Bandingkan dengan {r['context_calendar'].lower()} sebelumnya sebelum menyimpulkan",
                         alasan=f"Tanggal ini adalah {r['context_calendar'].lower()}.",
                         batasan="Model sudah memakai fitur kalender, tetapi kejadian khusus tidak tercatat."))
    if r["severity"] == "Tinggi":
        recs.append(dict(aksi="Eskalasi ke Facility Manager: tetapkan owner dan due date maksimal 1 hari",
                         alasan="Severity tinggi.", batasan="Keputusan tetap pada pengguna (human-in-the-loop)."))
    return recs


def evidence_gates(r: pd.Series, gate_g2: bool, k_med: float, decision_status: str | None) -> list[dict]:
    g = []
    g.append(dict(gate="G1 - Data layak", lolos=r["day_status"] != "not-ready",
                  respon="Status hari: " + r["day_status"] + ("" if r["day_status"] != "not-ready"
                                                              else " -> forecast & rekomendasi diblokir")))
    g.append(dict(gate="G2 - Model layak", lolos=gate_g2,
                  respon="Model mengungguli seasonal naive" if gate_g2 else "Fallback baseline; confidence diturunkan"))
    g.append(dict(gate="G3 - Deviasi material", lolos=abs(r["z"]) >= k_med,
                  respon=f"|z| = {abs(r['z']):.2f} vs threshold {k_med}" + ("" if abs(r["z"]) >= k_med else " -> hanya monitor")))
    g.append(dict(gate="G4 - Bukti kontekstual", lolos=r["n_evidence"] > 0,
                  respon=f"{r['n_evidence']} bukti" + ("" if r["n_evidence"] else " -> low confidence")))
    g.append(dict(gate="G5 - Actionability", lolos=r["n_evidence"] > 0 or r["residual"] < 0,
                  respon="Ada pemeriksaan manusia yang dapat dilakukan" if (r["n_evidence"] > 0 or r["residual"] < 0)
                  else "Minta data tambahan / tandai tidak dapat disimpulkan"))
    approved = decision_status in ("validated", "monitor", "rejected", "closed")
    g.append(dict(gate="G6 - Human approval", lolos=approved,
                  respon=f"Keputusan: {decision_status}" if approved else "Status tetap proposed; belum ditinjau Facility Manager"))
    return g
