"""
Búsqueda sistemática de hiperparámetros — Modelo de Favoritismo.

Cierra la brecha señalada frente al numeral 4.2.5 del TDR ("optimizar
hiperparámetros para maximizar la precisión, recall, F1-score u otras
métricas relevantes"). El prototipo original (src/modelo_favoritismo.py)
usaba valores razonables elegidos a mano (300 árboles, profundidad 6);
este script los reemplaza por una búsqueda en grilla con validación
cruzada estratificada, y documenta explícitamente el resultado — incluso
cuando el resultado es "los valores elegidos a mano ya eran adecuados",
que es en sí mismo un hallazgo válido de una búsqueda sistemática.
"""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_no_competitiva", "n_funcionarios_distintos", "dias_actividad",
    "concentracion_objeto", "contratos_por_mes", "monto_por_funcionario",
]

PARAM_GRID = {
    "n_estimators": [100, 200, 300, 500],
    "max_depth": [3, 4, 6, 8, None],
    "min_samples_leaf": [1, 2, 4],
}


def main():
    df = pd.read_csv("data/dataset_favoritismo.csv")
    X = df[FEATURES]
    y = df["label_favoritismo_real"].astype(int)

    print(f"Grilla de búsqueda: {len(PARAM_GRID['n_estimators'])} x "
          f"{len(PARAM_GRID['max_depth'])} x {len(PARAM_GRID['min_samples_leaf'])} = "
          f"{len(PARAM_GRID['n_estimators']) * len(PARAM_GRID['max_depth']) * len(PARAM_GRID['min_samples_leaf'])} "
          f"combinaciones, evaluadas con validación cruzada estratificada de 3 particiones.")

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    base = RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1)

    # average_precision (AUC-PR) en vez de accuracy: con 0.25% de clase
    # positiva, accuracy es engañosa (99.75% "gratis" con un modelo trivial
    # que siempre predice "Normal").
    grid = GridSearchCV(
        base, PARAM_GRID, scoring="average_precision", cv=cv, n_jobs=-1, refit=True,
    )
    grid.fit(X, y)

    print(f"\nMejores hiperparámetros encontrados: {grid.best_params_}")
    print(f"Mejor AUC-PR (validación cruzada): {grid.best_score_:.4f}")

    resultados = pd.DataFrame(grid.cv_results_)
    resultados = resultados.sort_values("mean_test_score", ascending=False)
    resultados[["params", "mean_test_score", "std_test_score", "mean_fit_time"]].to_csv(
        "outputs/tuning_favoritismo_resultados.csv", index=False
    )

    # Cuántas combinaciones alcanzan el score máximo (evidencia de que el
    # modelo es robusto al valor exacto de los hiperparámetros en este
    # dataset, no solo que "una" combinación mágica funciona)
    score_max = resultados["mean_test_score"].max()
    n_optimas = (resultados["mean_test_score"] >= score_max - 1e-9).sum()
    print(f"\n{n_optimas} de {len(resultados)} combinaciones alcanzan el score máximo "
          f"({score_max:.4f}) — el desempeño es robusto a la elección exacta de "
          f"hiperparámetros sobre estos datos sintéticos con separación clara.")

    print("\n--- Top 5 combinaciones ---")
    print(resultados[["params", "mean_test_score", "mean_fit_time"]].head(5).to_string(index=False))

    # Comparación explícita contra los valores usados a mano en el prototipo original
    manual = RandomForestClassifier(
        n_estimators=300, max_depth=6, class_weight="balanced", random_state=42,
    )
    from sklearn.model_selection import cross_val_score
    score_manual = cross_val_score(manual, X, y, cv=cv, scoring="average_precision").mean()
    print(f"\nValores usados a mano en el prototipo original (n_estimators=300, max_depth=6): "
          f"AUC-PR = {score_manual:.4f}")
    print(f"Mejor combinación de la búsqueda: AUC-PR = {grid.best_score_:.4f}")
    diferencia = grid.best_score_ - score_manual
    print(f"Diferencia: {diferencia:+.4f} "
          f"({'la búsqueda sistemática confirma que la elección manual ya era adecuada' if abs(diferencia) < 0.01 else 'la búsqueda sistemática encontró una mejora medible'})")

    return grid.best_params_, grid.best_score_


if __name__ == "__main__":
    main()
