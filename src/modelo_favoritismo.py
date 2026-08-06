"""
Modelo de detección de Favoritismo — Tercer/Cuarto Producto del TDR.

Cubre el numeral 4.2.2 ("Identificación de Favoritismo: Modelos de
clasificación... o de puntuación de riesgo") y el ítem 5 del checklist del
Anexo 3 ("Interpretabilidad Orientada a Auditoría (Caja Blanca): entrega de
artefactos de explicabilidad... para sustentar los hallazgos ante
auditores").

Modelo: Random Forest con class_weight='balanced' (la clase positiva es
rara por naturaleza — el favoritismo real es una minoría de los contratos).
Se usa Feature Importance nativa de scikit-learn como artefacto de
explicabilidad; en producción sobre Spark MLlib se reemplaza por SHAP
(TreeExplainer) sobre el RandomForestClassificationModel, que es el
formato que pide explícitamente el checklist.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_recall_curve, auc
)
import joblib

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_no_competitiva", "n_funcionarios_distintos", "dias_actividad",
    "concentracion_objeto", "contratos_por_mes", "monto_por_funcionario",
]


def cargar():
    return pd.read_csv("data/dataset_favoritismo.csv")


def entrenar_y_validar(df):
    X = df[FEATURES]
    y = df["label_favoritismo_real"].astype(int)

    print(f"Casos positivos (favoritismo real): {y.sum()} / {len(y)} "
          f"({y.mean()*100:.2f}%)")

    modelo = RandomForestClassifier(
        n_estimators=300, max_depth=6, class_weight="balanced",
        random_state=42, n_jobs=-1,
    )

    # Validación cruzada estratificada (numeral 4.2.5: "aplicar técnicas de
    # validación cruzada"). Con una clase positiva tan rara, 3 folds asegura
    # al menos 1-2 positivos por fold de prueba.
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    y_proba_cv = cross_val_predict(modelo, X, y, cv=cv, method="predict_proba")[:, 1]
    y_pred_cv = (y_proba_cv >= 0.5).astype(int)

    print("\n--- Métricas de validación cruzada (3-fold) ---")
    print(classification_report(y, y_pred_cv, target_names=["Normal", "Favoritismo"], zero_division=0))
    try:
        auc_roc = roc_auc_score(y, y_proba_cv)
        print(f"AUC-ROC: {auc_roc:.3f}")
    except ValueError:
        auc_roc = None

    precision, recall, _ = precision_recall_curve(y, y_proba_cv)
    auc_pr = auc(recall, precision)
    print(f"AUC-PR (más informativo con clases desbalanceadas): {auc_pr:.3f}")

    # Modelo final entrenado con todos los datos (para producción/scoring)
    modelo.fit(X, y)
    return modelo, auc_roc, auc_pr


def graficar_importancia(modelo, feature_names):
    importancias = pd.Series(modelo.feature_importances_, index=feature_names).sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    importancias.plot(kind="barh", ax=ax, color="#2b6cb0")
    ax.set_title("Importancia de variables — Modelo de Favoritismo\n(artefacto de explicabilidad para auditores)")
    ax.set_xlabel("Importancia (Gini)")
    plt.tight_layout()
    plt.savefig("outputs/charts/05_importancia_favoritismo.png", dpi=130)
    plt.close()
    return importancias


def generar_ranking_riesgo(modelo, df):
    """Puntaje de riesgo de favoritismo para todos los pares proveedor-entidad
    (numeral 3.2.d del TDR: 'Calcular métricas de riesgo de favoritismo')."""
    df = df.copy()
    df["score_riesgo_favoritismo"] = modelo.predict_proba(df[FEATURES])[:, 1]
    ranking = df.sort_values("score_riesgo_favoritismo", ascending=False)
    ranking.to_csv("outputs/ranking_riesgo_favoritismo.csv", index=False)

    top10 = ranking[["id_proveedor", "id_entidad", "n_contratos", "pct_no_competitiva",
                      "concentracion_objeto", "score_riesgo_favoritismo",
                      "label_favoritismo_real"]].head(10)
    print("\n--- Top 10 pares proveedor-entidad por riesgo de favoritismo ---")
    print(top10.to_string(index=False))
    aciertos = ranking.head(int(df["label_favoritismo_real"].sum())
                             )["label_favoritismo_real"].sum()
    print(f"\nDe los {int(df['label_favoritismo_real'].sum())} casos reales sembrados, "
          f"{aciertos} aparecen dentro del top {int(df['label_favoritismo_real'].sum())} del ranking.")
    return ranking


def main():
    df = cargar()
    modelo, auc_roc, auc_pr = entrenar_y_validar(df)
    graficar_importancia(modelo, FEATURES)
    generar_ranking_riesgo(modelo, df)
    joblib.dump(modelo, "outputs/models/modelo_favoritismo_rf.joblib")
    print("\nModelo guardado en outputs/models/modelo_favoritismo_rf.joblib")


if __name__ == "__main__":
    main()
