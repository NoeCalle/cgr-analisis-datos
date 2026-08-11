"""Benchmark sklearn de fraccionamiento basado en Isolation Forest.

Esta implementación no define el serving activo. Se conserva como detector
comparativo no supervisado, regresión reproducible y apoyo visual/interpretable.
El perfil operacional usa ``StandardScalerModel + KMeansModel`` en Spark MLlib
y dispone de tuning/holdout propios ligados al model registry.

El benchmark consume la capa Plata y la configuración publicada en
``outputs/tuning_fraccionamiento_resumen.json``. Sus scores son señales de
priorización, no determinaciones jurídicas, y no deben presentarse como métricas
del champion Spark servido.
"""

import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from rutas_datos import entrada_plata

FEATURES = [
    "n_contratos_grupo", "max_contratos_ventana_15d", "monto_total_ventana_15d",
    "pct_montos_bajo_umbral", "monto_total_grupo",
]
DEFAULT_PARAMS = {"n_estimators": 100, "max_samples": 0.8, "contamination": "auto"}
TUNING_PATH = Path("outputs/tuning_fraccionamiento_resumen.json")
SENAL_PRIORIZACION = "senal_priorizacion_fraccionamiento"


def cargar():
    return pd.read_csv(entrada_plata("dataset_fraccionamiento.csv"))


def parametros_seleccionados():
    if not TUNING_PATH.exists():
        print(f"ADVERTENCIA: no existe {TUNING_PATH}; se usan defaults {DEFAULT_PARAMS}.")
        return DEFAULT_PARAMS.copy()
    with TUNING_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    params = data.get("mejor_configuracion", {})
    requeridos = {"n_estimators", "max_samples", "contamination"}
    if not requeridos.issubset(params):
        raise ValueError(f"Resumen de tuning incompleto: faltan {sorted(requeridos - set(params))}")
    return {
        "n_estimators": int(params["n_estimators"]),
        "max_samples": float(params["max_samples"]),
        "contamination": params["contamination"],
    }


def detectar_anomalias(df, params):
    X = df[FEATURES]
    scaler = StandardScaler().fit(X)
    X_scaled = scaler.transform(X)
    modelo = IsolationForest(**params, random_state=42)
    modelo.fit(X_scaled)

    df = df.copy()
    df["score_anomalia"] = -modelo.decision_function(X_scaled)
    df["es_anomalia_modelo"] = modelo.predict(X_scaled) == -1
    return df, modelo, scaler


def regla_interpretable(df):
    df = df.copy()
    df[SENAL_PRIORIZACION] = (
        (df["max_contratos_ventana_15d"] >= 3)
        & (df["pct_montos_bajo_umbral"] >= 0.7)
    )
    return df


def validar_sanity_check(df):
    n_reales = int(df["label_fraccionamiento_real"].sum())
    if n_reales:
        top_n = df.nlargest(n_reales, "score_anomalia")
        aciertos = int(top_n["label_fraccionamiento_real"].sum())
        print(f"Sanity check in-sample Isolation Forest: {aciertos}/{n_reales} en top-{n_reales}.")
    regla_total = int(df[SENAL_PRIORIZACION].sum())
    regla_aciertos = int(df.loc[df[SENAL_PRIORIZACION], "label_fraccionamiento_real"].sum())
    print(
        f"Sanity check regla: {regla_total} grupos marcados, {regla_aciertos} sembrados. "
        "Consultar tuning_fraccionamiento_resumen.json para el holdout independiente."
    )


def graficar(df):
    fig, ax = plt.subplots(figsize=(8, 5))
    colores = df["label_fraccionamiento_real"].map({True: "#c53030", False: "#a0aec0"})
    tamanos = df["score_anomalia"].clip(lower=0) * 800 + 25
    ax.scatter(
        df["max_contratos_ventana_15d"], df["pct_montos_bajo_umbral"],
        s=tamanos, c=colores, alpha=0.7, edgecolor="white",
    )
    ax.set_xlabel("Máx. contratos en ventana de 15 días")
    ax.set_ylabel("Proporción bajo 95% de cuantía parametrizada")
    ax.set_title("Señales de posible fraccionamiento")
    plt.tight_layout()
    plt.savefig("outputs/charts/06_deteccion_fraccionamiento.png", dpi=130)
    plt.close()


def main():
    df = cargar()
    params = parametros_seleccionados()
    print(f"Configuración seleccionada: {params}")
    df, modelo, scaler = detectar_anomalias(df, params)
    df = regla_interpretable(df)
    validar_sanity_check(df)
    graficar(df)

    df.sort_values("score_anomalia", ascending=False).to_csv(
        "outputs/ranking_riesgo_fraccionamiento.csv", index=False
    )
    joblib.dump(modelo, "outputs/models/modelo_fraccionamiento_isoforest.joblib")
    joblib.dump(scaler, "outputs/models/scaler_fraccionamiento.joblib")


if __name__ == "__main__":
    main()
