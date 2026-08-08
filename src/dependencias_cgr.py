"""Catálogo canónico de dependencias institucionales CGR.

Estas dependencias NO son brechas técnicas del PoC público. Representan
información, infraestructura, gobierno o validación que solo puede cerrarse
dentro de la Contraloría General de la República (CGR).
"""

DEPENDENCIAS_CGR = [
    {
        "id": "CGR-DEP-01",
        "nombre": "Fuentes y Datamart institucional",
        "tipo": "Datos / Lakehouse",
        "descripcion": "Acceso y mapeo a fuentes internas CGR/SIAF/SEACE y a las capas Plata/Oro institucionales.",
        "evidencia_para_cierre": "Diccionario y linaje institucional aprobados; consultas sobre tablas/fuentes reales y permisos de lectura.",
        "afecta": [2, 3, 4, 8],
    },
    {
        "id": "CGR-DEP-02",
        "nombre": "Estándares SQL y planes de ejecución institucionales",
        "tipo": "Estándares / Performance",
        "descripcion": "Reglas internas para LEFT JOIN, cortocircuito, particionamiento y prohibición de Full Table Scans, evaluadas sobre esquemas reales.",
        "evidencia_para_cierre": "Revisión de estándares CGR y planes de ejecución aprobados sobre tablas de hechos institucionales.",
        "afecta": [3],
    },
    {
        "id": "CGR-DEP-03",
        "nombre": "Ground truth y umbrales de aceptación",
        "tipo": "Validación analítica",
        "descripcion": "Etiquetas/casos validados por especialistas y valores institucionales mínimos de Accuracy, F1-Score y AUC-ROC.",
        "evidencia_para_cierre": "Dataset de validación institucional, umbrales aprobados y acta/reporte de aceptación de métricas.",
        "afecta": [4, 10],
    },
    {
        "id": "CGR-DEP-04",
        "nombre": "Git, identidad, autenticación y secretos institucionales",
        "tipo": "Seguridad / MLOps",
        "descripcion": "Repositorio Git institucional, cuentas de servicio, autenticación, autorización, secretos y políticas de despliegue CGR.",
        "evidencia_para_cierre": "Repositorio institucional creado; accesos, secretos y controles de autenticación/autorización validados.",
        "afecta": [6],
    },
    {
        "id": "CGR-DEP-05",
        "nombre": "SQL Server y SSRS institucional",
        "tipo": "Integración",
        "descripcion": "Servidor SQL Server, catálogo, datasource, autenticación y servidor SSRS donde desplegar DDL y RDL del módulo.",
        "evidencia_para_cierre": "DDL aplicado; RDL desplegados; pruebas de consultas, permisos y visualización aprobadas en SSRS CGR.",
        "afecta": [7],
    },
    {
        "id": "CGR-DEP-06",
        "nombre": "Ambientes DEV/QA/PROD y clúster institucional",
        "tipo": "Infraestructura",
        "descripcion": "Ambientes CGR, Hadoop/HDFS/YARN/Spark y demás servicios institucionales necesarios para pruebas de integración y operación.",
        "evidencia_para_cierre": "Pipeline ejecutado en DEV/QA/PROD; pruebas de integración, rendimiento y operación aprobadas.",
        "afecta": [2, 3, 4, 6, 7],
    },
    {
        "id": "CGR-DEP-07",
        "nombre": "Certificación de usuarios y marcha blanca",
        "tipo": "Aceptación / Operación",
        "descripcion": "Validación por auditores/usuarios CGR mediante casos reales, incidencias, ajustes y periodo de marcha blanca.",
        "evidencia_para_cierre": "Actas de certificación, registro de incidencias resueltas y cierre de marcha blanca.",
        "afecta": ["cierre_contractual"],
    },
    {
        "id": "CGR-DEP-08",
        "nombre": "Transferencia formal y entrega institucional",
        "tipo": "Gobierno / Cierre",
        "descripcion": "Transferencia de conocimiento, entrega en repositorios institucionales y formalidades de presentación/propiedad/confidencialidad aplicables.",
        "evidencia_para_cierre": "Acta de transferencia, repositorio institucional actualizado y conformidad formal de entrega.",
        "afecta": ["cierre_contractual"],
    },
]

POR_ID = {d["id"]: d for d in DEPENDENCIAS_CGR}


def validar_catalogo():
    ids = [d["id"] for d in DEPENDENCIAS_CGR]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs de dependencias CGR duplicados")
    if ids != [f"CGR-DEP-{i:02d}" for i in range(1, len(ids) + 1)]:
        raise ValueError("El catálogo de dependencias CGR debe mantener IDs correlativos")
    return True
