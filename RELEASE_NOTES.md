# v1.0.0-rc.1 — Release Candidate del PoC independiente

> **No es una versión oficial de la CGR.** Es el primer release candidate del prototipo independiente construido a partir del TDR público del Proyecto Interno 1.8.2.

## Qué congela esta versión

- integridad OCDS validada y relación Contract → Award → Supplier;
- motor normativo parametrizado 2018–2026;
- benchmark supervisado de favoritismo con comparación OOF, tuning y SHAP;
- fraccionamiento con holdout independiente y limitaciones expuestas;
- ruta objetivo Apache Spark MLlib / GraphFrames ejecutada en CI;
- Lakehouse Bronce/Plata/Oro local y linaje explícito;
- Airflow y autoevaluación con promoción humana del modelo candidato;
- contrato SQL Server/SSRS con RDL de favoritismo y fraccionamiento;
- Productos 1–7 e Informe Final regenerables y auditados;
- checklist reproducible del Anexo 3;
- matriz canónica de dependencias institucionales CGR.

## Criterio de release

El release candidate solo puede etiquetarse si:

1. la corrida integral de CI termina correctamente;
2. la auditoría del Anexo 3 mantiene **0 brechas 🔴**;
3. la auditoría de coherencia del release no encuentra residuos críticos;
4. las dependencias no cerrables externamente permanecen identificadas como `CGR-DEP-XX`.

## Lo que esta versión no afirma

No afirma desempeño productivo ni conformidad institucional. Tampoco afirma despliegue en Datamart, HDFS/YARN, Git, DEV/QA/PROD, SQL Server/SSRS o esquemas de autenticación de la CGR.

Los pendientes institucionales están centralizados en `docs/Dependencias_Institucionales_CGR.md`.

## Principio de uso responsable

Las salidas de los modelos son señales de priorización para revisión humana. No son hallazgos, imputaciones ni determinaciones automáticas de irregularidad.
