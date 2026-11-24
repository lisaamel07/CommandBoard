"""Orkestrasi pipeline: ingest -> quality gate -> forecast -> anomaly scoring."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .anomaly import score_anomalies
from .forecast import ForecastResult, run_forecast
from .ingest import IngestResult, load_dataset
from .quality import QualityResult, apply_decisions, gate_from_score, run_quality

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT.parent / "DATA_170225.csv"


@dataclass
class PipelineResult:
    ingest: IngestResult
    quality: QualityResult
    clean: pd.DataFrame
    gate: str                  # gate dataset setelah quality decision
    forecast: ForecastResult | None
    scored: pd.DataFrame | None
    model_version: str


def run_pipeline(path: str | Path, overrides: dict[str, str],
                 k_low: float = 2.0, k_med: float = 3.0, k_high: float = 4.0) -> PipelineResult:
    ing = load_dataset(path)
    if ing.critical_error:
        q = QualityResult(pd.DataFrame(), pd.DataFrame(), {"Total": 0.0}, "not-ready", pd.DataFrame())
        return PipelineResult(ing, q, ing.df, "not-ready", None, None, "-")

    q = run_quality(ing.df)
    clean = apply_decisions(ing.df, q.row_flags, overrides)
    critical_check_failed = bool((q.checks["kritis"] & (q.checks["jumlah"] > 0)).any())
    unresolved = bool(((clean["flag_severity"] == "critical") & (clean["decision"] == "keep")).any())
    gate = gate_from_score(q.scores["Total"], critical_check_failed)
    if gate == "ready" and unresolved:
        gate = "caution"

    if gate == "not-ready":
        return PipelineResult(ing, q, clean, gate, None, None, "-")

    fc = run_forecast(clean)
    scored = score_anomalies(clean, fc.preds, fc.sigma, fc.gate_g2, k_low, k_med, k_high)
    version = f"{fc.selected}@{ing.checksum[:8]}"
    return PipelineResult(ing, q, clean, gate, fc, scored, version)
