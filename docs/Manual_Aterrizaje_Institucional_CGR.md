# Manual de Aterrizaje Institucional — Módulo de Análisis de Datos

> **Documento técnico para una eventual integración en CGR.** El repositorio de origen es un PoC público e independiente basado en un TDR público. Este manual no acredita aprobación, acceso, despliegue ni conformidad institucional.

## 1. Objetivo

Este manual describe cómo pasar de la versión pública reproducible a una instalación controlada dentro de infraestructura institucional, procurando que la adaptación se concentre en **fuentes, mappings, secretos, ambientes y gobierno**, sin reescribir los modelos por cambios de nombres físicos de tablas o columnas.

El resultado esperado del aterrizaje es:

```text
fuentes CGR aprobadas
      |
connector + mapping
      |
esquema canónico validado
      |
+-----+-------------------+
|                         |
TRAIN histórico           INFERENCE actual
|                         |
candidate Spark           champion Spark
|                         |
aprobación institucional  scores de priorización
|                         |
+-------------> registry--+
              |
       SQL Server / SSRS
```

## 2. Qué debe proporcionar la CGR

Antes de ejecutar el software con información institucional se necesitan, como mínimo, los elementos asociados a las dependencias `CGR-DEP-01..08`.

| Frente | Insumo/decisión institucional necesaria |
|---|---|
| Fuentes | tablas/vistas aprobadas, diccionario, linaje y permisos de lectura |
| Ground truth | histórico etiquetado para favoritismo/fraccionamiento y criterio de validación |
| Infraestructura | DEV/QA/PROD, Spark, almacenamiento y orquestación aprobados |
| Seguridad | identidad, roles, secretos, repositorio privado y segregación de funciones |
| MLOps | autoridad que aprueba/promueve modelos y ubicación del registry institucional |
| Reporting | SQL Server/SSRS, datasource, permisos y ruta de publicación |
| Aceptación | umbrales de métricas, casos de prueba, responsables y evidencias de conformidad |
| Operación | responsables de monitoreo, incidentes, rollback y mantenimiento normativo |

Sin esos elementos el repositorio puede demostrar el software, pero no declarar integración o certificación institucional.

## 3. Roles recomendados para el aterrizaje

Los nombres concretos pueden variar según la organización; lo importante es separar responsabilidades:

- **Administrador de plataforma:** repositorio, runtimes, Spark/Airflow, almacenamiento y despliegue.
- **Administrador/owner de datos:** vistas, diccionario, calidad, permisos y linaje.
- **Equipo analítico/científico de datos:** validación de features, métricas, candidate y drift.
- **Especialista funcional/auditor:** ground truth, interpretación de señales y aceptación funcional.
- **Seguridad:** secretos, cuentas de servicio, privilegios mínimos y revisión de datos sensibles.
- **Aprobador de modelo:** autoridad diferente del proceso automático de TRAIN.
- **Administrador SQL Server/SSRS:** DDL, datasource, RDL y permisos de reportes.

El código no debe utilizarse para reemplazar estos controles de gobierno.

## 4. Fase 0 — Congelar el punto de partida

### 4.1 Llevar el código a un repositorio institucional

Antes de introducir datos o secretos reales:

1. clonar el repositorio público;
2. crear/migrar a un repositorio privado institucional;
3. verificar permisos por rol;
4. mantener referencia al commit de origen para trazabilidad;
5. ejecutar CI sin datos institucionales;
6. evitar que cualquier output real pueda volver al remoto público.

El snapshot `v1.0.0-rc.1` es histórico. Para integración debe partirse de una revisión de `main` que contenga la capa institution-ready y la auditoría integral vigente.

### 4.2 Baseline mínimo

En una estación/runner limpio:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

Requisitos adicionales según uso:

- Java 17 para Spark;
- `pyodbc` + driver ODBC aprobado para SQL Server;
- Graphviz para gráficos del PoC;
- Airflow en entorno virtual/imagen independiente si se usarán DAGs;
- LibreOffice únicamente para regeneración/QA documental.

**Gate 0:** el repositorio debe pasar pruebas sin conectarse a datos internos.

## 5. Fase 1 — Diseñar las fuentes institucionales

### 5.1 Dominios canónicos

El repositorio entiende cinco dominios:

| Dominio | Propósito |
|---|---|
| `contracts` | contratos y atributos necesarios para scoring |
| `suppliers` | dimensión de proveedores |
| `entities` | dimensión de entidades |
| `officials` | dimensión/vínculos de funcionarios cuando exista base legal y permiso |
| `payments` | pagos/devengados/girados vinculados a contrato |

`contracts` es el mínimo obligatorio para el serving de los modelos. Los otros dominios se habilitan cuando el caso de uso y la fuente los requieren.

### 5.2 Campos obligatorios de contracts

INFERENCE requiere que existan en el mapping:

```text
id_contrato
id_proveedor
id_entidad
monto
fecha_contrato
modalidad
objeto
```

Las claves estructurales y `fecha_contrato` no pueden llegar nulas. `monto`, `modalidad` y `objeto` pueden contener nulos porque el quality gate/preprocesamiento tiene tratamiento explícito.

TRAIN requiere además:

```text
label_favoritismo
label_fraccionamiento
```

Los labels deben provenir de una definición institucional aprobada de ground truth. No deben inferirse automáticamente de los scores del mismo modelo.

### 5.3 Pagos

El dominio `payments` admite:

```text
id_pago
id_contrato
fecha_devengado
fecha_girado
fecha_pagado
monto_devengado
monto_pagado
estado
```

`id_pago` e `id_contrato` son las claves estructurales requeridas por el contrato canónico.

### 5.4 Vistas recomendadas

El conector SQL Server del repositorio **no recibe SQL libre desde YAML**. Ejecuta una proyección `SELECT columnas FROM tabla_o_vista` sobre identificadores configurados.

Por ello, si el origen institucional necesita joins, filtros, reglas de vigencia o consolidación SIAF/SEACE, la opción recomendada es que el equipo de datos publique **vistas estables y aprobadas**, por ejemplo una vista por dominio. Esto permite:

- controlar el SQL en la base de datos;
- revisar planes de ejecución;
- aplicar permisos mínimos;
- versionar el diccionario y linaje;
- mantener el ML desacoplado del modelo físico.

**Gate 1:** cada campo canónico debe tener fuente, definición, owner y regla de calidad conocidas.

## 6. Fase 2 — Configurar la integración

Copiar la plantilla fuera del control de versiones:

```bash
cp config/cgr.example.yaml config/cgr.yaml
```

`config/cgr.yaml` está ignorado por Git.

La dirección del mapping es siempre:

```yaml
campo_canonico: COLUMNA_FISICA
```

Ejemplo abreviado para INFERENCE:

```yaml
mode: inference

source:
  type: sqlserver
  connection_env: CGR_SOURCE_DATABASE_URL
  tables:
    contracts: dbo.VW_CONTRATOS_MODULO
    payments: dbo.VW_PAGOS_MODULO

mapping:
  contracts:
    id_contrato: ID_CONTRATO_FUENTE
    id_proveedor: ID_PROVEEDOR_FUENTE
    id_entidad: ID_ENTIDAD_FUENTE
    monto: MONTO_CONTRATO_FUENTE
    fecha_contrato: FECHA_CONTRATO_FUENTE
    modalidad: MODALIDAD_FUENTE
    objeto: OBJETO_CONTRATO_FUENTE
  payments:
    id_pago: ID_PAGO_FUENTE
    id_contrato: ID_CONTRATO_FUENTE
    fecha_devengado: FECHA_DEVENGADO_FUENTE
    fecha_pagado: FECHA_PAGADO_FUENTE
    monto_pagado: MONTO_PAGADO_FUENTE
```

Los nombres del ejemplo son placeholders. Deben reemplazarse por objetos institucionalmente aprobados.

## 7. Fase 3 — Secretos, conectividad y Spark

### 7.1 SQL Server

El YAML solo referencia el nombre de una variable:

```yaml
connection_env: CGR_SOURCE_DATABASE_URL
```

La cadena real se suministra por el mecanismo aprobado por la institución:

```bash
export CGR_SOURCE_DATABASE_URL='<cadena ODBC suministrada por infraestructura>'
```

No colocar passwords, tokens ni connection strings dentro del YAML. El cargador rechaza secrets inline.

El entorno debe instalar `pyodbc` y el driver ODBC aprobado. La aplicación no impone un driver específico.

### 7.2 Spark operacional

TRAIN e INFERENCE permiten configurar el master efectivo:

```bash
export CGR_SPARK_MASTER='<master Spark aprobado>'
export CGR_SPARK_SHUFFLE_PARTITIONS='<particiones aprobadas>'  # opcional
```

Si `CGR_SPARK_MASTER` no existe, el PoC usa `local[*]` como fallback para ejecución local. La reproducción histórica continúa fijando `local[*]` deliberadamente. TRAIN/INFERENCE registran el valor efectivo de `spark.sparkContext.master` en su evidencia.

La institución debe definir el valor compatible con su plataforma (`yarn`, Kubernetes u otro master válido), así como memoria, cores, dynamic allocation y demás propiedades por sus mecanismos de despliegue.

### 7.3 `spark_sql`: límite de escala que debe validarse

El conector `spark_sql` usa `SparkSession.table(...).select(...)`, pero la capa canónica pública actual materializa después el resultado con `toPandas()` para compartir el mismo contrato de validación usado por CSV y SQL Server. TRAIN/INFERENCE convierten posteriormente ese contrato nuevamente a Spark antes de ejecutar MLlib.

Esto significa que:

- los **modelos y feature engineering operacionales sí corren con Spark MLlib**;
- la **ingesta canónica no es Spark-native end-to-end** en esta versión pública;
- no debe usarse esta ruta para afirmar capacidad distribuida sobre un volumen que no quepa de forma segura en memoria del driver.

Para una implantación de gran volumen hay dos patrones razonables, a decidir con la arquitectura CGR:

1. extender la integración canónica para conservar un DataFrame Spark desde la fuente hasta el preprocesamiento; o
2. materializar tablas/vistas canónicas previamente en el Lakehouse institucional y hacer que TRAIN/INFERENCE las consuman de forma nativa.

Ambas opciones preservan nombres canónicos, features y modelos; la adaptación está en la frontera de ingesta. Debe resolverse y probarse con el volumen/topología reales antes de QA/PROD si la escala lo exige.

**Gate 2:** la aplicación debe conectarse con identidad de mínimo privilegio y la arquitectura debe demostrar que el mecanismo de ingesta es adecuado para el volumen objetivo.

## 8. Fase 4 — Validar antes de leer datos

Validación estática del YAML:

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --validate-only
```

Este comando comprueba, entre otros:

- `source.type` soportado;
- modo `training`/`inference`;
- dominios conocidos;
- campos canónicos;
- campos obligatorios de contracts;
- mappings duplicados;
- correspondencia mapping ↔ fuente;
- ausencia de secrets inline.

No abre conexión y no escribe datos.

**Gate 3:** `--validate-only` debe terminar correctamente antes de cualquier acceso real.

## 9. Fase 5 — Prueba controlada de lectura en DEV

Ejecutar la integración en un entorno con permisos controlados. Para datos sensibles, usar un directorio seguro fuera del working tree:

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --output-dir /ruta/segura/integracion_preview
```

El manifest de integración reporta filas y columnas canónicas. Verificar al menos:

- IDs conservados como texto;
- ausencia de truncamiento de ceros a la izquierda;
- fechas convertibles;
- montos numéricos;
- nulos estructurales = 0;
- cardinalidades razonables;
- relaciones contract–supplier/entity/payments consistentes;
- ausencia de columnas no autorizadas en el dataset canónico.

No versionar el preview institucional.

**Gate 4:** owner de datos + equipo analítico aprueban el contrato canónico de DEV.

## 10. Fase 6 — Configuración de TRAIN

Crear un archivo separado, por ejemplo `config/cgr-training.yaml`:

```yaml
mode: training
```

El mapping de `contracts` debe incluir los labels físicos aprobados:

```yaml
mapping:
  contracts:
    # ...campos operacionales...
    label_favoritismo: LABEL_FAVORITISMO_APROBADO
    label_fraccionamiento: LABEL_FRACCIONAMIENTO_APROBADO
```

Antes de entrenar, documentar:

- definición de cada etiqueta;
- periodo temporal cubierto;
- quién la validó;
- reglas de inclusión/exclusión;
- desbalance de clases;
- tratamiento de casos inciertos;
- partición temporal/holdout acordada;
- métricas y umbrales de aceptación institucional.

**No usar como ground truth una etiqueta derivada del score del propio modelo.**

## 11. Fase 7 — Entrenar un candidate Spark

```bash
.venv/bin/python src/spark/entrenar_candidato_spark.py \
  --config config/cgr-training.yaml
```

El proceso debe producir un **candidate**, no modificar el champion activo.

Artefactos de candidate se ubican por defecto bajo:

```text
outputs/runtime/spark_model_candidates/
```

En producción institucional esa ubicación puede sustituirse por almacenamiento/registry corporativo.

Revisar antes de promover:

- manifest del candidate;
- versión de código/commit;
- hash de artefactos;
- estado de preprocesamiento;
- configuración/hyperparámetros;
- métricas de validación;
- master/recursos Spark efectivos;
- estabilidad por periodo/segmento;
- capacidad operativa de revisión humana;
- observaciones del especialista funcional.

**Gate 5:** un candidate nunca se convierte en champion por el mero hecho de entrenarse.

## 12. Fase 8 — Promoción y gobierno del modelo

El PoC contiene una promoción técnica explícita:

```bash
.venv/bin/python src/promover_candidato_spark.py \
  --manifest outputs/runtime/spark_model_candidates/candidate_manifest.json \
  --approved-by "responsable autorizado" \
  --acknowledge-poc-only
```

Esta operación **no equivale a aprobación CGR**. El registry público conserva `institutional_approval=false`.

Para QA/PROD, la institución debe decidir si:

- envuelve este paso en un workflow aprobado;
- reemplaza el registry local por MLflow/u otra plataforma corporativa;
- exige firma/aprobación dual;
- separa cuenta de entrenamiento de cuenta de promoción;
- registra ticket, acta o evidencia equivalente;
- implementa rollback al champion anterior.

Condición mínima recomendada: TRAIN no debe tener permisos para promover automáticamente a PROD.

## 13. Fase 9 — INFERENCE institucional

Con un champion aprobado técnicamente y configuración `mode: inference`:

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/cgr.yaml \
  --registry outputs/model_registry.json \
  --output-dir /ruta/segura/inference
```

El scorer:

1. integra contratos actuales al esquema canónico;
2. carga registry/champion;
3. verifica integridad SHA-256;
4. carga el estado de preprocesamiento congelado;
5. aplica TRANSFORM sin FIT;
6. genera features Spark;
7. carga modelos MLlib persistidos;
8. produce scores;
9. vuelve a comprobar que el champion no cambió durante scoring.

La ruta de INFERENCE no debe recibir labels y no debe ejecutar tuning/training.

**Gate 6:** comprobar en QA que `labels_consumed=false`, `training_invoked=false` y `tuning_invoked=false` en la evidencia de serving equivalente, y que `spark_mode` corresponde al master aprobado.

## 14. Fase 10 — Pagos y modalidades

El módulo de pagos consume `contracts + payments`:

```bash
.venv/bin/python src/analisis_pagos_modalidades.py \
  --config config/cgr.yaml
```

Produce:

- resumen por contrato;
- montos devengados/pagados;
- ratio pagado / monto contractual;
- estados analíticos de pago;
- percentiles de demora;
- agregación de modalidades por régimen;
- clasificación **referencial** frente a cuantía.

La clasificación normativa **no declara ilegalidad**. Categorías como Contratación Directa, Comparación de Precios, Subasta Inversa, catálogos/acuerdos marco u otros supuestos pueden depender de hechos que no se deducen del monto.

Antes de usar este módulo con datos reales, el repositorio debe estar dentro del perímetro institucional, porque los CSV detallados pueden contener identificadores de contrato y montos.

## 15. Fase 11 — Airflow institucional

DAGs relevantes:

```text
reproducibilidad_poc_1_8_2
entrenamiento_candidato_1_8_2
inferencia_modelos_1_8_2
monitoreo_reentrenamiento_1_8_2
```

Variables soportadas/relevantes para TRAIN/INFERENCE:

```text
PROYECTO_DIR
CGR_PROJECT_PYTHON
CGR_DATA_CONFIG
CGR_TRAIN_CONFIG
CGR_MODEL_REGISTRY
CGR_INFERENCE_OUTPUT_DIR
CGR_SPARK_CANDIDATE_MANIFEST
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
```

Ejemplo conceptual:

```bash
export PROYECTO_DIR=/opt/cgr/modulo-analisis
export CGR_PROJECT_PYTHON=/opt/cgr/modulo-analisis/.venv/bin/python
export CGR_DATA_CONFIG=/secure/config/cgr.yaml
export CGR_TRAIN_CONFIG=/secure/config/cgr-training.yaml
export CGR_MODEL_REGISTRY=/secure/models/model_registry.json
export CGR_INFERENCE_OUTPUT_DIR=/secure/outputs/inference
export CGR_SPARK_MASTER='<master institucional>'
```

No almacenar secretos en variables de Airflow visibles para usuarios no autorizados; utilizar el backend/gestor de secretos institucional que corresponda.

## 16. Fase 12 — SQL Server y SSRS

El repositorio incluye:

```text
ssrs/schema_sql_server.sql
ssrs/ReporteRiesgoFavoritismo.rdl
ssrs/ReporteRiesgoFraccionamiento.rdl
```

`src/publicar_ssrs.py` es un stand-in local para validar contrato, columnas y conteos. No despliega en un servidor CGR.

Para cierre institucional:

1. revisar/adaptar DDL con DBA;
2. crear objetos en DEV;
3. definir datasource y cuenta de lectura de SSRS;
4. cargar salidas aprobadas;
5. desplegar RDL en carpeta institucional;
6. validar filtros, permisos y tiempos de consulta;
7. probar QA con usuarios funcionales;
8. promover a PROD mediante el proceso estándar.

**Gate 7:** la existencia de los RDL en Git no equivale a publicación SSRS.

## 17. Fase 13 — Monitoreo y reentrenamiento

El proyecto incluye autoevaluación/monitor de solo lectura y un DAG mensual de referencia. En operación deben definirse institucionalmente:

- frecuencia real;
- features vigiladas;
- umbrales de drift;
- ground truth disponible y latencia de etiquetado;
- métricas mínimas;
- responsable de investigar alertas;
- condición que habilita nuevo TRAIN;
- criterio de rollback;
- retención de logs y auditoría.

Reentrenamiento produce candidate. **No debe haber autopromoción silenciosa.**

## 18. Fase 14 — Seguridad y datos sensibles

Checklist mínimo antes de QA/PROD:

- repositorio privado institucional;
- cuentas de servicio separadas por ambiente;
- privilegio mínimo de lectura en fuentes;
- secretos fuera del repo;
- salida de INFERENCE en almacenamiento autorizado;
- PII restringida a quienes la necesiten;
- cifrado en tránsito/en reposo conforme política institucional;
- logs sin credenciales ni payloads sensibles innecesarios;
- retención y purga definidas;
- auditoría de promociones de modelo;
- segregación TRAIN/promoción/PROD;
- revisión de dependencias y vulnerabilidades;
- backups/rollback del registry y salidas críticas.

El PoC no define políticas internas de CGR; estas deben prevalecer sobre cualquier ejemplo de este manual.

## 19. Fase 15 — DEV → QA → PROD

Secuencia recomendada:

### DEV

- mappings y vistas;
- conectividad;
- calidad de datos;
- TRAIN inicial;
- pruebas unitarias/integración;
- medición de volumen máximo y memoria del driver;
- decisión sobre adaptador Spark-native si la escala lo requiere;
- performance preliminar;
- ajustes de reporting.

### QA

- datos representativos aprobados;
- validación de métricas contra umbrales institucionales;
- prueba del mecanismo de ingesta con volumen representativo;
- pruebas de permisos;
- pruebas de Airflow/Spark/SQL Server/SSRS;
- validación funcional por auditores;
- casos de error/rollback;
- documentación de incidencias.

### PROD

Solo después de conformidad QA:

- champion aprobado;
- configuración/secretos PROD;
- master/recursos Spark aprobados;
- frontera de ingesta adecuada al volumen PROD;
- datasource/reportes PROD;
- monitoreo activo;
- responsables de soporte definidos;
- plan de rollback probado.

## 20. Rollback

Antes de cada promoción guardar de forma trazable:

- `champion_id` anterior;
- registry anterior;
- hashes de artefactos;
- commit/tag de código;
- configuración de preprocesamiento;
- fecha/aprobador;
- motivo de promoción.

Ante degradación, error de datos o incidente:

1. detener nuevas ejecuciones si corresponde;
2. identificar último champion estable;
3. restaurar registry/artefactos aprobados;
4. verificar hashes;
5. ejecutar smoke controlado;
6. documentar incidente y causa;
7. reanudar solo con autorización.

El repo público demuestra hashes y promoción explícita; el mecanismo final de rollback debe integrarse al MLOps corporativo.

## 21. Criterios de aceptación del aterrizaje

Una instalación institucional puede considerarse técnicamente aterrizada cuando existe evidencia de que:

- la configuración real pasa `--validate-only`;
- las fuentes reales se convierten correctamente al esquema canónico;
- el mecanismo de ingesta soporta el volumen objetivo sin depender indebidamente de memoria del driver;
- el diccionario/linaje institucional está aprobado;
- los datos de TRAIN incluyen ground truth validado;
- candidate y champion están gobernados por aprobación explícita;
- INFERENCE opera sin labels/training/tuning;
- el master Spark efectivo coincide con la configuración aprobada;
- el clúster cumple performance y robustez acordadas;
- SQL Server/SSRS funcionan con permisos institucionales;
- DEV/QA/PROD están separados;
- seguridad y secretos están validados;
- monitoreo/rollback están operativos;
- usuarios funcionales completaron certificación/marcha blanca;
- transferencia y entrega están formalizadas.

Hasta que existan estas evidencias, los estados 🟡/🔵 de la auditoría deben permanecer abiertos.

## 22. Mapeo de dependencias CGR

| ID | Cómo se cierra durante el aterrizaje |
|---|---|
| `CGR-DEP-01` | vistas/tablas, permisos, diccionario y linaje reales aprobados |
| `CGR-DEP-02` | revisión SQL + planes de ejecución en infraestructura real |
| `CGR-DEP-03` | ground truth y umbrales institucionales aprobados |
| `CGR-DEP-04` | repo privado, identidad, secretos y autorización institucional |
| `CGR-DEP-05` | DDL/RDL desplegados y validados en SQL Server/SSRS |
| `CGR-DEP-06` | pruebas y operación en DEV/QA/PROD/clúster institucional, incluida escala de ingesta |
| `CGR-DEP-07` | certificación de usuarios, incidencias y marcha blanca cerradas |
| `CGR-DEP-08` | transferencia, repositorio institucional y entrega formal |

La fuente canónica de estas dependencias es [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md).

## 23. Troubleshooting rápido

### `Falta la variable de entorno ... con la conexión SQL Server`

La variable indicada en `source.connection_env` no está disponible para el proceso. Revisar el gestor de secretos/entorno del runner.

### `El conector SQL Server requiere pyodbc...`

Instalar `pyodbc` y el driver ODBC aprobado en la imagen/host institucional.

### `mapping.contracts no define campos obligatorios`

Falta al menos un campo canónico requerido por el modo. Revisar `src/core/schemas.py` y el mapping institucional.

### `La fuente ... no contiene columnas configuradas`

El mapping referencia una columna física inexistente o el usuario no ve la versión esperada de la vista.

### Error por nulos en `id_contrato`, `id_proveedor`, `id_entidad` o `fecha_contrato`

Es una falla estructural de calidad. No se imputa automáticamente porque no existe una recuperación genérica segura.

### TRAIN pide labels pero INFERENCE no

Es intencional. Usar archivos de configuración separados con `mode: training` y `mode: inference`.

### El candidate no aparece como champion

Es intencional. TRAIN no promueve. La promoción es un gate separado.

### Spark sigue usando `local[*]`

Definir `CGR_SPARK_MASTER` en el entorno que lanza TRAIN/INFERENCE y comprobar el campo `spark_mode` de la evidencia generada. El fallback local es deliberado para el PoC.

### El proceso se queda sin memoria al usar `spark_sql`

La integración pública actual materializa el contrato canónico en pandas. Para volúmenes mayores, usar vistas/tablas canónicas y adaptar la frontera de ingesta a Spark nativo antes de considerar la ruta apta para PROD.

## 24. Documentos relacionados

- [`Integracion_Datos.md`](Integracion_Datos.md) — referencia técnica de conectores y esquema canónico.
- [`Train_Inference.md`](Train_Inference.md) — lifecycle de modelos y serving.
- [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md) — dependencias que no puede cerrar el repo público.
- [`Checklist_Anexo_03.md`](Checklist_Anexo_03.md) — estado de criterios del Anexo 3.
- [`Auditoria_TDR_Completo.md`](Auditoria_TDR_Completo.md) — auditoría integral del TDR público.
- `../config/cgr.example.yaml` — plantilla de configuración sin datos/secretos reales.

## 25. Regla final

El objetivo del aterrizaje no es “hacer que el PoC parezca productivo”. Es **sustituir de forma controlada los stand-ins públicos por fuentes, infraestructura, gobierno y evidencias institucionales reales**, preservando trazabilidad y evitando que una señal analítica se convierta automáticamente en una conclusión de control.
