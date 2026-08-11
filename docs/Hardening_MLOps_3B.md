# Nota histórica — hardening MLOps

Este archivo se conserva únicamente como **referencia histórica del proceso de desarrollo**. La documentación funcional vigente ya no se organiza por etapas de corrección.

Para entender la arquitectura actual consultar:

- [`Arquitectura_MLOps.md`](Arquitectura_MLOps.md) — ciclo evaluación → TRAIN → candidate → promoción → champion → INFERENCE, registry, hashes, store versionado, rollback, monitor y Airflow;
- [`Train_Inference.md`](Train_Inference.md) — contrato operativo de TRAIN/INFERENCE;
- [`Evaluacion_Spark_y_Performance.md`](Evaluacion_Spark_y_Performance.md) — evaluación Spark, fingerprints y límites de performance.

Los detalles de cuándo se introdujo cada control permanecen disponibles en el historial Git y en los pull requests. No deben utilizarse como descripción de la arquitectura vigente.
