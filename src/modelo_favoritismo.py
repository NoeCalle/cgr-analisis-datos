"""
Modelo de detección de Favoritismo — Tercer/Cuarto Producto del TDR.

Random Forest con validación cruzada y explicabilidad SHAP. Consume la capa
Plata del PoC y, cuando existe, usa la configuración seleccionada por
`src/tuning_favoritismo.py` en `outputs/tuning_favoritismo_resumen.json`.
"""

import json
from pathlib import Path

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
DEFAULT_PARAMS = {"n_estimators": 100, "max_depth": 3, "min_samples_leaf": 1}
TUNING_PATH = Path("outputs/tuning_favoritismo_resumen.json")


def cargar():
    return pd.read_csv(entrada_plata("dataset_favoritismo.csv"))


def parametros_seleccionados():
    if not TUNING_PATH.exists():
        print(f"ADVERTENCIA: no existe {TUNING_PATH}; se usan defaults documentados {DEFAULT_PARAMS}.")
        return DEFAULT_PARAMS.copy()
    with TUNING_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    params = data.get("mejor_configuracion", {})
    requeridos = {"n_estimators", "max_depth", "min_samples_leaf"}
    if not requeridos.issubset(params):
        raise ValueError(f"Resumen de tuning incompleto: faltan {sorted(requeridos - set(params))}")
    print(f"Configuración leída de tuning: {params}")
    return params


def entrenar_y_validar(df, params):
    X = df[FEATURES]
    y = df["label_favoritismo_real"].astype(int)
    print(f"Casos positivos sembrados: {y.sum()} / {len(y)} ({y.mean()*100:.2f}%)")

    modelo = RandomForestClassifier(
        **params,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    y_proba_cv = cross_val_predict(modelo, X, y, cv=cv, method="predict_proba")[:, 1]
    y_pred_cv = (y_proba_cv >= 0.5).astype(int)

    print("\n--- Métricas CV del modelo seleccionado ---")
    print(classification_report(y, y_pred_cv, target_names=["Normal", "Favoritismo"], zero_division=0))
    auc_roc = roc_auc_score(y, y_proba_cv)
    precision, recall, _ = precision_recall_curve(y, y_proba_cv)
    auc_pr = auc(recall, precision)
    print(f"AUC-ROC: {auc_roc:.3f} | AUC-PR: {auc_pr:.3f}")

    modelo.fit(X, y)
    return modelo, auc_roc, auc_pr


def graficar_importancia(modelo, feature_names):
    importancias = pd.Series(modelo.feature_importances_, index=feature_names).sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    importancias.plot(kind="barh", ax=ax)
    ax.set_title("Importancia de variables — Modelo de Favoritismo")
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
    return shap_values


def generar_ranking_riesgo(modelo, df):
    df = df.copy()
    df["score_riesgo_favoritismo"] = modelo.predict_proba(df[FEATURES])[:, 1]
    ranking = df.sort_values("score_riesgo_favoritismo", ascending=False)
    ranking.to_csv("outputs/ranking_riesgo_favoritismo.csv", index=False)
    n_reales = int(df["label_favoritismo_real"].sum())
    aciertos = int(ranking.head(n_reales)["label_favoritismo_real"].sum())
    print(f"Sanity check sintético top-{n_reales}: {aciertos}/{n_reales}.")
    return ranking


def main():
    df = cargar()
    params = parametros_seleccionados()
    modelo, _, _ = entrenar_y_validar(df, params)
    graficar_importancia(modelo, FEATURES)
    explicar_con_shap(modelo, df)
    generar_ranking_riesgo(modelo, df)
    joblib.dump(modelo, "outputs/models/modelo_favoritismo_rf.joblib")
    print("Modelo guardado en outputs/models/modelo_favoritismo_rf.joblib")


if __name__ == "__main__":
    main()
