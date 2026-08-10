"""Tuning y evaluación independiente — benchmark IsolationForest de fraccionamiento.

Isolation Forest se entrena sin etiquetas. Las etiquetas sintéticas se usan
solo para selección/evaluación. Un holdout final se reserva antes del tuning.

La selección se divide en dos problemas distintos:
1) ``n_estimators``/``max_samples`` se eligen por AUC-PR y recall@K del ranking;
2) ``contamination`` se calibra después, solo en desarrollo, por F1 medio.

Esto evita fingir que ``contamination`` fue elegido por AUC-PR: ese parámetro
mueve el umbral de clasificación, pero no cambia el orden de los scores para una
misma muestra/semilla. El archivo sigue siendo benchmark de compatibilidad; el
champion activo Spark KMeans tiene su propia evaluación y holdout.
"""

import itertools
import json

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    accuracy_score,
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
RANKING_GRID = {
    "n_estimators": [100, 200, 300],
    "max_samples": [0.5, 0.8, 1.0],
}
CONTAMINATION_GRID = ["auto", 0.03, 0.05, 0.08, 0.12]
FINAL_TEST_SIZE = 0.30
VALIDATION_SIZE = 0.30
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
        n_estimators=int(n_estimators),
        max_samples=float(max_samples),
        contamination=contamination,
        random_state=seed,
    )
    modelo.fit(scaler.transform(X_train))
    return modelo, scaler


def separar_holdout_final(df):
    desarrollo, test = train_test_split(
        df,
        test_size=FINAL_TEST_SIZE,
        random_state=2026,
        stratify=df["label_fraccionamiento_real"].astype(int),
    )
    return desarrollo.reset_index(drop=True), test.reset_index(drop=True)


def evaluar_ranking_en_desarrollo(desarrollo, params):
    auc_prs, recalls = [], []
    for seed in VALIDATION_SEEDS:
        train, val = train_test_split(
            desarrollo,
            test_size=VALIDATION_SIZE,
            random_state=seed,
            stratify=desarrollo["label_fraccionamiento_real"].astype(int),
        )
        modelo, scaler = entrenar_modelo(
            train[FEATURES],
            params["n_estimators"],
            params["max_samples"],
            "auto",
            seed,
        )
        scores = -modelo.decision_function(scaler.transform(val[FEATURES]))
        y = val["label_fraccionamiento_real"].astype(int)
        auc_prs.append(float(average_precision_score(y, scores)))
        recall_k = recall_at_k_from_scores(scores, y)
        if recall_k is not None:
            recalls.append(recall_k)
    return {
        "auc_pr_validacion_medio": float(sum(auc_prs) / len(auc_prs)),
        "auc_pr_min": float(min(auc_prs)),
        "auc_pr_max": float(max(auc_prs)),
        "recall_at_k_validacion_medio": float(sum(recalls) / len(recalls)),
        "recall_at_k_min": float(min(recalls)),
        "recall_at_k_max": float(max(recalls)),
    }


def seleccionar_ranking(desarrollo):
    combinaciones = [
        {"n_estimators": n, "max_samples": m}
        for n, m in itertools.product(
            RANKING_GRID["n_estimators"], RANKING_GRID["max_samples"]
        )
    ]
    filas = [
        {**params, **evaluar_ranking_en_desarrollo(desarrollo, params)}
        for params in combinaciones
    ]
    resultados = pd.DataFrame(filas).sort_values(
        ["auc_pr_validacion_medio", "recall_at_k_validacion_medio", "n_estimators"],
        ascending=[False, False, True],
    )
    return resultados, resultados.iloc[0].to_dict()


def evaluar_contamination_en_desarrollo(desarrollo, ranking_params, contamination):
    f1s, precisions, recalls = [], [], []
    for seed in VALIDATION_SEEDS:
        train, val = train_test_split(
            desarrollo,
            test_size=VALIDATION_SIZE,
            random_state=seed,
            stratify=desarrollo["label_fraccionamiento_real"].astype(int),
        )
        modelo, scaler = entrenar_modelo(
            train[FEATURES],
            ranking_params["n_estimators"],
            ranking_params["max_samples"],
            contamination,
            seed,
        )
        pred = (modelo.predict(scaler.transform(val[FEATURES])) == -1).astype(int)
        y = val["label_fraccionamiento_real"].astype(int)
        f1s.append(float(f1_score(y, pred, zero_division=0)))
        precisions.append(float(precision_score(y, pred, zero_division=0)))
        recalls.append(float(recall_score(y, pred, zero_division=0)))
    return {
        "contamination": contamination,
        "f1_validacion_medio": float(sum(f1s) / len(f1s)),
        "precision_validacion_media": float(sum(precisions) / len(precisions)),
        "recall_validacion_medio": float(sum(recalls) / len(recalls)),
    }


def seleccionar_contamination(desarrollo, ranking_params):
    filas = [
        evaluar_contamination_en_desarrollo(desarrollo, ranking_params, c)
        for c in CONTAMINATION_GRID
    ]
    tabla = pd.DataFrame(filas).sort_values(
        ["f1_validacion_medio", "precision_validacion_media", "recall_validacion_medio"],
        ascending=False,
    )
    return tabla, tabla.iloc[0].to_dict()


def evaluar_holdout_final(desarrollo, test, ranking_params, contamination):
    modelo, scaler = entrenar_modelo(
        desarrollo[FEATURES],
        int(ranking_params["n_estimators"]),
        float(ranking_params["max_samples"]),
        contamination,
        2026,
    )
    X_test_scaled = scaler.transform(test[FEATURES])
    scores = -modelo.decision_function(X_test_scaled)
    pred = (modelo.predict(X_test_scaled) == -1).astype(int)
    y = test["label_fraccionamiento_real"].astype(int)
    return {
        "recall_at_k": recall_at_k_from_scores(scores, y),
        "accuracy": float(accuracy_score(y, pred)),
        "auc_roc": float(roc_auc_score(y, scores)),
        "auc_pr": float(average_precision_score(y, scores)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "n_test": int(len(test)),
        "positivos_test": int(y.sum()),
        "anomalias_predichas": int(pred.sum()),
    }


def main():
    df = pd.read_csv(entrada_plata("dataset_fraccionamiento.csv"))
    desarrollo, test = separar_holdout_final(df)
    ranking_results, best_ranking = seleccionar_ranking(desarrollo)
    contamination_results, best_threshold = seleccionar_contamination(
        desarrollo, best_ranking
    )

    # Un único CSV conserva las dos fases de selección sin presentar
    # contamination como si modificara AUC-PR.
    ranking_export = ranking_results.copy()
    ranking_export.insert(0, "fase", "ranking")
    threshold_export = contamination_results.copy()
    threshold_export.insert(0, "fase", "threshold")
    pd.concat([ranking_export, threshold_export], ignore_index=True, sort=False).to_csv(
        "outputs/tuning_fraccionamiento_resultados.csv", index=False
    )

    contamination = best_threshold["contamination"]
    metricas_test = evaluar_holdout_final(
        desarrollo, test, best_ranking, contamination
    )
    resumen = {
        "schema_version": 2,
        "diseno": "holdout final separado antes del tuning; ranking y umbral calibrados solo en desarrollo",
        "metrica_seleccion": "AUC-PR media para ranking; F1 medio para contamination/umbral binario",
        "metricas_reportadas_holdout": ["accuracy", "auc_roc", "auc_pr", "precision", "recall", "f1", "recall_at_k"],
        "n_total": int(len(df)),
        "positivos_total": int(df["label_fraccionamiento_real"].sum()),
        "n_desarrollo": int(len(desarrollo)),
        "positivos_desarrollo": int(desarrollo["label_fraccionamiento_real"].sum()),
        "mejor_configuracion": {
            "n_estimators": int(best_ranking["n_estimators"]),
            "max_samples": float(best_ranking["max_samples"]),
            "contamination": contamination,
            "auc_pr_validacion_medio": float(best_ranking["auc_pr_validacion_medio"]),
            "recall_at_k_validacion_medio": float(best_ranking["recall_at_k_validacion_medio"]),
            "f1_umbral_validacion_medio": float(best_threshold["f1_validacion_medio"]),
        },
        "selection_protocol": {
            "ranking_params": "n_estimators/max_samples seleccionados por AUC-PR y recall@K",
            "binary_threshold": "contamination seleccionada después por F1 de validación",
            "holdout_used_for_selection": False,
        },
        "metricas_holdout_final": metricas_test,
        "advertencia": "benchmark sintético de compatibilidad; el champion Spark KMeans tiene evaluación independiente",
    }
    with open("outputs/tuning_fraccionamiento_resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print("Mejor configuración:", resumen["mejor_configuracion"])
    print("Métricas HOLDOUT FINAL:", metricas_test)
    return resumen


if __name__ == "__main__":
    main()
