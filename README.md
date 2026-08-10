# Módulo de Análisis de Datos para Priorización de Riesgos de Contratación

> **Prototipo público e independiente basado en el TDR del Proyecto Interno 1.8.2.**  
> Este repositorio no constituye una implementación oficial, no utiliza accesos internos de la Contraloría General de la República (CGR) y no implica aprobación institucional.

Este proyecto implementa una arquitectura reproducible para **integrar datos de contratación, generar señales analíticas de riesgo y priorizar casos para revisión humana**. Incluye análisis de posible favoritismo y fraccionamiento, vínculos proveedor–funcionario, pagos y modalidades de contratación, Apache Spark MLlib, GraphFrames, Airflow, capas Bronce/Plata/Oro, trazabilidad, reporting SQL Server/SSRS y un ciclo operacional TRAIN/INFERENCE con promoción explícita de modelos.

Las salidas son **señales de priorización**. No constituyen hallazgos de control, imputaciones, decisiones jurídicas ni determinaciones automáticas de irregularidad.

## Estado del proyecto

La rama `main` contiene el PoC endurecido para facilitar una futura integración institucional. La auditoría integral del TDR público registra:

| Estado | Criterios | Interpretación |
|---|---:|---|
| ✅ | 12 | Cubiertos con evidencia reproducible del repositorio |
| 🟡 | 8 | Software/contrato resuelto; cierre literal requiere datos, infraestructura o validación CGR |
| 🔵 | 5 | Actividades exclusivamente institucionales/contractuales |
| 🔴 | **0** | **No quedan brechas rojas dentro de los criterios evaluados del TDR público** |

El checklist específico del Anexo 3 se mantiene en **6 ✅ / 4 🟡 / 1 🔵 / 0 🔴**.

`0 🔴` no equivale a certificación productiva. El cierre institucional todavía requiere fuentes reales, ground truth, clúster, seguridad, DEV/QA/PROD, SQL Server/SSRS, usuarios y conformidad CGR. La diferencia es que la ruta `spark_sql` ya conserva un **Spark DataFrame de extremo a extremo** desde la tabla/vista hasta MLlib y la salida distribuida, sin `toPandas()` intermedio.

La versión `v1.0.0-rc.1` permanece como snapshot histórico e inmutable del primer release candidate. `main` incorpora mejoras posteriores de integración institucional, separación TRAIN/INFERENCE, serving Spark MLlib, pagos, auditoría integral del TDR y ejecución Spark-native.

## Capacidades principales

| Componente | Función |
|---|---|
| Integración canónica | Desacopla tablas/columnas físicas mediante conectores y mappings YAML |
| Spark-native | `spark_sql` mantiene DataFrames Spark en mapping, validación, preprocesamiento, TRAIN e INFERENCE |
| Calidad y preprocesamiento | Valida esquema, trata nulos/outliers y congela el estado usado en serving |
| Favoritismo | Prioriza pares proveedor–entidad con benchmark metodológico y champion Spark MLlib |
| Fraccionamiento | Combina KMeans MLlib, distancia al centroide y señal interpretable temporal/cuantiativa |
| Grafos | Analiza vínculos proveedor–funcionario con NetworkX/GraphFrames |
| Pagos y modalidades | Resume ejecución de pagos, ratios, demoras y contexto de modalidades por régimen |
| MLOps | Separa TRAIN, candidate, promoción explícita, champion e INFERENCE sin reentrenamiento |
| Orquestación | DAGs separados para reproducibilidad, TRAIN, INFERENCE y monitoreo |
| Reporting | Mantiene contrato T-SQL/RDL para SQL Server/SSRS |
| Trazabilidad | Diccionario, diagrama, linaje, hashes, registry y `run_manifest.json` |
| Documentación | Genera Productos 1–7 e Informe Final desde evidencia machine-readable |

## Arquitectura operacional

```text
Fuentes institucionales
(SQL Server / Spark SQL / CSV controlado)
              |
              v
      connector + mapping YAML
              |
              v
        esquema canónico
              |
      +-------+--------+
      |                |
      | TRAIN          | INFERENCE
      v                v
FIT preprocesador   preprocesador congelado
      |                |
      v                v
features Spark      features Spark
      |                |
      v                v
modelos MLlib      champion MLlib
      |                |
      v                v
candidate --------> scores de priorización
      |                |
      | aprobación     v
      +----------> Oro / SQL Server / SSRS
```

Para `source.type: spark_sql`, la ruta es distribuida desde `SparkSession.table(...)` hasta MLlib y la escritura Parquet de rankings. Para `local_csv` y `sqlserver` se conserva un adaptador pandas→Spark por compatibilidad y simplicidad de integración.

**INFERENCE no consume labels, no hace `.fit()`, no ejecuta tuning y no reentrena.** La promoción de un candidate es una operación separada y debe quedar detrás del gate de aprobación que defina la institución.

## Ruta de reproducibilidad del PoC

```text
datos sintéticos / datos públicos agregados
            |
          Bronce
            |
          Plata
      +-----+----------------+
      |          |           |
   sklearn    Spark MLlib   GraphFrames
      |          |           |
      +----------+-----------+
                 |
                Oro
                 |
       linaje + manifiesto
                 |
       documentación formal
```

Esta ruta reconstruye la evidencia histórica del PoC y conserva decisiones legacy necesarias para reproducibilidad. No debe confundirse con el serving operacional.

## Contrato de datos

Los modelos dependen de **nombres canónicos**, no de nombres físicos de SIAF, SEACE, Datamart u otra fuente. El mapping usa:

```yaml
campo_canonico: COLUMNA_FISICA
```

Dominios soportados:

- `contracts`
- `suppliers`
- `entities`
- `officials`
- `payments`

Campos obligatorios de `contracts` en INFERENCE:

```text
id_contrato
id_proveedor
id_entidad
monto
fecha_contrato
modalidad
objeto
categoria_principal
```

TRAIN añade:

```text
label_favoritismo
label_fraccionamiento
```

`categoria_principal` debe existir porque fraccionamiento la utiliza para resolver el contexto normativo; puede venir nula y utilizar el fallback definido por el proveedor de umbrales.

Referencia técnica: [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md).

## Inicio rápido local

### Requisitos

- Python 3.12 recomendado;
- Java 17 para Spark;
- Graphviz para artefactos gráficos;
- LibreOffice solo para regenerar/materializar los DOCX formales;
- Airflow solo si se ejecutarán los DAGs;
- `pyodbc` + driver ODBC únicamente para SQL Server.

### Instalación

```bash
git clone https://github.com/NoeCalle/cgr-analisis-datos.git
cd cgr-analisis-datos

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

En Windows, usar los ejecutables equivalentes de `.venv\Scripts\`.

### Pruebas

```bash
.venv/bin/pytest -q
```

### Validar una configuración sin conectarse

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.example.yaml \
  --validate-only
```

### INFERENCE local con champion Spark

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

### Pagos y modalidades

```bash
.venv/bin/python src/analisis_pagos_modalidades.py \
  --config config/local-tdr.yaml
```

## Integración institucional

La adaptación principal prevista es **configuración + infraestructura**, no una reescritura del ML:

1. migrar el código a un repositorio institucional privado;
2. aprobar tablas/vistas y diccionario de datos;
3. copiar `config/cgr.example.yaml` a configuración privada;
4. mapear columnas físicas al esquema canónico;
5. inyectar secretos mediante el mecanismo institucional;
6. validar en DEV;
7. preparar ground truth histórico para TRAIN;
8. entrenar candidate Spark;
9. evaluar y promover mediante aprobación autorizada;
10. ejecutar INFERENCE sobre contratos actuales;
11. publicar salidas aprobadas en el almacenamiento/SQL Server/SSRS institucional;
12. validar QA/PROD, monitoreo, rollback y operación.

Manual completo: **[`docs/Manual_Aterrizaje_Institucional_CGR.md`](docs/Manual_Aterrizaje_Institucional_CGR.md)**.

La plantilla `config/cgr.example.yaml` contiene placeholders; **no representa nombres reales de tablas, vistas o columnas de la CGR**.

## Spark operacional y escala

TRAIN e INFERENCE aceptan:

```bash
export CGR_SPARK_MASTER='<master Spark aprobado>'
export CGR_SPARK_SHUFFLE_PARTITIONS='<n>'  # opcional
```

Si `CGR_SPARK_MASTER` no existe, el PoC usa `local[*]` como fallback local. La ruta histórica mantiene `local[*]` deliberadamente para reproducibilidad.

Con `source.type: spark_sql`:

```text
Spark SQL
  -> mapping canónico Spark
  -> validación/casteo Spark
  -> FIT/TRANSFORM Spark
  -> feature engineering Spark
  -> MLlib
  -> Parquet distribuido
```

Las medianas por objeto aprendidas durante TRAIN se almacenan como un artefacto Parquet Spark cuando la fuente es distribuida; INFERENCE vuelve a cargarlas sin colectar la dimensión completa al driver.

## TRAIN, candidate, promoción e INFERENCE

### TRAIN Spark

```bash
.venv/bin/python src/spark/entrenar_candidato_spark.py \
  --config config/local-training.yaml
```

TRAIN genera un **candidate** y no reemplaza el champion.

### Promoción técnica del PoC

```bash
.venv/bin/python src/promover_candidato_spark.py \
  --manifest outputs/runtime/spark_model_candidates/candidate_manifest.json \
  --approved-by "operador técnico" \
  --acknowledge-poc-only
```

Este comando representa solo promoción técnica dentro del PoC. En una implantación real debe quedar subordinado a la segregación de funciones y al MLOps institucional.

### INFERENCE Spark

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

El perfil activo del PoC es `spark_mllib`; sklearn permanece como benchmark/compatibilidad.

Más detalle: [`docs/Train_Inference.md`](docs/Train_Inference.md).

## Airflow

| DAG | Propósito |
|---|---|
| `reproducibilidad_poc_1_8_2` | reconstruir evidencia del PoC |
| `entrenamiento_candidato_1_8_2` | entrenar candidate Spark sin promoverlo |
| `inferencia_modelos_1_8_2` | puntuar con champion Spark sin reentrenar |
| `monitoreo_reentrenamiento_1_8_2` | controles de monitoreo/autoevaluación |

Variables principales:

```text
PROYECTO_DIR
CGR_PROJECT_PYTHON
CGR_DATA_CONFIG
CGR_TRAIN_CONFIG
CGR_MODEL_REGISTRY
CGR_INFERENCE_OUTPUT_DIR
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
```

## Salidas y evidencia

| Ruta | Contenido |
|---|---|
| `lakehouse/oro/` | salidas downstream del PoC |
| `outputs/model_registry.json` | registry técnico y perfil activo |
| `outputs/champions_spark/` | champion Spark MLlib del PoC |
| `outputs/runtime/` | candidates e inferencias operacionales; no versionados |
| `outputs/linaje_datos.csv` | linaje fuente → transformación → feature → modelo/salida |
| `data/diccionario_datos.csv` | diccionario de datos |
| `outputs/run_manifest.json` | commit, versiones, hashes, parámetros y artefactos |
| `outputs/analisis_pagos_modalidades.json` | resumen machine-readable de pagos/modalidades |
| `ssrs/` | DDL T-SQL y RDL de reporting |
| `reporte/` | Productos 1–7 e Informe Final |

Para `spark_sql`, los rankings operacionales detallados se escriben como **Parquet distribuido**. Los derivados identificables de fuentes reales no deben publicarse en este repositorio público.

## Seguridad y gobernanza

- secretos fuera de YAML y Git;
- `connection_env` para SQL Server;
- proyección de identificadores configurados, sin SQL libre desde YAML;
- vistas institucionales aprobadas para joins/reglas complejas;
- datos reales y PII únicamente en almacenamiento institucional autorizado;
- promotion gate separado de TRAIN;
- revisión humana obligatoria de señales;
- segregación de permisos entre TRAIN, aprobación y PROD.

## Calidad y CI

GitHub Actions valida, entre otros:

- regresiones y reproducibilidad legacy;
- integración canónica pandas y Spark-native;
- prohibición de `.toPandas()` en `spark_sql`, TRAIN e INFERENCE;
- mapping/casteo Spark con nombres físicos arbitrarios;
- FIT distribuido del preprocesador y medianas Parquet;
- TRAIN candidate aislado;
- promoción explícita y serving Spark;
- INFERENCE sin labels/training/tuning;
- escritura Parquet distribuida para `spark_sql`;
- Spark MLlib, GraphFrames, Oro y trazabilidad;
- generación, render y QA de los ocho DOCX;
- auditoría del Anexo 3 y auditoría integral del TDR.

## Desarrollo y contribuciones

Todo cambio funcional debería:

1. evitar datos reales, PII y secretos en Git;
2. añadir/actualizar pruebas cuando cambie un contrato;
3. ejecutar `pytest -q`;
4. mantener separados TRAIN, promoción e INFERENCE;
5. preservar la ruta Spark-native sin collect implícito;
6. actualizar documentación, diccionario y linaje cuando cambien interfaces;
7. dejar que CI regenere evidencia derivada.

Para adopción institucional se recomienda trabajar con ramas/PR y proteger `main` con checks obligatorios.

<!-- RELEASE-CANDIDATE-START -->
## Release candidate histórico

Versión declarada del snapshot original del PoC independiente: **`v1.0.0-rc.1`**.

El tag conserva la evidencia del primer release candidate y no se mueve con las mejoras posteriores de `main`. No representa aprobación ni despliegue institucional de la CGR.

Evidencia de ese snapshot:

- `RELEASE_NOTES.md`;
- `docs/Checklist_Anexo_03.md`;
- `docs/Dependencias_Institucionales_CGR.md`;
- `docs/Auditoria_Final_Release.md`;
- `outputs/auditoria_release.json`.
<!-- RELEASE-CANDIDATE-END -->

## Documentación

| Documento | Uso |
|---|---|
| [`docs/Manual_Aterrizaje_Institucional_CGR.md`](docs/Manual_Aterrizaje_Institucional_CGR.md) | guía de integración institucional |
| [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md) | esquema canónico y conectores |
| [`docs/Train_Inference.md`](docs/Train_Inference.md) | ciclo de modelos y serving |
| [`docs/Dependencias_Institucionales_CGR.md`](docs/Dependencias_Institucionales_CGR.md) | pendientes institucionales |
| [`docs/Checklist_Anexo_03.md`](docs/Checklist_Anexo_03.md) | auditoría Anexo 3 |
| [`docs/Auditoria_TDR_Completo.md`](docs/Auditoria_TDR_Completo.md) | auditoría integral del TDR |
| [`docs/Auditoria_Final_Release.md`](docs/Auditoria_Final_Release.md) | gate técnico del RC histórico |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | alcance de `v1.0.0-rc.1` |

## Estructura del repositorio

```text
config/                    perfiles y plantillas de integración
src/                       pipeline, conectores, modelos y auditorías
airflow_home/dags/          orquestación
lakehouse/                  Bronce/Plata/Oro reproducible
outputs/                    evidencia, registry, métricas y linaje
ssrs/                       contrato SQL Server/SSRS
reporte/                    generadores y documentos formales
tests/                      regresiones funcionales y arquitectónicas
docs/                       documentación técnica y auditorías
```

## Limitaciones

- No contiene datos internos ni credenciales CGR.
- El ground truth del benchmark es sintético; las métricas no estiman desempeño productivo.
- La ruta Spark-native está implementada para `spark_sql`, pero su rendimiento real debe probarse en el clúster, catálogo, permisos y volumen institucionales.
- CSV/SQL Server mantienen un adaptador pandas→Spark; esto es deliberado y no se presenta como procesamiento distribuido.
- SQL Server/SSRS real, DEV/QA/PROD, certificación, marcha blanca y transferencia requieren CGR.
- Las señales no reemplazan juicio profesional ni revisión jurídica/técnica.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
