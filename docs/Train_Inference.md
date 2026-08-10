# TRAIN / INFERENCE — ciclo operacional de modelos

Este documento describe el ciclo operacional vigente del PoC público independiente.

> Nada de lo aquí descrito constituye aprobación, despliegue ni arquitectura oficial de la Contraloría General de la República. El objetivo es dejar un contrato técnico preparado para una futura integración institucional.

## Objetivo

Una ejecución destinada a puntuar contratos actuales no debe poder:

- requerir ground truth;
- recalcular estadísticas de preprocesamiento;
- ejecutar tuning;
- reentrenar modelos;
- sobrescribir el modelo servido.

El contrato es:

```text
TRAIN Spark -> candidate Spark -> promoción explícita -> champion Spark
                                                  |
                                                  +-> INFERENCE Spark
                                                      sin labels / fit / tuning
```

`scikit-learn` se conserva como benchmark metodológico y perfil de compatibilidad. El perfil operacional activo del PoC es `spark_mllib`.

La promoción técnica del PoC **no equivale a aprobación institucional CGR**. El registry público persiste `institutional_approval=false`.

## 1. Dos rutas que no deben confundirse

### Reproducibilidad histórica

`reproducibilidad_poc_1_8_2` reconstruye la evidencia histórica del PoC. Incluye Plata legacy, benchmarks sklearn, Spark MLlib y GraphFrames. Puede entrenar porque su función es reconstruir evidencia y conserva `local[*]` deliberadamente.

### Serving operacional

TRAIN e INFERENCE usan la integración canónica y el preprocesamiento corregido. No consumen la Plata legacy como fuente de serving.

Para `source.type: spark_sql`, la ruta operacional mantiene un DataFrame Spark desde la tabla/vista hasta MLlib y la salida distribuida. Para `local_csv` y `sqlserver`, se conserva un adaptador pandas→Spark por compatibilidad.

La separación evita *train-serving skew* y evita confundir benchmark histórico con serving.

## 2. Preprocesamiento: FIT solo en TRAIN

Existen dos implementaciones equivalentes según la frontera de datos.

### Fuentes pandas (`local_csv` / `sqlserver`)

`src/preprocesamiento.py` mantiene:

- `ajustar_estado_preprocesamiento(...)`: aprende estadísticas;
- `aplicar_estado_preprocesamiento(...)`: aplica estadísticas ya aprendidas;
- `preparar_para_features_entrenamiento(...)`: FIT + TRANSFORM;
- `preparar_para_features_inferencia(...)`: TRANSFORM.

### Fuente Spark (`spark_sql`)

`src/spark/ajustar_preprocesamiento_spark.py` aprende las mismas categorías de estado de forma distribuida:

- mediana de monto por objeto;
- mediana global;
- moda de modalidad;
- moda de objeto;
- P99 de monto;
- versión del esquema.

Las medianas por objeto no se colectan al driver en la ruta operacional. Se persisten como un **directorio Parquet Spark** y el JSON del preprocesador marca `monto_mediana_por_objeto_external=true`.

`src/spark/preprocesamiento_serving_spark.py` aplica el JSON y, cuando corresponde, el DataFrame de medianas externo. No contiene `.fit()`.

### Corrección legacy preservada

El pipeline histórico podía sustituir un monto válido cuando `objeto` era nulo debido a la semántica de `groupby(...).transform(...)`. Esa conducta se conserva únicamente en la reconstrucción legacy para reproducir el RC histórico.

TRAIN/INFERENCE modernos siempre preservan un monto observado válido.

## 3. TRAIN Spark operacional

Ejecución local de demostración:

```bash
python src/spark/entrenar_candidato_spark.py \
  --config config/local-training.yaml
```

TRAIN requiere:

- `label_favoritismo`;
- `label_fraccionamiento`.

Flujo conceptual:

```text
fuente histórica con labels
    -> integración canónica
    -> FIT estado de preprocesamiento
    -> TRANSFORM Spark
    -> features Spark
    -> RandomForestClassifier MLlib
    -> StandardScalerModel + KMeansModel MLlib
    -> candidate Spark
```

### TRAIN con `spark_sql`

```text
Spark table/view
    -> integrar_spark()
    -> schema Spark canónico
    -> FIT distribuido
    -> medianas por objeto Parquet
    -> features Spark
    -> MLlib
    -> candidate
```

No existe `toPandas()` en esta ruta.

El manifest del candidate registra:

```text
source_type
input_engine
spark_native_ingestion
pandas_materialization
spark_mode
training_data_fingerprint_sha256
```

Para `spark_sql` se espera:

```text
input_engine = spark_native
spark_native_ingestion = true
pandas_materialization = false
```

Los artefactos candidate quedan bajo `outputs/runtime/spark_model_candidates/`, ignorado por Git. TRAIN no modifica el champion ni el registry activo.

## 4. Master Spark operacional

TRAIN e INFERENCE usan una sesión operacional configurable mediante:

```text
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
```

Si `CGR_SPARK_MASTER` no existe, el PoC usa `local[*]` como fallback local. La corrida registra `spark.sparkContext.master`.

Memoria, cores, dynamic allocation, catálogo, autenticación y otras propiedades deben configurarse conforme a la plataforma institucional.

## 5. Registry unificado

`outputs/model_registry.json` usa `schema_version: 2` y admite perfiles:

```text
serving_profiles
├── sklearn
└── spark_mllib   <- active_serving_profile
```

El perfil `spark_mllib` conserva:

- `RandomForestClassificationModel`;
- `KMeansModel`;
- `StandardScalerModel`;
- estado de preprocesamiento JSON;
- opcionalmente `preprocessor_medians` como Parquet Spark para candidates entrenados desde `spark_sql`.

Los modelos Spark son directorios MLlib. `src/registro_modelos.py` calcula huellas SHA-256 de los artefactos. La promoción copia y registra también el artefacto de medianas cuando existe.

El loader conserva compatibilidad con el registry schema 1 histórico del perfil sklearn.

## 6. Candidate no es Champion

TRAIN solo produce `status: candidate`. La promoción Spark se ejecuta por separado:

```bash
python src/promover_candidato_spark.py \
  --manifest outputs/runtime/spark_model_candidates/candidate_manifest.json \
  --approved-by "operador técnico del PoC" \
  --acknowledge-poc-only
```

Sin `--acknowledge-poc-only` la promoción técnica del PoC se bloquea.

En una implantación institucional este paso debe quedar detrás del workflow, aprobación, segregación de funciones y registry/MLOps que defina la CGR.

## 7. INFERENCE Spark MLlib

Ejecución local:

```bash
python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

Flujo:

```text
contratos actuales SIN labels
    -> integración canónica
    -> carga registry/champion
    -> verificación SHA-256
    -> carga estado congelado
    -> TRANSFORM Spark sin FIT
    -> features Spark
    -> load RandomForestClassificationModel
    -> load StandardScalerModel + KMeansModel
    -> scores de priorización
    -> verificación SHA-256 posterior
```

`score_inference_spark.py` no importa sklearn/joblib, no instancia algoritmos de entrenamiento y no contiene `.fit()`.

### INFERENCE con `spark_sql`

```text
Spark table/view
    -> integrar_spark()
    -> preprocesamiento Spark
    -> features Spark
    -> champion MLlib
    -> ranking Spark
    -> Parquet distribuido
```

No existe conversión a pandas. Si el champion fue entrenado con medianas distribuidas, INFERENCE vuelve a cargarlas con `spark.read.parquet(...)`.

La evidencia de serving registra:

```text
input_engine = spark_native
spark_native_ingestion = true
pandas_materialization = false
detail_outputs.format = parquet_distributed
```

Para fuentes pandas, el scorer utiliza el adapter pandas→Spark y conserva CSV único por compatibilidad local.

## 8. Salidas

Por defecto las salidas operacionales permanecen bajo `outputs/runtime/inference_spark/`.

- `spark_sql`: rankings como **Parquet distribuido**;
- `local_csv` / `sqlserver`: CSV de archivo único de compatibilidad.

Los outputs reales/identificables deben residir únicamente en almacenamiento institucional autorizado.

## 9. Perfil sklearn de compatibilidad

`src/score_inference.py` continúa disponible para regresión y comparación. Carga explícitamente el perfil `sklearn`; no define el serving activo.

Esta ruta permite comprobar que la evolución hacia MLlib no destruyó el contrato probado anteriormente.

## 10. Airflow: responsabilidades separadas

### Reproducibilidad

```text
DAG: reproducibilidad_poc_1_8_2
```

Reconstruye benchmark/evidencia legacy.

### TRAIN

```text
DAG: entrenamiento_candidato_1_8_2
```

Llama `src/spark/entrenar_candidato_spark.py`. Genera candidate; no promueve.

### INFERENCE

```text
DAG: inferencia_modelos_1_8_2
```

Llama `src/spark/score_inference_spark.py`. No genera datos sintéticos, no ejecuta tuning y no entrena.

Las tareas pueden recibir `CGR_SPARK_MASTER`, `CGR_SPARK_SHUFFLE_PARTITIONS`, `CGR_DATA_CONFIG`, `CGR_TRAIN_CONFIG` y el registry.

## 11. Evidencia CI

GitHub Actions valida automáticamente que:

1. las regresiones legacy siguen reconstruyendo el baseline histórico;
2. TRAIN/INFERENCE modernos preservan montos observados válidos;
3. TRAIN no modifica champion;
4. la promoción exige reconocimiento explícito del alcance PoC;
5. INFERENCE no consume labels ni ejecuta training/tuning;
6. los hashes del champion permanecen estables durante scoring;
7. el master operacional es configurable;
8. `spark_sql` devuelve un DataFrame Spark;
9. mapping, casteo y validación `spark_sql` permanecen en Spark;
10. el FIT distribuido persiste medianas por objeto como Parquet;
11. `spark_sql.py`, TRAIN e INFERENCE no contienen `.toPandas()`;
12. la ruta pandas rechaza `spark_sql` para impedir collect implícito;
13. rankings `spark_sql` se escriben como Parquet distribuido;
14. después del serving siguen pasando Spark legacy, GraphFrames, Oro, trazabilidad y documentación formal.

La regresión específica está en `tests/test_spark_native_integration.py`.

## 12. Qué sigue dependiendo de CGR

El contrato de software ya cubre separación TRAIN/INFERENCE, registry, master configurable y una frontera `spark_sql` Spark-native. No puede resolver desde este repositorio:

- autoridad institucional para aprobar/promover modelos;
- registry/MLOps corporativo;
- credenciales, roles y segregación DEV/QA/PROD;
- fuentes históricas y ground truth institucional;
- clúster, catálogo y almacenamiento Spark institucional;
- particionamiento, capacidad, performance y robustez con volumen real;
- criterios numéricos de aceptación productiva no consignados en el TDR público;
- SQL Server/SSRS institucional;
- marcha blanca, certificación y transferencia formal.

La ruta Spark-native elimina la materialización pandas que existía anteriormente, pero **no sustituye una prueba de carga y operación en el clúster real**.
