# Módulo de Análisis de Datos — Prototipo independiente (CGR 1.8.2)

> **Prototipo independiente.** Este repositorio no constituye una
> implementación oficial ni cuenta con aprobación institucional de la
> Contraloría General de la República (CGR). Es un ejercicio técnico propio,
> construido a partir de un TDR público de mayo de 2026.

Prueba de concepto del “Módulo de análisis de datos para dar soporte a los
auditores durante la ejecución de los servicios de control”, con énfasis en:

- priorización de señales de posible favoritismo;
- priorización de señales de posible fraccionamiento;
- análisis de vínculos proveedor–funcionario en el escenario sintético;
- Spark MLlib, Airflow, Lakehouse Bronce/Plata/Oro, SSRS y MLOps como PoC.

Las salidas de riesgo son **señales para revisión de auditor**. No constituyen
hallazgos, imputaciones ni determinaciones automáticas de irregularidad.

## Estado del plan de cierre de brechas

### ✅ P0 — Integridad OCDS y normativa: cerrado

La parte más crítica del pipeline real fue reconstruida y validada:

- relación OCDS correcta: `Contract -> Award -> Supplier`;
- clave analítica: `OCID::contract.id`;
- adjudicatarios tomados de `awards_suppliers.csv`, sin mezclar suppliers de
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

El detalle agregado y hashes SHA-256 están en
`outputs/validacion_p0_datos_reales.json`. La cifra anterior de 47,442
contratos ya no es válida; sus rankings `*_REAL.csv` fueron retirados.

### ✅ P1 — Núcleo técnico de modelado/reproducibilidad: cerrado

El núcleo técnico del plan P1 ya está integrado y validado automáticamente:

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
- GitHub Actions reconstruye el dataset, publica Plata, ejecuta comparación y
  tuning y verifica los artefactos en cada push/PR.
- `run_manifest.json` permite registrar commit, versiones, hashes, parámetros y
  evidencia de una ejecución completa.

#### Evidencia vigente — Favoritismo

Comparación out-of-fold sobre **2,328 pares proveedor-entidad**, con 6 casos
positivos sintéticos difíciles:

| Modelo | AUC-PR | AUC-ROC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| **Random Forest** | **0.755** | 0.999 | 0.571 | 0.667 | **0.615** |
| Regresión Logística | 0.621 | 0.995 | 0.333 | 0.667 | 0.444 |
| Gradient Boosting | 0.418 | 0.749 | 0.429 | 0.500 | 0.462 |

Random Forest sigue siendo el candidato mejor sustentado, pero ya no se
presenta un AUC-PR artificial de 1.00. La comparación reproducible está en
`outputs/comparacion_modelos_favoritismo.json`.

Tuning Random Forest:

- configuración seleccionada: `n_estimators=100`, `max_depth=3`,
  `min_samples_leaf=1`;
- AUC-PR medio en CV de tuning: **0.844**;
- la configuración histórica 300 árboles / profundidad 6 obtiene el mismo
  AUC-PR, por lo que se conserva la alternativa más liviana.

#### Evidencia vigente — Fraccionamiento

El benchmark independiente deja visible una limitación importante del modelo
estadístico puro:

- dataset: 180 grupos, 8 positivos sintéticos;
- desarrollo: 112 grupos / 5 positivos;
- holdout final: 68 grupos / 3 positivos;
- mejor validación repetida: AUC-PR medio **0.402**;
- holdout final: AUC-ROC **0.856**, AUC-PR **0.171**, precision **0.176**,
  recall **1.000**, F1 **0.300**, recall@K **0.000**.

Esto no se oculta: Isolation Forest identifica una región amplia de anomalías,
pero su precisión/ranking es débil en este benchmark. La regla interpretable y
la revisión humana siguen siendo complementos importantes; ninguna de ellas
convierte automáticamente una señal en un hallazgo jurídico.

La evidencia está en `outputs/tuning_fraccionamiento_resumen.json` y
`outputs/tuning_fraccionamiento_resultados.csv`.

### 🟡 P1 documental — pendiente de regeneración

Los `.docx` actuales fueron generados antes de parte de las correcciones P0/P1.
Se conservan como evidencia histórica, pero **no son la versión final vigente**.
El siguiente cierre es regenerar Productos 1–7 y el reporte consolidado a partir
de los JSON/manifiestos actuales, eliminando métricas, umbrales y afirmaciones
obsoletas escritas a mano.

## Correspondencia resumida con el TDR

| Área TDR | Estado PoC |
|---|---|
| EDA y calidad de datos | Implementado |
| Feature engineering | Implementado y endurecido |
| Favoritismo supervisado | Comparación OOF + RF + tuning + SHAP |
| Fraccionamiento no supervisado | Isolation Forest + holdout + señal interpretable |
| Spark MLlib | Implementado en modo local; clúster institucional pendiente |
| Grafos | networkx + GraphFrames en escenario sintético |
| Airflow DAGs | Implementados; Python de proyecto separado |
| Bronce / Plata / Oro | Simulación local funcional; Lakehouse CGR pendiente |
| Autoevaluación/reentrenamiento | Modelo candidato + revisión humana requerida |
| SSRS | Esquema T-SQL + RDL + SQLite stand-in; servidor institucional pendiente |
| Linaje/diccionario | Diccionario, diagrama y run manifest |
| DEV/QA/PROD, Git institucional, certificación | Dependencia institucional CGR |
| Transferencia formal / marcha blanca | Dependencia contractual/institucional |

## Estructura

```text
src/                         Python principal
src/spark/                   Spark MLlib, GraphFrames, Delta, SQL, streaming, HMS
airflow_home/dags/           DAG principal + monitoreo
lakehouse/bronce/             Simulación de ingesta cruda
lakehouse/plata/              Datos limpios/features consumidos por modelos
lakehouse/oro/                Salidas para reporting/integración
ssrs/                         DDL T-SQL + RDL PoC
reporte/                      Generadores y documentos formales
outputs/                      Evidencias, modelos, tuning, manifests
tests/                        Pruebas de regresión
.github/workflows/            CI
```

## Reproducir el entorno Python

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

python3 -m venv .venv_airflow
.venv_airflow/bin/pip install "apache-airflow==3.3.0" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.0/constraints-3.12.txt"

export PROYECTO_DIR="$PWD"
export CGR_PROJECT_PYTHON="$PWD/.venv/bin/python"
export AIRFLOW_HOME="$PWD/airflow_home"
```

## Pruebas

```bash
.venv/bin/pytest -q
```

GitHub Actions añade además un smoke end-to-end de generación sintética,
preprocesamiento, Plata y selección de modelos.

## Pipeline sintético orquestado

```bash
.venv_airflow/bin/airflow dags test modulo_analisis_datos_1_8_2
```

```text
fuentes -> Bronce -> preprocesamiento/features -> Plata
                    |-> comparar modelos favoritismo -> tuning -> modelo
                    |-> tuning fraccionamiento + holdout -> modelo
                    |-> grafos
                                      ↓
                                     Oro
                                      ↓
                              run_manifest.json
                                      ↓
                                 documentación
```

## Datos reales OCDS/OECE

Los crudos y derivados identificables no se publican. Para reproducir la
validación local, seguir `data_real/README.md` con `main.csv`, `contracts.csv`,
`awards.csv`, `awards_suppliers.csv` y `parties.csv`.

Los rankings reales se generan localmente, pero están ignorados por Git para
evitar publicar asociaciones entre proveedores reales y señales estadísticas
fuera de contexto.

## Documentación formal

Los documentos actuales en `reporte/` y `reporte/productos_formales/` son
históricos. La versión final del PoC se regenerará desde la evidencia actual y
mantendrá explícitamente como **pendientes institucionales**: Datamart real,
Hadoop/YARN productivo, Git institucional, SQL Server/SSRS real, DEV/QA/PROD,
certificación, incidencias de ambientes, marcha blanca y transferencia formal.

## Licencia

El código está bajo licencia MIT. Los datos públicos de OECE/OCP conservan su
licencia de origen (CC BY 4.0 cuando corresponda). Si el prototipo evolucionara
a un encargo contractual, los activos generados bajo dicho encargo deberán
separarse y regirse por las cláusulas de propiedad/confidencialidad del TDR.
