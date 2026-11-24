"""F4-F5 - Forecasting harian dengan split kronologis (O3 Forecast Panel).

Kandidat: naive, seasonal naive (lag 7), moving average 7 hari, regresi Ridge,
dan Gradient Boosting (keluarga yang sama dengan XGBoost). Model dipilih dari
kinerja validation; Evidence Gate G2 mewajibkan model mengungguli seasonal naive,
jika tidak maka sistem kembali (fallback) ke seasonal naive.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TARGET = "TOTAL_BUILDING_ELECTRICITY"
TRAIN_END = pd.Timestamp("2024-06-30")
VAL_END = pd.Timestamp("2024-12-31")
WARMUP_DAYS = 90

MODEL_ORDER = ["naive", "seasonal_naive", "moving_average_7", "ridge", "gradient_boosting"]
MODEL_LABEL = {
    "naive": "Naive (t-1)",
    "seasonal_naive": "Seasonal naive (t-7)",
    "moving_average_7": "Moving average 7 hari",
    "ridge": "Regresi Ridge (kalender + lag)",
    "gradient_boosting": "Gradient Boosting (setara XGBoost)",
}
NOT_RUN = {
    "ARIMA/Prophet": "Belum dijalankan pada MVP (butuh statsmodels/prophet). Dapat ditambahkan sebagai kandidat.",
    "LSTM/BiLSTM": "Tidak dijalankan: 910 observasi berisiko overfit (Bab 5.4); tetap kandidat bila data bertambah.",
}
SIMPLE_TOLERANCE = 0.02  # pilih model paling sederhana bila MAE-nya dalam 2% dari yang terbaik


@dataclass
class ForecastResult:
    metrics: pd.DataFrame
    selected: str
    best_by_val: str
    gate_g2: bool
    gate_note: str
    sigma: float
    q_low: float
    q_high: float
    preds: pd.DataFrame          # DATE, forecast, lo, hi, model (rolling-origin, out-of-sample)
    next_day: pd.DataFrame        # forecast untuk tanggal setelah data terakhir
    split_preds: pd.DataFrame     # prediksi val/test semua model (untuk grafik perbandingan)
    importance: pd.DataFrame | None


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    y = df[TARGET]
    dow = df["DATE"].dt.dayofweek
    for k in range(7):
        f[f"dow_{k+1}"] = (dow == k).astype(float)
    f["is_weekend"] = df["IS_WEEKEND"].astype(float)
    f["is_holiday"] = df["IS_HOLIDAY"].astype(float)
    m = df["DATE"].dt.month
    f["month_sin"] = np.sin(2 * np.pi * m / 12)
    f["month_cos"] = np.cos(2 * np.pi * m / 12)
    f["lag_1"] = y.shift(1)
    f["lag_7"] = y.shift(7)
    f["lag_14"] = y.shift(14)
    f["roll_7"] = y.shift(1).rolling(7).mean()
    f["roll_28"] = y.shift(1).rolling(28).mean()
    return f


def _ml(name: str):
    if name == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                         min_samples_leaf=20, random_state=0)


def _predict(name: str, X: pd.DataFrame, train_mask: pd.Series, y: pd.Series, pred_mask: pd.Series):
    if name == "naive":
        return X.loc[pred_mask, "lag_1"].to_numpy(), None
    if name == "seasonal_naive":
        return X.loc[pred_mask, "lag_7"].to_numpy(), None
    if name == "moving_average_7":
        return X.loc[pred_mask, "roll_7"].to_numpy(), None
    model = _ml(name)
    model.fit(X.loc[train_mask], y.loc[train_mask])
    return model.predict(X.loc[pred_mask]), model


def metrics(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    ok = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[ok], y_pred[ok]
    err = y_true - y_pred
    denom = (np.abs(y_true) + np.abs(y_pred)) / 2
    smape = 100 * np.mean(np.where(denom == 0, 0, np.abs(err) / denom))
    return dict(MAE=np.mean(np.abs(err)), RMSE=np.sqrt(np.mean(err ** 2)), sMAPE=smape, n=int(ok.sum()))


def run_forecast(clean: pd.DataFrame) -> ForecastResult:
    df = clean.reset_index(drop=True)
    X = make_features(df)
    y = df[TARGET]
    usable = X.notna().all(axis=1) & ~df["excluded"]
    is_train = df["DATE"] <= TRAIN_END
    is_val = (df["DATE"] > TRAIN_END) & (df["DATE"] <= VAL_END)
    is_test = df["DATE"] > VAL_END

    rows, split_preds, val_resid = [], [], {}
    for name in MODEL_ORDER:
        p_val, _ = _predict(name, X, usable & is_train, y, usable & is_val)
        p_test, _ = _predict(name, X, usable & (is_train | is_val), y, usable & is_test)
        mv = metrics(y[usable & is_val], p_val)
        mt = metrics(y[usable & is_test], p_test)
        val_resid[name] = y[usable & is_val].to_numpy() - p_val
        rows.append({"model": name, "Model": MODEL_LABEL[name],
                     "val_MAE": mv["MAE"], "val_RMSE": mv["RMSE"], "val_sMAPE": mv["sMAPE"],
                     "test_MAE": mt["MAE"], "test_RMSE": mt["RMSE"], "test_sMAPE": mt["sMAPE"]})
        split_preds.append(pd.DataFrame({"DATE": df.loc[usable & is_val, "DATE"], "model": name,
                                         "split": "validation", "forecast": p_val}))
        split_preds.append(pd.DataFrame({"DATE": df.loc[usable & is_test, "DATE"], "model": name,
                                         "split": "test", "forecast": p_test}))
    m = pd.DataFrame(rows)
    sn = m.set_index("model")
    for split in ("val", "test"):
        m[f"{split}_skill_vs_snaive"] = 1 - m[f"{split}_MAE"] / sn.at["seasonal_naive", f"{split}_MAE"]

    best = m.loc[m["val_MAE"].idxmin(), "model"]
    best_mae = m["val_MAE"].min()
    # paling sederhana di dalam toleransi
    chosen = next(n for n in MODEL_ORDER if sn.at[n, "val_MAE"] <= best_mae * (1 + SIMPLE_TOLERANCE))
    gate = sn.at[chosen, "val_MAE"] < sn.at["seasonal_naive", "val_MAE"] or chosen == "seasonal_naive"
    if chosen == "seasonal_naive":
        note = "Seasonal naive adalah model terbaik/termudah pada validation; dipakai sebagai model terpilih."
    elif gate:
        note = (f"{MODEL_LABEL[chosen]} mengungguli seasonal naive pada validation "
                f"(skill {m.set_index('model').at[chosen, 'val_skill_vs_snaive']:.1%}). G2 lolos.")
    else:
        note = f"{MODEL_LABEL[chosen]} kalah dari seasonal naive -> fallback ke seasonal naive (confidence diturunkan)."
        chosen = "seasonal_naive"
    m["terpilih"] = m["model"] == chosen

    resid = val_resid[chosen]
    resid = resid[~np.isnan(resid)]
    mad = np.median(np.abs(resid - np.median(resid)))
    sigma = float(1.4826 * mad) if mad > 0 else float(np.std(resid))
    q_low, q_high = (float(q) for q in np.quantile(resid, [0.05, 0.95]))

    # ---- rolling-origin, refit tiap awal bulan (out-of-sample untuk seluruh histori) ----
    preds = pd.DataFrame({"DATE": df["DATE"], "forecast": np.nan})
    start = df["DATE"].min() + pd.Timedelta(days=WARMUP_DAYS)
    months = pd.date_range(start.to_period("M").to_timestamp(), df["DATE"].max(), freq="MS")
    importance = None
    for ms in months:
        me = ms + pd.offsets.MonthEnd(0)
        pm = (df["DATE"] >= ms) & (df["DATE"] <= me) & X.notna().all(axis=1)
        tm = usable & (df["DATE"] < ms)
        if pm.sum() == 0 or tm.sum() < 60:
            continue
        p, model = _predict(chosen, X, tm, y, pm)
        preds.loc[pm, "forecast"] = p
    preds["lo"] = preds["forecast"] + q_low
    preds["hi"] = preds["forecast"] + q_high
    preds["model"] = chosen

    # ---- forecast hari berikutnya setelah data terakhir ----
    last = df["DATE"].max()
    nd = last + pd.Timedelta(days=1)
    fut = pd.DataFrame({"DATE": [nd], "IS_WEEKEND": [int(nd.dayofweek >= 5)], "IS_HOLIDAY": [0],
                        TARGET: [np.nan]})
    ext = pd.concat([df[["DATE", "IS_WEEKEND", "IS_HOLIDAY", TARGET]], fut], ignore_index=True)
    Xe = make_features(ext)
    ue = pd.concat([usable, pd.Series([False])], ignore_index=True)
    pm = pd.Series(False, index=Xe.index)
    pm.iloc[-1] = True
    p, model = _predict(chosen, Xe, ue, ext[TARGET], pm)
    next_day = pd.DataFrame({"DATE": [nd], "forecast": p, "lo": p + q_low, "hi": p + q_high,
                             "catatan": ["IS_HOLIDAY diasumsikan 0 (kalender libur belum tersedia)"]})

    # ---- explainability (F12, Could): koefisien Ridge atau permutation-free gain proxy ----
    if chosen == "ridge" and model is not None:
        coef = model[-1].coef_
        importance = pd.DataFrame({"fitur": X.columns, "bobot": np.abs(coef)}).sort_values("bobot", ascending=False)
    elif chosen == "gradient_boosting" and model is not None:
        from sklearn.inspection import permutation_importance
        tm = usable & (df["DATE"] <= VAL_END)
        r = permutation_importance(model, X.loc[tm], y.loc[tm], n_repeats=5, random_state=0)
        importance = pd.DataFrame({"fitur": X.columns, "bobot": r.importances_mean}).sort_values("bobot", ascending=False)

    return ForecastResult(m, chosen, best, bool(gate), note, sigma, q_low, q_high,
                          preds, next_day, pd.concat(split_preds, ignore_index=True), importance)
