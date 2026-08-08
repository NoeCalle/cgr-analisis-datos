# Auditoría final — Anexo N.º 03 del TDR

> Prototipo independiente. Esta matriz separa evidencia reproducible del PoC de los requisitos que solo pueden cerrarse dentro de la infraestructura y gobierno de la CGR.

## Leyenda

- ✅ cubierto por evidencia verificable del PoC.
- 🟡 PoC parcial; el cierre literal requiere información o validación institucional.
- 🔵 dependencia institucional CGR.
- 🔴 brecha técnica cerrable en este repositorio.

## Checklist

| N.º | Estado | Criterio | Evidencia en repo | Residual |
|---:|:---:|---|---|---|
| 1 | ✅ | Exploración del análisis de datos | `src/eda.py`<br>`outputs/charts/01_distribucion_montos.png`<br>`outputs/charts/04_serie_temporal.png` | Sin residual técnico relevante para el PoC; la EDA deberá repetirse sobre datos internos cuando CGR los habilite. |
| 2 | 🟡 | Calidad e ingeniería de características: uso exclusivo de capas Plata/Oro del Datamart institucional y justificación estadística de nulos/outliers | `lakehouse/plata/dataset_favoritismo.csv`<br>`lakehouse/plata/dataset_fraccionamiento.csv`<br>`src/preprocesamiento.py`<br>`reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx` | El PoC usa Plata/Oro locales y documenta nulos/outliers; el requisito literal de Datamart institucional solo puede validarse dentro de CGR. |
| 3 | 🟡 | Estándares institucionales de extracción SQL: LEFT JOIN, lógica de cortocircuito y prohibición de Full Table Scans en tablas de hechos | `src/spark/estandares_sql.py`<br>`outputs/extraccion_estandar_sql.csv` | Las técnicas están demostradas localmente; la conformidad literal con reglas, esquemas y planes de ejecución institucionales requiere revisión/ejecución en CGR. |
| 4 | 🟡 | Performance y validación del modelo: superar umbrales mínimos de Accuracy, F1-Score y AUC-ROC | `outputs/comparacion_modelos_favoritismo.json`<br>`outputs/tuning_favoritismo_resumen.json`<br>`outputs/tuning_fraccionamiento_resumen.json` | El TDR público provisto exige umbrales mínimos pero no consigna sus valores numéricos; no se inventan. Además, la validación productiva requiere ground truth y ambientes CGR. |
| 5 | ✅ | Interpretabilidad orientada a auditoría (SHAP, LIME o Feature Importance) | `outputs/charts/05_importancia_favoritismo.png`<br>`outputs/charts/07_shap_summary_favoritismo.png`<br>`outputs/charts/08_shap_waterfall_caso.png` | Los artefactos están disponibles en el PoC; su interpretación final debe contextualizarse con casos y datos institucionales. |
| 6 | 🔵 | Despliegue, autenticación y MLOps: código versionado en Git institucional | `.github/workflows/tests.yml`<br>`airflow_home/dags/modulo_analisis_datos_1_8_2.py`<br>`outputs/run_manifest.json` | Git institucional, autenticación, despliegue y operación en ambientes CGR no son accesibles desde el repositorio público independiente. |
| 7 | 🟡 | Integración para ecosistema SSRS: resultados del modelo, predicciones y puntajes de riesgo | `ssrs/schema_sql_server.sql`<br>`ssrs/ReporteRiesgoFavoritismo.rdl`<br>`ssrs/ReporteRiesgoFraccionamiento.rdl`<br>`outputs/ssrs_publicacion_manifest.json` | Contrato SQL/RDL y publicación stand-in están verificados; falta ejecutar DDL, autenticación, despliegue y pruebas en SQL Server/SSRS CGR. |
| 8 | ✅ | Documentación de linaje y diccionario de datos desde la fuente hasta el modelo final | `outputs/linaje_datos.csv`<br>`data/diccionario_datos.csv`<br>`outputs/run_manifest.json` | Linaje técnico del PoC cubierto; las fuentes/tablas institucionales deberán sustituir los nodos locales al desplegar en CGR. |
| 9 | ✅ | Hiperparámetros de los modelos y sus explicaciones | `outputs/tuning_favoritismo_resumen.json`<br>`outputs/tuning_fraccionamiento_resumen.json`<br>`outputs/spark_favoritismo_resumen.json`<br>`outputs/spark_fraccionamiento_resumen.json` | Documentados y versionados para el PoC; deben recalibrarse con datos institucionales antes de producción. |
| 10 | ✅ | Reporte completo de métricas de desempeño de los modelos | `outputs/comparacion_modelos_favoritismo.json`<br>`outputs/tuning_fraccionamiento_resumen.json`<br>`reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx` | Métricas del benchmark reproducible cubiertas; no se presentan como desempeño productivo. |
| 11 | ✅ | Oportunidades de mejora para la evolución del modelo | `reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx`<br>`README.md` | Las recomendaciones están documentadas; priorización institucional dependerá de usuarios, ground truth y capacidad operativa CGR. |

## Resultado

- ✅: 6 criterios.
- 🟡: 4 criterios.
- 🔵: 1 criterios.
- 🔴: 0 criterios.

**Criterio 4:** el TDR público provisto exige superar umbrales mínimos de Accuracy, F1-Score y AUC-ROC, pero no consigna sus valores numéricos. Por ello esta auditoría no inventa umbrales ni declara conformidad cuantitativa institucional.

El objetivo de cierre externo se considera alcanzado únicamente si el conteo 🔴 es cero. Los estados 🟡/🔵 deben mantenerse visibles hasta disponer de datos, reglas, ambientes, accesos y validaciones CGR.
