"""Genera evidencia explícita de linaje de datos del PoC.

El Anexo 3 del TDR pide rastrear el dato desde la fuente hasta el modelo final.
Sprint 4 añade el recorrido de pagos sintéticos y hace explícito que el serving
operacional de favoritismo consume ``monto_capped`` mientras la reconstrucción
legacy conserva ``monto``. Este artefacto no sustituye el lineage institucional.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OUTPUT = Path("outputs/linaje_datos.csv")

COLUMNAS = [
    "dominio",
    "fuente_logica",
    "campo_fuente",
    "transformacion_principal",
    "campo_plata",
    "feature_modelo",
    "implementacion_modelo",
    "salida_oro",
    "observacion",
]

LINAJE = [
    # Favoritismo
    ("favoritismo", "SEACE/OCDS o sintético", "id_proveedor", "validación de identidad/adjudicatario y agrupación proveedor-entidad", "id_proveedor", "clave de agrupación", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.id_proveedor", "En OCDS real el supplier se resuelve por Contract -> Award -> Supplier."),
    ("favoritismo", "SEACE/OCDS o sintético", "id_entidad", "normalización de entidad compradora y agrupación proveedor-entidad", "id_entidad", "clave de agrupación", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.id_entidad", "Entidad compradora; no implica relación irregular."),
    ("favoritismo", "SEACE/OCDS o sintético", "id_contrato", "conteo por proveedor-entidad", "id_contrato", "n_contratos", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.n_contratos", "En OCDS real la clave analítica es OCID::contract.id."),
    ("favoritismo", "SEACE/OCDS o sintético", "monto", "imputación y cap P99 aprendido solo en TRAIN operacional", "monto / monto_capped", "monto_total / monto_promedio", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.score_riesgo_favoritismo", "Serving Sprint 4 usa monto_capped; legacy RC1 conserva monto para reproducibilidad."),
    ("favoritismo", "SEACE/OCDS o sintético", "modalidad", "separación semántica de modalidades", "es_contratacion_directa", "pct_contratacion_directa", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.pct_contratacion_directa", "Comparación de Precios no se equipara a Contratación Directa."),
    ("favoritismo", "SEACE/OCDS o sintético", "modalidad", "separación semántica de modalidades", "es_comparacion_precios", "pct_comparacion_precios", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.pct_comparacion_precios", "Feature independiente."),
    ("favoritismo", "SEACE/OCDS o sintético", "objeto", "número de objetos distintos por proveedor-entidad", "objeto", "n_objetos_unicos / concentracion_objeto", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.score_riesgo_favoritismo", "Concentración es señal estadística, no prueba de favoritismo."),
    ("favoritismo", "SIAF/legajo sintético o institucional", "id_funcionario", "conteo de funcionarios distintos por proveedor-entidad", "id_funcionario", "n_funcionarios_distintos / monto_por_funcionario", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.score_riesgo_favoritismo", "OCDS abierto no contiene funcionarios individuales."),
    ("favoritismo", "SEACE/OCDS o sintético", "fecha_contrato", "rango temporal por proveedor-entidad", "fecha_contrato", "dias_actividad / contratos_por_mes", "sklearn RF / Spark MLlib RF", "ranking_riesgo_favoritismo.score_riesgo_favoritismo", "Feature de intensidad temporal."),

    # Fraccionamiento
    ("fraccionamiento", "SEACE/OCDS o sintético", "id_proveedor + id_entidad + objeto", "agrupación de contratos comparables", "id_proveedor + id_entidad + objeto", "clave de grupo", "sklearn IsolationForest / Spark MLlib KMeans", "ranking_riesgo_fraccionamiento.clave_grupo", "La agrupación es una aproximación analítica para priorización."),
    ("fraccionamiento", "SEACE/OCDS o sintético", "fecha_contrato", "ventana móvil de 15 días", "fecha_contrato", "max_contratos_ventana_15d", "sklearn IsolationForest / Spark SQL + KMeans", "ranking_riesgo_fraccionamiento.max_contratos_ventana_15d", "Ventana configurable en una implementación institucional."),
    ("fraccionamiento", "SEACE/OCDS o sintético", "monto", "suma dentro de ventana y grupo sin capar cuantía", "monto", "monto_total_ventana_15d / monto_total_grupo", "sklearn IsolationForest / Spark MLlib KMeans", "ranking_riesgo_fraccionamiento.score_anomalia", "Se conserva monto para comparaciones normativas."),
    ("fraccionamiento", "SEACE/OCDS o sintético", "fecha_contrato + categoria_principal + monto", "consulta al motor normativo por fecha/régimen/categoría", "umbral_aplicable", "pct_montos_bajo_umbral", "sklearn IsolationForest / Spark SQL + KMeans", "ranking_riesgo_fraccionamiento.senal_priorizacion_fraccionamiento", "No constituye determinación jurídica de fraccionamiento."),

    # Pagos y modalidades Sprint 4
    ("pagos", "SIAF sintético o institucional", "id_pago + id_contrato", "validación de integridad referencial pago→contrato", "payments canónico", "n_pagos", "análisis estadístico descriptivo", "resumen_pagos_contrato.csv", "El PoC versiona pagos sintéticos; pagos SIAF reales requieren CGR."),
    ("pagos", "SIAF sintético o institucional", "monto_devengado + monto_pagado", "agregación por contrato y comparación contra monto contractual", "payments canónico", "monto_devengado_total / monto_pagado_total / ratio_pagado_contrato", "análisis estadístico descriptivo", "resumen_pagos_contrato.csv", "Sobrepago es solo señal para revisar; no hallazgo."),
    ("pagos", "SIAF sintético o institucional", "fecha_devengado + fecha_pagado", "cálculo de días devengado→pagado y percentiles", "payments canónico", "dias_devengado_a_pagado", "análisis estadístico descriptivo", "analisis_pagos_modalidades.json", "Demoras sintéticas prueban el contrato analítico."),
    ("modalidades", "SEACE/OCDS o sintético", "fecha_contrato + monto + modalidad + categoria_principal", "régimen por fecha y procedimiento referencial por cuantía", "contracts canónico", "clasificacion_modalidad", "motor normativo referencial", "resumen_modalidades_regimen.csv", "Modalidades especiales no se juzgan solo por cuantía; requieren contexto jurídico."),

    # Vínculos
    ("vinculos", "RNP/SUNAT/legajo sintético o institucional", "telefono", "comparación proveedor-funcionario", "telefono", "comparte_telefono", "NetworkX / Spark GraphFrames", "ranking_vinculos_proveedor_funcionario.comparte_telefono", "Datos de contacto son sintéticos en el PoC."),
    ("vinculos", "RNP/SUNAT/legajo sintético o institucional", "direccion", "comparación proveedor-funcionario", "direccion", "comparte_direccion", "NetworkX / Spark GraphFrames", "ranking_vinculos_proveedor_funcionario.comparte_direccion", "Datos de contacto son sintéticos en el PoC."),

    # Arquitectura de capas
    ("arquitectura", "data/*.csv", "contratos/pagos/dimensiones sintéticos", "copia sin transformación", "lakehouse/bronce/*", "N/A", "ETL local PoC", "N/A", "Bronce simula la capa raw del TDR."),
    ("arquitectura", "lakehouse/bronce/*", "contratos/dimensiones", "limpieza, imputación y feature engineering", "lakehouse/plata/*", "datasets de modelado", "ETL local PoC", "N/A", "Los modelos canónicos consumen Plata; pagos se analizan mediante contrato canónico sin alterar Plata legacy."),
    ("arquitectura", "lakehouse/plata/* + análisis pagos", "features/dimensiones/resúmenes", "scoring/modelado/análisis descriptivo", "N/A", "scores, señales y resúmenes", "sklearn + Spark MLlib/GraphFrames + análisis pagos", "lakehouse/oro/*.csv", "Oro contiene salidas downstream; no datasets intermedios de features."),
]


def main():
    df = pd.DataFrame(LINAJE, columns=COLUMNAS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Linaje generado: {len(df)} relaciones en {OUTPUT}")
    return df


if __name__ == "__main__":
    main()
