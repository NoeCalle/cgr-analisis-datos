# Cierre técnico — Etapa 5B

## Objetivo

La Etapa 5 detectó una brecha que no aparecía en la auditoría automática: TRAIN e INFERENCE ya aceptaban `spark_sql` de forma Spark-native, pero los evaluadores que producen los hiperparámetros/evidencia obligatoria para TRAIN partían de la ruta pandas. En un corpus institucional Spark esto generaba un ciclo imposible: TRAIN exigía evidencia del mismo fingerprint distribuido, pero la evaluación no podía producirla.

## Corrección P1

Los evaluadores activos son:

- `src/spark/evaluar_favoritismo_spark.py`;
- `src/spark/evaluar_fraccionamiento_spark.py`.

Cuando `source.type: spark_sql` ambos usan ahora:

```text
Spark table/view
    -> integrar_spark()
    -> fingerprint_spark_dataframe()
    -> split de desarrollo/holdout en Spark
    -> FIT distribuido del preprocesador
    -> TRANSFORM Spark
    -> features Spark
    -> tuning/evaluación MLlib
    -> métricas agregadas en Spark
    -> evidencia con fingerprint del mismo corpus
    -> TRAIN
```

No se materializan las observaciones de evaluación mediante `.toPandas()`.

En fraccionamiento tampoco se recolectan IDs para volver a Spark con listas `isin(...)`: los splits repetidos de validación se asignan con ventanas y hashes determinísticos dentro de Spark.

Las fuentes `local_csv` y `sqlserver` conservan el adaptador pandas documentado. Esa compatibilidad local no cambia la frontera institucional `spark_sql`.

## Gate de regresión

`tests/test_spark_evaluation_native.py` comprueba:

- splits estratificados Spark;
- métricas distribuidas;
- validación de fraccionamiento sin listas locales;
- ausencia de `.toPandas()` en los evaluadores;
- presencia de `integrar_spark()` y fingerprint Spark;
- declaración explícita `spark_native_evaluation` en la evidencia.

`src/auditar_tdr_completo.py` también incluye un gate estructural. Si esta frontera se rompe, el criterio 10 del TDR pasa a 🔴 y la auditoría falla.

## Reproducibilidad

`outputs/run_manifest.json` conserva `schema_version: 3` por compatibilidad, pero añade `reproducibility` con una huella SHA-256 calculada únicamente sobre entradas estables:

- dependencias fijadas;
- package lock de reportes;
- configuraciones locales;
- código clave del pipeline;
- datasets deterministas del benchmark.

La huella excluye metadata naturalmente variable como `generado_utc` y `duracion_s`. Esto permite distinguir dos conceptos:

```text
trazabilidad de ejecución != identidad reproducible del experimento
```

## Benchmark de performance

`src/spark/benchmark_operacional.py` permite ejecutar un benchmark parametrizable sobre la fuente configurada. Registra:

- `source_type` e `input_engine`;
- master y versión Spark;
- particiones shuffle;
- fingerprint del corpus;
- filas y grupos procesados;
- tiempos de integración, FIT y acciones de features;
- throughput referencial.

El resultado siempre contiene:

```text
institutional_acceptance = false
```

Por tanto, un benchmark local nunca se presenta como prueba de capacidad, robustez o aceptación de la infraestructura CGR.

## Límites que continúan abiertos legítimamente

Etapa 5B no intenta simular como resueltos los elementos que requieren institución:

- clúster y almacenamiento distribuido CGR;
- volumen, concurrencia y skew reales;
- pruebas de carga DEV/QA/PROD;
- ground truth institucional;
- umbrales numéricos de aceptación;
- operación de monitor distribuido sobre una fuente `spark_sql` institucional;
- certificación y marcha blanca.

El monitor batch público continúa rechazando `spark_sql` en lugar de colectarlo al driver. Convertirlo en monitor distribuido requiere definir la fuente de lotes, persistencia de métricas y plataforma de observabilidad institucional; no se oculta con una simulación local.

## Resultado esperado

Con CI verde y artefactos regenerados, el criterio 10 vuelve de la brecha manual detectada en Etapa 5 a estado 🟡: la parte cerrable desde el repositorio queda implementada; performance/robustez productiva permanece como dependencia institucional.
