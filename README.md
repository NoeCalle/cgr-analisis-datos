# Módulo de Análisis de Datos para Priorización de Riesgos de Contratación

> **Prototipo público e independiente basado en el TDR del Proyecto Interno 1.8.2.**  
> Este repositorio no constituye una implementación oficial, no utiliza accesos internos de la Contraloría General de la República (CGR) y no implica aprobación institucional.

El proyecto implementa una arquitectura reproducible para **integrar datos de contratación, generar señales analíticas de riesgo y priorizar casos para revisión humana**. Incluye análisis de posible favoritismo y fraccionamiento, vínculos proveedor–funcionario, pagos y modalidades de contratación, Spark MLlib, GraphFrames, Airflow, capas Bronce/Plata/Oro, trazabilidad, reporting SSRS y ciclo TRAIN/INFERENCE con promoción explícita de modelos.

Las salidas son **señales de priorización**. No constituyen hallazgos de control, imputaciones, decisiones jurídicas ni determinaciones automáticas de irregularidad.

## Estado del proyecto

La rama `main` contiene el PoC endurecido para facilitar una futura integración institucional. La auditoría integral del TDR público registra actualmente:

| Estado | Criterios | Interpretación |
|---|---:|---|
| ✅ | 12 | Cubiertos con evidencia reproducible del repositorio |
| 🟡 | 8 | Software/contrato resuelto; cierre literal requiere datos, infraestructura o validación CGR |
| 🔵 | 5 | Actividades exclusivamente institucionales/contractuales |
| 🔴 | **0** | **No quedan brechas técnicas conocidas cerrables únicamente desde este repositorio** |

El checklist específico del Anexo 3 se mantiene en **6 ✅ / 4 🟡 / 1 🔵 / 0 🔴**.

La versión `v1.0.0-rc.1` permanece como snapshot histórico e inmutable del release candidate original. `main` incorpora mejoras posteriores de integración institucional, separación TRAIN/INFERENCE, serving Spark MLlib, análisis de pagos y auditoría integral del TDR.

## Qué hace la herramienta

| Componente | Función |
|---|---|
| Integración canónica | Desacopla tablas/columnas físicas mediante conectores y mappings YAML |
| Calidad y preprocesamiento | Valida esquema, trata nulos/outliers y congela el estado de preprocesamiento usado en serving |
| Favoritismo | Prioriza pares proveedor–entidad mediante benchmark metodológico y champion Spark MLlib |
| Fraccionamiento | Combina detección no supervisada, KMeans MLlib y una señal interpretable temporal/cuantiativa |
| Grafos | Analiza vínculos proveedor–funcionario con NetworkX/GraphFrames |
| Pagos y modalidades | Resume ejecución de pagos, ratios, demoras y contexto de modalidades por régimen |
| MLOps | Separa TRAIN, candidate, promoción explícita, champion e INFERENCE sin reentrenamiento |
| Orquestación | DAGs independientes para reproducibilidad, TRAIN, INFERENCE y monitoreo |
| Reporting | Publica salidas Oro y mantiene contrato T-SQL/RDL para SQL Server/SSRS |
| Trazabilidad | Diccionario, diagrama, linaje, hashes, registry y `run_manifest.json` |
| Documentación | Genera Productos 1–7 e Informe Final desde evidencia machine-readable |

## Arquitectura

### Ruta operacional

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

**INFERENCE no consume labels, no hace `.fit()`, no ejecuta tuning y no reentrena.** La promoción de un candidate es una operación separada y debe quedar detrás del gate de aprobación definido por la institución.

### Ruta de reproducibilidad del PoC

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

Esta ruta reconstruye la evidencia del PoC. No debe confundirse con la ruta operacional para contratos actuales.

## Contrato de datos

Los modelos dependen de **nombres canónicos**, no de nombres físicos de SIAF, SEACE, Datamart u otra fuente. El mapping siempre usa la dirección:

```yaml
campo_canonico: COLUMNA_FISICA
```

Dominios soportados:

- `contracts`
- `suppliers`
- `entities`
- `officials`
- `payments`

Campos mínimos de `contracts` en INFERENCE:

```text
id_contrato
id_proveedor
id_entidad
monto
fecha_contrato
modalidad
objeto
```

TRAIN añade obligatoriamente:

```text
label_favoritismo
label_fraccionamiento
```

Los campos físicos reales se configuran en YAML. No es necesario editar el código de los modelos para cambiar nombres de tablas o columnas compatibles con el contrato canónico.

Referencia completa: [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md).

## Inicio rápido local

### Requisitos

- Python 3.12 recomendado;
- Java 17 para Spark;
- Graphviz para artefactos gráficos;
- LibreOffice solo si se desea regenerar/materializar los DOCX formales;
- Airflow solo para ejecutar los DAGs;
- `pyodbc` + driver ODBC institucional únicamente si se usa SQL Server.

### Instalación

```bash
git clone https://github.com/NoeCalle/cgr-analisis-datos.git
cd cgr-analisis-datos

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

En Windows, sustituir `.venv/bin/python` y `.venv/bin/pip` por los ejecutables equivalentes de `.venv\Scripts\`.

### Verificar el repositorio

```bash
.venv/bin/pytest -q
```

### Validar el contrato de integración sin conectarse

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.example.yaml \
  --validate-only
```

### Ejecutar INFERENCE local con el champion Spark del PoC

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

La evidencia agregada del smoke vigente confirma que la ruta Spark puntúa contratos sin consumir labels, training ni tuning.

### Analizar pagos y modalidades con datos sintéticos

```bash
.venv/bin/python src/analisis_pagos_modalidades.py \
  --config config/local-tdr.yaml
```

Los resultados se generan en `outputs/analisis_pagos_modalidades.json`, `outputs/resumen_pagos_contrato.csv`, `outputs/resumen_modalidades_regimen.csv` y gráficos asociados.

## Integración institucional

La adaptación prevista es **configuración + infraestructura**, no una reescritura del ML:

1. llevar el código a un repositorio institucional privado;
2. aprobar las vistas/tablas que alimentarán cada dominio canónico;
3. copiar `config/cgr.example.yaml` a un archivo institucional no versionado;
4. mapear columnas físicas a campos canónicos;
5. inyectar credenciales mediante variables de entorno/gestor de secretos;
6. validar configuración y calidad en DEV;
7. preparar dataset histórico con ground truth para TRAIN;
8. entrenar candidate Spark, evaluar y promover solo mediante aprobación autorizada;
9. ejecutar INFERENCE sobre contratos actuales;
10. conectar las salidas aprobadas a SQL Server/SSRS y operar en QA/PROD.

El procedimiento detallado, responsabilidades, gates, rollback y checklist de cierre están en:

**[`docs/Manual_Aterrizaje_Institucional_CGR.md`](docs/Manual_Aterrizaje_Institucional_CGR.md)**

La plantilla `config/cgr.example.yaml` contiene únicamente placeholders. **No representa nombres reales de tablas, vistas o columnas de la CGR.**

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

Este comando solo representa promoción técnica dentro del PoC. En una implantación real debe quedar subordinado al proceso institucional de aprobación, segregación de funciones y registry/MLOps que defina la CGR.

### INFERENCE Spark

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

El perfil activo del PoC es `spark_mllib`. El perfil sklearn se conserva para benchmark, compatibilidad y regresión.

Más detalle: [`docs/Train_Inference.md`](docs/Train_Inference.md).

## Airflow

El proyecto mantiene cuatro DAGs con responsabilidades separadas:

| DAG | Propósito |
|---|---|
| `reproducibilidad_poc_1_8_2` | reconstruir evidencia del PoC |
| `entrenamiento_candidato_1_8_2` | entrenar candidate Spark sin promoverlo |
| `inferencia_modelos_1_8_2` | puntuar con champion Spark sin reentrenar |
| `monitoreo_reentrenamiento_1_8_2` | controles de monitoreo/autoevaluación |

Variables de entorno principales para integración:

```text
PROYECTO_DIR
CGR_PROJECT_PYTHON
CGR_DATA_CONFIG
CGR_TRAIN_CONFIG
CGR_MODEL_REGISTRY
CGR_INFERENCE_OUTPUT_DIR
```

Airflow debe ejecutarse en su entorno propio; las tareas ML usan el Python del proyecto indicado por `CGR_PROJECT_PYTHON`.

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
| `ssrs/` | DDL T-SQL y dos RDL de reporting |
| `reporte/` | Productos 1–7 e Informe Final |

Los rankings o derivados identificables de fuentes reales no deben publicarse en este repositorio público.

## Seguridad y gobernanza

- La configuración rechaza secrets inline como `password`, `token`, `secret`, `api_key` o `connection_string`.
- SQL Server utiliza una referencia `connection_env`; la cadena real vive fuera del YAML.
- `config/cgr.yaml` y archivos locales equivalentes están excluidos de Git.
- El conector SQL Server proyecta identificadores configurados y no acepta SQL libre desde el YAML.
- Para consultas institucionales complejas se recomienda exponer **vistas aprobadas** y mapearlas al contrato canónico.
- Los datos reales, PII, candidates y salidas operacionales deben permanecer en almacenamiento/repositorios institucionales con controles de acceso.
- La promoción de modelos no es automática.
- Toda señal requiere revisión humana y contexto jurídico/técnico antes de cualquier actuación de control.

## Calidad, pruebas y CI

GitHub Actions ejecuta una cadena end-to-end que incluye:

- pruebas de regresión;
- generación sintética;
- análisis de pagos/modalidades;
- benchmark sklearn;
- Spark MLlib y GraphFrames;
- TRAIN candidate aislado;
- promoción técnica controlada para el smoke;
- INFERENCE sin labels/reentrenamiento;
- Oro, linaje, diccionario y manifiesto;
- generación y QA de los ocho DOCX;
- auditoría del Anexo 3;
- auditoría integral del TDR.

Los resultados de auditoría se materializan en `outputs/` y `docs/` y no equivalen a conformidad institucional.

## Documentación

| Documento | Uso |
|---|---|
| [`docs/Manual_Aterrizaje_Institucional_CGR.md`](docs/Manual_Aterrizaje_Institucional_CGR.md) | guía principal para adaptar el repo a infraestructura CGR |
| [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md) | contrato canónico, conectores y mappings |
| [`docs/Train_Inference.md`](docs/Train_Inference.md) | lifecycle de modelos y serving |
| [`docs/Dependencias_Institucionales_CGR.md`](docs/Dependencias_Institucionales_CGR.md) | pendientes que solo puede cerrar la institución |
| [`docs/Checklist_Anexo_03.md`](docs/Checklist_Anexo_03.md) | auditoría de los 11 criterios del Anexo 3 |
| [`docs/Auditoria_TDR_Completo.md`](docs/Auditoria_TDR_Completo.md) | lectura integral del TDR público |
| [`docs/Auditoria_Final_Release.md`](docs/Auditoria_Final_Release.md) | gate técnico del release candidate |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | alcance del snapshot release candidate |

La documentación contractual generada está en `reporte/productos_formales/` y `reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx`.

## Estructura del repositorio

```text
config/                    configuración de integración y perfiles locales
src/                       pipeline Python, conectores, validación, modelos y MLOps
src/connectors/            local_csv, SQL Server y Spark SQL
src/core/                  esquema canónico y validación de configuración
src/spark/                 MLlib, serving, GraphFrames y utilidades Spark
airflow_home/dags/         reproducibilidad, TRAIN, INFERENCE y monitoreo
lakehouse/                 capas Bronce / Plata / Oro del PoC
ssrs/                      DDL T-SQL + RDL
reporte/                   generación y documentos formales
docs/                      manuales, auditorías y dependencias
outputs/                   evidencia reproducible y registry
tests/                     regresiones y contratos automatizados
.github/workflows/         CI, auditorías y release gates
```

## Límites del PoC

El repositorio no puede sustituir ni simular como completadas las siguientes responsabilidades institucionales:

- accesos y diccionarios reales SIAF/SEACE/Datamart;
- ground truth validado por auditores;
- umbrales productivos de aceptación;
- HDFS/YARN/clúster Spark y ambientes DEV/QA/PROD CGR;
- identidad, secretos, Git y segregación de funciones institucional;
- despliegue real SQL Server/SSRS;
- certificación, marcha blanca e incidencias reales;
- transferencia y entrega contractual.

Estas dependencias se mantienen de forma canónica en [`docs/Dependencias_Institucionales_CGR.md`](docs/Dependencias_Institucionales_CGR.md).

## Licencia

El código del repositorio se distribuye bajo licencia [MIT](LICENSE). Los datos públicos externos mantienen sus condiciones/licencias de origen. Una eventual implantación contractual debe revisar propiedad intelectual, confidencialidad, activos previos y obligaciones de entrega conforme al marco institucional aplicable.
