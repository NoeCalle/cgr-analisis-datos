# Nota histórica — cierre de evaluación Spark

Este archivo se conserva únicamente como **referencia histórica del proceso de desarrollo**. La documentación funcional vigente ya no se organiza por etapas de corrección.

La especificación actual se encuentra en:

- [`Evaluacion_Spark_y_Performance.md`](Evaluacion_Spark_y_Performance.md) — evaluación distribuida, fingerprints, holdout, reproducibilidad y benchmark operacional;
- [`Arquitectura_MLOps.md`](Arquitectura_MLOps.md) — relación entre evaluación, TRAIN y candidate;
- [`Integracion_Datos.md`](Integracion_Datos.md) — frontera `spark_sql` Spark-native.

El estado actual exige que la evaluación Spark pueda producir evidencia sobre el mismo corpus/fingerprint requerido por TRAIN. Los detalles de cómo se llegó a este contrato permanecen disponibles en Git y no forman parte de la documentación principal de la herramienta.
