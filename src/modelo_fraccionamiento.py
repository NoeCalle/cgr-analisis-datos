"""
Modelo de detección de posible Fraccionamiento — Producto 6/7 del TDR.

Isolation Forest complementado por una regla interpretable de priorización.
La salida NO determina jurídicamente fraccionamiento. En el flujo orquestado
se consume `lakehouse/plata/dataset_fraccionamiento.csv`; `data/` es fallback
standalone.

La evaluación impresa en este script es un sanity check in-sample del PoC.
La evaluación independiente para selección de hiperparámetros está en
`src/tuning_fraccionamiento.py`, que reserva un holdout final antes del tuning.
"""

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


def cargar():
    return pd.read_csv(entrada_plata("dataset_fraccionamiento.csv"))


def detectar_anomalias(df):
    X = df[FEATURES]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Configuración operativa del PoC. La validación/tuning independiente se
    # ejecuta por separado; no se usa el holdout final para configurar aquí.
    modelo = IsolationForest(
        n_estimators=100,
        max_samples=0.8,
        contamination="auto",
        random_state=42,
    )
    modelo.fit(X_scaled)

    df = df.copy()
    df["score_anomalia"] = -modelo.decision_function(X_scaled)
    df["es_anomalia_modelo"] = modelo.predict(X_scaled) == -1
    return df, modelo, scaler


def regla_interpretable(df):
    """Señal de priorización: no equivale a una conclusión jurídica."""
    df = df.copy()
    df["cumple_regla_fraccionamiento"] = (
        (df["max_contratos_ventana_15d"] >= 3)
        & (df["pct_montos_bajo_umbral"] >= 0.7)
    )
    return df


def validar_sanity_check(df):
    """Diagnóstico in-sample sobre ground truth sembrado, no métrica final."""
    n_reales = int(df["label_fraccionamiento_real"].sum())
    print(f"Casos sembrados: {n_reales} / {len(df)}")
    if n_reales:
        top_n = df.sort_values("score_anomalia", ascending=False).head(n_reales)
        aciertos_modelo = int(top_n["label_fraccionamiento_real"].sum())
        print(
            f"Sanity check Isolation Forest: {aciertos_modelo}/{n_reales} casos sembrados "
            f"en top-{n_reales}. NO es evaluación independiente."
        )

    regla_total = int(df["cumple_regla_fraccionamiento"].sum())
    regla_aciertos = int(
        df.loc[df["cumple_regla_fraccionamiento"], "label_fraccionamiento_real"].sum()
    )
    print(
        f"Sanity check regla: {regla_total} grupos marcados, {regla_aciertos} sembrados. "
        "La regla fue construida sobre un patrón similar al usado para sembrar los casos."
    )


def graficar(df):
    fig, ax = plt.subplots(figsize=(8, 5))
    colores = df["label_fraccionamiento_real"].map({True: "#c53030", False: "#a0aec0"})
    tamanos = df["score_anomalia"].clip(lower=0) * 800 + 25
    ax.scatter(
        df["max_contratos_ventana_15d"],
        df["pct_montos_bajo_umbral"],
        s=tamanos,
        c=colores,
        alpha=0.7,
        edgecolor="white",
    )
    ax.set_xlabel("Máx. contratos en ventana de 15 días")
    ax.set_ylabel("Proporción bajo 95% de cuantía parametrizada")
    ax.set_title("Señales de posible fraccionamiento\n(tamaño = score; rojo = caso sintético sembrado)")
    plt.tight_layout()
    plt.savefig("outputs/charts/06_deteccion_fraccionamiento.png", dpi=130)
    plt.close()


def main():
    df = cargar()
    df, modelo, scaler = detectar_anomalias(df)
    df = regla_interpretable(df)
    validar_sanity_check(df)
    graficar(df)

    ranking = df.sort_values("score_anomalia", ascending=False)
    ranking.to_csv("outputs/ranking_riesgo_fraccionamiento.csv", index=False)
    joblib.dump(modelo, "outputs/models/modelo_fraccionamiento_isoforest.joblib")
    joblib.dump(scaler, "outputs/models/scaler_fraccionamiento.joblib")
    print("\nModelo y scaler guardados en outputs/models/.")


if __name__ == "__main__":
    main()
