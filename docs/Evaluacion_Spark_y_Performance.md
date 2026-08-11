# Evaluación Spark y performance

## Objetivo

Este documento describe cómo se evalúan los modelos Spark del serving, cómo se garantiza que la evidencia pertenezca al mismo corpus usado por TRAIN y qué puede —y qué no puede— demostrarse con benchmarks locales de rendimiento.

El principio central es separar dos conceptos:

```text
evaluación metodológica reproducible
            !=
aceptación productiva institucional
```

El repositorio implementa la primera. La segunda requiere datos, infraestructura, concurrencia, SLAs y criterios de aceptación CGR.

## 1. Evaluadores activos

Los evaluadores del perfil `spark_mllib` son:

```text
src/spark/evaluar_favoritismo_spark.py
src/spark/evaluar_fraccionamiento_spark.py
```

Generan la evidencia que consume TRAIN:

```text
outputs/tuning_favoritismo_spark_resumen.json
outputs/tuning_fraccionamiento_spark_resumen.json
```

La evidencia registra:

- algoritmo/pipeline;
- source type e input engine;
- fingerprint del corpus;
- features;
- diseño de split;
- configuración seleccionada;
- métricas de desarrollo y holdout;
- engine de preprocesamiento;
- advertencias de alcance.

## 2. Fingerprint del corpus

Cada evaluación calcula una huella SHA-256 del corpus canónico. TRAIN calcula su propia huella y exige coincidencia con ambos resúmenes de evaluación.

```text
corpus evaluado
      |
      +--> fingerprint A
      |
      +--> tuning/holdout
                |
                v
          evidencia A

corpus TRAIN
      |
      +--> fingerprint B

TRAIN permitido solo si A == B
```

### Por qué

Las métricas y los hiperparámetros solo justifican un candidate cuando fueron obtenidos sobre el mismo universo de entrenamiento. Esta comprobación evita reutilizar resultados de un benchmark público como si fueran evidencia de un corpus institucional distinto.

## 3. Favoritismo: diseño de evaluación

Unidad de split:

```text
id_proveedor + id_entidad
```

El holdout se reserva **antes del FIT del preprocesador**.

Flujo:

```text
contratos canónicos
      |
      +--> grupos desarrollo
      |       |
      |       +--> FIT preprocesador
      |       +--> CV/tuning RandomForest
      |
      +--> grupos holdout
              |
              +--> TRANSFORM con estado aprendido en desarrollo
              +--> evaluación final
```

El monto utilizado es `monto_capped`, donde el P99 procede exclusivamente del conjunto de desarrollo.

### Métrica primaria

AUC-PR se utiliza como criterio principal por el desbalance de la clase positiva.

Métricas complementarias:

- Accuracy;
- AUC-ROC;
- precision;
- recall;
- F1;
- recall@K.

### Por qué reservar el holdout antes del FIT

Si el preprocesador aprende estadísticas utilizando también el holdout, el conjunto final ya no es completamente independiente. Reservarlo antes del FIT reduce leakage y hace que la evaluación se parezca más al comportamiento de INFERENCE sobre datos no vistos.

## 4. Fraccionamiento: diseño de evaluación

Unidad de split:

```text
id_proveedor + id_entidad + objeto_familia
```

KMeans se ajusta **sin labels**. Las etiquetas se utilizan para:

- estratificar evaluación cuando corresponde;
- comparar configuraciones `k`;
- medir rendimiento del ranking.

Flujo:

```text
grupo contractual
   -> features
   -> StandardScaler
   -> KMeans
   -> distancia al centroide
   -> score_anomalia
```

La selección de `k` se realiza únicamente con desarrollo. El holdout final no participa en la selección.

### Por qué usar labels si el modelo es no supervisado

Un algoritmo no supervisado puede ajustarse sin etiquetas y, aun así, ser evaluado contra un conjunto de casos conocidos. Las etiquetas no determinan los centroides; sirven para medir si el ranking resultante prioriza casos positivos de forma útil.

## 5. `spark_sql`: evaluación distribuida

Cuando `source.type: spark_sql`, los evaluadores utilizan:

```text
SparkSession.table(...)
    -> integrar_spark()
    -> fingerprint Spark
    -> split Spark
    -> FIT distribuido
    -> TRANSFORM Spark
    -> features Spark
    -> MLlib
    -> métricas agregadas
```

No se materializan las observaciones con `.toPandas()`.

Los splits de fraccionamiento se realizan mediante funciones/window/hash determinísticas dentro de Spark, evitando recolectar listas de IDs al driver para reconstruir particiones.

### Por qué

Una evaluación que obligara a colectar el corpus al driver impediría cerrar el ciclo metodológico sobre fuentes distribuidas: TRAIN exigiría evidencia del mismo corpus Spark, pero la evaluación no podría producirla de manera escalable.

## 6. Qué sí puede colectarse al driver

La prohibición de materialización se aplica a las **observaciones del dataset** dentro de la frontera distribuida. Es válido recolectar resultados escalares de control, por ejemplo:

- conteos por clase;
- métricas agregadas;
- parámetros seleccionados;
- pequeñas muestras diagnósticas en caso de error.

### Por qué

Spark necesita devolver al proceso conductor ciertos resultados de coordinación. El objetivo no es “cero collect bajo cualquier circunstancia”, sino evitar que el volumen contractual se convierta en un DataFrame local.

## 7. Reproducibilidad

`outputs/run_manifest.json` registra metadata de ejecución y una sección de reproducibilidad basada en entradas estables.

Se separan:

```text
trazabilidad de ejecución
  commit + timestamp + duración + entorno

identidad reproducible del experimento
  dependencias + configuración + código clave + datasets deterministas
```

### Por qué

Dos ejecuciones reproducibles pueden ocurrir en momentos distintos y tener diferente duración. Un hash de identidad no debería cambiar únicamente porque el timestamp cambió.

## 8. Seeds y determinismo

Los modelos y splits reproducibles utilizan seeds configuradas/fijas cuando el algoritmo lo admite.

Esto permite:

- comparar regresiones;
- comprobar que un cambio de código produce un cambio real de evidencia;
- reducir variabilidad innecesaria en CI.

No debe interpretarse como garantía de bit-identicalidad de todos los artefactos Spark entre plataformas distintas, ya que versiones de runtime, orden físico o implementación distribuida pueden afectar serialización.

## 9. Benchmark operacional

`src/spark/benchmark_operacional.py` permite medir de forma parametrizable:

- source type;
- input engine;
- Spark master/versión;
- shuffle partitions;
- fingerprint del corpus;
- filas/grupos;
- tiempos de integración;
- tiempos de FIT;
- acciones de features;
- throughput referencial.

El resultado incluye explícitamente:

```text
institutional_acceptance = false
```

### Por qué

Una laptop, runner de CI o `local[*]` no representan el clúster, almacenamiento, red, concurrencia ni volumen que utilizaría la institución.

## 10. Qué exige una prueba de performance institucional

Para convertir el benchmark en evidencia de aceptación se deben definir al menos:

- volumen objetivo;
- número de contratos y grupos;
- skew esperado;
- concurrencia;
- tamaño/particionado de fuentes;
- recursos por executor;
- dynamic allocation;
- límites de memoria;
- tiempos máximos por etapa;
- ventanas operativas;
- SLO/SLA;
- comportamiento ante reintentos/fallos;
- criterio de degradación aceptable;
- ambientes DEV/QA/PROD.

Sin esos criterios no existe una referencia objetiva para afirmar “cumple performance”.

## 11. Benchmark sintético y desempeño real

El benchmark sintético tiene etiquetas controladas y sirve para verificar:

- que el pipeline aprende señales esperadas;
- que los splits/evaluaciones funcionan;
- que las métricas se calculan correctamente;
- que TRAIN consume la evidencia correcta;
- que CI detecta regresiones metodológicas.

No sirve para estimar directamente precisión sobre expedientes CGR.

Una métrica perfecta o alta sobre el benchmark puede indicar que el caso sintético es fácilmente separable; no debe presentarse como desempeño productivo.

## 12. Datos públicos OCDS/OECE

La prueba con datos abiertos reales permite observar:

- portabilidad del contrato de features;
- comportamiento sobre distribuciones reales;
- integridad de joins contractuales;
- funcionamiento de reglas normativas y `objeto_familia`.

No valida el champion porque no dispone de ground truth institucional de favoritismo/fraccionamiento.

### Por qué no usar el propio score como label

Hacerlo produciría evaluación circular: el modelo terminaría siendo “correcto” porque se compara con una etiqueta derivada de su propia señal.

## 13. Monitoreo distribuido

El monitor batch público no pretende ser un monitor `spark_sql` productivo. Para una implementación distribuida deben definirse:

- fuente de lotes;
- ventana temporal;
- persistencia de baseline;
- agregación de PSI;
- storage de métricas;
- observabilidad;
- alertas;
- retención;
- ground truth tardío;
- integración con candidate/retraining.

El PoC prefiere rechazar una ruta no soportada antes que colectar silenciosamente el corpus al driver.

## 14. Gates de regresión

Las pruebas estructurales protegen, entre otros:

- ausencia de `.toPandas()` en evaluadores Spark protegidos;
- uso de `integrar_spark()` para `spark_sql`;
- fingerprint Spark;
- splits distribuidos;
- métricas agregadas;
- fraccionamiento sin listas locales de IDs;
- declaración de `spark_native_evaluation` en evidencia;
- correspondencia de fingerprint entre evaluación y TRAIN.

Si se rompe la frontera distribuida, la auditoría TDR debe reflejar la brecha en el criterio de Spark/escalabilidad.

## 15. Interpretación recomendada

La evidencia debe leerse en este orden:

1. ¿el pipeline evaluado coincide con el servido?;
2. ¿el fingerprint coincide con TRAIN?;
3. ¿el holdout quedó fuera de selección/FIT?;
4. ¿las métricas son adecuadas al desbalance?;
5. ¿los resultados provienen de benchmark sintético, datos públicos o corpus institucional?;
6. ¿existe aceptación funcional/productiva documentada?;

Solo el último punto permite hablar de aceptación institucional. Los cinco primeros permiten hablar de **consistencia metodológica y reproducibilidad técnica**.
