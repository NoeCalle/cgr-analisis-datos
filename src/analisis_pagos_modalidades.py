"""Análisis estadístico/exploratorio de pagos, montos y modalidades — Sprint 4.

Materializa una evidencia que faltaba en la lectura integral del TDR. Consume el
contrato canónico de ``contracts`` + ``payments`` y produce estadísticas, tablas
y gráficos estáticos programáticos.

La clasificación de modalidad frente a cuantía es referencial. Nunca declara
ilegalidad ni hallazgo: modalidades especiales pueden depender de supuestos que
no se infieren del monto por sí solo.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from core.config import cargar_config
from ingestar_canonico import integrar
from registro_modelos import guardar_json_determinista
from umbrales_normativos import (
    FUENTES_NORMATIVAS,
    clasificar_modalidad_frente_regimen,
    obtener_regimen,
)

OUTPUT_JSON = Path("outputs/analisis_pagos_modalidades.json")
OUTPUT_PAGOS = Path("outputs/resumen_pagos_contrato.csv")
OUTPUT_MODALIDADES = Path("outputs/resumen_modalidades_regimen.csv")
CHART_RATIO = Path("outputs/charts/11_ratio_pago_contrato.png")
CHART_MODALIDADES = Path("outputs/charts/12_modalidades_regimen.png")


def _to_float(value):
    return None if pd.isna(value) else float(value)


def _clasificar_ratio(ratio, pagos_count: int) -> str:
    if pagos_count == 0 or ratio is None or pd.isna(ratio):
        return "sin_pago_o_sin_cuantia"
    if ratio <= 0.01:
        return "pendiente_sin_pago"
    if ratio < 0.98:
        return "pago_parcial"
    if ratio > 1.02:
        return "sobrepago_senal_revisar"
    return "pagado_aproximadamente_completo"


def construir_resumen_pagos(contracts: pd.DataFrame, payments: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    pagos = payments.copy()
    for col in ["monto_devengado", "monto_pagado"]:
        if col not in pagos:
            pagos[col] = np.nan
        pagos[col] = pd.to_numeric(pagos[col], errors="coerce")
    for col in ["fecha_devengado", "fecha_girado", "fecha_pagado"]:
        if col in pagos:
            pagos[col] = pd.to_datetime(pagos[col], errors="coerce")

    ids_contrato = set(contracts["id_contrato"].astype(str))
    huerfanos = int((~pagos["id_contrato"].astype(str).isin(ids_contrato)).sum())

    pagos["dias_devengado_a_pagado"] = (
        pagos["fecha_pagado"] - pagos["fecha_devengado"]
    ).dt.days
    retrasos = pagos.loc[
        pagos["dias_devengado_a_pagado"].notna() & (pagos["dias_devengado_a_pagado"] >= 0),
        "dias_devengado_a_pagado",
    ]

    agg = (
        pagos.groupby("id_contrato", dropna=False)
        .agg(
            n_pagos=("id_pago", "count"),
            monto_devengado_total=("monto_devengado", "sum"),
            monto_pagado_total=("monto_pagado", "sum"),
            fecha_primer_devengado=("fecha_devengado", "min"),
            fecha_ultimo_pago=("fecha_pagado", "max"),
        )
        .reset_index()
    )

    contratos = contracts[["id_contrato", "monto", "modalidad", "fecha_contrato", "categoria_principal", "objeto"]].copy()
    contratos["monto"] = pd.to_numeric(contratos["monto"], errors="coerce")
    resumen = contratos.merge(agg, on="id_contrato", how="left")
    resumen["n_pagos"] = resumen["n_pagos"].fillna(0).astype(int)
    resumen["monto_devengado_total"] = resumen["monto_devengado_total"].fillna(0.0)
    resumen["monto_pagado_total"] = resumen["monto_pagado_total"].fillna(0.0)
    resumen["ratio_pagado_contrato"] = np.where(
        resumen["monto"].notna() & (resumen["monto"] > 0),
        resumen["monto_pagado_total"] / resumen["monto"],
        np.nan,
    )
    resumen["estado_pago_analitico"] = [
        _clasificar_ratio(r, int(n))
        for r, n in zip(resumen["ratio_pagado_contrato"], resumen["n_pagos"])
    ]

    estado_counts = resumen["estado_pago_analitico"].value_counts().to_dict()
    ratio_validos = resumen["ratio_pagado_contrato"].dropna()
    metricas = {
        "payments_rows": int(len(pagos)),
        "contracts_rows": int(len(contracts)),
        "contracts_with_payments": int((resumen["n_pagos"] > 0).sum()),
        "orphan_payments": huerfanos,
        "contract_amount_missing_rows": int(resumen["monto"].isna().sum()),
        "monto_contractual_total_valido": float(resumen["monto"].sum(skipna=True)),
        "monto_devengado_total": float(resumen["monto_devengado_total"].sum()),
        "monto_pagado_total": float(resumen["monto_pagado_total"].sum()),
        "ratio_pagado_global_sobre_monto_valido": (
            float(resumen["monto_pagado_total"].sum() / resumen["monto"].sum(skipna=True))
            if resumen["monto"].sum(skipna=True) > 0 else None
        ),
        "estado_pago_contratos": {str(k): int(v) for k, v in estado_counts.items()},
        "ratio_pagado_p50": _to_float(ratio_validos.quantile(0.50)) if len(ratio_validos) else None,
        "ratio_pagado_p90": _to_float(ratio_validos.quantile(0.90)) if len(ratio_validos) else None,
        "dias_devengado_a_pagado_p50": _to_float(retrasos.quantile(0.50)) if len(retrasos) else None,
        "dias_devengado_a_pagado_p90": _to_float(retrasos.quantile(0.90)) if len(retrasos) else None,
        "dias_devengado_a_pagado_p95": _to_float(retrasos.quantile(0.95)) if len(retrasos) else None,
    }
    return resumen, metricas


def construir_resumen_modalidades(contracts: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = contracts.copy()
    df["fecha_contrato"] = pd.to_datetime(df["fecha_contrato"], errors="raise")
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce")
    df["regimen"] = df["fecha_contrato"].map(obtener_regimen)

    clasificaciones = [
        clasificar_modalidad_frente_regimen(
            row.fecha_contrato,
            row.monto,
            row.modalidad,
            objeto=row.objeto,
            categoria_principal=row.categoria_principal,
        )
        for row in df.itertuples(index=False)
    ]
    df["clasificacion_modalidad"] = [c["clasificacion"] for c in clasificaciones]
    df["procedimiento_referencial_cuantia"] = [
        c["procedimiento_referencial"] for c in clasificaciones
    ]

    tabla = (
        df.assign(modalidad=df["modalidad"].fillna("SIN_DATO"))
        .groupby(["regimen", "modalidad", "clasificacion_modalidad"], dropna=False)
        .agg(
            n_contratos=("id_contrato", "count"),
            monto_contractual=("monto", "sum"),
        )
        .reset_index()
        .sort_values(["regimen", "n_contratos"], ascending=[True, False])
    )

    metricas = {
        "contratos_por_regimen": {
            str(k): int(v) for k, v in df["regimen"].value_counts().to_dict().items()
        },
        "clasificacion_modalidad": {
            str(k): int(v)
            for k, v in df["clasificacion_modalidad"].value_counts().to_dict().items()
        },
        "modalidades_observadas": {
            str(k): int(v)
            for k, v in df["modalidad"].fillna("SIN_DATO").value_counts().to_dict().items()
        },
        "nota_interpretacion": (
            "La comparación por cuantía es referencial. 'requiere_revision_contexto' no significa "
            "ilegalidad; exige revisar el supuesto jurídico, objeto, causal y demás antecedentes."
        ),
    }
    return tabla, metricas


def generar_graficos(resumen_pagos: pd.DataFrame, resumen_modalidades: pd.DataFrame) -> None:
    CHART_RATIO.parent.mkdir(parents=True, exist_ok=True)

    ratios = resumen_pagos["ratio_pagado_contrato"].dropna().clip(lower=0, upper=1.20)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.hist(ratios, bins=24)
    ax.set_title("Distribución sintética del ratio pagado / monto contractual")
    ax.set_xlabel("Ratio pagado sobre monto contractual (recortado a 1.20 para visualización)")
    ax.set_ylabel("Contratos")
    fig.tight_layout()
    fig.savefig(CHART_RATIO, dpi=160)
    plt.close(fig)

    pivot = (
        resumen_modalidades.groupby(["regimen", "modalidad"])["n_contratos"]
        .sum()
        .reset_index()
    )
    top = pivot.groupby("modalidad")["n_contratos"].sum().nlargest(8).index
    pivot = pivot[pivot["modalidad"].isin(top)].pivot(
        index="modalidad", columns="regimen", values="n_contratos"
    ).fillna(0)
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    pivot.plot(kind="barh", ax=ax)
    ax.set_title("Modalidades observadas por régimen en el dataset sintético")
    ax.set_xlabel("Contratos")
    ax.set_ylabel("Modalidad")
    fig.tight_layout()
    fig.savefig(CHART_MODALIDADES, dpi=160)
    plt.close(fig)


def analizar(config_path: str | Path = "config/local-tdr.yaml") -> dict:
    config = cargar_config(config_path)
    datasets, integration_summary = integrar(config)
    if "payments" not in datasets:
        raise ValueError("El análisis TDR de pagos requiere el dominio canónico 'payments'.")

    contracts = datasets["contracts"]
    payments = datasets["payments"]
    resumen_pagos, pagos_metricas = construir_resumen_pagos(contracts, payments)
    resumen_modalidades, modalidades_metricas = construir_resumen_modalidades(contracts)
    generar_graficos(resumen_pagos, resumen_modalidades)

    OUTPUT_PAGOS.parent.mkdir(parents=True, exist_ok=True)
    resumen_pagos.to_csv(OUTPUT_PAGOS, index=False)
    resumen_modalidades.to_csv(OUTPUT_MODALIDADES, index=False)

    summary = {
        "schema_version": 1,
        "scope": "analisis_profundo_pagos_y_modalidades_tdr_poc",
        "nature": "Datos sintéticos; no representan pagos SIAF ni decisiones de contratación reales.",
        "source_type": integration_summary["source_type"],
        "payments": pagos_metricas,
        "modalidades": modalidades_metricas,
        "normative_provenance_2023_2026": FUENTES_NORMATIVAS,
        "artifacts": {
            "resumen_pagos_contrato": OUTPUT_PAGOS.as_posix(),
            "resumen_modalidades_regimen": OUTPUT_MODALIDADES.as_posix(),
            "chart_ratio_pago": CHART_RATIO.as_posix(),
            "chart_modalidades_regimen": CHART_MODALIDADES.as_posix(),
        },
        "institutional_dependency": (
            "El reemplazo de pagos sintéticos por pagos SIAF reales, y la validación jurídica/funcional "
            "de modalidades, requiere fuentes, diccionarios y especialistas CGR."
        ),
    }
    guardar_json_determinista(OUTPUT_JSON, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Analiza pagos, montos y modalidades del contrato canónico.")
    parser.add_argument("--config", default="config/local-tdr.yaml")
    args = parser.parse_args()
    analizar(args.config)


if __name__ == "__main__":
    main()
