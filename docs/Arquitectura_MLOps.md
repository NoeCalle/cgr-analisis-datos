# Arquitectura MLOps y ciclo de vida de modelos

## Objetivo

Este documento describe el ciclo operacional vigente del módulo: cómo se evalúan, entrenan, registran, promueven, sirven, monitorizan y revierten los modelos. El diseño separa explícitamente **evaluación**, **TRAIN**, **promoción** e **INFERENCE** para evitar que una ejecución de entrenamiento cambie silenciosamente el modelo servido.

El repositorio es un PoC público e independiente. La arquitectura implementa contratos técnicos reproducibles, pero la autoridad de aprobación, identidad de usuarios, workflow corporativo y plataforma MLOps institucional deben definirse en el entorno CGR.

## 1. Ciclo de vida

```text
fuente histórica con ground truth
          |
          v
      evaluación
   CV / tuning / holdout
          |
          | evidencia ligada al fingerprint del corpus
          v
        TRAIN
          |
          v
       candidate
          |
          | revisión técnica / gate
          v
   promoción explícita
          |
          v
       champion
          |
          +----------> INFERENCE
          |               |
          |               v
          |            rankings
          |               |
          +----------> monitoreo
                          |
                 candidate si corresponde
```

Principios:

- `spark_mllib` es el perfil de serving objetivo;
- sklearn se conserva como benchmark y perfil de compatibilidad;
- TRAIN nunca promueve automáticamente;
- INFERENCE no consume labels, no hace FIT y no ejecuta tuning;
- el monitor puede detectar drift y solicitar/generar candidate, pero no lo promueve;
- la promoción técnica del PoC no equivale a aprobación institucional.

## 2. Evaluación antes de TRAIN

Los evaluadores Spark activos son:

```text
src/spark/evaluar_favoritismo_spark.py
src/spark/evaluar_fraccionamiento_spark.py
```

Ambos producen evidencia que incluye:

- fingerprint SHA-256 del corpus canónico;
- diseño de desarrollo/holdout;
- parámetros seleccionados;
- métricas de validación/holdout;
- características utilizadas;
- engine/fuente de ejecución.

TRAIN exige que las evidencias de favoritismo y fraccionamiento correspondan al **mismo fingerprint** que el corpus con el que se va a entrenar.

### Por qué

Un conjunto de hiperparámetros seleccionado sobre otro dataset puede ser técnicamente válido pero metodológicamente ajeno al candidate que se pretende entrenar. Ligar evidencia y TRAIN al mismo fingerprint evita reutilizar silenciosamente resultados de otro corpus.

Cuando la fuente es `spark_sql`, la evaluación puede mantenerse distribuida: integración, split, FIT/TRANSFORM, métricas y fingerprint se resuelven en Spark sin materializar las observaciones en pandas.

## 3. TRAIN

Entrada mínima:

- configuración `mode: training`;
- contrato canónico completo;
- `label_favoritismo`;
- `label_fraccionamiento`;
- evidencia de evaluación del mismo corpus.

Flujo Spark:

```text
fuente
 -> integración canónica
 -> quality gates
 -> FIT preprocesamiento
 -> TRANSFORM
 -> features
 -> RandomForest MLlib (favoritismo)
 -> StandardScaler + KMeans (fraccionamiento)
 -> candidate manifest
```

TRAIN genera artefactos en una ruta candidate controlada. No modifica `active_serving_profile`, no reemplaza el champion y no habilita serving por sí mismo.

### Por qué

Separar TRAIN de promoción evita que una tarea de experimentación o reentrenamiento modifique automáticamente el comportamiento de producción. También permite aplicar validación funcional, seguridad y segregación de funciones fuera del proceso de entrenamiento.

## 4. Candidate manifest

El candidate registra, entre otros:

- `candidate_id`;
- framework/perfil;
- configuración de modelos;
- fingerprint del corpus;
- estado de validación;
- rutas de artefactos;
- SHA-256 de cada artefacto;
- evidencia utilizada para selección;
- preprocesador;
- datos de engine/Spark.

Los candidates de esquema vigente solo pueden promoverse cuando su estado de validación es compatible con el gate de promoción.

Los candidates generados por un evento de drift pueden quedar como:

```text
validation_state = pending_candidate_evaluation
```

Ese estado impide promoverlos hasta disponer de evaluación adecuada.

## 5. Model registry

`outputs/model_registry.json` mantiene un registry unificado con perfiles separados:

```text
serving_profiles
├── sklearn
└── spark_mllib
```

El perfil activo se declara mediante:

```text
active_serving_profile
```

Cada perfil conserva:

- `champion_id`;
- metadata de promoción;
- información de entrenamiento;
- modelos;
- artefactos y hashes.

El perfil sklearn existe para regresión/compatibilidad. El perfil operacional objetivo del PoC es `spark_mllib`.

## 6. Champion store inmutable

Las promociones nuevas se publican bajo:

```text
outputs/champion_store/<profile>/<candidate_id>/
```

La promoción sigue esta secuencia conceptual:

```text
candidate
   -> validar manifest y paths
   -> copiar conjunto completo a staging
   -> verificar SHA-256
   -> publicar directorio versionado
   -> actualizar registry
```

El registry cambia su puntero **solo después** de verificar el conjunto completo.

### Por qué

Sobrescribir archivos fijos uno por uno puede dejar un champion parcialmente actualizado si el proceso se interrumpe. Un store versionado por `candidate_id` permite tratar cada versión como un conjunto coherente y hace posible volver a un champion anterior.

## 7. Compatibilidad hacia atrás

El loader mantiene soporte para registries/champions anteriores que ya estén versionados. Las nuevas promociones no vuelven a utilizar el layout fijo antiguo.

### Por qué

La compatibilidad de lectura permite reproducir evidencia ya publicada sin obligar a una migración destructiva de artefactos. La escritura nueva, en cambio, utiliza el contrato versionado más seguro.

## 8. Promoción

La promoción Spark se ejecuta de forma explícita:

```bash
python src/promover_candidato_spark.py \
  --manifest <candidate_manifest.json> \
  --approved-by "operador técnico" \
  --acknowledge-poc-only
```

El flag `--acknowledge-poc-only` fuerza a reconocer que la operación representa una promoción técnica dentro del PoC y no una aprobación CGR.

En una implantación real, la promoción debería quedar detrás de:

- identidad autenticada;
- roles separados;
- evidencia aprobada;
- workflow de cambio;
- auditoría;
- registry/model store corporativo.

## 9. Rollback

El historial del registry conserva champions anteriores cuando sus artefactos permanecen disponibles. `src/rollback_champion.py` permite mover explícitamente el puntero hacia una versión histórica después de verificar nuevamente su integridad.

### Por qué

Rollback no debe significar “reentrenar intentando reconstruir el modelo anterior”. Debe significar volver a los artefactos exactos ya aprobados y versionados.

## 10. INFERENCE

La ruta operacional Spark se encuentra en:

```text
src/spark/score_inference_spark.py
```

Contrato:

```text
contratos actuales SIN labels
 -> integración canónica
 -> registry/champion
 -> verificación SHA-256
 -> preprocesador congelado
 -> TRANSFORM sin FIT
 -> features
 -> modelos MLlib
 -> rankings en staging
 -> nueva verificación SHA-256
 -> publicación final
```

Para `spark_sql`, los rankings detallados se escriben como Parquet distribuido. Para fuentes pandas se conserva CSV único como compatibilidad local.

### Por qué se verifica antes y después

La primera verificación impide puntuar con un artefacto corrupto o distinto del registrado. La segunda impide publicar resultados si el conjunto de artefactos cambia durante la ejecución.

### Por qué se usa staging

Una inferencia fallida no debe dejar como salida “final” un ranking incompleto o generado con un champion que no superó el gate de integridad.

## 11. Concurrencia y aislamiento

Las rutas Airflow de TRAIN, INFERENCE y monitoreo utilizan ejecuciones aisladas y `max_active_runs=1`.

### Por qué

Los modelos y salidas son artefactos con identidad propia. Mezclar dos ejecuciones en un mismo directorio podría romper hashes, manifests o publicación atómica. El aislamiento reduce esa superficie de colisión y simplifica recuperación ante fallos.

## 12. Monitoreo del champion

El monitor activo es:

```text
src/autoevaluacion_champion.py
```

Su objetivo es medir el comportamiento del **champion realmente servido**, no de un benchmark paralelo.

Controles principales:

### Favoritismo

- PSI sobre features seleccionadas;
- recall@K cuando existen labels válidos;
- correspondencia entre baseline y fingerprint del champion.

### Fraccionamiento

- PSI de features;
- distribución de `score_anomalia`;
- recall@K cuando existen labels válidos.

### Reentrenamiento

- drift puede generar una necesidad de reentrenamiento;
- un candidate solo puede generarse automáticamente cuando existen labels suficientes y confiables;
- el candidate resultante no se promueve;
- si todavía no tiene evaluación adecuada, queda pendiente de evaluación.

### Por qué distinguir “sin labels” de “cero positivos”

Un lote sin labels permite evaluar drift, pero no desempeño. Un lote etiquetado con cero positivos contiene información distinta: se conoce el ground truth del lote, aunque recall@K no sea calculable. La operación institucional debe conservar esa diferencia semántica.

## 13. Monitor de solo lectura

`src/monitoreo_modelos.py` consolida:

- perfil activo;
- champion;
- integridad del último smoke de inferencia;
- última decisión de drift/reentrenamiento;
- alertas de contrato.

No entrena, no hace tuning y no promueve candidates.

## 14. Airflow

DAGs operacionales:

| DAG | Responsabilidad |
|---|---|
| `entrenamiento_candidato_1_8_2` | ejecutar TRAIN y producir candidate |
| `inferencia_modelos_1_8_2` | ejecutar scoring con el champion |
| `monitoreo_reentrenamiento_1_8_2` | revisar un lote externo configurado |

El DAG de monitoreo no fabrica datos sintéticos como parte de una corrida operacional. El lote se proporciona mediante configuración (`CGR_MONITOR_BATCH_PATH`).

Si no existe `CGR_MONITOR_SCHEDULE`, el monitor no se agenda automáticamente.

### Por qué

El repositorio puede demostrar la lógica de monitoreo, pero no debe inventar la frecuencia operativa, la fuente de lotes ni el SLA que tendría que definir la institución.

## 15. CI y promoción de smoke

CI puede ejercitar el mecanismo de promoción para comprobar que funciona, pero esa promoción vive únicamente en el workspace efímero del job. Antes de persistir evidencia verificable se restaura el registry/champion versionado en el commit y se regeneran los resúmenes dependientes de ese estado.

### Por qué

Una prueba de CI no debe convertirse accidentalmente en una decisión de serving persistida en `main`.

## 16. Límites institucionales

El repositorio implementa el contrato técnico, pero no puede definir por sí solo:

- quién tiene autoridad para aprobar/promover;
- IAM/SSO/MFA y segregación real;
- registry corporativo;
- almacenamiento distribuido y permisos;
- alertamiento y telemetría productivos;
- SLA/SLO;
- umbrales de aceptación institucional;
- frecuencia de retraining;
- proceso formal de rollback/cambio;
- DEV/QA/PROD y marcha blanca.

Esos elementos deben permanecer como dependencias institucionales hasta existir evidencia del ambiente real.
