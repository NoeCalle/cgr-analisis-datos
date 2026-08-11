# Hardening MLOps — Etapa 3B

## Arquitectura conceptual congelada

La Etapa 3B **no cambia la arquitectura funcional ni la arquitectura ML** del PoC. El contrato vigente continúa siendo:

```text
fuente configurada
      |
esquema canónico
      |
      +--> TRAIN --> candidate --> evaluación/gate --> promoción explícita --> champion
      |                                                               |
      +----------------------------------------------------------> INFERENCE
                                                                      |
                                                                   rankings
                                                                      |
                                                                 monitoreo
                                                                      |
                                                          candidate si corresponde
```

Decisiones que permanecen invariantes:

- `spark_mllib` es el perfil de serving objetivo del PoC;
- sklearn se conserva como benchmark/perfil de compatibilidad;
- TRAIN e INFERENCE siguen separados;
- INFERENCE no consume labels, no hace FIT y no retunea;
- TRAIN genera candidate y no debe habilitar serving por sí mismo;
- la promoción es una operación explícita y no equivale a aprobación CGR;
- un candidate generado por drift tampoco se promueve automáticamente.

Una auditoría posterior puede descubrir defectos, pero un rediseño conceptual debe tratarse como una decisión arquitectónica separada, no como una corrección silenciosa.

## Correcciones puntuales de 3B

### 1. CI no cambia el champion persistido

GitHub Actions puede ejercitar técnicamente una promoción para el smoke test, pero esa promoción es efímera. Antes de persistir evidencia, `src/ci_validar_pipeline.py` restaura el registry y los champions versionados en el commit y regenera inference/monitor/trazabilidad contra ese estado.

Por tanto, un push exitoso no convierte el candidate de CI en el champion persistido de `main`.

### 2. Promoción versionada y rollback

Las nuevas promociones se materializan en:

```text
outputs/champion_store/<profile>/<candidate_id>/...
```

El conjunto completo se copia primero a staging, se verifican los SHA-256 y recién después se publica el directorio inmutable. El registry cambia su puntero solo después de esa verificación.

El champion anterior se conserva en `history` y `src/rollback_champion.py` permite un rollback explícito hacia un champion histórico cuyos artefactos sigan verificando sus hashes.

Los champions legacy existentes en `outputs/champions/` y `outputs/champions_spark/` siguen siendo legibles; no se fuerza una migración destructiva.

### 3. Candidate ligado a evidencia del mismo corpus

Las evaluaciones operacionales Spark registran `training_data_fingerprint_sha256` del corpus canónico. TRAIN exige que las evidencias de favoritismo y fraccionamiento correspondan al mismo fingerprint y registra también el SHA-256 de cada resumen de validación dentro del manifest.

En el benchmark público/local, un candidate que consume esa evidencia queda con:

```text
validation_state = evaluated_same_corpus
```

Para una fuente institucional distinta —incluida una eventual fuente `spark_sql`— no se permite reutilizar silenciosamente las métricas del benchmark público. La evaluación/ground truth correspondiente debe ejecutarse en el entorno institucional y quedar ligada al fingerprint de ese corpus antes de la promoción.

Un candidate creado a raíz de drift hereda temporalmente los parámetros del champion y queda con:

```text
validation_state = pending_candidate_evaluation
```

El registry bloquea la promoción de un candidate schema 2 mientras siga pendiente de evaluación.

### 4. Publicación de INFERENCE después del gate de integridad

INFERENCE genera primero los rankings en un directorio de staging. El champion se verifica nuevamente antes de publicar. Solo después de superar ese gate el staging reemplaza el directorio final mediante un cambio controlado con backup/rollback local.

Un fallo de integridad ya no deja como salida final un ranking que la propia ejecución considera inválido.

### 5. Monitoreo ligado al champion y a ambos modelos

`src/autoevaluacion_champion.py` comprueba que el baseline configurado tenga el mismo fingerprint que el corpus registrado en el champion activo.

El monitor vigila:

- favoritismo: drift de features y `recall@K` cuando existen labels;
- fraccionamiento: drift de sus features, distribución de `score_anomalia` y `recall@K` cuando existen labels.

Si un lote no contiene labels, el drift puede seguir medido pero la generación automática de un candidate queda bloqueada.

`src/monitoreo_modelos.py` consume por defecto `outputs/log_reentrenamiento_champion.csv`, no el log sklearn histórico.

El monitor batch del PoC no colecta una fuente `spark_sql` al driver. Un monitor distribuido contra la fuente Spark institucional debe ejecutarse en la plataforma CGR; 3B no finge esa infraestructura.

### 6. Airflow: ejecuciones aisladas y monitor externo

TRAIN, INFERENCE y monitoreo usan `max_active_runs=1` y rutas aisladas por `{{ ts_nodash }}`.

Variables nuevas/principales:

```text
CGR_SPARK_CANDIDATE_BASE
CGR_INFERENCE_OUTPUT_BASE
CGR_MONITOR_CONFIG
CGR_MONITOR_BATCH_PATH
CGR_MONITOR_BATCH_NAME
CGR_MONITOR_OUTPUT_BASE
CGR_MONITOR_SCHEDULE
```

El DAG de monitoreo **no genera lotes sintéticos**. `CGR_MONITOR_BATCH_PATH` debe señalar el lote externo a revisar. Si `CGR_MONITOR_SCHEDULE` no está definido, el DAG no se agenda automáticamente.

La generación de `data/lote_nuevo_normal.csv` y `data/lote_nuevo_con_drift.csv` se conserva únicamente como evidencia reproducible/smoke del PoC.

### 7. Runtime Airflow reproducible

Airflow se mantiene separado del entorno ML. `requirements-airflow.txt` fija el runtime utilizado para validar DAGs y `.github/workflows/airflow-dags.yml` lo instala con las constraints oficiales de esa versión antes de cargar `airflow_home/dags/` mediante `DagBag`.

## Límites que siguen siendo institucionales

3B no inventa controles que requieren una plataforma real. Siguen pendientes de definición/ejecución CGR:

- identidad y segregación de funciones institucional;
- branch protection/review policy del repositorio institucional;
- registry/model store corporativo;
- almacenamiento distribuido y permisos;
- DEV/QA/PROD;
- alertamiento, telemetría y SLAs;
- ground truth y umbrales de aceptación reales;
- prueba de carga, concurrencia, skew y capacidad en el clúster;
- procedimiento formal de aprobación/promoción/rollback;
- operación SSRS/SQL Server, certificación y marcha blanca.

Estas dependencias no deben declararse resueltas por el PoC público.
