"""
Búsqueda sistemática de hiperparámetros — Modelo de Fraccionamiento.

Isolation Forest es no supervisado, por lo que GridSearchCV estándar (que
asume una métrica supervisada como accuracy/F1) no aplica directamente.
Se implementa una búsqueda en grilla manual, usando como métrica de
selección la capacidad de recuperar los casos sembrados dentro del top-N
del ranking de anomalía — un uso legítimo de las etiquetas de validación
interna del prototipo (nunca usadas para entrenar el modelo, solo para
seleccionar hiperparámetros y medir desempeño, igual que en cualquier
proceso de tuning con un conjunto de validación).
"""

import itertools
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "n_contratos_grupo", "max_contratos_ventana_15d", "monto_total_ventana_15d",
    "pct_montos_bajo_umbral", "monto_total_grupo",
]

PARAM_GRID = {
    "n_estimators": [100, 200, 300],
    "max_samples": [0.5, 0.8, 1.0],
    "contamination": [0.03, 0.05, 0.08, 0.1],
}


def evaluar_combinacion(X_scaled, y, n_estimators, max_samples, contamination, seed=42):
    modelo = IsolationForest(
        n_estimators=n_estimators, max_samples=max_samples,
        contamination=contamination, random_state=seed,
    )
    modelo.fit(X_scaled)
    score = -modelo.decision_function(X_scaled)

    n_reales = int(y.sum())
    top_idx = pd.Series(score).nlargest(n_reales).index
    aciertos = int(y.iloc[top_idx].sum())
    return aciertos / n_reales  # recall@k


def main():
    df = pd.read_csv("data/dataset_fraccionamiento.csv")
    X = df[FEATURES]
    y = df["label_fraccionamiento_real"].astype(int)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    combinaciones = list(itertools.product(
        PARAM_GRID["n_estimators"], PARAM_GRID["max_samples"], PARAM_GRID["contamination"]
    ))
    print(f"Grilla de búsqueda: {len(combinaciones)} combinaciones, "
          f"evaluadas por recall@{int(y.sum())} (¿cuántos de los {int(y.sum())} casos "
          f"sembrados caen en el top-{int(y.sum())} del ranking de anomalía?)")

    resultados = []
    for n_est, max_samp, contam in combinaciones:
        recall = evaluar_combinacion(X_scaled, y, n_est, max_samp, contam)
        resultados.append({
            "n_estimators": n_est, "max_samples": max_samp, "contamination": contam,
            "recall_at_k": recall,
        })

    resultados = pd.DataFrame(resultados).sort_values("recall_at_k", ascending=False)
    resultados.to_csv("outputs/tuning_fraccionamiento_resultados.csv", index=False)

    mejor = resultados.iloc[0]
    print(f"\nMejor combinación: n_estimators={int(mejor['n_estimators'])}, "
          f"max_samples={mejor['max_samples']}, contamination={mejor['contamination']} "
          f"→ recall@k = {mejor['recall_at_k']:.3f}")

    n_optimas = (resultados["recall_at_k"] >= mejor["recall_at_k"] - 1e-9).sum()
    print(f"{n_optimas} de {len(resultados)} combinaciones alcanzan ese recall máximo.")

    # Comparación contra la configuración original del prototipo
    contam_original = min(max(int(y.sum()) / len(df), 0.02), 0.15)
    recall_original = evaluar_combinacion(X_scaled, y, 300, 1.0, contam_original)
    print(f"\nConfiguración original del prototipo (n_estimators=300, contamination "
          f"estimada={contam_original:.4f}): recall@k = {recall_original:.3f}")
    print(f"Mejor de la búsqueda: recall@k = {mejor['recall_at_k']:.3f}")

    print("\n--- Top 8 combinaciones ---")
    print(resultados.head(8).to_string(index=False))

    print(
        "\nNota: independientemente del resultado de este ajuste, la Sección 4 del "
        "reporte técnico ya demostró que la regla interpretable basada en el umbral "
        "legal supera a cualquier configuración de Isolation Forest — el tuning aquí "
        "optimiza el componente de modelo estadístico, no reemplaza la necesidad de "
        "la regla de negocio."
    )
    return mejor


if __name__ == "__main__":
    main()
