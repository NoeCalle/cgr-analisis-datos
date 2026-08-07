"""
Comparación de algoritmos candidatos — Favoritismo (Producto 3 del TDR).

Evalúa Regresión Logística, Random Forest y Gradient Boosting con las mismas
particiones StratifiedKFold y predicciones out-of-fold. El objetivo es dejar
evidencia reproducible de la selección, no afirmar que un algoritmo fue
"evaluado" solo porque se lo menciona en un informe.

El benchmark sigue siendo sintético y pequeño en clase positiva; estas métricas
sirven para comparar candidatos dentro del PoC, no para estimar producción.
"""

import json

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

from rutas_datos import entrada_plata

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]


def candidatos():
    return {
        "RegresionLogistica": LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=42
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=100, max_depth=3, min_samples_leaf=1,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(random_state=42),
    }


def predicciones_oof(modelo, X, y, cv, usar_sample_weight=False):
    proba = np.zeros(len(y), dtype=float)
    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train = y.iloc[train_idx]
        if usar_sample_weight:
            pesos = compute_sample_weight(class_weight="balanced", y=y_train)
            modelo.fit(X_train, y_train, sample_weight=pesos)
        else:
            modelo.fit(X_train, y_train)
        proba[test_idx] = modelo.predict_proba(X_test)[:, 1]
    return proba


def metricas(y, proba, umbral=0.5):
    pred = (proba >= umbral).astype(int)
    return {
        "auc_pr": float(average_precision_score(y, proba)),
        "auc_roc": float(roc_auc_score(y, proba)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
    }


def main():
    df = pd.read_csv(entrada_plata("dataset_favoritismo.csv"))
    X = df[FEATURES]
    y = df["label_favoritismo_real"].astype(int)
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)

    resultados = []
    for nombre, modelo in candidatos().items():
        proba = predicciones_oof(
            modelo, X, y, cv,
            usar_sample_weight=(nombre == "GradientBoosting"),
        )
        resultados.append({"modelo": nombre, **metricas(y, proba)})

    tabla = pd.DataFrame(resultados).sort_values(
        ["auc_pr", "f1", "auc_roc"], ascending=False
    )
    tabla.to_csv("outputs/comparacion_modelos_favoritismo.csv", index=False)

    resumen = {
        "diseno": "predicciones out-of-fold, StratifiedKFold 3-fold, mismas particiones para todos",
        "features": FEATURES,
        "n_registros": len(df),
        "positivos": int(y.sum()),
        "criterio_primario": "AUC-PR por desbalance severo",
        "resultados": tabla.to_dict(orient="records"),
        "mejor_candidato": tabla.iloc[0]["modelo"],
        "advertencia": "comparación sobre benchmark sintético; no estima desempeño productivo",
    }
    with open("outputs/comparacion_modelos_favoritismo.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print(tabla.to_string(index=False))
    print(f"Candidato con mayor AUC-PR OOF: {resumen['mejor_candidato']}")
    return resumen


if __name__ == "__main__":
    main()
