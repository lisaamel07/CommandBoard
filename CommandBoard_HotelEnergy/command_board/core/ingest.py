"""F1 (bagian 1) - Ingestion & schema validation untuk DATA_170225.csv.

Dataset memakai format angka campuran: koma desimal ("1,53"), titik ribuan
("4.923.072"), kadang keduanya ("1.234,5"), dan spasi di sekitar nilai.
Parser di sini menangani semua bentuk tersebut secara eksplisit.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

CALENDAR_COLS = ["DAY_OF_WEEK", "IS_WEEKEND", "IS_HOLIDAY", "WEEK_OF_MONTH", "MONTH"]
NUMERIC_COLS = [
    "LWBP_USED", "LWBP_PRICE", "WBP_USED", "WBP_PRICE", "KVARH_USED", "TOTAL_PRICE",
    "TOTAL_BUILDING_ELECTRICITY",
    "A_ELECTRICITY_USED", "A_ELECTRICITY_PRICE",
    "B_ELECTRICITY_USED", "B_ELECTRICITY_PRICE",
    "C_ELECTRICITY_USED", "C_ELECTRICITY_PRICE",
]
EXPECTED_COLS = ["DATE"] + CALENDAR_COLS + NUMERIC_COLS

_THOUSANDS = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$")


def parse_number(value) -> float:
    """Ubah teks angka format Indonesia/campuran menjadi float. NaN bila gagal."""
    if value is None:
        return np.nan
    s = str(value).strip().replace(" ", "")
    if s == "" or s.lower() in {"nan", "null", "-"}:
        return np.nan
    if _THOUSANDS.match(s):          # 4.923.072 atau 1.234,5
        s = s.replace(".", "")
    s = s.replace(",", ".")           # 1,53 -> 1.53
    try:
        return float(s)
    except ValueError:
        return np.nan


@dataclass
class IngestResult:
    df: pd.DataFrame
    log: list[dict] = field(default_factory=list)
    critical_error: bool = False
    checksum: str = ""


def load_dataset(path: str | Path) -> IngestResult:
    path = Path(path)
    log: list[dict] = []
    raw_bytes = path.read_bytes()
    checksum = hashlib.sha256(raw_bytes).hexdigest()[:16]
    log.append({"langkah": "Baca file", "status": "OK",
                "detail": f"{path.name} ({len(raw_bytes)/1024:.0f} KB, sha256 {checksum})"})

    raw = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig", dtype=str)
    raw.columns = [c.strip() for c in raw.columns]

    missing = [c for c in EXPECTED_COLS if c not in raw.columns]
    extra = [c for c in raw.columns if c not in EXPECTED_COLS]
    critical = bool(missing)
    log.append({"langkah": "Validasi schema",
                "status": "GAGAL" if missing else "OK",
                "detail": (f"Kolom hilang: {missing}. " if missing else "19 kolom sesuai data dictionary. ")
                          + (f"Kolom tambahan diabaikan: {extra}" if extra else "")})
    if critical:
        return IngestResult(raw, log, True, checksum)

    df = pd.DataFrame()
    df["DATE"] = pd.to_datetime(raw["DATE"].str.strip(), errors="coerce")
    bad_dates = int(df["DATE"].isna().sum())
    log.append({"langkah": "Parsing tanggal", "status": "OK" if bad_dates == 0 else "GAGAL",
                "detail": f"{bad_dates} tanggal tidak terbaca"})
    critical |= bad_dates > 0

    for c in CALENDAR_COLS:
        df[c] = pd.to_numeric(raw[c].str.strip(), errors="coerce").astype("Int64")

    parse_fail = 0
    for c in NUMERIC_COLS:
        parsed = raw[c].map(parse_number)
        parse_fail += int(parsed.isna().sum() - raw[c].isna().sum())
        df[c] = parsed
    log.append({"langkah": "Parsing angka (koma desimal / titik ribuan)",
                "status": "OK" if parse_fail == 0 else "PERINGATAN",
                "detail": f"{len(NUMERIC_COLS)} kolom numerik; {parse_fail} nilai gagal diparse"})

    df = df.sort_values("DATE").reset_index(drop=True)
    log.append({"langkah": "Rentang data", "status": "OK",
                "detail": f"{df['DATE'].min():%Y-%m-%d} s.d. {df['DATE'].max():%Y-%m-%d}, {len(df)} baris"})
    return IngestResult(df, log, critical, checksum)
