"""API + web frontend Hotel Energy Command Board.

Memakai modul core/ yang sama dengan versi Streamlit (quality gate, forecast,
anomaly scoring, bounded recommendation, decision log).

Jalankan:  python -m uvicorn server:app --port 8600   (dari folder command_board)
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import store
from core.forecast import MODEL_LABEL, NOT_RUN, TRAIN_END, VAL_END
from core.pipeline import DEFAULT_DATA, run_pipeline
from core.quality import DECISIONS
from core.reco import evidence_gates, recommend

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
STATE = {"k": (2.0, 3.0, 4.0)}
PERM = {
    "decide": {"Facility Manager"},
    "validate": {"Facility Manager", "Staf Teknis"},
    "quality": {"Analis Data"},
    "threshold": {"Analis Data"},
}

app = FastAPI(title="Hotel Energy Command Board API")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


# ---------------------------------------------------------------- helpers
def clean(v):
    if v is None:
        return None
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(v) or math.isinf(v) else round(float(v), 6)
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v


def records(df: pd.DataFrame) -> list[dict]:
    return [{k: clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def require(role: str, action: str) -> None:
    if role not in PERM[action]:
        raise HTTPException(403, f"Peran '{role}' tidak berhak melakukan aksi ini.")


@lru_cache(maxsize=8)
def _pipeline(mtime: float, overrides: tuple, k: tuple):
    return run_pipeline(DEFAULT_DATA, dict(overrides), *k)


def pipeline():
    ov = tuple(sorted(store.get_quality_overrides().items()))
    return _pipeline(DEFAULT_DATA.stat().st_mtime, ov, STATE["k"])


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/data")
def data():
    res = pipeline()
    q = res.quality
    out: dict = {
        "meta": {
            "gate": res.gate, "model_version": res.model_version, "checksum": res.ingest.checksum,
            "file": DEFAULT_DATA.name, "k": list(STATE["k"]), "trust": clean(q.scores),
            "date_min": clean(res.clean["DATE"].min()), "date_max": clean(res.clean["DATE"].max()),
            "train_end": clean(TRAIN_END), "val_end": clean(VAL_END), "decisions_allowed": DECISIONS,
        },
        "ingest_log": res.ingest.log,
        "checks": records(q.checks.drop(columns=["kritis"])),
        "flags": records(q.row_flags),
        "quality_decisions": records(store.quality_decisions_df()),
        "decisions": records(store.decisions_df()),
        "audit": records(store.audit_df().head(200)),
    }
    if res.scored is None:
        return out

    s = res.scored
    raw = res.ingest.df.set_index("DATE")["TOTAL_BUILDING_ELECTRICITY"]
    ser = pd.DataFrame({
        "d": s["DATE"], "total": s["TOTAL_BUILDING_ELECTRICITY"], "raw": s["DATE"].map(raw),
        "fc": s["forecast"], "lo": s["lo"], "hi": s["hi"], "resid": s["residual"], "rp": s["residual_pct"], "z": s["z"],
        "cost": s["TOTAL_PRICE"], "lp": s["LWBP_PRICE"], "wp": s["WBP_PRICE"],
        "lwbp": s["LWBP_USED"], "wbp": s["WBP_USED"], "ws": s["WBP_SHARE"], "wcs": s["WBP_COST_SHARE"],
        "kv": s["KVARH_USED"], "pf": s["PF_INDIKATIF"],
        "A": s["A_ELECTRICITY_USED"], "B": s["B_ELECTRICITY_USED"], "C": s["C_ELECTRICITY_USED"],
        "Ap": s["A_ELECTRICITY_PRICE"], "Bp": s["B_ELECTRICITY_PRICE"], "Cp": s["C_ELECTRICITY_PRICE"],
        "zA": s["z_Zone A"], "zB": s["z_Zone B"], "zC": s["z_Zone C"], "zw": s["z_wbp_share"],
        "zk": s["z_kvarh"], "zc": s["z_cost"],
        "sev": s["severity"], "conf": s["confidence"], "score": s["anomaly_score"], "alert": s["is_alert"],
        "blocked": s["blocked"], "nev": s["n_evidence"], "tz": s["top_zone"],
        "st": s["day_status"], "trust": s["day_trust"], "ex": s["excluded"], "fs": s["flag_severity"],
        "fr": s["flag_reasons"], "dec": s["decision"], "cal": s["context_calendar"],
        "dow": s["DAY_OF_WEEK"].astype(int), "hol": s["IS_HOLIDAY"].astype(int),
    })
    out["series"] = records(ser)

    status = store.latest_status_by_date()
    fc = res.forecast
    alerts = []
    for _, r in s[s["is_alert"]].iterrows():
        ds = r["DATE"].strftime("%Y-%m-%d")
        alerts.append({
            "d": ds, "evidence": list(r["evidence"]), "recs": recommend(r),
            "gates": evidence_gates(r, fc.gate_g2, STATE["k"][1], status.get(ds)),
            "status": "diblokir" if r["blocked"] else status.get(ds, "proposed"),
        })
    out["alerts"] = clean(alerts)

    sp = fc.split_preds
    out["forecast"] = {
        "selected": fc.selected, "label": MODEL_LABEL[fc.selected], "labels": MODEL_LABEL, "g2": fc.gate_g2,
        "note": fc.gate_note, "sigma": clean(fc.sigma), "q_low": clean(fc.q_low), "q_high": clean(fc.q_high),
        "metrics": records(fc.metrics), "not_run": NOT_RUN,
        "split": {m: [[clean(d), clean(v)] for d, v in zip(g["DATE"], g["forecast"])] for m, g in sp.groupby("model")},
        "next_day": records(fc.next_day)[0],
        "importance": records(fc.importance.head(10)) if fc.importance is not None else None,
    }
    return out


class QualityIn(BaseModel):
    role: str
    items: list[dict]          # [{date, decision}]
    reason: str


@app.post("/api/quality-decisions")
def set_quality(body: QualityIn):
    require(body.role, "quality")
    if not body.reason.strip():
        raise HTTPException(400, "Alasan wajib diisi.")
    for it in body.items:
        if it.get("decision") not in DECISIONS:
            raise HTTPException(400, f"Keputusan tidak valid: {it}")
        store.set_quality_decision(it["date"], it["decision"], body.reason, body.role)
    return {"ok": True, "n": len(body.items)}


class ThresholdIn(BaseModel):
    role: str
    k: list[float]


@app.post("/api/threshold")
def set_threshold(body: ThresholdIn):
    require(body.role, "threshold")
    lo, med, hi = body.k
    if not lo <= med <= hi:
        raise HTTPException(400, "Harus Rendah ≤ Sedang ≤ Tinggi.")
    STATE["k"] = (lo, med, hi)
    store.audit(body.role, "threshold", "-", "update", f"k={lo}/{med}/{hi}")
    return {"ok": True}


class DecisionIn(BaseModel):
    role: str
    alert_date: str
    owner: str
    due_date: str
    priority: str
    status: str
    action: str
    note: str


@app.post("/api/decisions")
def add_decision(body: DecisionIn):
    require(body.role, "decide")
    if not body.owner.strip() or not body.note.strip():
        raise HTTPException(400, "Owner dan catatan wajib diisi (accountability).")
    if body.status not in ("validated", "monitor", "rejected"):
        raise HTTPException(400, "Status tidak valid.")
    s = pipeline().scored.set_index("DATE")
    r = s.loc[pd.Timestamp(body.alert_date)]
    if bool(r["blocked"]):
        raise HTTPException(400, "Alert diblokir oleh G1; data hari itu tidak layak.")
    did = store.add_decision(alert_date=body.alert_date, role=body.role, owner=body.owner, due_date=body.due_date,
                             priority=body.priority, status=body.status, action=body.action, note=body.note,
                             severity=r["severity"], confidence=r["confidence"],
                             model_version=pipeline().model_version, trust_status=r["day_status"])
    return {"ok": True, "id": did}


class UpdateIn(BaseModel):
    role: str
    validation_result: str = ""
    close: bool = False
    close_reason: str = ""


@app.post("/api/decisions/{did}")
def update_decision(did: int, body: UpdateIn):
    require(body.role, "validate")
    dec = store.decisions_df().set_index("id")
    if did not in dec.index:
        raise HTTPException(404, "Action tidak ditemukan.")
    kw = {}
    if body.validation_result.strip():
        kw["validation_result"] = body.validation_result
    if body.close:
        require(body.role, "decide")
        if not body.close_reason or not (body.validation_result.strip() or dec.at[did, "validation_result"]):
            raise HTTPException(400, "Menutup action wajib menyertakan evidence validasi dan close reason.")
        kw.update(status="closed", close_reason=body.close_reason)
    if not kw:
        raise HTTPException(400, "Tidak ada perubahan.")
    store.update_decision(did, body.role, **kw)
    return {"ok": True}


class RoleIn(BaseModel):
    role: str


@app.post("/api/reset")
def reset(body: RoleIn):
    if body.role not in PERM["decide"] | PERM["quality"]:
        raise HTTPException(403, "Tidak berhak.")
    store.reset_all(body.role)
    STATE["k"] = (2.0, 3.0, 4.0)
    return {"ok": True}
