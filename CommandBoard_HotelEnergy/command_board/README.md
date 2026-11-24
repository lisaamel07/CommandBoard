# Hotel Energy Command Board — Prototipe MVP

Implementasi Bab 3 (Artefak) laporan *Keberlanjutan Sistem Informasi – Command Board Hotel*.
Data: `../DATA_170225.csv` (910 hari, 3 Jan 2023 – 30 Jun 2025).

## Menjalankan
```
pip install -r requirements.txt
```
**Versi web modern** (glassmorphism, GSAP + ScrollTrigger, Motion, Lenis, ECharts, mode gelap):
```
python -m uvicorn server:app --port 8600
```
lalu buka http://localhost:8600. Library JS disimpan lokal di `web/static/vendor/` (bisa offline).

**Versi Streamlit** (sesuai Bab 3.5):
```
streamlit run app.py
```
Kedua versi memakai modul `core/` dan database `data/command_board.sqlite` yang sama.

## Peta fungsi → kode
| Fungsi | Output | Lokasi |
|---|---|---|
| F1 validasi schema, tanggal, missing, duplikat, invalid, outlier, rekonsiliasi | O1 | `core/ingest.py`, `core/quality.py` |
| F2 trust score (kelengkapan, validitas, konsistensi, kewajaran pola) + gate | O1 | `core/quality.py`, halaman Data Quality |
| F3 KPI eksekutif | O2 | `views/executive.py` |
| F4–F5 perbandingan model, split kronologis, MAE/RMSE/sMAPE, interval | O3 | `core/forecast.py`, `views/forecasting.py` |
| F6 residual, threshold, severity, confidence, evidence | O4 | `core/anomaly.py` |
| F7 WBP/LWBP, WBP share, KVARh | O5 | `views/tariff_reactive.py` |
| F8 kontribusi & deviasi Zone A–C | O6 | `views/zone.py` |
| F9 bounded recommendation + evidence gate G1–G6 | O7 | `core/reco.py`, `views/anomaly_reco.py` |
| F10 ekspor ringkasan, decision note, action log | O8 | `views/report_decision.py`, `core/store.py` |
| F11 filter periode/kalender/zona/severity/status | – | semua halaman |
| F12 explainability (bila model berbasis fitur terpilih) | – | `views/forecasting.py` |

Log keputusan, quality decision, dan audit trail tersimpan di `data/command_board.sqlite`.

## Catatan data penting
- Format angka campuran (koma desimal, titik ribuan) → parser khusus di `core/ingest.py`.
- Artefak meter: 2023-08-01 (lonjakan ~30×), Zone C 27–28 Okt 2023 (+/−356 ribu), KVARh 5–6 Feb 2023 (+/−33).
  Default keputusan: *correct* (interpolasi waktu); dapat diubah Analis Data menjadi *keep*/*exclude*.
- TOTAL_BUILDING_ELECTRICITY ≠ Zone A+B+C (korelasi ≈ 0) → gap ditampilkan, tidak dipaksa sama.
- Tarif per unit konstan (WBP = 1,5× LWBP) → biaya merupakan turunan dari pemakaian.
