"""
Tuning y evaluación independiente — detección de posible fraccionamiento.

Isolation Forest se entrena sin etiquetas. Las etiquetas sintéticas se usan
solo para comparar configuraciones en VALIDACIÓN. Un holdout final se separa
antes del tuning y se consulta una sola vez al final.

Por el fuerte desbalance y el escaso número de positivos, AUC-PR es el criterio
primario de selección; recall@K queda como métrica secundaria de ranking. En el
holdout final se reportan AUC-ROC, AUC-PR, precision, recall, F1 y recall@K.
Todo sigue siendo benchmark sintético y NO estima desempeño productivo.
"""

import itertools
import json

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from rutas_datos import entrada_plata

FEATURES = [
    "n_contratos_grupo", "max_contratos_ventana_15d", "monto_total_ventana_15d",
    "pct_montos_bajo_umbral", "monto_total_grupo",
]
PARAM_GRID = {
    "n_estimators": [100, 200, 300],
    "max_samples": [0.5, 0.8, 1.0],
    "contamination": ["auto", 0.03, 0.05, 0.08],
}
FINAL_TEST_SIZE = 0.375
VALIDATION_SIZE = 0.40
VALIDATION_SEEDS = [11, 23, 37, 53, 71]


def recall_at_k_from_scores(scores, y_eval):
    n_pos = int(y_eval.sum())
    if n_pos == 0:
        return None
    temp = pd.DataFrame({"score": scores, "label": y_eval.to_numpy()}, index=y_eval.index)
    return float(temp.nlargest(n_pos, "score")["label"].sum() / n_pos)


def entrenar_modelo(X_train, n_estimators, max_samples, contamination, seed):
    scaler = StandardScaler().fit(X_train)
    modelo = IsolationForest(
        n_estimators=n_estimators,
        max_samples=max_samples,
        contamination=contamination,
        random_state=seed,
    )
    modelo.fit(scaler.transform(X_train))
    return modelo, scaler


def evaluar_split(X_train, X_eval, y_eval, params, seed):
    modelo, scaler = entrenar_modelo(
        X_train,
        params["n_estimators"],
        params["max_samples"],
        params["contamination"],
        seed,
    )
    scores = -modelo.decision_function(scaler.transform(X_eval))
    return {
        "auc_pr": float(average_precision_score(y_eval, scores)),
        "recall_at_k": recall_at_k_from_scores(scores, y_eval),
    }


def separar_holdout_final(df):
    desarrollo, test = train_test_split(
        df,
        test_size=FINAL_TEST_SIZE,
        random_state=2026,
        stratify=df["label_fraccionamiento_real"].astype(int),
    )
    return desarrollo.reset_index(drop=True), test.reset_index(drop=True)


def evaluar_configuracion_en_desarrollo(desarrollo, params):
    auc_prs, recalls = [], []
    for seed in VALIDATION_SEEDS:
        train, val = train_test_split(
            desarrollo,
            test_size=VALIDATION_SIZE,
            random_state=seed,
            stratify=desarrollo["label_fraccionamiento_real"].astype(int),
        )
        m = evaluar_split(
            train[FEATURES],
            val[FEATURES],
            val["label_fraccionamiento_real"].astype(int),
            params,
            seed,
        )
        auc_prs.append(m["auc_pr"])
        if m["recall_at_k"] is not None:
            recalls.append(m["recall_at_k"])
    return {
        "auc_pr_validacion_medio": sum(auc_prs) / len(auc_prs),
        "auc_pr_min": min(auc_prs),
        "auc_pr_max": max(auc_prs),
        "recall_at_k_validacion_medio": sum(recalls) / len(recalls),
        "recall_at_k_min": min(recalls),
        "recall_at_k_max": max(recalls),
    }


def seleccionar_mejor(desarrollo):
    combinaciones = [
        {"n_estimators": n, "max_samples": m, "contamination": c}
        for n, m, c in itertools.product(
            PARAM_GRID["n_estimators"],
            PARAM_GRID["max_samples"],
            PARAM_GRID["contamination"],
        )
    ]
    filas = []
    for params in combinaciones:
        filas.append({**params, **evaluar_configuracion_en_desarrollo(desarrollo, params)})

    resultados = pd.DataFrame(filas).sort_values(
        ["auc_pr_validacion_medio", "recall_at_k_validacion_medio", "n_estimators"],
        ascending=[False, False, True],
    )
    resultados.to_csv("outputs/tuning_fraccionamiento_resultados.csv", index=False)
    return resultados.iloc[0].to_dict()


def evaluar_holdout_final(desarrollo, test, mejor):
    params = {
        "n_estimators": int(mejor["n_estimators"]),
        "max_samples": float(mejor["max_samples"]),
        "contamination": mejor["contamination"],
    }
    modelo, scaler = entrenar_modelo(desarrollo[FEATURES], **params, seed=2026)
    X_test_scaled = scaler.transform(test[FEATURES])
    scores = -modelo.decision_function(X_test_scaled)
    pred = (modelo.predict(X_test_scaled) == -1).astype(int)
    y = test["label_fraccionamiento_real"].astype(int)

    return {
        "recall_at_k": recall_at_k_from_scores(scores, y),
        "auc_roc": float(roc_auc_score(y, scores)),
        "auc_pr": float(average_precision_score(y, scores)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "n_test": len(test),
        "positivos_test": int(y.sum()),
        "anomalias_predichas": int(pred.sum()),
    }


def main():
    df = pd.read_csv(entrada_plata("dataset_fraccionamiento.csv"))
    desarrollo, test = separar_holdout_final(df)
    mejor = seleccionar_mejor(desarrollo)
    metricas_test = evaluar_holdout_final(desarrollo, test, mejor)

    resumen = {
        "diseno": "holdout final separado antes del tuning; validaciones repetidas solo en desarrollo",
        "metrica_seleccion": "AUC-PR media en validaciones repetidas",
        "n_total": len(df),
        "positivos_total": int(df["label_fraccionamiento_real"].sum()),
        "n_desarrollo": len(desarrollo),
        "positivos_desarrollo": int(desarrollo["label_fraccionamiento_real"].sum()),
        "mejor_configuracion": {
            "n_estimators": int(mejor["n_estimators"]),
            "max_samples": float(mejor["max_samples"]),
            "contamination": mejor["contamination"],
            "auc_pr_validacion_medio": float(mejor["auc_pr_validacion_medio"]),
            "recall_at_k_validacion_medio": float(mejor["recall_at_k_validacion_medio"]),
        },
        "metricas_holdout_final": metricas_test,
        "advertencia": "benchmark sintético con pocos positivos; no estima desempeño productivo",
    }
    with open("outputs/tuning_fraccionamiento_resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print("Mejor configuración:", resumen["mejor_configuracion"])
    print("Métricas HOLDOUT FINAL:", metricas_test)
    return resumen


if __name__ == "__main__":
    main()
