"""
Búsqueda sistemática de hiperparámetros — Modelo de Favoritismo.

Usa la misma matriz de features del modelo final. Contratación Directa y
Comparación de Precios permanecen separadas. En el pipeline orquestado consume
la capa Plata; `data/` es un fallback explícito para ejecución standalone.
"""

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score

from rutas_datos import entrada_plata

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]

PARAM_GRID = {
    "n_estimators": [100, 200, 300, 500],
    "max_depth": [3, 4, 6, 8, None],
    "min_samples_leaf": [1, 2, 4],
}


def main():
    df = pd.read_csv(entrada_plata("dataset_favoritismo.csv"))
    X = df[FEATURES]
    y = df["label_favoritismo_real"].astype(int)

    print(
        f"Grilla: {len(PARAM_GRID['n_estimators'])} x {len(PARAM_GRID['max_depth'])} x "
        f"{len(PARAM_GRID['min_samples_leaf'])} combinaciones; CV estratificada 3-fold."
    )
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    base = RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1)
    grid = GridSearchCV(base, PARAM_GRID, scoring="average_precision", cv=cv, n_jobs=-1, refit=True)
    grid.fit(X, y)

    resultados = pd.DataFrame(grid.cv_results_).sort_values("mean_test_score", ascending=False)
    resultados[["params", "mean_test_score", "std_test_score", "mean_fit_time"]].to_csv(
        "outputs/tuning_favoritismo_resultados.csv", index=False
    )

    manual = RandomForestClassifier(
        n_estimators=300, max_depth=6, class_weight="balanced", random_state=42
    )
    score_manual = cross_val_score(manual, X, y, cv=cv, scoring="average_precision").mean()
    print(f"Mejores hiperparámetros: {grid.best_params_}")
    print(f"Mejor AUC-PR (CV): {grid.best_score_:.4f}")
    print(f"Baseline histórico 300/6: AUC-PR = {score_manual:.4f}")
    return grid.best_params_, grid.best_score_


if __name__ == "__main__":
    main()
