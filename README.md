# Módulo de Análisis de Datos — Prototipo independiente (CGR 1.8.2)

> **Prototipo independiente.** Este repositorio no constituye una
> implementación oficial ni cuenta con aprobación institucional de la
> Contraloría General de la República (CGR). Es un ejercicio técnico propio,
> construido a partir de un TDR público de mayo de 2026.

Prueba de concepto del “Módulo de análisis de datos para dar soporte a los
auditores durante la ejecución de los servicios de control”, con énfasis en:

- priorización de señales de posible favoritismo;
- priorización de señales de posible fraccionamiento;
- análisis de vínculos proveedor–funcionario en escenario sintético;
- Spark MLlib, Airflow, Lakehouse Bronce/Plata/Oro, SSRS y MLOps como PoC.

Las salidas de riesgo son **señales para revisión de auditor**. No constituyen
hallazgos, imputaciones ni determinaciones automáticas de irregularidad.

## Estado del cierre de brechas

### ✅ P0 — Integridad OCDS y normativa: cerrado

La parte más crítica del pipeline de datos públicos fue reconstruida y validada:

- relación OCDS correcta: `Contract -> Award -> Supplier`;
- clave analítica: `OCID::contract.id`;
- adjudicatarios obtenidos de `awards_suppliers.csv`, sin mezclar suppliers de
  distintas adjudicaciones del mismo proceso;
- consorcios preservados según la identidad adjudicataria publicada;
- `mainProcurementCategory` (`goods/services/works`) tiene prioridad para el
  contexto normativo;
- motor normativo parametrizado 2018–2026 y cambio de régimen desde
  22/04/2025 (Ley 32069);
- tests de regresión de integridad y normativa;
- artefactos reales identificables antiguos retirados del repositorio público.

Regeneración P0 sobre los crudos OCDS utilizados:

| Métrica | Resultado |
|---|---:|
| Contratos crudos | 47,510 |
| Contratos analíticos con award + supplier resolubles | **47,254** |
| Contratos excluidos por vínculo no resoluble | 256 |
| Adjudicatarios distintos presentes en contratos | 25,861 |
| Entidades distintas | 2,732 |
| Categoría `goods` | 23,630 |
| Categoría `services` | 18,584 |
| Categoría `works` | 5,040 |

El detalle agregado y los hashes SHA-256 están en
`outputs/validacion_p0_datos_reales.json`. El conteo anterior de 47,442 se
conserva únicamente como antecedente explícitamente descartado; sus rankings
`*_REAL.csv` fueron retirados.

### ✅ P1 — Núcleo técnico de modelado/reproducibilidad: cerrado

El núcleo técnico está integrado y cubierto por CI:

- Contratación Directa y Comparación de Precios son features separadas.
- El dataset sintético incorpora **hard negatives** para evitar métricas
  artificialmente perfectas por separación trivial.
- La categoría contractual sintética también es estructurada
  (`goods/services/works`).
- Favoritismo compara ejecutablemente Regresión Logística, Random Forest y
  Gradient Boosting con las mismas predicciones out-of-fold.
- El tuning seleccionado se persiste en JSON y el modelo final consume esa
  configuración.
- Fraccionamiento separa un **holdout final antes del tuning**; AUC-PR es la
  métrica primaria de selección por el fuerte desbalance.
- Autoevaluación usa holdout independiente y produce un modelo **candidato**,
  sin promoción automática.
- Los modelos consumen Plata; reporting consume Oro.
- Airflow usa el Python del proyecto, separado del entorno de Airflow.
- `run_manifest.json` registra commit, versiones, hashes, parámetros y
  artefactos de una ejecución completa.

#### Evidencia vigente — Favoritismo

Las métricas de comparación se reproducen con las versiones declaradas por el
proyecto (`pandas 3.0.2`, `numpy 2.4.4`, `scikit-learn 1.8.0`).

Comparación out-of-fold sobre **2,328 pares proveedor-entidad**, con 6 casos
positivos sintéticos difíciles:

| Modelo | AUC-PR | AUC-ROC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| **Random Forest** | **0.671** | 0.999 | **0.667** | 0.333 | 0.444 |
| Regresión Logística | 0.621 | 0.995 | 0.333 | **0.667** | 0.444 |
| Gradient Boosting | 0.418 | 0.749 | 0.429 | 0.500 | **0.462** |

Random Forest mantiene el mayor AUC-PR y sigue siendo el candidato preferido
del benchmark metodológico para ranking probabilístico e interpretabilidad con
SHAP. El F1 no se usa como criterio primario porque el objetivo es priorización
bajo desbalance severo.

Tuning Random Forest sklearn:

- configuración seleccionada: `n_estimators=100`, `max_depth=3`,
  `min_samples_leaf=1`;
- AUC-PR medio en CV de tuning: **0.844**;
- la configuración 300 árboles / profundidad 6 obtiene el mismo AUC-PR, por lo
  que se conserva la alternativa más liviana.

#### Evidencia vigente — Fraccionamiento

El benchmark independiente deja visible una limitación importante del modelo
estadístico puro:

- dataset: 180 grupos, 8 positivos sintéticos;
- desarrollo: 112 grupos / 5 positivos;
- holdout final: 68 grupos / 3 positivos;
- mejor validación repetida: AUC-PR medio **0.402**;
- holdout final: AUC-ROC **0.856**, AUC-PR **0.171**, precision **0.176**,
  recall **1.000**, F1 **0.300**, recall@K **0.000**.

Isolation Forest identifica una región amplia de anomalías, pero su precisión y
ranking de positivos son débiles en este benchmark. La regla interpretable y la
revisión humana siguen siendo complementos; ninguna señal se convierte
automáticamente en un hallazgo jurídico.

### ✅ P1 documental — generación automática integrada

Los Productos 1–7 y el reporte técnico ya no mantienen cifras independientes
escritas a mano. El flujo es:

1. `src/generar_evidencia_documental.py` construye
   `outputs/evidencia_documental.json` a partir de datasets y JSON vigentes.
2. `reporte/evidencia.js` expone esa fuente a los generadores Node.
3. `reporte/generar_productos_formales.js` genera Productos 1–7.
4. `reporte/generar_reporte.js` genera el reporte técnico consolidado.
5. GitHub Actions abre los DOCX con `python-docx`, busca afirmaciones obsoletas
   y persiste la documentación validada en `main`.

La documentación distingue explícitamente lo demostrado por el PoC de las
dependencias institucionales.

### ✅ Sprint A — Spark canónico y trazabilidad: cerrado

Spark dejó de ser una ruta paralela del repositorio. La ejecución reproducible
actual diferencia dos responsabilidades:

- **scikit-learn:** benchmark metodológico, comparación de candidatos,
  validación independiente y explicabilidad;
- **Apache Spark MLlib / GraphFrames:** implementación objetivo del TDR que se
  ejecuta de forma real en `local[*]` dentro del pipeline reproducible.

El cierre del Sprint A incluye:

- Java 17 + `pyspark==4.1.1` instalados y ejecutados en GitHub Actions;
- Random Forest de favoritismo implementado y ejecutado con Spark MLlib,
  `CrossValidator`, AUC-PR y folds estratificados determinísticos;
- KMeans MLlib + distancia al centroide + ventanas Spark SQL para el componente
  no supervisado de fraccionamiento;
- GraphFrames ejecutado sobre la misma capa Plata usada por el resto del PoC;
- `src/spark/estandares_sql.py` ejecutado en CI para LEFT JOIN y evidencia de
  partition pruning;
- DAG principal de Airflow con las ramas Spark MLlib/GraphFrames incorporadas;
- modelos binarios Spark tratados como artefactos de runtime; la evidencia
  reproducible versionada son rankings y resúmenes JSON/CSV;
- Oro contiene solo salidas downstream, incluidas las salidas Spark/GraphFrames,
  y ya no conserva datasets intermedios de feature engineering;
- diccionario y diagrama se regeneran en la misma ejecución CI;
- `outputs/linaje_datos.csv` documenta explícitamente
  fuente → transformación → Plata → feature → implementación → salida Oro;
- `run_manifest.json` usa schema 3 y registra también las versiones y evidencias
  de Spark/GraphFrames.

La métrica Spark de favoritismo no se usa como estimación de desempeño: el
benchmark solo contiene seis positivos. Por ello la comparación OOF de sklearn
permanece como evidencia metodológica principal, mientras Spark demuestra la
implementación y ejecución de la arquitectura exigida por el TDR.

Lo que sigue pendiente en esta área requiere infraestructura institucional:
HDFS/YARN distribuido, Lakehouse/Datamart real de CGR, fuentes internas y
validación de desempeño en el clúster institucional.

## Correspondencia resumida con el TDR

| Área TDR | Estado PoC |
|---|---|
| EDA y calidad de datos | Implementado |
| Feature engineering | Implementado y endurecido |
| Favoritismo supervisado | Benchmark OOF/tuning/SHAP + implementación Spark MLlib ejecutada en CI |
| Fraccionamiento no supervisado | Isolation Forest con holdout + Spark MLlib KMeans + señal interpretable |
| Spark MLlib | **Ejecutado y validado en CI con Spark real `local[*]`; clúster CGR pendiente** |
| Grafos | NetworkX de referencia + **GraphFrames ejecutado en CI** |
| Airflow DAGs | Implementados; incluyen rutas sklearn y Spark; Python de proyecto separado |
| Bronce / Plata / Oro | Simulación local funcional; Oro solo downstream; Lakehouse CGR pendiente |
| Autoevaluación/reentrenamiento | Modelo candidato + revisión humana requerida |
| SSRS | Esquema T-SQL + RDL; servidor institucional pendiente |
| Linaje/diccionario | Diccionario + diagrama + **linaje explícito** + run manifest |
| DEV/QA/PROD, Git institucional, certificación | Dependencia institucional CGR |
| Transferencia formal / marcha blanca | Dependencia contractual/institucional |

## Estructura

```text
src/                         Python principal
src/spark/                   Spark MLlib, GraphFrames, Delta, SQL, streaming, HMS
airflow_home/dags/           DAG principal + monitoreo
lakehouse/bronce/            Simulación de ingesta cruda
lakehouse/plata/             Datos limpios/features consumidos por modelos
lakehouse/oro/               Solo salidas para reporting/integración
ssrs/                        DDL T-SQL + RDL PoC
reporte/                     Generadores y documentos formales
outputs/                     Evidencias, rankings, tuning, manifests y linaje
tests/                       Pruebas de regresión
.github/workflows/           CI end-to-end sklearn + Spark
```

## Reproducir el entorno Python

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

python3 -m venv .venv_airflow
.venv_airflow/bin/pip install "apache-airflow==3.3.0" \
  --constraint "https://raw.githubusercontent.com/apache-airflow/airflow/constraints-3.3.0/constraints-3.12.txt"

export PROYECTO_DIR="$PWD"
export CGR_PROJECT_PYTHON="$PWD/.venv/bin/python"
export AIRFLOW_HOME="$PWD/airflow_home"
```

Graphviz (`dot`) debe estar instalado en el sistema para regenerar el diagrama.
Spark requiere una JVM compatible; CI usa Java 17.

## Pruebas

```bash
.venv/bin/pytest -q
```

GitHub Actions ejecuta además un smoke end-to-end con generación sintética,
Bronce/Plata, benchmark sklearn, Spark MLlib, GraphFrames, SQL Spark, Oro,
diccionario, linaje, manifiesto y documentación.

## Pipeline sintético orquestado

```bash
.venv_airflow/bin/airflow dags test modulo_analisis_datos_1_8_2
```

```text
fuentes -> Bronce -> preprocesamiento/features -> Plata
                    |-> benchmark sklearn favoritismo -> tuning -> modelo
                    |-> benchmark sklearn fraccionamiento -> tuning/holdout -> modelo
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
                                 documentación
```

Los DOCX requieren Node.js y se generan/validan en GitHub Actions; el DAG de
Airflow deja lista la evidencia machine-readable que consumen los generadores.

## Datos reales OCDS/OECE

Los crudos y derivados identificables no se publican. Para reproducir la
validación local, seguir `data_real/README.md` con `main.csv`, `contracts.csv`,
`awards.csv`, `awards_suppliers.csv` y `parties.csv`.

Los rankings reales se generan localmente, pero están ignorados por Git para
evitar publicar asociaciones entre proveedores reales y señales estadísticas
fuera de contexto.

## Documentación formal

Para regenerar localmente después de producir la evidencia:

```bash
python src/generar_evidencia_documental.py
cd reporte
npm ci
npm run all
```

GitHub Actions ejecuta el mismo flujo y valida que los DOCX no reintroduzcan
variables, métricas o afirmaciones obsoletas. El conteo histórico 47,442 solo se
permite si está explícitamente presentado como antecedente descartado; el valor
vigente debe ser 47,254.

## Licencia

El código está bajo licencia MIT. Los datos públicos de OECE/OCP conservan su
licencia de origen (CC BY 4.0 cuando corresponda). Si el prototipo evolucionara
a un encargo contractual, los activos generados bajo dicho encargo deberán
separarse y regirse por las cláusulas de propiedad/confidencialidad del TDR.
