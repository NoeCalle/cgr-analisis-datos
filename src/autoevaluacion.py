"""
Autoevaluación y autoentrenamiento — objetivo específico 3.2.c del TDR.

Correcciones P1:
- Contratación Directa y Comparación de Precios son features separadas.
- El disparador de desempeño se define como umbral absoluto de recall mínimo
  (0.80), no como una supuesta "caída de 20 puntos" sin baseline.
- Un modelo reentrenado se evalúa sobre un holdout del lote nuevo que NO se
  incorpora al entrenamiento del candidato.
- El modelo nuevo se guarda como CANDIDATO; no reemplaza automáticamente al
  modelo productivo. La promoción requiere revisión/aprobación, dejando una
  trazabilidad más adecuada para un contexto de auditoría.
"""

from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

FEATURES_PSI = [
    "monto_total", "pct_contratacion_directa", "pct_comparacion_precios",
    "concentracion_objeto",
]
FEATURES_MODELO = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]
UMBRAL_PSI = 0.25
UMBRAL_RECALL_MINIMO = 0.80
LOG_PATH = "outputs/log_reentrenamiento.csv"


def calcular_psi(dist_entrenamiento, dist_nueva, n_bins=10):
    breakpoints = np.quantile(dist_entrenamiento, np.linspace(0, 1, n_bins + 1))
    breakpoints[0], breakpoints[-1] = -np.inf, np.inf
    breakpoints = np.unique(breakpoints)
    if len(breakpoints) < 2:
        return 0.0

    freq_train = np.histogram(dist_entrenamiento, bins=breakpoints)[0] / len(dist_entrenamiento)
    freq_new = np.histogram(dist_nueva, bins=breakpoints)[0] / len(dist_nueva)
    freq_train = np.clip(freq_train, 1e-4, None)
    freq_new = np.clip(freq_new, 1e-4, None)
    return float(np.sum((freq_new - freq_train) * np.log(freq_new / freq_train)))


def construir_features(df_contratos):
    df = df_contratos.copy()
    df["es_contratacion_directa"] = df["modalidad"].eq("Contratación Directa")
    df["es_comparacion_precios"] = df["modalidad"].eq("Comparación de Precios")
    df["fecha_contrato"] = pd.to_datetime(df["fecha_contrato"])

    grp = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        monto_promedio=("monto", "mean"),
        n_objetos_unicos=("objeto", "nunique"),
        pct_contratacion_directa=("es_contratacion_directa", "mean"),
        pct_comparacion_precios=("es_comparacion_precios", "mean"),
        n_funcionarios_distintos=("id_funcionario", "nunique"),
        fecha_min=("fecha_contrato", "min"),
        fecha_max=("fecha_contrato", "max"),
        label_favoritismo_real=("es_favoritismo_real", "max"),
    ).reset_index()

    grp["dias_actividad"] = (grp["fecha_max"] - grp["fecha_min"]).dt.days.clip(lower=1)
    grp["concentracion_objeto"] = 1 - (grp["n_objetos_unicos"] / grp["n_contratos"])
    grp["contratos_por_mes"] = grp["n_contratos"] / (grp["dias_actividad"] / 30)
    grp["monto_por_funcionario"] = grp["monto_total"] / grp["n_funcionarios_distintos"].clip(lower=1)
    return grp.drop(columns=["fecha_min", "fecha_max"])


def evaluar_deriva(df_train, df_nuevo):
    resultados = {
        feat: round(calcular_psi(df_train[feat].values, df_nuevo[feat].values), 4)
        for feat in FEATURES_PSI
    }
    return resultados, max(resultados.values())


def evaluar_recall_ranking(modelo, df_eval):
    """Recall@K sobre casos etiquetados por feedback de auditor."""
    positivos = df_eval[df_eval["label_favoritismo_real"].astype(bool)]
    if len(positivos) == 0:
        return None
    proba = modelo.predict_proba(df_eval[FEATURES_MODELO])[:, 1]
    temp = df_eval.copy()
    temp["score"] = proba
    n_pos = len(positivos)
    top = temp.nlargest(n_pos, "score")
    return float(top["label_favoritismo_real"].astype(int).sum() / n_pos)


def dividir_lote_para_reentrenamiento(df_nuevo):
    """Separa datos nuevos de actualización y holdout independiente."""
    y = df_nuevo["label_favoritismo_real"].astype(int)
    # Stratify solo si ambas clases tienen suficientes observaciones.
    counts = y.value_counts()
    stratify = y if len(counts) == 2 and counts.min() >= 2 else None
    if len(df_nuevo) < 4:
        return df_nuevo.copy(), None
    train_new, holdout = train_test_split(
        df_nuevo,
        test_size=0.30,
        random_state=42,
        stratify=stratify,
    )
    return train_new, holdout


def entrenar_candidato(df_train_original, df_nuevo_train):
    combinado = pd.concat([df_train_original, df_nuevo_train], ignore_index=True)
    modelo = RandomForestClassifier(
        n_estimators=100,
        max_depth=3,
        min_samples_leaf=1,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    modelo.fit(combinado[FEATURES_MODELO], combinado["label_favoritismo_real"].astype(int))
    return modelo, len(combinado)


def registrar_decision(
    escenario,
    psi_resultados,
    psi_max,
    recall_antes,
    disparo,
    motivo,
    n_datos_post=None,
    recall_holdout_post=None,
    candidato_generado=False,
):
    entrada = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "escenario": escenario,
        "psi_monto_total": psi_resultados.get("monto_total"),
        "psi_pct_contratacion_directa": psi_resultados.get("pct_contratacion_directa"),
        "psi_pct_comparacion_precios": psi_resultados.get("pct_comparacion_precios"),
        "psi_concentracion_objeto": psi_resultados.get("concentracion_objeto"),
        "psi_max": psi_max,
        "recall_lote_nuevo_antes": recall_antes,
        "reentrenamiento_disparado": disparo,
        "motivo": motivo,
        "n_registros_candidato": n_datos_post,
        "recall_holdout_post": recall_holdout_post,
        "modelo_candidato_generado": candidato_generado,
        "promocion_automatica": False,
    }
    nuevo = pd.DataFrame([entrada])
    try:
        existente = pd.read_csv(LOG_PATH)
        # Permitir evolución de esquema del log sin perder histórico.
        log = pd.concat([existente, nuevo], ignore_index=True, sort=False)
    except FileNotFoundError:
        log = nuevo
    log.to_csv(LOG_PATH, index=False)
    return entrada


def evaluar_lote(escenario, modelo_actual, df_train_features):
    print(f"\n{'='*60}\nESCENARIO: {escenario}\n{'='*60}")
    contratos_nuevos = pd.read_csv(f"data/lote_nuevo_{escenario}.csv")
    df_nuevo = construir_features(contratos_nuevos)

    psi_resultados, psi_max = evaluar_deriva(df_train_features, df_nuevo)
    recall_antes = evaluar_recall_ranking(modelo_actual, df_nuevo)

    dispara_drift = psi_max > UMBRAL_PSI
    dispara_recall = recall_antes is not None and recall_antes < UMBRAL_RECALL_MINIMO
    disparo = dispara_drift or dispara_recall

    motivos = []
    if dispara_drift:
        motivos.append(f"PSI máximo {psi_max:.4f} > {UMBRAL_PSI}")
    if dispara_recall:
        motivos.append(f"recall {recall_antes:.2f} < mínimo {UMBRAL_RECALL_MINIMO:.2f}")
    motivo = "; ".join(motivos) if motivos else "sin señales que requieran reentrenamiento"

    n_post = None
    recall_holdout = None
    candidato = False
    if disparo:
        nuevo_train, holdout = dividir_lote_para_reentrenamiento(df_nuevo)
        modelo_candidato, n_post = entrenar_candidato(df_train_features, nuevo_train)
        ruta = f"outputs/models/modelo_favoritismo_candidato_{escenario}.joblib"
        joblib.dump(modelo_candidato, ruta)
        candidato = True
        if holdout is not None:
            recall_holdout = evaluar_recall_ranking(modelo_candidato, holdout)
        print(f"Candidato generado: {ruta}")
        print("No se promueve automáticamente: requiere revisión/aprobación.")
    else:
        print(f"Sin acción: {motivo}")

    registrar_decision(
        escenario,
        psi_resultados,
        psi_max,
        recall_antes,
        disparo,
        motivo,
        n_post,
        recall_holdout,
        candidato,
    )
    return disparo


def main():
    modelo = joblib.load("outputs/models/modelo_favoritismo_rf.joblib")
    train = pd.read_csv("data/dataset_favoritismo.csv")

    normal = evaluar_lote("normal", modelo, train)
    drift = evaluar_lote("con_drift", modelo, train)

    print(f"\nLote normal → disparo: {normal}")
    print(f"Lote con drift → disparo: {drift}")
    print(f"Registro de decisiones: {LOG_PATH}")


if __name__ == "__main__":
    main()
