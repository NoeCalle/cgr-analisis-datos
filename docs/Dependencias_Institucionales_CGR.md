# Dependencias institucionales CGR

> Fuente canónica de pendientes que **no pueden cerrarse desde este repositorio público independiente**. No deben convertirse en simulaciones destinadas a aparentar cumplimiento institucional.

| ID | Dependencia | Tipo | Qué falta para cerrarla | Criterios/etapa afectada |
|---|---|---|---|---|
| CGR-DEP-01 | Fuentes y Datamart institucional | Datos / Lakehouse | Diccionario y linaje institucional aprobados; consultas sobre tablas/fuentes reales y permisos de lectura. | 2, 3, 4, 8 |
| CGR-DEP-02 | Estándares SQL y planes de ejecución institucionales | Estándares / Performance | Revisión de estándares CGR y planes de ejecución aprobados sobre tablas de hechos institucionales. | 3 |
| CGR-DEP-03 | Ground truth y umbrales de aceptación | Validación analítica | Dataset de validación institucional, umbrales aprobados y acta/reporte de aceptación de métricas. | 4, 10 |
| CGR-DEP-04 | Git, identidad, autenticación y secretos institucionales | Seguridad / MLOps | Repositorio institucional creado; accesos, secretos y controles de autenticación/autorización validados. | 6 |
| CGR-DEP-05 | SQL Server y SSRS institucional | Integración | DDL aplicado; RDL desplegados; pruebas de consultas, permisos y visualización aprobadas en SSRS CGR. | 7 |
| CGR-DEP-06 | Ambientes DEV/QA/PROD y clúster institucional | Infraestructura | Pipeline ejecutado en DEV/QA/PROD; pruebas de integración, rendimiento y operación aprobadas. | 2, 3, 4, 6, 7 |
| CGR-DEP-07 | Certificación de usuarios y marcha blanca | Aceptación / Operación | Actas de certificación, registro de incidencias resueltas y cierre de marcha blanca. | cierre_contractual |
| CGR-DEP-08 | Transferencia formal y entrega institucional | Gobierno / Cierre | Acta de transferencia, repositorio institucional actualizado y conformidad formal de entrega. | cierre_contractual |

## Regla de cierre

Una dependencia solo cambia de estado cuando existe la evidencia institucional indicada. La existencia de un stand-in local, datos sintéticos o una configuración placeholder **no sustituye** esa evidencia.

## Alcance del release candidate

El release candidate del PoC puede considerarse técnicamente cerrado con estas dependencias abiertas, siempre que la auditoría del Anexo 3 mantenga **0 brechas rojas (🔴)**. Los estados 🟡/🔵 siguen visibles hasta la ejecución dentro de CGR.
