# Módulo de Análisis de Datos — Prototipo independiente (CGR 1.8.2)

> **Prototipo independiente.** Este repositorio no constituye una implementación
> oficial ni cuenta con aprobación institucional de la Contraloría General de la
> República (CGR). Es un ejercicio técnico propio construido a partir de un TDR
> público de mayo de 2026.

Prueba de concepto del “Módulo de análisis de datos para dar soporte a los
auditores durante la ejecución de los servicios de control”, orientada a:

- señales de posible favoritismo;
- señales de posible fraccionamiento;
- vínculos proveedor–funcionario en escenario sintético;
- Spark MLlib, GraphFrames, Airflow, Lakehouse Bronce/Plata/Oro, SSRS y MLOps.

Las salidas son **señales para priorización de revisión**. No constituyen
hallazgos, imputaciones ni determinaciones automáticas de irregularidad.

## Estado del cierre de brechas

### ✅ P0 — Integridad OCDS y normativa

La relación de datos públicos fue reconstruida como:

`Contract(main_ocid, awardID) -> Award(main_ocid, id) -> Supplier`

La clave analítica del contrato real es `OCID::contract.id`. Se prioriza
`mainProcurementCategory` (`goods/services/works`) y el motor normativo está
parametrizado 2018–2026, incluido el cambio de régimen desde 22/04/2025.

| Métrica OCDS validada | Resultado |
|---|---:|
| Contratos crudos | 47,510 |
| Contratos con award + supplier resolubles | **47,254** |
| Excluidos por vínculo no resoluble | 256 |
| Adjudicatarios distintos | 25,861 |
| Entidades distintas | 2,732 |
| `goods` | 23,630 |
| `services` | 18,584 |
| `works` | 5,040 |

La evidencia agregada y hashes SHA-256 están en
`outputs/validacion_p0_datos_reales.json`. Los rankings reales identificables no
se publican.

### ✅ P1 — Modelado y reproducibilidad

- Contratación Directa y Comparación de Precios son features separadas.
- El benchmark sintético incluye **hard negatives**.
- Favoritismo compara Regresión Logística, Random Forest y Gradient Boosting con
  predicciones out-of-fold.
- El tuning se persiste y el modelo final consume la configuración elegida.
- Fraccionamiento separa un **holdout final antes del tuning** y usa AUC-PR como
  criterio primario.
- La autoevaluación genera un **modelo candidato**; no hay promoción automática.
- Los modelos consumen Plata y el reporting consume Oro.
- Las versiones del entorno están fijadas en `requirements.txt`.

#### Benchmark de favoritismo

Sobre 2,328 pares proveedor-entidad y 6 positivos sintéticos:

| Modelo | Accuracy | AUC-PR | AUC-ROC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| **Random Forest** | 0.998 | **0.671** | 0.999 | **0.667** | 0.333 | 0.444 |
| Regresión Logística | 0.996 | 0.621 | 0.995 | 0.333 | **0.667** | 0.444 |
| Gradient Boosting | 0.997 | 0.418 | 0.749 | 0.429 | 0.500 | **0.462** |

Accuracy se reporta porque el Anexo 3 la solicita expresamente, pero **no se usa
como criterio primario**: con solo 6 positivos y un desbalance severo puede dar
una impresión engañosamente optimista. La referencia metodológica principal es
AUC-PR.

Tuning RF sklearn: `n_estimators=100`, `max_depth=3`,
`min_samples_leaf=1`; AUC-PR medio CV **0.844**.

#### Benchmark de fraccionamiento

- 180 grupos / 8 positivos sintéticos;
- desarrollo: 112 / 5 positivos;
- holdout final: 68 / 3 positivos;
- AUC-PR de validación medio: **0.402**;
- holdout: Accuracy **0.794**, AUC-ROC **0.856**, AUC-PR **0.171**,
  precision **0.176**, recall **1.000**, F1 **0.300**, recall@K **0.000**.

La debilidad del ranking de Isolation Forest queda expuesta deliberadamente; la
regla interpretable y la revisión humana son complementarias. Accuracy se
mantiene como métrica informativa exigida por el Anexo 3, no como criterio de
selección.

### ✅ Sprint A — Spark canónico y trazabilidad

Spark dejó de ser una demostración paralela. La arquitectura reproducible
separa responsabilidades:

- **scikit-learn:** benchmark metodológico, comparación, holdout y SHAP;
- **Apache Spark MLlib / GraphFrames:** implementación objetivo del TDR,
  ejecutada con Spark real en `local[*]`.

El Sprint A incorpora:

- Java 17 + `pyspark==4.1.1` en GitHub Actions;
- Random Forest de favoritismo con Spark MLlib y CrossValidator;
- KMeans MLlib + distancia al centroide + ventanas Spark SQL para
  fraccionamiento;
- GraphFrames sobre la misma capa Plata;
- `src/spark/estandares_sql.py` dentro del CI para LEFT JOIN y partition pruning;
- DAG de Airflow con ramas Spark MLlib y GraphFrames;
- modelos binarios Spark como runtime no versionado; rankings y resúmenes JSON/CSV
  son la evidencia reproducible;
- Oro limitado a salidas downstream, sin datasets intermedios de features;
- diccionario y diagrama regenerados por CI;
- `outputs/linaje_datos.csv` con trazabilidad
  fuente → transformación → Plata → feature → modelo → Oro;
- `run_manifest.json` schema 3 con versiones, hashes y evidencia Spark/GraphFrames.

El benchmark Spark de favoritismo tiene solo 6 positivos y su AUC-PR CV puede
ser de alta varianza. **No se usa como estimación de desempeño productivo**; la
comparación OOF sklearn es la referencia metodológica del PoC. Spark demuestra
la implementación y ejecución de la arquitectura objetivo.

En esta área, lo pendiente requiere infraestructura CGR: HDFS/YARN distribuido,
Lakehouse/Datamart institucional, fuentes internas y validación de desempeño en
el clúster institucional.

### ✅ Sprint B — Documentación formal alineada al Anexo 1

Los Productos 1–7 y el Informe Final fueron reestructurados siguiendo los
lineamientos formales del Anexo 1 del TDR dentro de lo demostrable por este PoC:

- Arial 11 y espacio simple para el cuerpo documental;
- carátula con nombre de consultoría, producto, consultor y fecha;
- páginas numeradas en la parte inferior derecha;
- márgenes espejo preparados para impresión a doble cara;
- índice real de capítulos con números de página, actualizado con LibreOffice;
- índices de tablas/cuadros y gráficos cuando corresponden;
- lista de abreviaturas/acrónimos, glosario y referencias bibliográficas;
- estructura específica del Plan de Trabajo, Informes de Producto e Informe Final;
- gráficos y tablas provenientes de la evidencia reproducible del pipeline;
- P3 y P6 incorporan explícitamente la ejecución y configuración Spark MLlib;
- P7 documenta validación, despliegue PoC, integración, monitoreo, repositorio y
  las dependencias institucionales de certificación, marcha blanca y transferencia.

Los ocho DOCX se regeneran, se postprocesan para materializar el índice, se
convierten temporalmente a PDF y pasan una auditoría estructural en CI antes de
ser persistidos en `main`. También existen pruebas de regresión para impedir que
vuelvan nombres obsoletos o el recorte de gráficos.

**Desviación deliberada del PoC público:** el Anexo 1 solicita el logo de la CGR
en la tapa de una entrega institucional. Este repositorio independiente mantiene
un espacio reservado en lugar de usar el logo oficial, para no sugerir aprobación
o autoría institucional inexistente.

Los documentos verificados están en:

- `reporte/productos_formales/Producto_01_Plan_de_Trabajo.docx`
- `reporte/productos_formales/Producto_02_Preprocesamiento_Favoritismo.docx`
- `reporte/productos_formales/Producto_03_Modelo_Favoritismo.docx`
- `reporte/productos_formales/Producto_04_Entrenamiento_Favoritismo.docx`
- `reporte/productos_formales/Producto_05_Preprocesamiento_Fraccionamiento.docx`
- `reporte/productos_formales/Producto_06_Modelo_Fraccionamiento.docx`
- `reporte/productos_formales/Producto_07_Informe_Final.docx`
- `reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx`

### ✅ Sprint C — SSRS y auditoría final del Anexo 3

La integración de reporting dejó de ser un único RDL de demostración. El PoC
ahora mantiene un contrato verificable de publicación para SSRS:

- `ssrs/schema_sql_server.sql` define tablas, restricciones, índices y vistas de
  consumo estables;
- `ssrs/ReporteRiesgoFavoritismo.rdl` consume `vw_SSRS_Favoritismo`;
- `ssrs/ReporteRiesgoFraccionamiento.rdl` consume
  `vw_SSRS_Fraccionamiento`;
- `src/publicar_ssrs.py` valida localmente claves, columnas, rangos y conteos
  mediante un stand-in SQLite;
- `outputs/ssrs_publicacion_manifest.json` registra hashes de las fuentes Oro,
  conteos publicados y las dependencias institucionales pendientes;
- la señal de fraccionamiento tiene un único nombre canónico:
  `senal_priorizacion_fraccionamiento`;
- Accuracy se incorporó a la evidencia de favoritismo y al holdout de
  fraccionamiento porque el Anexo 3 la menciona explícitamente.

La auditoría literal del Anexo 3 se genera automáticamente en:

- `docs/Checklist_Anexo_03.md`;
- `outputs/checklist_anexo3.json`.

Resultado vigente del checklist:

| Estado | Criterios | Interpretación |
|---|---:|---|
| ✅ | 6 | Cubiertos por evidencia verificable del PoC |
| 🟡 | 4 | PoC demostrable; el cierre literal requiere información, infraestructura o validación CGR |
| 🔵 | 1 | Dependencia institucional CGR |
| 🔴 | **0** | **No quedan brechas técnicas conocidas que sean cerrables exclusivamente desde este repositorio** |

Los cuatro criterios 🟡 corresponden a Datamart Plata/Oro institucional,
estándares/planes SQL institucionales, umbrales y validación productiva de
performance, e integración ejecutada en SQL Server/SSRS CGR. El criterio 🔵 es
Git/autenticación/despliegue/MLOps institucional.

**Importante sobre performance:** el TDR público provisto exige superar umbrales
mínimos de Accuracy, F1-Score y AUC-ROC, pero no consigna sus valores numéricos.
El PoC reporta esas métricas donde corresponden, pero no inventa umbrales ni
declara conformidad cuantitativa institucional.

### ✅ Documentación reproducible

La documentación ya no mantiene cifras independientes escritas a mano. El flujo
es:

`run_manifest.json -> evidencia_documental.json -> generadores DOCX -> índice paginado -> QA DOCX/PDF -> main`

## Correspondencia resumida con el TDR

| Área TDR | Estado PoC |
|---|---|
| EDA y calidad de datos | Implementado |
| Feature engineering | Implementado y endurecido |
| Favoritismo supervisado | Benchmark OOF/tuning/SHAP + Spark MLlib en CI |
| Fraccionamiento no supervisado | Isolation Forest con holdout + Spark MLlib KMeans |
| Spark MLlib | **Ejecutado en CI con Spark real `local[*]`; clúster CGR pendiente** |
| Grafos | NetworkX de referencia + **GraphFrames ejecutado en CI** |
| Airflow | DAG principal + monitoreo; ramas sklearn y Spark |
| Bronce / Plata / Oro | Simulación funcional; Datamart/Lakehouse CGR pendiente |
| Autoevaluación | Modelo candidato; promoción requiere revisión humana |
| SSRS | **Contrato T-SQL + 2 RDL + publicación local validada; servidor CGR pendiente** |
| Linaje / diccionario | Diccionario + diagrama + linaje explícito + manifest |
| Formato documental Anexo 1 | **Implementado y validado; logo oficial reservado para contexto institucional** |
| Checklist Anexo 3 | **6 ✅ / 4 🟡 / 1 🔵 / 0 🔴** |
| DEV/QA/PROD y Git institucional | Dependencia CGR |
| Certificación, marcha blanca y transferencia formal | Dependencia CGR |

## Estructura

```text
src/                         Python principal
src/spark/                   Spark MLlib, GraphFrames, Delta, SQL, streaming, HMS
airflow_home/dags/           DAG principal + monitoreo
lakehouse/bronce/            Ingesta cruda simulada
lakehouse/plata/             Datos limpios/features consumidos por modelos
lakehouse/oro/               Solo salidas para reporting/integración
ssrs/                        DDL T-SQL + RDL + contrato de publicación PoC
reporte/                     Generadores + Productos 1–7 + Informe Final
docs/                        Checklist auditable del Anexo 3
outputs/                     Evidencia, rankings, tuning, manifests y linaje
tests/                       Pruebas de regresión y contrato SSRS
.github/workflows/           CI end-to-end + auditoría Anexo 3
```

## Reproducir

### Entorno del proyecto

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Graphviz (`dot`) debe estar instalado en el sistema y Spark requiere una JVM
compatible; CI usa Java 17.

### Airflow aislado

```bash
python3 -m venv .venv_airflow
.venv_airflow/bin/pip install "apache-airflow==3.3.0" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.0/constraints-3.12.txt"

export PROYECTO_DIR="$PWD"
export CGR_PROJECT_PYTHON="$PWD/.venv/bin/python"
export AIRFLOW_HOME="$PWD/airflow_home"
```

### Tests

```bash
.venv/bin/pytest -q
```

GitHub Actions ejecuta además generación sintética, Bronce/Plata, benchmark
sklearn, Spark MLlib, GraphFrames, SQL Spark, Oro, diccionario, linaje,
manifiesto, documentación formal, contrato SSRS y auditoría del Anexo 3.

### Pipeline Airflow

```bash
.venv_airflow/bin/airflow dags test modulo_analisis_datos_1_8_2
```

```text
fuentes -> Bronce -> preprocesamiento/features -> Plata
                    |-> sklearn favoritismo -> tuning -> modelo
                    |-> sklearn fraccionamiento -> tuning/holdout -> modelo
                    |-> Spark MLlib favoritismo
                    |-> Spark MLlib fraccionamiento
                    |-> NetworkX -> GraphFrames
                                      ↓
                                     Oro
                                      ↓
                           diccionario + diagrama
                                      ↓
                               linaje_datos.csv
                                      ↓
                              run_manifest.json
                                      ↓
                         evidencia_documental.json
                                      ↓
                           DOCX + índice paginado
                                      ↓
                             QA DOCX / PDF
                                      ↓
                         SSRS contract + Anexo 3
```

## Datos reales OCDS/OECE

Los crudos y derivados identificables no se publican. Para reproducir la
validación local, seguir `data_real/README.md` con `main.csv`, `contracts.csv`,
`awards.csv`, `awards_suppliers.csv` y `parties.csv`.

## Publicación SSRS local

Después de generar Oro:

```bash
python src/publicar_ssrs.py
```

La base `ssrs/reportes.db` es un stand-in local no versionado. La evidencia
persistente queda en `outputs/ssrs_publicacion_manifest.json`. El despliegue real
en SQL Server/SSRS requiere infraestructura y autenticación CGR.

## Documentación formal

La generación base se ejecuta con:

```bash
python src/generar_evidencia_documental.py
cd reporte
npm ci
npm run all
```

La materialización automática de índices paginados requiere LibreOffice/UNO;
GitHub Actions ejecuta ese postprocesamiento, audita los DOCX, realiza un render
PDF de control y persiste en `main` las versiones verificadas.

## Licencia

El código está bajo MIT. Los datos públicos OECE/OCP mantienen su licencia de
origen (CC BY 4.0 cuando corresponda). Un eventual encargo contractual debe
separar los activos previos de aquellos sujetos a propiedad/confidencialidad del
TDR.
