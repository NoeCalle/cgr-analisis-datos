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
contribución técnica al control gubernamental y a la lucha anticorrupción
— con evidencia de ejecución real, no solo teórica, sobre los tres casos
de uso priorizados del TDR (favoritismo, fraccionamiento, vínculos
proveedor-funcionario).

## Estado

✅ **Finalizado.** Los 7 productos formales del TDR (Anexo 01) están
completos, más un conjunto sustancial de mejoras y cierres de brecha
construidos después de la primera versión. Ver "Qué incluye" abajo y el
[reporte técnico completo](reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx)
para el detalle con evidencia de cada pieza.

## Qué incluye

**Los 3 casos de uso del TDR**, con modelos entrenados, validados y
explicables (SHAP):
- Detección de favoritismo (Random Forest)
- Detección de fraccionamiento (Isolation Forest + regla del umbral legal — la regla gana con 100% de precisión)
- Vínculos proveedor-funcionario (grafo con networkx y con Spark GraphFrames real)

**Ejecutado y verificado en el entorno de desarrollo** (no solo diseñado
en papel):
- Apache Spark MLlib real (RandomForestClassifier, KMeans)
- Apache Airflow real — 2 DAGs, `airflow dags test`, 100% de tareas exitosas
- Búsqueda sistemática de hiperparámetros (GridSearchCV + CrossValidator, coincidencia cruzada entre plataformas)
- Estándares SQL institucionales (LEFT JOIN, poda de particiones anti Full Table Scan)
- Integración SSRS (esquema T-SQL + reporte `.rdl` real)
- Autoevaluación y autoentrenamiento (Population Stability Index + reentrenamiento condicional, orquestado con Airflow)
- Delta Lake real (ACID, historial de versiones, time travel, Change Data Feed)
- Spark GraphFrames real (PageRank, Connected Components)
- R, Scala, Python, SQL, Java — los 5 lenguajes del Anexo 2 del TDR, verificados

**Adicional, fuera del alcance formal del TDR:** el pipeline completo se
corrió también sobre 47,442 contratos **reales** de contrataciones
públicas del Perú (portal de datos abiertos OCDS de la OECE, no de la
CGR) — ver `data_real/`.

## Qué queda fuera de alcance (y por qué)

| Componente | Motivo |
|---|---|
| Hadoop YARN / HDFS | No se completó una instalación pseudo-distribuida (single-node) por límites de tamaño de archivo, no por imposibilidad técnica — Apache documenta ese modo explícitamente. Se investigó `hadoop-client-minicluster` (27.1 MB, obtenido) pero requiere un segundo archivo de 40-70 MB que excede el límite de subida de este entorno; el tarball completo (554 MB) también. El beneficio real de producción (replicación tolerante a fallos, reparto de recursos entre nodos) sí requiere máquinas físicas distintas — eso no cambia con más código. |
| SQL Server real, SSAS, Power BI | Requieren licencia o cuenta — fuera de alcance por decisión, ya que el prototipo se construye enteramente con herramientas de licencia abierta. |

Ambos casos están documentados con honestidad técnica en el reporte
(Anexo B) y en el Producto 7 (Sección 11) — no se ocultan como si
estuvieran resueltos.

## Estructura del repositorio

Separado en **código fuente** (lo que se ejecuta) y **artefactos /
evidencia** (lo que ese código produjo, versionado para que los
resultados sean revisables sin tener que re-ejecutar todo):

```
CÓDIGO FUENTE
  src/                     Scripts principales (generación, EDA, preprocesamiento, modelos, autoevaluación)
  src/spark/               Versiones en Apache Spark real (MLlib, GraphFrames, Delta Lake, estándares SQL, streaming, HMS)
  airflow_home/dags/       Los 2 DAGs de Airflow (pipeline principal + monitoreo/reentrenamiento)
  reporte/generar_*.js     Scripts que generan los .docx (no los .docx en sí)
  ssrs/schema_sql_server.sql   Esquema T-SQL (definición, no un artefacto generado)

DEPENDENCIAS BINARIAS (no artefactos del proyecto, pero versionadas por
la misma razón que los datos reales: sin ellas, nadie puede reproducir
sin repetir el mismo problema de acceso a Maven Central)
  jars/                    GraphFrames, Delta Lake y el intento de Hadoop minicluster — ver jars/README.md

ARTEFACTOS / EVIDENCIA (generados por el código de arriba; se pueden
borrar y regenerar corriendo los scripts correspondientes)
  data/                    Datos sintéticos generados (contratos, proveedores, entidades, funcionarios)
  data_real/*.csv          Salida del pipeline sobre datos reales de SEACE — ver su propio README
  outputs/                 Gráficos, modelos entrenados (.joblib), rankings de riesgo, logs
  reporte/*.docx           Reporte técnico consolidado y los 7 productos formales, ya generados
  reporte/productos_formales/  Los 7 productos formales del Anexo 01, como documentos separados
  ssrs/*.rdl               Reporte SSRS ya generado
```

Nota de honestidad (revisión externa, agosto 2026): el repositorio no
está reorganizado en carpetas físicas separadas (ej. `artefactos/` vs
`codigo/`) — habría significado mover muchas rutas ya verificadas contra
las últimas correcciones, con riesgo de romper algo sin poder
re-verificar todo a tiempo. Esta tabla es la separación conceptual
explícita que faltaba, no una reestructuración física.

## Cómo reproducir

### 0. Instalar el entorno (paso que faltaba documentar — corregido tras revisión externa)

```bash
# Dependencias de Python (versiones fijadas en requirements.txt)
pip install -r requirements.txt --break-system-packages

# Dependencias de Node.js (generación de los .docx del reporte)
cd reporte && npm install && cd ..

# R (para src/analisis_r.R) — vía apt en Debian/Ubuntu
apt-get install -y r-base-core

# Apache Airflow — en un entorno virtual SEPARADO (evita conflictos de
# dependencias con el resto del proyecto):
python3 -m venv .venv_airflow
.venv_airflow/bin/pip install "apache-airflow==3.3.0" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.0/constraints-3.12.txt"
```

Los `.jar` de Spark (GraphFrames, Delta Lake, el intento de Hadoop) ya
están versionados en `jars/` — no hace falta descargarlos de nuevo (ver
`jars/README.md` si necesitas otra versión).

### 1. Ejecutar el pipeline

Orden de ejecución (o usar directamente el DAG de Airflow, que hace lo
mismo de forma orquestada):

```
python3 src/generar_datos.py
python3 src/eda.py                        # opcional
python3 src/preprocesamiento.py
python3 src/modelo_favoritismo.py
python3 src/modelo_fraccionamiento.py
python3 src/modelo_grafos.py
python3 src/generar_diccionario_diagrama.py

# Versiones en Spark real (requieren los .jar de jars/):
python3 src/spark/modelo_favoritismo_spark.py
python3 src/spark/modelo_fraccionamiento_spark.py
python3 src/spark/vinculos_graphframes.py
python3 src/spark/lakehouse_delta.py
python3 src/spark/estandares_sql.py

# Autoevaluación y publicación:
python3 src/autoevaluacion.py
python3 src/publicar_ssrs.py

# O todo orquestado con Airflow (con AIRFLOW_HOME apuntando a airflow_home/):
airflow dags test modulo_analisis_datos_1_8_2
airflow dags test monitoreo_reentrenamiento_1_8_2
```

## Documentación

- **[Reporte_Tecnico_Prototipo_CGR_1.8.2.docx](reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx)** — documento único consolidado, la forma más rápida de leer todo el trabajo con evidencia y hallazgos.
- **`reporte/productos_formales/`** — los 7 productos formales del Anexo 01, cada uno con la carátula, estructura y numeración que exige el TDR (relevante porque el TDR liga cada pago a la aprobación de un producto individual, no de un reporte único).
- **`data_real/README.md`** — cómo reproducir la validación con datos reales de SEACE.
- **`jars/README.md`** — de dónde salieron los `.jar` de GraphFrames/Delta Lake/Hadoop y por qué hicieron falta.

## Licencia

El código de este repositorio está bajo licencia **MIT** (ver
[`LICENSE`](LICENSE)) — cualquiera, incluida la CGR, puede usarlo, copiarlo,
modificarlo y redistribuirlo libremente, sin restricciones ni necesidad de
pedir permiso.

Esto es distinto de la licencia de los **datos** en `data_real/`, que son
de la OECE bajo **CC BY 4.0** (requiere atribución) — ver
`data_real/README.md`. El código y los datos reales tienen licencias
separadas porque tienen dueños distintos.

## Nota sobre los datos

Los datasets en `data/` son **sintéticos**, generados para fines de
demostración — no contienen información real de proveedores, funcionarios
ni entidades públicas. Los datasets en `data_real/` (procesados) sí son
**reales**: contrataciones públicas del Perú, publicadas legalmente en
formato abierto por la OECE bajo licencia CC BY 4.0 — no son datos
internos de la CGR.

## Hallazgo principal

En el caso de fraccionamiento, ni Isolation Forest (scikit-learn) ni
KMeans (Spark MLlib real) igualan la precisión de una regla simple basada
en el umbral legal de Adjudicación Simplificada (100% vs. 37.5% y 0%
respectivamente). El valor de este tipo de herramienta está tanto en
traducir correctamente la normativa de contrataciones a reglas
computables como en el modelo estadístico en sí.
