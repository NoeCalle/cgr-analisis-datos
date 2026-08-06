"""
Autoevaluación y Autoentrenamiento — objetivo específico 3.2.c del TDR:
"Incorporar mecanismos de autoevaluación y, cuando sea pertinente, de
autoentrenamiento para permitir la actualización continua de los modelos
mediante el análisis de nuevos datos, asegurando que los algoritmos se
mantengan precisos, pertinentes y adaptados a la evolución de los
patrones de contratación."

Mecanismo de decisión (dos señales independientes, cualquiera dispara
reentrenamiento):
  1. DERIVA DE DATOS (data drift): Population Stability Index (PSI) entre
     la distribución de entrenamiento y la del nuevo lote, sobre variables
     clave. PSI > 0.25 = deriva significativa (umbral estándar de la
     industria de riesgo crediticio, reutilizado aquí).
  2. DEGRADACIÓN DE DESEMPEÑO: si el nuevo lote trae casos ya conocidos
     (retroalimentación de auditores, numeral 3.2.c), se mide si el
     modelo actual los sigue detectando. Una caída de recall es la señal
     más directa de que el modelo quedó desactualizado.

Cuando se dispara, se reentrena con el histórico + el nuevo lote
combinados, se versiona el modelo, y se deja un registro auditable de la
decisión (no un reentrenamiento silencioso).
"""

import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

FEATURES_PSI = ["monto_total", "pct_no_competitiva", "concentracion_objeto"]
FEATURES_MODELO = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_no_competitiva", "n_funcionarios_distintos", "dias_actividad",
    "concentracion_objeto", "contratos_por_mes", "monto_por_funcionario",
]
UMBRAL_PSI = 0.25
UMBRAL_CAIDA_RECALL = 0.20  # dispara si el recall sobre casos nuevos conocidos cae más de 20 puntos
MODALIDADES_NO_COMPETITIVAS = {"Contratación Directa", "Comparación de Precios"}
LOG_PATH = "outputs/log_reentrenamiento.csv"


def calcular_psi(dist_entrenamiento, dist_nueva, n_bins=10):
    """Population Stability Index — mide qué tanto cambió la distribución
    de una variable entre dos períodos. Interpretación estándar:
    <0.10 sin cambio relevante | 0.10-0.25 cambio moderado | >0.25 cambio significativo."""
    breakpoints = np.quantile(dist_entrenamiento, np.linspace(0, 1, n_bins + 1))
    breakpoints[0], breakpoints[-1] = -np.inf, np.inf
    breakpoints = np.unique(breakpoints)

    freq_train = np.histogram(dist_entrenamiento, bins=breakpoints)[0] / len(dist_entrenamiento)
    freq_new = np.histogram(dist_nueva, bins=breakpoints)[0] / len(dist_nueva)
    freq_train = np.clip(freq_train, 1e-4, None)
    freq_new = np.clip(freq_new, 1e-4, None)

    psi = np.sum((freq_new - freq_train) * np.log(freq_new / freq_train))
    return float(psi)


def construir_features(df_contratos):
    """Misma agregación proveedor+entidad de src/preprocesamiento.py,
    aplicada aquí al nuevo lote."""
    df = df_contratos.copy()
    df["es_modalidad_no_competitiva"] = df["modalidad"].isin(MODALIDADES_NO_COMPETITIVAS)
    df["fecha_contrato"] = pd.to_datetime(df["fecha_contrato"])

    grp = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"), monto_total=("monto", "sum"),
        monto_promedio=("monto", "mean"), n_objetos_unicos=("objeto", "nunique"),
        pct_no_competitiva=("es_modalidad_no_competitiva", "mean"),
        n_funcionarios_distintos=("id_funcionario", "nunique"),
        fecha_min=("fecha_contrato", "min"), fecha_max=("fecha_contrato", "max"),
        label_favoritismo_real=("es_favoritismo_real", "max"),
    ).reset_index()

    grp["dias_actividad"] = (grp["fecha_max"] - grp["fecha_min"]).dt.days.clip(lower=1)
    grp["concentracion_objeto"] = 1 - (grp["n_objetos_unicos"] / grp["n_contratos"])
    grp["contratos_por_mes"] = grp["n_contratos"] / (grp["dias_actividad"] / 30)
    grp["monto_por_funcionario"] = grp["monto_total"] / grp["n_funcionarios_distintos"]
    return grp.drop(columns=["fecha_min", "fecha_max"])


def evaluar_deriva(df_train, df_nuevo):
    resultados = {}
    for feat in FEATURES_PSI:
        psi = calcular_psi(df_train[feat].values, df_nuevo[feat].values)
        resultados[feat] = round(psi, 4)
    psi_max = max(resultados.values())
    return resultados, psi_max


def evaluar_degradacion(modelo, df_nuevo):
    """Recall del modelo ACTUAL sobre los casos de favoritismo del nuevo
    lote (si los hay) — la retroalimentación de auditores del numeral 3.2.c."""
    positivos = df_nuevo[df_nuevo["label_favoritismo_real"] == True]
    if len(positivos) == 0:
        return None  # sin casos conocidos en este lote, no se puede medir directamente
    proba = modelo.predict_proba(df_nuevo[FEATURES_MODELO])[:, 1]
    df_nuevo = df_nuevo.copy()
    df_nuevo["score"] = proba
    n_reales = len(positivos)
    top_n = df_nuevo.sort_values("score", ascending=False).head(n_reales)
    recall = top_n["label_favoritismo_real"].sum() / n_reales
    return float(recall)


def reentrenar(df_train_original, df_nuevo_features):
    """Reentrena combinando el histórico con el nuevo lote."""
    combinado = pd.concat([df_train_original, df_nuevo_features], ignore_index=True)
    X = combinado[FEATURES_MODELO]
    y = combinado["label_favoritismo_real"].astype(int)
    modelo_nuevo = RandomForestClassifier(
        n_estimators=100, max_depth=3, min_samples_leaf=1,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    modelo_nuevo.fit(X, y)
    return modelo_nuevo, len(combinado)


def registrar_decision(escenario, psi_resultados, psi_max, recall_antes, disparo, motivo, n_datos_post=None):
    entrada = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "escenario": escenario,
        "psi_monto_total": psi_resultados.get("monto_total"),
        "psi_pct_no_competitiva": psi_resultados.get("pct_no_competitiva"),
        "psi_concentracion_objeto": psi_resultados.get("concentracion_objeto"),
        "psi_max": psi_max,
        "recall_casos_nuevos": recall_antes,
        "reentrenamiento_disparado": disparo,
        "motivo": motivo,
        "n_registros_modelo_resultante": n_datos_post,
    }
    df_entrada = pd.DataFrame([entrada])
    try:
        existente = pd.read_csv(LOG_PATH)
        df_log = pd.concat([existente, df_entrada], ignore_index=True)
    except FileNotFoundError:
        df_log = df_entrada
    df_log.to_csv(LOG_PATH, index=False)
    return entrada


def evaluar_lote(escenario, modelo, df_train_features):
    print(f"\n{'='*60}\nESCENARIO: {escenario}\n{'='*60}")
    df_contratos_nuevo = pd.read_csv(f"data/lote_nuevo_{escenario}.csv")
    df_nuevo_features = construir_features(df_contratos_nuevo)

    psi_resultados, psi_max = evaluar_deriva(df_train_features, df_nuevo_features)
    print(f"PSI por variable: {psi_resultados}")
    print(f"PSI máximo: {psi_max:.4f} (umbral de disparo: {UMBRAL_PSI})")

    recall_nuevo = evaluar_degradacion(modelo, df_nuevo_features)
    if recall_nuevo is not None:
        print(f"Recall del modelo actual sobre casos nuevos conocidos: {recall_nuevo:.2f}")

    dispara_por_drift = psi_max > UMBRAL_PSI
    dispara_por_recall = (recall_nuevo is not None) and (recall_nuevo < (1 - UMBRAL_CAIDA_RECALL))
    disparo = dispara_por_drift or dispara_por_recall

    motivos = []
    if dispara_por_drift:
        motivos.append(f"PSI máximo ({psi_max:.4f}) supera el umbral ({UMBRAL_PSI})")
    if dispara_por_recall:
        motivos.append(f"recall sobre casos nuevos ({recall_nuevo:.2f}) por debajo de {1-UMBRAL_CAIDA_RECALL:.2f}")
    motivo = "; ".join(motivos) if motivos else "sin señales de deriva ni degradación"

    n_datos_post = None
    if disparo:
        print(f"⚠ REENTRENAMIENTO DISPARADO: {motivo}")
        modelo_nuevo, n_datos_post = reentrenar(df_train_features, df_nuevo_features)
        import joblib
        joblib.dump(modelo_nuevo, f"outputs/models/modelo_favoritismo_rf_v2_{escenario}.joblib")
        recall_post = evaluar_degradacion(modelo_nuevo, df_nuevo_features)
        print(f"Modelo reentrenado con {n_datos_post} registros (histórico + nuevo lote).")
        if recall_post is not None:
            print(f"Recall del modelo REENTRENADO sobre los mismos casos nuevos: {recall_post:.2f}")
    else:
        print(f"✓ Sin acción: {motivo}")

    registrar_decision(escenario, psi_resultados, psi_max, recall_nuevo, disparo, motivo, n_datos_post)
    return disparo


def main():
    import joblib
    modelo = joblib.load("outputs/models/modelo_favoritismo_rf.joblib")
    df_train_features = pd.read_csv("data/dataset_favoritismo.csv")

    disparo_normal = evaluar_lote("normal", modelo, df_train_features)
    disparo_drift = evaluar_lote("con_drift", modelo, df_train_features)

    print(f"\n{'='*60}\nRESUMEN\n{'='*60}")
    print(f"Lote normal → reentrenamiento disparado: {disparo_normal} (esperado: False)")
    print(f"Lote con drift → reentrenamiento disparado: {disparo_drift} (esperado: True)")
    print(f"Mecanismo funcionando correctamente: {disparo_normal == False and disparo_drift == True}")
    print(f"\nRegistro completo de decisiones en {LOG_PATH}")


if __name__ == "__main__":
    main()
