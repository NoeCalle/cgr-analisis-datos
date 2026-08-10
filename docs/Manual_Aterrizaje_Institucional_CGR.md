# Manual de Aterrizaje Institucional — Módulo de Análisis de Datos

> **Documento técnico para una eventual integración en CGR.** El repositorio de origen es un PoC público e independiente basado en un TDR público. Este manual no acredita aprobación, acceso, despliegue ni conformidad institucional.

## 1. Objetivo

Este manual describe cómo pasar de la versión pública reproducible a una instalación controlada dentro de infraestructura institucional, procurando que la adaptación se concentre en **fuentes, mappings, secretos, ambientes y gobierno**, sin reescribir los modelos por cambios de nombres físicos de tablas o columnas.

El resultado esperado es:

```text
fuentes CGR aprobadas
      |
connector + mapping
      |
esquema canónico validado
      |
+-----+-------------------+
|                         |
TRAIN histórico           INFERENCE actual
|                         |
candidate Spark           champion Spark
|                         |
aprobación institucional  scores de priorización
|                         |
+-------------> registry--+
              |
       SQL Server / SSRS
```

Cuando la fuente institucional se expone como `spark_sql`, la ruta puede mantenerse Spark-native desde la tabla/vista hasta MLlib y la salida Parquet distribuida.

## 2. Qué debe proporcionar la CGR

Antes de ejecutar el software con información institucional se necesitan los elementos asociados a `CGR-DEP-01..08`.

| Frente | Insumo/decisión necesaria |
|---|---|
| Fuentes | tablas/vistas aprobadas, diccionario, linaje y permisos de lectura |
| Ground truth | histórico etiquetado para favoritismo/fraccionamiento y criterio de validación |
| Infraestructura | DEV/QA/PROD, Spark, almacenamiento y orquestación aprobados |
| Seguridad | identidad, roles, secretos, repositorio privado y segregación de funciones |
| MLOps | autoridad que aprueba/promueve modelos y registry institucional |
| Reporting | SQL Server/SSRS, datasource, permisos y ruta de publicación |
| Aceptación | umbrales de métricas, casos de prueba y responsables |
| Operación | responsables de monitoreo, incidentes, rollback y mantenimiento normativo |

Sin esos elementos el repositorio puede demostrar el software, pero no declarar integración o certificación institucional.

## 3. Roles recomendados

- **Administrador de plataforma:** repositorio, runtimes, Spark/Airflow, almacenamiento y despliegue.
- **Owner de datos:** vistas, diccionario, calidad, permisos y linaje.
- **Equipo analítico/científico de datos:** features, métricas, candidate y drift.
- **Especialista funcional/auditor:** ground truth, interpretación de señales y aceptación funcional.
- **Seguridad:** secretos, cuentas de servicio, privilegio mínimo y datos sensibles.
- **Aprobador de modelo:** autoridad separada del proceso automático de TRAIN.
- **Administrador SQL Server/SSRS:** DDL, datasource, RDL y permisos.

## 4. Fase 0 — Congelar el punto de partida

Antes de introducir datos o secretos reales:

1. clonar el repositorio público;
2. migrarlo a un repositorio privado institucional;
3. registrar el commit de origen;
4. proteger ramas/checks conforme a la política CGR;
5. ejecutar CI sin datos internos;
6. impedir que outputs reales puedan volver al remoto público.

`v1.0.0-rc.1` es un snapshot histórico. Para integración debe usarse una revisión aprobada de `main` que incluya la capa institution-ready y la ruta Spark-native vigente.

Baseline mínimo:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

Requisitos adicionales según uso:

- Java 17 para Spark;
- `pyodbc` + driver ODBC aprobado para SQL Server;
- Graphviz para artefactos gráficos;
- Airflow en runtime separado si se usarán DAGs;
- LibreOffice solo para regeneración/QA documental.

**Gate 0:** el repositorio debe pasar pruebas sin conectarse a datos internos.

## 5. Fase 1 — Diseñar las fuentes

### 5.1 Dominios canónicos

| Dominio | Propósito |
|---|---|
| `contracts` | contratos y atributos necesarios para scoring |
| `suppliers` | dimensión de proveedores |
| `entities` | dimensión de entidades |
| `officials` | vínculos de funcionarios cuando exista base legal y permiso |
| `payments` | pagos/devengados/girados vinculados a contrato |

`contracts` es el mínimo para serving. Los demás dominios se habilitan según el caso de uso.

### 5.2 Campos obligatorios de `contracts`

INFERENCE requiere:

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

Las claves estructurales y `fecha_contrato` no pueden llegar nulas. `monto`, `modalidad`, `objeto` y `categoria_principal` pueden contener nulos porque existe tratamiento/fallback explícito.

`categoria_principal` debe existir para resolver el contexto normativo del análisis de fraccionamiento.

TRAIN añade:

```text
label_favoritismo
label_fraccionamiento
```

Los labels deben provenir de ground truth institucional aprobado y no de los scores del propio modelo.

### 5.3 Pagos

`payments` admite:

```text
id_pago
id_contrato
fecha_devengado
fecha_girado
fecha_pagado
monto_devengado
monto_pagado
estado
```

### 5.4 Vistas recomendadas

El conector SQL Server no recibe SQL libre desde YAML. Para joins, filtros, vigencias o consolidaciones SIAF/SEACE, se recomienda publicar **vistas estables y aprobadas** por dominio.

**Gate 1:** cada campo canónico debe tener fuente, definición, owner y regla de calidad.

## 6. Fase 2 — Configurar la integración

Copiar la plantilla a una configuración privada:

```bash
cp config/cgr.example.yaml config/cgr.yaml
```

La dirección del mapping es:

```yaml
campo_canonico: COLUMNA_FISICA
```

Ejemplo:

```yaml
mode: inference

source:
  type: sqlserver
  connection_env: CGR_SOURCE_DATABASE_URL
  tables:
    contracts: dbo.VW_CONTRATOS_MODULO
    payments: dbo.VW_PAGOS_MODULO

mapping:
  contracts:
    id_contrato: ID_CONTRATO_FUENTE
    id_proveedor: ID_PROVEEDOR_FUENTE
    id_entidad: ID_ENTIDAD_FUENTE
    monto: MONTO_CONTRATO_FUENTE
    fecha_contrato: FECHA_CONTRATO_FUENTE
    modalidad: MODALIDAD_FUENTE
    objeto: OBJETO_CONTRATO_FUENTE
    categoria_principal: CATEGORIA_PRINCIPAL_FUENTE
```

Los nombres son placeholders, no objetos reales de CGR.

## 7. Fase 3 — Secretos, conectividad y Spark

### 7.1 SQL Server

El YAML solo referencia una variable:

```yaml
connection_env: CGR_SOURCE_DATABASE_URL
```

La cadena real se inyecta mediante el gestor de secretos/entorno aprobado. No guardar passwords, tokens ni connection strings en YAML o Git.

### 7.2 Spark operacional

TRAIN e INFERENCE aceptan:

```bash
export CGR_SPARK_MASTER='<master Spark aprobado>'
export CGR_SPARK_SHUFFLE_PARTITIONS='<particiones aprobadas>'  # opcional
```

Sin `CGR_SPARK_MASTER`, el PoC usa `local[*]` como fallback local. La reconstrucción histórica mantiene `local[*]` deliberadamente. TRAIN/INFERENCE registran el master efectivo.

La institución debe definir memoria, cores, dynamic allocation, catálogo, autenticación y demás propiedades en su plataforma.

### 7.3 `spark_sql`: ruta distribuida vigente

Para `source.type: spark_sql`, el flujo ya es:

```text
SparkSession.table(...)
      -> Spark DataFrame
      -> mapping canónico Spark
      -> validación/casteo Spark
      -> FIT/TRANSFORM Spark
      -> feature engineering Spark
      -> MLlib
      -> Parquet distribuido
```

No existe `toPandas()` en esta ruta. La integración pandas rechaza `spark_sql` explícitamente para evitar un collect implícito.

Durante TRAIN, las medianas por objeto se calculan en Spark y se persisten como Parquet. INFERENCE las carga nuevamente como DataFrame Spark.

Esto elimina el cuello de botella pandas que existía en una versión anterior del adaptador, pero **no demuestra por sí solo capacidad productiva en el clúster CGR**. Deben probarse particionamiento, tiempos, memoria, skew, concurrencia y volumen real.

**Gate 2:** identidad de mínimo privilegio, master aprobado y prueba de que la ruta elegida soporta el volumen objetivo.

## 8. Fase 4 — Validar antes de leer datos

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --validate-only
```

Comprueba estructura YAML, tipo de fuente, modo, dominios, campos canónicos, obligatorios, mappings duplicados, correspondencia mapping↔fuente y ausencia de secrets inline.

**Gate 3:** `--validate-only` debe terminar correctamente.

## 9. Fase 5 — Lectura controlada en DEV

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --output-dir /ruta/segura/integracion_preview
```

Verificar:

- IDs preservados como texto;
- fechas convertibles;
- montos numéricos;
- nulos estructurales = 0;
- cardinalidades razonables;
- relaciones con proveedores/entidades/pagos;
- ausencia de columnas no autorizadas.

Para `spark_sql`, confirmar además que el manifest reporte `native_engine=spark` y que el preview se escriba de forma distribuida sin colectar filas.

**Gate 4:** owner de datos + equipo analítico aprueban el contrato canónico de DEV.

## 10. Fase 6 — Configuración de TRAIN

Crear `config/cgr-training.yaml` con:

```yaml
mode: training
```

y mapear los labels aprobados.

Antes de entrenar, documentar definición de etiquetas, periodo, responsable, inclusión/exclusión, desbalance, casos inciertos, partición temporal/holdout y métricas de aceptación.

## 11. Fase 7 — Entrenar candidate Spark

```bash
.venv/bin/python src/spark/entrenar_candidato_spark.py \
  --config config/cgr-training.yaml
```

TRAIN produce un **candidate**, no modifica el champion.

Antes de promover revisar:

- manifest y `candidate_id`;
- commit;
- hashes;
- preprocesador y medianas Parquet si aplica;
- configuración/hyperparámetros;
- métricas;
- `spark_mode`;
- `input_engine`;
- `spark_native_ingestion`;
- `pandas_materialization`;
- estabilidad por periodo/segmento;
- capacidad de revisión humana.

Si la fuente es `spark_sql`, se espera:

```text
input_engine = spark_native
spark_native_ingestion = true
pandas_materialization = false
```

**Gate 5:** entrenar no implica aprobar.

## 12. Fase 8 — Promoción y gobierno

El PoC ofrece una promoción técnica explícita:

```bash
.venv/bin/python src/promover_candidato_spark.py \
  --manifest outputs/runtime/spark_model_candidates/candidate_manifest.json \
  --approved-by "responsable autorizado" \
  --acknowledge-poc-only
```

No equivale a aprobación CGR. En QA/PROD debe integrarse al workflow y segregación institucional, idealmente con registry corporativo, auditoría y rollback.

## 13. Fase 9 — INFERENCE institucional

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/cgr.yaml \
  --registry outputs/model_registry.json \
  --output-dir /ruta/segura/inference
```

El scorer:

1. integra contratos al esquema canónico;
2. carga registry/champion;
3. verifica SHA-256;
4. carga preprocesamiento congelado;
5. carga medianas Parquet si el champion las usa;
6. aplica TRANSFORM sin FIT;
7. genera features Spark;
8. carga modelos MLlib;
9. produce rankings;
10. verifica nuevamente los hashes.

La ruta no debe recibir labels ni ejecutar tuning/training.

Para `spark_sql`, verificar:

```text
input_engine = spark_native
spark_native_ingestion = true
pandas_materialization = false
detail_outputs.format = parquet_distributed
```

**Gate 6:** además confirmar que `spark_mode` es el aprobado y que los tiempos/recursos cumplen lo acordado.

## 14. Fase 10 — Pagos y modalidades

```bash
.venv/bin/python src/analisis_pagos_modalidades.py \
  --config config/cgr.yaml
```

Produce resumen por contrato, devengados/pagados, ratio de pago, estados analíticos, demoras, modalidades por régimen y clasificación referencial frente a cuantía.

La clasificación normativa **no declara ilegalidad** ni reemplaza revisión jurídica/funcional.

## 15. Fase 11 — Airflow

DAGs relevantes:

```text
reproducibilidad_poc_1_8_2
entrenamiento_candidato_1_8_2
inferencia_modelos_1_8_2
monitoreo_reentrenamiento_1_8_2
```

Variables relevantes:

```text
PROYECTO_DIR
CGR_PROJECT_PYTHON
CGR_DATA_CONFIG
CGR_TRAIN_CONFIG
CGR_MODEL_REGISTRY
CGR_INFERENCE_OUTPUT_DIR
CGR_SPARK_CANDIDATE_MANIFEST
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
```

No almacenar secretos en variables de Airflow visibles para usuarios no autorizados.

## 16. Fase 12 — SQL Server y SSRS

El repositorio incluye:

```text
ssrs/schema_sql_server.sql
ssrs/ReporteRiesgoFavoritismo.rdl
ssrs/ReporteRiesgoFraccionamiento.rdl
```

`src/publicar_ssrs.py` valida localmente el contrato, pero no despliega en un servidor CGR.

Para cierre institucional: revisar DDL, crear objetos DEV, definir datasource, cargar salidas aprobadas, desplegar RDL, validar permisos/tiempos y promover vía QA/PROD.

**Gate 7:** RDL en Git no equivale a publicación SSRS.

## 17. Fase 13 — Monitoreo y reentrenamiento

El proyecto incluye autoevaluación/monitor de solo lectura y un DAG mensual de referencia. En operación deben definirse frecuencia, features vigiladas, drift, ground truth, métricas mínimas, responsables, condiciones de TRAIN, rollback y retención.

Reentrenamiento produce candidate. **No debe existir autopromoción silenciosa.**

## 18. Fase 14 — Seguridad

Checklist mínimo:

- repositorio privado;
- cuentas separadas por ambiente;
- privilegio mínimo;
- secretos fuera del repo;
- outputs en almacenamiento autorizado;
- PII restringida;
- cifrado según política;
- logs sin secretos/payloads innecesarios;
- retención/purga definidas;
- auditoría de promociones;
- segregación TRAIN/promoción/PROD;
- revisión de dependencias/vulnerabilidades;
- backups y rollback.

Las políticas internas CGR prevalecen sobre cualquier ejemplo de este manual.

## 19. Fase 15 — DEV → QA → PROD

### DEV

- mappings y vistas;
- conectividad y calidad;
- TRAIN inicial;
- pruebas unitarias/integración;
- validación Spark-native si se usa `spark_sql`;
- pruebas de particionamiento, skew y volumen;
- performance preliminar;
- reporting.

### QA

- datos representativos aprobados;
- métricas contra umbrales institucionales;
- volumen representativo;
- permisos;
- Airflow/Spark/SQL Server/SSRS;
- validación funcional;
- error/rollback;
- documentación de incidencias.

### PROD

Solo después de conformidad QA:

- champion aprobado;
- secretos/configuración PROD;
- master/recursos Spark aprobados;
- particionamiento/capacidad probados;
- datasource/reportes PROD;
- monitoreo activo;
- responsables de soporte;
- rollback probado.

## 20. Rollback

Antes de cada promoción registrar:

- champion anterior;
- registry anterior;
- hashes;
- commit/tag;
- preprocesador y medianas asociadas;
- fecha/aprobador;
- motivo.

Ante degradación: detener si corresponde, restaurar champion estable, verificar hashes, ejecutar smoke, documentar incidente y reanudar solo con autorización.

## 21. Criterios de aceptación del aterrizaje

Una instalación puede considerarse técnicamente aterrizada cuando existe evidencia de que:

- la configuración real pasa `--validate-only`;
- las fuentes reales se convierten al esquema canónico;
- `spark_sql`, si se usa, permanece Spark-native sin pandas intermedio;
- la ruta soporta el volumen objetivo en el clúster real;
- diccionario/linaje están aprobados;
- TRAIN usa ground truth validado;
- candidate/champion están gobernados;
- INFERENCE opera sin labels/training/tuning;
- el master coincide con la configuración aprobada;
- performance y robustez cumplen lo acordado;
- SQL Server/SSRS funcionan con permisos institucionales;
- DEV/QA/PROD están separados;
- seguridad/secretos están validados;
- monitoreo/rollback están operativos;
- usuarios completaron certificación/marcha blanca;
- transferencia y entrega están formalizadas.

Hasta entonces los estados 🟡/🔵 deben permanecer abiertos.

## 22. Mapeo de dependencias CGR

| ID | Cierre institucional |
|---|---|
| `CGR-DEP-01` | vistas/tablas, permisos, diccionario y linaje reales |
| `CGR-DEP-02` | estándares SQL + planes de ejecución |
| `CGR-DEP-03` | ground truth y umbrales aprobados |
| `CGR-DEP-04` | repo privado, identidad, secretos y autorizaciones |
| `CGR-DEP-05` | DDL/RDL desplegados y validados |
| `CGR-DEP-06` | DEV/QA/PROD/clúster, carga, performance y operación |
| `CGR-DEP-07` | certificación, incidencias y marcha blanca |
| `CGR-DEP-08` | transferencia y entrega formal |

Fuente canónica: [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md).

## 23. Troubleshooting rápido

### Falta `CGR_SOURCE_DATABASE_URL`

Revisar gestor de secretos/entorno del runner.

### `pyodbc` o driver ODBC no disponible

Instalar el driver aprobado en la imagen/host institucional.

### `mapping.contracts no define campos obligatorios`

Revisar `src/core/schemas.py`; `categoria_principal` también es estructuralmente requerida.

### Columna física inexistente

El mapping no coincide con la vista/tabla o el usuario no ve la versión esperada.

### Nulos en claves o `fecha_contrato`

Es una falla estructural de calidad; no se imputa automáticamente.

### TRAIN pide labels pero INFERENCE no

Es intencional. Mantener configs separadas.

### Candidate no aparece como champion

Es intencional. La promoción es un gate separado.

### Spark usa `local[*]`

Definir `CGR_SPARK_MASTER` y comprobar `spark_mode`.

### `spark_sql` aparece con `pandas_materialization=true`

No es el comportamiento esperado de la ruta actual. Revisar que se esté usando `source.type: spark_sql`, `integrar_spark()` y una versión vigente del código. La regresión `tests/test_spark_native_integration.py` debe pasar.

### Rendimiento insuficiente en `spark_sql`

La ruta ya es distribuida; revisar particionamiento de las tablas, skew, shuffle partitions, tamaño de executors, dynamic allocation, catálogo y estrategia de escritura. Ajustar en DEV/QA y medir con volumen representativo antes de PROD.

## 24. Documentos relacionados

- [`Integracion_Datos.md`](Integracion_Datos.md) — conectores, esquema canónico y Spark-native.
- [`Train_Inference.md`](Train_Inference.md) — lifecycle y serving.
- [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md) — dependencias institucionales.
- [`Checklist_Anexo_03.md`](Checklist_Anexo_03.md) — Anexo 3.
- [`Auditoria_TDR_Completo.md`](Auditoria_TDR_Completo.md) — auditoría integral.
- `../config/cgr.example.yaml` — plantilla sin secretos reales.

## 25. Regla final

El objetivo del aterrizaje no es hacer que el PoC “parezca productivo”. Es **sustituir de forma controlada los stand-ins públicos por fuentes, infraestructura, gobierno y evidencias institucionales reales**, preservando trazabilidad y revisión humana.
