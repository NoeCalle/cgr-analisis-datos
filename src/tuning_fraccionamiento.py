"""
Tuning y evaluación independiente — detección de posible fraccionamiento.

Isolation Forest se entrena sin etiquetas. Las etiquetas sembradas se usan
solo para evaluar configuraciones en subconjuntos de VALIDACIÓN. Un holdout
final estratificado se separa antes del tuning y no participa en la selección
de hiperparámetros; se consulta una sola vez al final.

Con solo 8 positivos sintéticos, las métricas tienen alta varianza. Este diseño
mejora la independencia de la evaluación pero no convierte el benchmark
sintético en evidencia de desempeño productivo.
"""

import itertools
import json

import pandas as pd
from sklearn.ensemble import IsolationForest
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


def recall_at_k(modelo, scaler, X_eval, y_eval):
    n_pos = int(y_eval.sum())
    if n_pos == 0:
        return None
    scores = -modelo.decision_function(scaler.transform(X_eval))
    temp = pd.DataFrame({"score": scores, "label": y_eval.to_numpy()}, index=y_eval.index)
    return float(temp.nlargest(n_pos, "score")["label"].sum() / n_pos)


def entrenar_y_evaluar(X_train, X_eval, y_eval, n_estimators, max_samples, contamination, seed):
    scaler = StandardScaler().fit(X_train)
    modelo = IsolationForest(
        n_estimators=n_estimators,
        max_samples=max_samples,
        contamination=contamination,
        random_state=seed,
    )
    modelo.fit(scaler.transform(X_train))
    return recall_at_k(modelo, scaler, X_eval, y_eval)


def separar_holdout_final(df):
    desarrollo, test = train_test_split(
        df,
        test_size=FINAL_TEST_SIZE,
        random_state=2026,
        stratify=df["label_fraccionamiento_real"].astype(int),
    )
    return desarrollo.reset_index(drop=True), test.reset_index(drop=True)


def evaluar_configuracion_en_desarrollo(desarrollo, params):
    recalls = []
    for seed in VALIDATION_SEEDS:
        train, val = train_test_split(
            desarrollo,
            test_size=VALIDATION_SIZE,
            random_state=seed,
            stratify=desarrollo["label_fraccionamiento_real"].astype(int),
        )
        recall = entrenar_y_evaluar(
            train[FEATURES],
            val[FEATURES],
            val["label_fraccionamiento_real"].astype(int),
            params["n_estimators"],
            params["max_samples"],
            params["contamination"],
            seed,
        )
        if recall is not None:
            recalls.append(recall)
    return sum(recalls) / len(recalls), min(recalls), max(recalls)


def seleccionar_mejor(desarrollo):
    combinaciones = [
        {"n_estimators": n, "max_samples": m, "contamination": c}
        for n, m, c in itertools.product(
            PARAM_GRID["n_estimators"], PARAM_GRID["max_samples"], PARAM_GRID["contamination"]
        )
    ]
    filas = []
    for params in combinaciones:
        media, minimo, maximo = evaluar_configuracion_en_desarrollo(desarrollo, params)
        filas.append({**params, "recall_validacion_medio": media, "recall_min": minimo, "recall_max": maximo})
    resultados = pd.DataFrame(filas).sort_values(
        ["recall_validacion_medio", "n_estimators"], ascending=[False, True]
    )
    resultados.to_csv("outputs/tuning_fraccionamiento_resultados.csv", index=False)
    return resultados.iloc[0].to_dict(), resultados


def evaluar_holdout_final(desarrollo, test, mejor):
    scaler = StandardScaler().fit(desarrollo[FEATURES])
    modelo = IsolationForest(
        n_estimators=int(mejor["n_estimators"]),
        max_samples=float(mejor["max_samples"]),
        contamination=mejor["contamination"],
        random_state=2026,
    )
    modelo.fit(scaler.transform(desarrollo[FEATURES]))
    return recall_at_k(modelo, scaler, test[FEATURES], test["label_fraccionamiento_real"].astype(int))


def main():
    df = pd.read_csv(entrada_plata("dataset_fraccionamiento.csv"))
    desarrollo, test = separar_holdout_final(df)

    print(
        f"Dataset total: {len(df)} / {int(df['label_fraccionamiento_real'].sum())} positivos.\n"
        f"Desarrollo: {len(desarrollo)} / {int(desarrollo['label_fraccionamiento_real'].sum())}.\n"
        f"Holdout final: {len(test)} / {int(test['label_fraccionamiento_real'].sum())}."
    )

    mejor, _ = seleccionar_mejor(desarrollo)
    recall_test = evaluar_holdout_final(desarrollo, test, mejor)
    resumen = {
        "diseno": "holdout final separado antes del tuning; validaciones repetidas solo en desarrollo",
        "n_total": len(df),
        "positivos_total": int(df["label_fraccionamiento_real"].sum()),
        "n_desarrollo": len(desarrollo),
        "positivos_desarrollo": int(desarrollo["label_fraccionamiento_real"].sum()),
        "n_test_final": len(test),
        "positivos_test_final": int(test["label_fraccionamiento_real"].sum()),
        "mejor_configuracion": {
            "n_estimators": int(mejor["n_estimators"]),
            "max_samples": float(mejor["max_samples"]),
            "contamination": mejor["contamination"],
            "recall_validacion_medio": float(mejor["recall_validacion_medio"]),
        },
        "recall_at_k_holdout_final": recall_test,
        "advertencia": "benchmark sintético con pocos positivos; no estima desempeño productivo",
    }
    with open("outputs/tuning_fraccionamiento_resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print("\nMejor configuración según validación interna:", resumen["mejor_configuracion"])
    print(f"Recall@K en holdout FINAL: {recall_test}")
    return resumen


if __name__ == "__main__":
    main()
