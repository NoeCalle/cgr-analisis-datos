# Módulo de Análisis de Datos — Prototipo (Proyecto Interno CGR 1.8.2)

> **Prototipo independiente.** Este repositorio no constituye una
> implementación oficial ni cuenta con aprobación institucional de la
> Contraloría General de la República (CGR). Es un ejercicio técnico
> propio, construido a partir de un TDR público, no un encargo ni un
> producto entregado a la CGR.

Prototipo funcional construido para demostrar viabilidad técnica del
"Módulo de análisis de datos para dar soporte a los auditores durante la
ejecución de los servicios de control", descrito en el TDR de contratación
de un Consultor Científico de Datos (Contraloría General de la República,
Mayo 2026).

**Objetivo del prototipo:** construir, con licencia abierta, una
contribución técnica al control gubernamental y a la lucha anticorrupción,
con evidencia reproducible sobre los tres casos de uso priorizados del TDR:
favoritismo, posible fraccionamiento y vínculos proveedor-funcionario.

## Estado

🟡 **Prueba de concepto funcional en proceso de endurecimiento técnico.**
Existen los 7 documentos que reflejan la estructura de productos del TDR y
un conjunto amplio de implementaciones técnicas (Spark, Airflow, Delta,
GraphFrames, SSRS stand-in, MLOps). Tras una auditoría técnica de agosto de
2026 se inició un plan de cierre de brechas antes de volver a declarar el
prototipo como "finalizado".

La primera prioridad (P0) es **integridad de datos reales + normativa**:
- la carga OCDS fue corregida para usar `Contract -> Award -> Supplier`;
- la clave de contrato es ahora `OCID::contract.id`;
- los consorcios se forman por adjudicación, no por proceso completo;
- el motor normativo fue corregido y distingue el cambio de régimen desde
  el 22/04/2025 (Ley 32069);
- se añadieron pruebas de regresión en `tests/`.

> Los CSV procesados y rankings `*_REAL.csv` generados antes de esta
> corrección se consideran **artefactos históricos/stale hasta regenerarlos**
> desde los crudos OCDS. No deben usarse como evidencia vigente ni como
> hallazgos confirmados. Ver `data_real/README.md`.

## Qué incluye

**Los 3 casos de uso del TDR:**
- Favoritismo: Random Forest supervisado sobre datos sintéticos + score no
  supervisado de priorización sobre datos abiertos sin ground truth.
- Posible fraccionamiento: Isolation Forest/KMeans + regla interpretable de
  ventana temporal y cuantías normativas, tratada como **señal de alerta**,
  no como determinación jurídica automática.
- Vínculos proveedor-funcionario: grafo con networkx y Spark GraphFrames
  sobre datos sintéticos; en datos abiertos reales se limita a relaciones
  organizacionales porque OCDS no publica funcionarios individuales.

**Ejecutado y verificado en el entorno de desarrollo** (no solo diseñado):
- Apache Spark MLlib (RandomForestClassifier, KMeans)
- Apache Airflow — 2 DAGs
- Búsqueda sistemática de hiperparámetros
- Estándares SQL institucionales simulados (LEFT JOIN, poda de particiones)
- Integración SSRS mediante esquema T-SQL + `.rdl` y SQLite como stand-in
- Autoevaluación y reentrenamiento experimental
- Delta Lake (ACID, historial, time travel, Change Data Feed)
- Spark GraphFrames (PageRank, Connected Components)
- R, Scala, Python, SQL y Java como demostraciones del ecosistema del Anexo 2

**Adicional, fuera del alcance formal del TDR:** existe un pipeline para
datos públicos reales de contrataciones del Perú (OCDS/OECE). La ejecución
histórica produjo 47,442 filas analíticas, pero esa cifra **no se considera
vigente** después de la corrección P0 de relación contrato-adjudicación-
proveedor. Debe recalcularse desde los crudos. Ver `data_real/`.

## Qué queda fuera de alcance local

| Componente | Motivo / estado |
|---|---|
| Lakehouse Plata/Oro institucional CGR | Requiere acceso a la plataforma institucional; el repo solo reproduce el patrón arquitectónico. |
| Hadoop YARN / HDFS productivo | No se completó un clúster distribuido. El modo single-node es técnicamente posible, pero no demuestra las propiedades de un clúster real. |
| SQL Server/SSRS, SSAS y Power BI institucionales | Se entrega interfaz/esquema PoC; la validación real requiere infraestructura/licencias/accesos CGR. |
| Git institucional, DEV/QA/PROD, certificación y marcha blanca | Solo pueden cerrarse durante una implementación institucional. |
| Transferencia formal a usuarios CGR | Depende de ejecución contractual y coordinación institucional. |

## Estructura del repositorio

```text
CÓDIGO FUENTE
  src/                         Scripts principales
  src/spark/                   MLlib, GraphFrames, Delta, SQL, streaming, HMS
  airflow_home/dags/           DAG principal + monitoreo/reentrenamiento
  reporte/generar_*.js         Generadores de documentos
  ssrs/schema_sql_server.sql   Esquema T-SQL
  tests/                       Pruebas de regresión P0 y futuras

DEPENDENCIAS BINARIAS
  jars/                        GraphFrames, Delta Lake y pruebas Hadoop

ARTEFACTOS / EVIDENCIA
  data/                        Datos sintéticos y datasets derivados
  data_real/*.csv              Datos reales procesados (ver estado en su README)
  outputs/                     Gráficos, modelos, rankings y logs
  reporte/*.docx               Documentos generados
  reporte/productos_formales/  Productos 1–7 generados
  ssrs/*.rdl                   Reporte SSRS generado
```

## Cómo reproducir

### 0. Instalar el entorno

```bash
pip install -r requirements.txt --break-system-packages
cd reporte && npm install && cd ..
```

R, Java/Spark y Airflow requieren sus respectivos runtimes. Airflow se ha
mantenido en un entorno virtual separado para evitar conflictos de
versiones; esta integración será endurecida en una fase posterior del plan.

### 1. Ejecutar pruebas de regresión

```bash
pytest -q
```

Las pruebas P0 verifican como mínimo:
- un contrato recibe suppliers de **su award**, no de todos los awards del
  proceso;
- `contract.id` repetido en OCID diferentes no colisiona;
- un award sin supplier no hereda el supplier de otro award;
- topes 2022–2026 parametrizados;
- cambio de régimen el 22/04/2025;
- prioridad de `mainProcurementCategory` sobre texto libre;
- fallo explícito para años normativos no parametrizados.

### 2. Pipeline sintético

```bash
python3 src/generar_datos.py
python3 src/eda.py
python3 src/preprocesamiento.py
python3 src/modelo_favoritismo.py
python3 src/modelo_fraccionamiento.py
python3 src/modelo_grafos.py
python3 src/generar_diccionario_diagrama.py
```

### 3. Pipeline real OCDS/OECE

Seguir `data_real/README.md`. Se necesitan los crudos:
`main.csv`, `contracts.csv`, `awards.csv`, `awards_suppliers.csv` y
`parties.csv`.

```bash
python3 src/cargar_datos_reales_seace.py
pytest -q
python3 src/modelo_real.py
```

### 4. Componentes Spark / MLOps / SSRS PoC

```bash
python3 src/spark/modelo_favoritismo_spark.py
python3 src/spark/modelo_fraccionamiento_spark.py
python3 src/spark/vinculos_graphframes.py
python3 src/spark/lakehouse_delta.py
python3 src/spark/estandares_sql.py
python3 src/autoevaluacion.py
python3 src/publicar_ssrs.py
```

## Documentación

- `reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx` — reporte consolidado
  generado antes de algunas correcciones P0; será regenerado al cerrar las
  brechas de datos/modelado para evitar documentar cifras obsoletas.
- `reporte/productos_formales/` — Productos 1–7 generados; mismo criterio de
  actualización que el reporte consolidado.
- `data_real/README.md` — procedimiento y estado de la validación real.
- `jars/README.md` — dependencias JVM versionadas.

## Licencia

El código de este repositorio está bajo licencia **MIT** (ver `LICENSE`).
Los datos públicos reales procedentes de OECE conservan su licencia **CC BY
4.0** y requieren atribución.

## Nota metodológica

Los datasets de `data/` son sintéticos y permiten pruebas funcionales con
ground truth sembrado. Las métricas perfectas obtenidas en esos escenarios
**no son estimaciones del desempeño esperado en producción**. En particular,
el 100% de la regla sintética de posible fraccionamiento es un *sanity check*
de implementación sobre casos construidos con el patrón que la regla busca.

El objetivo productivo del módulo no debe ser "declarar corrupción" ni
"probar fraccionamiento" automáticamente, sino **priorizar señales explicables
y trazables para revisión de auditor**, en línea con el propósito del TDR.
