# TRAIN / INFERENCE — Sprints 2 y 3

Este documento describe la separación operacional incorporada después del release candidate `v1.0.0-rc.1` del PoC público independiente.

> Nada de lo aquí descrito constituye aprobación, despliegue ni arquitectura oficial de la Contraloría General de la República. El objetivo es reducir el trabajo de adaptación futura y dejar explícitas las dependencias institucionales.

## Objetivo

Una ejecución destinada a puntuar contratos actuales no debe poder:

- requerir ground truth;
- recalcular estadísticas de preprocesamiento;
- ejecutar tuning;
- reentrenar modelos;
- sobrescribir el modelo servido.

Desde Sprint 3 el contrato objetivo es:

```text
TRAIN Spark -> candidate Spark -> promoción explícita -> champion Spark
                                                  |
                                                  +-> INFERENCE Spark
                                                      sin labels / fit / tuning
```

`scikit-learn` se conserva como benchmark metodológico y perfil de compatibilidad. El perfil operacional activo del PoC es `spark_mllib`.

La promoción técnica del PoC **no equivale a aprobación institucional CGR**. El registry persiste `institutional_approval=false`.

## 1. Dos rutas que no deben confundirse

### Reproducibilidad histórica

La ruta `reproducibilidad_poc_1_8_2` reconstruye la evidencia congelada del RC1. Incluye la Plata legacy, benchmarks sklearn, Spark MLlib y GraphFrames. Puede entrenar porque su función es reconstruir evidencia.

### Serving operacional

TRAIN e INFERENCE usan la integración canónica de Sprint 1 y el preprocesamiento corregido introducido en Sprint 2. No consumen la Plata legacy como fuente de serving.

Esta separación es deliberada: promover directamente un modelo Spark entrenado sobre la Plata legacy y puntuarlo con el preprocesamiento corregido produciría *train-serving skew*.

## 2. Preprocesamiento: FIT solo en TRAIN

`src/preprocesamiento.py` mantiene:

- `ajustar_estado_preprocesamiento(...)`: aprende estadísticas;
- `aplicar_estado_preprocesamiento(...)`: aplica estadísticas ya aprendidas;
- `preparar_para_features_entrenamiento(...)`: FIT + TRANSFORM sklearn;
- `preparar_para_features_inferencia(...)`: TRANSFORM sklearn.

El estado aprendido contiene:

- mediana de monto por objeto;
- mediana global de monto;
- moda de modalidad;
- moda de objeto;
- P99 de monto;
- versión del esquema.

Sprint 3 lo exporta además como JSON framework-neutral. `src/spark/preprocesamiento_serving_spark.py` aplica ese JSON con expresiones Spark y **no contiene ningún `.fit()`**.

### Corrección legacy preservada sin contaminar serving

Durante Sprint 2 se detectó que el pipeline histórico:

```python
df.groupby("objeto")["monto"].transform(...)
```

podía excluir filas con `objeto` nulo y sustituir posteriormente un `monto` válido por la mediana global. El caso de regresión `C002938` tenía `objeto` nulo y monto observado `117888.71`.

La ruta legacy conserva esa semántica únicamente para reconstruir las métricas históricas de `v1.0.0-rc.1`. TRAIN/INFERENCE nuevos preservan siempre un monto observado válido.

## 3. TRAIN Spark operacional

Configuración de demostración: `config/local-training.yaml`.

TRAIN requiere:

- `label_favoritismo`;
- `label_fraccionamiento`.

Ejecución objetivo:

```bash
python src/spark/entrenar_candidato_spark.py \
  --config config/local-training.yaml
```

Flujo:

```text
fuente histórica con labels
    -> integración canónica
    -> FIT estado de preprocesamiento corregido
    -> JSON congelado
    -> TRANSFORM Spark
    -> features Spark
    -> RandomForestClassifier MLlib
    -> StandardScalerModel + KMeansModel MLlib
    -> candidate Spark
```

Los artefactos candidate quedan bajo `outputs/runtime/spark_model_candidates/`, ignorado por Git. TRAIN no modifica `outputs/model_registry.json` ni `outputs/champions_spark/`; CI compara hashes antes y después para impedir regresiones.

Para favoritismo, el entrenamiento final reutiliza la configuración seleccionada por la evidencia metodológica Spark cuando está disponible (`outputs/spark_favoritismo_resumen.json`), pero **no vuelve a ejecutar tuning dentro de INFERENCE**. Para fraccionamiento se persisten por separado el `StandardScalerModel` y el `KMeansModel`.

## 4. Registry unificado

`outputs/model_registry.json` usa `schema_version: 2` y admite múltiples perfiles:

```text
serving_profiles
├── sklearn
└── spark_mllib   <- active_serving_profile
```

El perfil `sklearn` conserva:

- RandomForestClassifier;
- IsolationForest;
- StandardScaler;
- preprocesador joblib/JSON.

El perfil `spark_mllib` conserva:

- `RandomForestClassificationModel`;
- `KMeansModel`;
- `StandardScalerModel`;
- estado de preprocesamiento JSON.

Los modelos Spark son directorios MLlib. `src/registro_modelos.py` calcula una huella SHA-256 determinística sobre sus archivos y excluye únicamente los `.crc` locales de Hadoop, que no forman parte del artefacto versionado.

El loader sigue aceptando en memoria el registry schema 1 del Sprint 2 y lo migra a un perfil `sklearn`, evitando romper la trazabilidad histórica.

## 5. Candidate no es Champion

TRAIN solo produce `status: candidate`. La promoción Spark se ejecuta por separado:

```bash
python src/promover_candidato_spark.py \
  --manifest outputs/runtime/spark_model_candidates/candidate_manifest.json \
  --approved-by "operador técnico del PoC" \
  --acknowledge-poc-only
```

Sin `--acknowledge-poc-only` la operación se bloquea.

El bootstrap CI utiliza además `--if-missing`: crea el primer champion Spark, pero una nueva corrida TRAIN posterior **no lo reemplaza silenciosamente**. La promoción de una versión nueva debe seguir siendo una acción explícita.

Los artefactos activos quedan en:

```text
outputs/model_registry.json
outputs/champions_spark/preprocesador_contratos.json
outputs/champions_spark/modelo_favoritismo_rf/
outputs/champions_spark/modelo_fraccionamiento_kmeans/
outputs/champions_spark/scaler_fraccionamiento/
```

## 6. INFERENCE Spark MLlib

Configuración local: `config/local.yaml`. No contiene labels.

Ejecución:

```bash
python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

Flujo:

```text
contratos actuales SIN labels
    -> integración canónica
    -> carga registry schema 2
    -> verificación SHA-256 champion Spark
    -> carga estado JSON congelado
    -> TRANSFORM Spark sin FIT
    -> feature engineering Spark sin labels
    -> load RandomForestClassificationModel
    -> load StandardScalerModel + KMeansModel
    -> scores de priorización
    -> segunda verificación SHA-256 champion
```

`src/spark/score_inference_spark.py` no importa sklearn/joblib, no instancia algoritmos de entrenamiento y no contiene `.fit()`.

Las salidas detalladas permanecen bajo `outputs/runtime/inference_spark/`. La evidencia agregada reproducible se conserva en `outputs/inference_spark_smoke_summary.json`.

## 7. Perfil sklearn de compatibilidad

`src/score_inference.py` continúa disponible para regresión y comparación. Carga explícitamente el perfil `sklearn`; ya no define cuál es el serving activo.

Su evidencia queda en `outputs/inference_smoke_summary.json` y permite comprobar que la evolución a MLlib no destruyó el contrato probado en Sprint 2.

## 8. Airflow: responsabilidades separadas

### Reproducibilidad

```text
DAG: reproducibilidad_poc_1_8_2
```

Reconstruye benchmark/evidencia legacy.

### TRAIN operacional

```text
DAG: entrenamiento_candidato_1_8_2
```

Llama `src/spark/entrenar_candidato_spark.py`. Genera candidate; no promueve.

### INFERENCE operacional

```text
DAG: inferencia_modelos_1_8_2
```

Llama `src/spark/score_inference_spark.py`. No genera datos sintéticos, no ejecuta tuning y no entrena.

## 9. Evidencia CI vigente

GitHub Actions valida automáticamente que:

1. las regresiones legacy siguen reconstruyendo RC1;
2. el preprocesamiento nuevo conserva montos válidos aunque `objeto` sea nulo;
3. TRAIN sklearn de compatibilidad no modifica champion;
4. TRAIN Spark operacional no modifica registry/champion;
5. el candidate Spark declara `preprocessing_contract=corrected_frozen_json_v1`;
6. la promoción exige reconocimiento explícito del alcance PoC;
7. `active_serving_profile` termina en `spark_mllib`;
8. INFERENCE Spark consume cero labels y ejecuta cero training/tuning;
9. `sklearn_serving_dependency=false`;
10. los hashes del champion Spark permanecen idénticos durante scoring;
11. para el dataset sintético vigente se producen 2,328 scores de favoritismo y 180 de fraccionamiento a partir de 3,709 contratos;
12. después del serving smoke siguen pasando Spark legacy, GraphFrames, Oro, trazabilidad y los ocho DOCX formales.

El champion Spark vigente del PoC se identifica mediante `champion_id` dentro del registry. El identificador es técnico; no es una aprobación ni versión institucional.

## 10. Qué sigue dependiendo de CGR

La separación TRAIN/INFERENCE y el serving MLlib resuelven el **contrato de software** dentro del PoC. No pueden resolver desde este repositorio:

- autoridad institucional para aprobar/promover modelos;
- registry/MLOps corporativo que defina CGR;
- credenciales, roles y segregación DEV/QA/PROD;
- fuentes históricas y ground truth institucional;
- HDFS/YARN/Lakehouse y clúster Spark institucional;
- políticas de recursos, particionamiento y tuning del clúster real;
- criterios numéricos de aceptación productiva no consignados en el TDR público;
- despliegue SQL Server/SSRS real, marcha blanca, certificación y transferencia formal.

Esas responsabilidades deben integrarse mediante los controles, plataformas y autorizaciones que defina la CGR.
