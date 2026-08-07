"""
Modelo de detección de Favoritismo — Tercer/Cuarto Producto del TDR.

Random Forest con validación cruzada estratificada y explicabilidad SHAP.
Corrección P1: Contratación Directa y Comparación de Precios se modelan como
variables separadas y, dentro del flujo orquestado, el modelo consume la capa
Plata del PoC. `data/` queda solo como fallback explícito para ejecución
standalone.
"""

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import auc, classification_report, precision_recall_curve, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from rutas_datos import entrada_plata

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]


def cargar():
    return pd.read_csv(entrada_plata("dataset_favoritismo.csv"))


def entrenar_y_validar(df):
    X = df[FEATURES]
    y = df["label_favoritismo_real"].astype(int)
    print(f"Casos positivos (favoritismo sembrado): {y.sum()} / {len(y)} ({y.mean()*100:.2f}%)")

    modelo = RandomForestClassifier(
        n_estimators=100, max_depth=3, min_samples_leaf=1,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )

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
    print(f"AUC-PR: {auc_pr:.3f}")

    modelo.fit(X, y)
    return modelo, auc_roc, auc_pr


def graficar_importancia(modelo, feature_names):
    importancias = pd.Series(modelo.feature_importances_, index=feature_names).sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    importancias.plot(kind="barh", ax=ax)
    ax.set_title("Importancia de variables — Modelo de Favoritismo\n(Gini, vista agregada)")
    ax.set_xlabel("Importancia (Gini)")
    plt.tight_layout()
    plt.savefig("outputs/charts/05_importancia_favoritismo.png", dpi=130)
    plt.close()
    return importancias


def explicar_con_shap(modelo, df):
    X = df[FEATURES]
    explainer = shap.TreeExplainer(modelo)
    shap_values = explainer(X)
    if len(shap_values.shape) == 3:
        shap_values = shap_values[:, :, 1]

    plt.figure(figsize=(8, 5.5))
    shap.summary_plot(shap_values, X, show=False)
    plt.title("Impacto SHAP por variable — Modelo de Favoritismo")
    plt.tight_layout()
    plt.savefig("outputs/charts/07_shap_summary_favoritismo.png", dpi=130)
    plt.close()

    idx_top = df["label_favoritismo_real"].astype(bool)
    pos = np.where(idx_top.values)[0][0] if idx_top.any() else int(np.argmax(modelo.predict_proba(X)[:, 1]))
    plt.figure(figsize=(8, 5))
    shap.plots.waterfall(shap_values[pos], show=False)
    caso = df.iloc[pos]
    plt.title(f"Explicación individual: {caso['id_proveedor']} en {caso['id_entidad']}")
    plt.tight_layout()
    plt.savefig("outputs/charts/08_shap_waterfall_caso.png", dpi=130)
    plt.close()
    print(f"\nArtefactos SHAP generados para {caso['id_proveedor']} / {caso['id_entidad']}")
    return shap_values


def generar_ranking_riesgo(modelo, df):
    df = df.copy()
    df["score_riesgo_favoritismo"] = modelo.predict_proba(df[FEATURES])[:, 1]
    ranking = df.sort_values("score_riesgo_favoritismo", ascending=False)
    ranking.to_csv("outputs/ranking_riesgo_favoritismo.csv", index=False)
    top10 = ranking[[
        "id_proveedor", "id_entidad", "n_contratos",
        "pct_contratacion_directa", "pct_comparacion_precios",
        "concentracion_objeto", "score_riesgo_favoritismo", "label_favoritismo_real",
    ]].head(10)
    print("\n--- Top 10 pares proveedor-entidad por score de riesgo ---")
    print(top10.to_string(index=False))
    n_reales = int(df["label_favoritismo_real"].sum())
    aciertos = ranking.head(n_reales)["label_favoritismo_real"].sum()
    print(f"\nSanity check sintético: {aciertos}/{n_reales} casos sembrados dentro del top-{n_reales}.")
    return ranking


def main():
    df = cargar()
    modelo, _, _ = entrenar_y_validar(df)
    graficar_importancia(modelo, FEATURES)
    explicar_con_shap(modelo, df)
    generar_ranking_riesgo(modelo, df)
    joblib.dump(modelo, "outputs/models/modelo_favoritismo_rf.joblib")
    print("\nModelo guardado en outputs/models/modelo_favoritismo_rf.joblib")


if __name__ == "__main__":
    main()
