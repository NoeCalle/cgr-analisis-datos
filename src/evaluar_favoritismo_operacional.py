"""Evaluación reproducible del modelo operacional de favoritismo.

La evidencia de selección usa exactamente la misma fuente monetaria que
TRAIN/INFERENCE modernos: ``monto_capped``. Se reserva un holdout final por
par proveedor-entidad ANTES de ajustar el preprocesador; el preprocesador se
ajusta solo con el conjunto de desarrollo y luego se congela para el holdout.

Los resultados siguen siendo un benchmark sintético del PoC y no estiman
performance productivo CGR.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.utils.class_weight import compute_sample_weight

from core.config import cargar_config
from ingestar_canonico import integrar
from preprocesamiento import (
    aplicar_estado_preprocesamiento,
    ajustar_estado_preprocesamiento,
    features_favoritismo,
)
from modelo_favoritismo import FEATURES

CONFIG_PATH = "config/local-training.yaml"
AMOUNT_SOURCE = "monto_capped"
HOLDOUT_SIZE = 0.25
HOLDOUT_SEED = 2026
PARAM_GRID = {
    "n_estimators": [100, 200, 300],
    "max_depth": [3, 4, 6, None],
    "min_samples_leaf": [1, 2, 4],
}


def _group_labels(contracts: pd.DataFrame) -> pd.DataFrame:
    return (
        contracts.groupby(["id_proveedor", "id_entidad"], as_index=False)["label_favoritismo"]
        .max()
        .rename(columns={"label_favoritismo": "label"})
    )


def _split_raw_contracts(contracts: pd.DataFrame):
    grupos = _group_labels(contracts)
    y = grupos["label"].astype(int)
    if y.nunique() != 2 or y.value_counts().min() < 4:
        raise ValueError(
            "Benchmark de favoritismo insuficiente para holdout estratificado: "
            f"conteos={y.value_counts().to_dict()}"
        )
    dev_groups, holdout_groups = train_test_split(
        grupos,
        test_size=HOLDOUT_SIZE,
        random_state=HOLDOUT_SEED,
        stratify=y,
    )
    dev_keys = set(zip(dev_groups["id_proveedor"], dev_groups["id_entidad"]))
    holdout_keys = set(zip(holdout_groups["id_proveedor"], holdout_groups["id_entidad"]))
    if dev_keys & holdout_keys:
        raise AssertionError("Split de favoritismo superpuesto")
    keys = list(zip(contracts["id_proveedor"], contracts["id_entidad"]))
    dev_mask = pd.Series([k in dev_keys for k in keys], index=contracts.index)
    holdout_mask = pd.Series([k in holdout_keys for k in keys], index=contracts.index)
    return contracts.loc[dev_mask].copy(), contracts.loc[holdout_mask].copy()


def construir_dev_holdout(config_path: str = CONFIG_PATH):
    config = cargar_config(config_path)
    if config.get("mode") != "training":
        raise ValueError("La evaluación operacional requiere mode: training")
    datasets, _ = integrar(config)
    contracts = datasets["contracts"]
    dev_raw, holdout_raw = _split_raw_contracts(contracts)

    estado = ajustar_estado_preprocesamiento(dev_raw)
    dev_proc = aplicar_estado_preprocesamiento(dev_raw, estado)
    holdout_proc = aplicar_estado_preprocesamiento(holdout_raw, estado)
    dev = features_favoritismo(
        dev_proc,
        label_col="label_favoritismo",
        output_label="label_favoritismo",
        monto_col=AMOUNT_SOURCE,
    )
    holdout = features_favoritismo(
        holdout_proc,
        label_col="label_favoritismo",
        output_label="label_favoritismo",
        monto_col=AMOUNT_SOURCE,
    )
    return contracts, dev, holdout, estado


def _cv_for(y: pd.Series) -> StratifiedKFold:
    min_class = int(y.astype(int).value_counts().min())
    n_splits = min(5, min_class)
    if n_splits < 3:
        raise ValueError(f"No hay positivos suficientes para CV: mínimo por clase={min_class}")
    return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)


def _metricas(y, proba, threshold=0.5):
    pred = (np.asarray(proba) >= threshold).astype(int)
    n_pos = int(np.asarray(y).sum())
    recall_at_k = None
    if n_pos:
        temp = pd.DataFrame({"score": proba, "label": np.asarray(y).astype(int)})
        recall_at_k = float(temp.nlargest(n_pos, "score")["label"].sum() / n_pos)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "auc_pr": float(average_precision_score(y, proba)),
        "auc_roc": float(roc_auc_score(y, proba)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "recall_at_k": recall_at_k,
        "threshold": float(threshold),
    }


def _oof_predictions(modelo, X, y, cv, *, use_sample_weight=False):
    proba = np.zeros(len(y), dtype=float)
    for train_idx, val_idx in cv.split(X, y):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train = y.iloc[train_idx]
        if use_sample_weight:
            weights = compute_sample_weight(class_weight="balanced", y=y_train)
            modelo.fit(X_train, y_train, sample_weight=weights)
        else:
            modelo.fit(X_train, y_train)
        proba[val_idx] = modelo.predict_proba(X_val)[:, 1]
    return proba


def evaluar(config_path: str = CONFIG_PATH):
    contracts, dev, holdout, estado = construir_dev_holdout(config_path)
    X_dev, y_dev = dev[FEATURES], dev["label_favoritismo"].astype(int)
    X_test, y_test = holdout[FEATURES], holdout["label_favoritismo"].astype(int)
    cv = _cv_for(y_dev)

    candidatos = {
        "RegresionLogistica": LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=42
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=100, max_depth=3, min_samples_leaf=1,
            class_weight="balanced", random_state=42, n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(random_state=42),
    }
    resultados = []
    for nombre, modelo in candidatos.items():
        proba = _oof_predictions(
            modelo,
            X_dev,
            y_dev,
            cv,
            use_sample_weight=(nombre == "GradientBoosting"),
        )
        resultados.append({"modelo": nombre, **_metricas(y_dev, proba)})

    tabla = pd.DataFrame(resultados).sort_values(
        ["auc_pr", "f1", "auc_roc"], ascending=False
    )
    tabla.to_csv("outputs/comparacion_modelos_favoritismo.csv", index=False)
    comparacion = {
        "schema_version": 2,
        "pipeline": "operational_frozen_preprocessor",
        "amount_source": AMOUNT_SOURCE,
        "split": "holdout final por par proveedor-entidad reservado antes del FIT del preprocesador",
        "preprocessor_fit_scope": "development_only",
        "cv": f"StratifiedKFold(n_splits={cv.n_splits}, shuffle=True, random_state=42)",
        "features": FEATURES,
        "n_contracts_total": int(len(contracts)),
        "n_dev": int(len(dev)),
        "positivos_dev": int(y_dev.sum()),
        "n_holdout": int(len(holdout)),
        "positivos_holdout": int(y_test.sum()),
        "criterio_primario": "AUC-PR por desbalance",
        "resultados": tabla.to_dict(orient="records"),
        "mejor_candidato": str(tabla.iloc[0]["modelo"]),
        "advertencia": "benchmark sintético; no estima desempeño productivo",
    }
    Path("outputs/comparacion_modelos_favoritismo.json").write_text(
        json.dumps(comparacion, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    base = RandomForestClassifier(
        class_weight="balanced", random_state=42, n_jobs=-1
    )
    grid = GridSearchCV(
        base,
        PARAM_GRID,
        scoring="average_precision",
        cv=cv,
        n_jobs=-1,
        refit=True,
    )
    grid.fit(X_dev, y_dev)
    resultados_grid = pd.DataFrame(grid.cv_results_).sort_values("mean_test_score", ascending=False)
    resultados_grid[["params", "mean_test_score", "std_test_score"]].to_csv(
        "outputs/tuning_favoritismo_resultados.csv", index=False
    )

    best = {k: (v.item() if hasattr(v, "item") else v) for k, v in grid.best_params_.items()}
    holdout_proba = grid.best_estimator_.predict_proba(X_test)[:, 1]
    holdout_metrics = _metricas(y_test, holdout_proba)
    tuning = {
        "schema_version": 2,
        "pipeline": "operational_frozen_preprocessor",
        "amount_source": AMOUNT_SOURCE,
        "features": FEATURES,
        "metrica_seleccion": "average_precision (AUC-PR) en desarrollo",
        "cv": comparacion["cv"],
        "holdout_final": "reservado antes de tuning y antes del FIT del preprocesador",
        "n_total": int(len(dev) + len(holdout)),
        "n_desarrollo": int(len(dev)),
        "positivos_desarrollo": int(y_dev.sum()),
        "n_holdout": int(len(holdout)),
        "positivos_holdout": int(y_test.sum()),
        "mejor_configuracion": best,
        "mejor_auc_pr_cv": float(grid.best_score_),
        "metricas_holdout_final": holdout_metrics,
        "preprocessor": {
            "schema_version": int(estado["schema_version"]),
            "fit_scope": "development_only",
            "monto_p99": float(estado["monto_p99"]),
        },
        "advertencia": "benchmark sintético; el holdout no debe reutilizarse para retuning",
    }
    Path("outputs/tuning_favoritismo_resumen.json").write_text(
        json.dumps(tuning, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(tuning, ensure_ascii=False, indent=2))
    return {"comparacion": comparacion, "tuning": tuning}


if __name__ == "__main__":
    evaluar()
