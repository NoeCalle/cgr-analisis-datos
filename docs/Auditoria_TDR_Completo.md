# Auditoría integral vigente del TDR público

> PoC independiente. Esta matriz distingue evidencia técnica reproducible de dependencias que solo pueden cerrarse con datos, infraestructura, usuarios, permisos o conformidad de la CGR.

## Resumen

- ✅ Cubierto por PoC: **12**
- 🟡 PoC demostrable / cierre literal CGR: **8**
- 🔵 Dependencia institucional: **5**
- 🔴 Brecha cerrable desde repo: **0**

| # | Sección TDR | Estado | Requisito | Dependencias CGR |
|---:|---|:---:|---|---|
| 1 | 4.1.1 / 6 | ✅ | Análisis Exploratorio de Datos (EDA) y estadísticas descriptivas | — |
| 2 | 4.1.2-4.1.3 / 6 | 🟡 | Identificación, adquisición, integración y consolidación SIAF/SEACE | CGR-DEP-01, CGR-DEP-06 |
| 3 | 4.1.4 / Productos 2 y 5 | ✅ | Limpieza, faltantes, outliers, codificación y normalización/estandarización | — |
| 4 | 4.1.5 | ✅ | Enriquecimiento y generación de características | — |
| 5 | 6 | 🟡 | Análisis Profundo de Pagos y Modalidades de Contratación | CGR-DEP-01 |
| 6 | 4.2.2 / Productos 3-4 | ✅ | Identificación de proveedores favoritos | — |
| 7 | 4.2.3 / Productos 6-7 | ✅ | Detección de fraccionamiento, compras repetitivas y objetos/servicios similares | — |
| 8 | 4.2.4 | 🟡 | Evaluación de vínculos proveedor-funcionario mediante grafos/redes | CGR-DEP-01 |
| 9 | 4.2.5 | ✅ | Entrenamiento, validación cruzada, holdout y optimización de hiperparámetros | — |
| 10 | 3.2.a / 4.2.6 | 🟡 | Apache Spark MLlib escalable y pruebas de rendimiento/robustez | CGR-DEP-06, CGR-DEP-03 |
| 11 | 4.3.1-4.3.2 | ✅ | Reportes automáticos con tablas, estadísticas, gráficos y métricas | — |
| 12 | 4.4 | ✅ | Documentación técnica completa, código fuente, diccionario y diagrama | — |
| 13 | Anexo 2 / 6 | 🟡 | Lakehouse Bronce/Plata/Oro y DAGs de orquestación | CGR-DEP-01, CGR-DEP-06 |
| 14 | 3.2.c / 6 | ✅ | Autoevaluación y estrategia de actualización/reentrenamiento sostenible | — |
| 15 | 3.2.f / Producto 7 | ✅ | Separación TRAIN/INFERENCE, persistencia y serving sin reentrenamiento | — |
| 16 | 3.2.f / 4.2.6 / 6 | 🟡 | Despliegue, seguridad, mantenimiento y monitorización operacional | CGR-DEP-04, CGR-DEP-06 |
| 17 | 6 / Producto 7 | 🔵 | Pruebas de integración en ambientes DEV/QA/PROD y puesta a producción | CGR-DEP-06, CGR-DEP-04 |
| 18 | Anexo 3 / Producto 7 | 🟡 | Publicación e integración en SQL Server/SSRS | CGR-DEP-05, CGR-DEP-06 |
| 19 | Anexo 3 / 3.2.e | 🟡 | Umbrales institucionales y validación productiva de Accuracy/F1/AUC-ROC | CGR-DEP-03, CGR-DEP-06 |
| 20 | 6 / Producto 7 | 🔵 | Certificación, levantamiento de observaciones/incidencias y marcha blanca | CGR-DEP-07, CGR-DEP-06 |
| 21 | 6 / Transferencia de Conocimiento | 🔵 | Transferencia de conocimiento a usuarios técnicos y funcionales | CGR-DEP-08 |
| 22 | 13 | 🔵 | Accesos a bases de datos y herramientas colaborativas CGR | CGR-DEP-01, CGR-DEP-04, CGR-DEP-06 |
| 23 | 14 | 🔵 | Entrega/propiedad/confidencialidad y repositorio institucional | CGR-DEP-08, CGR-DEP-04 |
| 24 | Anexo 1 | ✅ | Formato formal de Productos e Informe Final | — |
| 25 | 6 / análisis normativo | ✅ | Trazabilidad normativa por fecha/régimen para umbrales y modalidades | — |

## Detalle

### 1. Análisis Exploratorio de Datos (EDA) y estadísticas descriptivas — ✅

EDA, estadísticas y gráficos programáticos forman parte de la evidencia reproducible.

Evidencia: `outputs/evidencia_documental.json`, `outputs/charts`

### 2. Identificación, adquisición, integración y consolidación SIAF/SEACE — 🟡

Existe contrato canónico y conectores pandas/Spark-native; la lectura de fuentes internas reales requiere acceso, diccionario y plataforma CGR.

Evidencia: `docs/Integracion_Datos.md`, `config/cgr.example.yaml`, `src/core/schemas.py`, `src/core/schemas_spark.py`

### 3. Limpieza, faltantes, outliers, codificación y normalización/estandarización — ✅

FIT/TRANSFORM están separados; el P99 se congela y existe FIT distribuido para fuentes spark_sql.

Evidencia: `src/preprocesamiento.py`, `src/spark/ajustar_preprocesamiento_spark.py`, `outputs/champions_spark/preprocesador_contratos.json`

### 4. Enriquecimiento y generación de características — ✅

Features de favoritismo/fraccionamiento y linaje fuente→feature están materializados; fraccionamiento conserva objeto_familia y una única semántica de ventana pandas/Spark.

Evidencia: `data/dataset_favoritismo.csv`, `data/dataset_fraccionamiento.csv`, `outputs/linaje_datos.csv`

### 5. Análisis Profundo de Pagos y Modalidades de Contratación — 🟡

El motor analítico y la evidencia sintética están implementados; el cierre literal requiere pagos SIAF y mapeos institucionales reales.

Evidencia: `data/pagos_siaf_sintetico.csv`, `outputs/analisis_pagos_modalidades.json`, `outputs/resumen_pagos_contrato.csv`, `outputs/resumen_modalidades_regimen.csv`, `outputs/charts/11_ratio_pago_contrato.png`, `outputs/charts/12_modalidades_regimen.png`

### 6. Identificación de proveedores favoritos — ✅

El champion Spark de favoritismo se selecciona y evalúa con el mismo pipeline operacional que TRAIN/INFERENCE (monto_capped), conserva holdout final y Feature Importance ligada al modelo servido.

Evidencia: `outputs/comparacion_modelos_favoritismo.json`, `outputs/tuning_favoritismo_resumen.json`, `outputs/tuning_favoritismo_spark_resumen.json`, `outputs/model_registry.json`, `outputs/ranking_riesgo_favoritismo_spark.csv`

### 7. Detección de fraccionamiento, compras repetitivas y objetos/servicios similares — ✅

El KMeans Spark activo dispone de evaluación/holdout propios; la señal temporal usa cantidad y monto de la misma ventana de 15 días y agrupa variantes lexicales controladas mediante objeto_familia. Isolation Forest queda como benchmark de compatibilidad.

Evidencia: `src/core/objeto_similarity.py`, `outputs/tuning_fraccionamiento_spark_resumen.json`, `outputs/tuning_fraccionamiento_resumen.json`, `outputs/ranking_riesgo_fraccionamiento_spark.csv`

### 8. Evaluación de vínculos proveedor-funcionario mediante grafos/redes — 🟡

GraphFrames se ejecuta sobre escenario sintético; los vínculos y datos personales institucionales requieren fuentes y permisos CGR.

Evidencia: `outputs/graphframes_resumen.json`, `outputs/vinculos_graphframes_sospechosos.csv`

### 9. Entrenamiento, validación cruzada, holdout y optimización de hiperparámetros — ✅

El champion Spark consume hiperparámetros seleccionados por evaluaciones del mismo pipeline activo; los benchmarks sklearn quedan identificados como compatibilidad y los holdouts no participan del retuning.

Evidencia: `outputs/tuning_favoritismo_spark_resumen.json`, `outputs/tuning_fraccionamiento_spark_resumen.json`, `outputs/tuning_favoritismo_resumen.json`, `outputs/tuning_fraccionamiento_resumen.json`, `outputs/model_registry.json`

### 10. Apache Spark MLlib escalable y pruebas de rendimiento/robustez — 🟡

TRAIN, INFERENCE y evaluación/tuning spark_sql conservan ejecución Spark-native y fingerprint distribuido; existe benchmark parametrizable, pero clúster, volumen, performance, robustez y aceptación productiva requieren infraestructura/ground truth CGR.

Evidencia: `outputs/inference_spark_smoke_summary.json`, `outputs/tuning_favoritismo_spark_resumen.json`, `outputs/tuning_fraccionamiento_spark_resumen.json`, `src/core/schemas_spark.py`, `src/spark/evaluar_favoritismo_spark.py`, `src/spark/evaluar_fraccionamiento_spark.py`, `src/spark/benchmark_operacional.py`, `tests/test_spark_native_integration.py`, `tests/test_spark_evaluation_native.py`

### 11. Reportes automáticos con tablas, estadísticas, gráficos y métricas — ✅

La documentación formal se genera desde evidencia machine-readable y gráficos programáticos.

Evidencia: `src/generar_evidencia_documental.py`, `reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx`, `outputs/charts`

### 12. Documentación técnica completa, código fuente, diccionario y diagrama — ✅

Código, versiones, hashes, diccionario, diagrama y documentación están versionados; el run manifest separa metadata variable de una huella estable de reproducibilidad.

Evidencia: `data/diccionario_datos.csv`, `outputs/charts/09_diagrama_modelo_datos.png`, `outputs/run_manifest.json`, `README.md`

### 13. Lakehouse Bronce/Plata/Oro y DAGs de orquestación — 🟡

La arquitectura es funcional en el PoC y dispone de frontera Spark-native; Datamart/HDFS/YARN/Airflow institucional y su operación requieren CGR.

Evidencia: `lakehouse/bronce`, `lakehouse/plata`, `lakehouse/oro`, `airflow_home/dags/dag_modulo_analisis_datos.py`

### 14. Autoevaluación y estrategia de actualización/reentrenamiento sostenible — ✅

La autoevaluación carga exactamente el champion Spark activo del registry, calcula deriva/recall@K sobre sus features congeladas y solo genera candidates; no existe autopromoción silenciosa.

Evidencia: `src/autoevaluacion_champion.py`, `airflow_home/dags/dag_monitoreo_reentrenamiento.py`, `outputs/monitoreo_champion.json`, `outputs/log_reentrenamiento_champion.csv`, `outputs/model_registry.json`

### 15. Separación TRAIN/INFERENCE, persistencia y serving sin reentrenamiento — ✅

El perfil activo es Spark MLlib; inference no consume labels, training ni tuning.

Evidencia: `outputs/model_registry.json`, `outputs/inference_spark_smoke_summary.json`, `airflow_home/dags/dag_inferencia_modelos.py`

### 16. Despliegue, seguridad, mantenimiento y monitorización operacional — 🟡

Controles de software y monitoreo del champion activo existen; identidad, secretos, segregación, operación y aceptación productiva son institucionales.

Evidencia: `docs/Train_Inference.md`, `src/monitoreo_modelos.py`, `src/autoevaluacion_champion.py`, `airflow_home/dags/dag_monitoreo_reentrenamiento.py`, `outputs/monitoreo_champion.json`, `outputs/model_registry.json`

### 17. Pruebas de integración en ambientes DEV/QA/PROD y puesta a producción — 🔵

No es demostrable fuera de los ambientes, accesos y controles institucionales.

Evidencia: actividad institucional

### 18. Publicación e integración en SQL Server/SSRS — 🟡

Contrato T-SQL/RDL validado localmente; despliegue real requiere SQL Server/SSRS CGR.

Evidencia: `ssrs/schema_sql_server.sql`, `ssrs/ReporteRiesgoFavoritismo.rdl`, `ssrs/ReporteRiesgoFraccionamiento.rdl`, `outputs/ssrs_publicacion_manifest.json`

### 19. Umbrales institucionales y validación productiva de Accuracy/F1/AUC-ROC — 🟡

El PoC reporta métricas CV/holdout de los modelos activos y benchmarks de compatibilidad; el TDR público no aporta mínimos numéricos ni ground truth institucional.

Evidencia: `outputs/tuning_favoritismo_spark_resumen.json`, `outputs/tuning_fraccionamiento_spark_resumen.json`, `outputs/tuning_favoritismo_resumen.json`, `outputs/tuning_fraccionamiento_resumen.json`

### 20. Certificación, levantamiento de observaciones/incidencias y marcha blanca — 🔵

Requiere usuarios, casos, ambientes e incidencias reales de la CGR.

Evidencia: actividad institucional

### 21. Transferencia de conocimiento a usuarios técnicos y funcionales — 🔵

Las sesiones y actas de transferencia son una actividad contractual institucional.

Evidencia: actividad institucional

### 22. Accesos a bases de datos y herramientas colaborativas CGR — 🔵

El repositorio no puede crear ni simular como reales permisos institucionales.

Evidencia: actividad institucional

### 23. Entrega/propiedad/confidencialidad y repositorio institucional — 🔵

El PoC mantiene licencia/avisos propios; la cesión y entrega contractual se formalizan dentro de CGR.

Evidencia: actividad institucional

### 24. Formato formal de Productos e Informe Final — ✅

Los ocho DOCX son regenerados, indexados, auditados y renderizados en CI.

Evidencia: `reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx`, `reporte/productos_formales/Producto_01_Plan_de_Trabajo.docx`, `reporte/productos_formales/Producto_07_Informe_Final.docx`

### 25. Trazabilidad normativa por fecha/régimen para umbrales y modalidades — ✅

El rango sintético 2023-2026 conserva fuentes oficiales versionadas y cambio de régimen 22/04/2025.

Evidencia: `src/umbrales_normativos.py`, `outputs/analisis_pagos_modalidades.json`
