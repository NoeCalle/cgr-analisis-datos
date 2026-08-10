# Integración de datos — referencia técnica

Este documento describe la capa configurable que desacopla los modelos de los nombres físicos de tablas y columnas de cualquier fuente externa o institucional.

> El repositorio sigue siendo un prototipo público e independiente. Los nombres de `config/cgr.example.yaml` son marcadores de posición y no representan el esquema real de la CGR.

Para el procedimiento completo de aterrizaje institucional, consultar [`Manual_Aterrizaje_Institucional_CGR.md`](Manual_Aterrizaje_Institucional_CGR.md).

## Principio

El código analítico trabaja contra un **esquema canónico**:

```text
fuente física -> connector -> mapping YAML -> esquema canónico -> preprocesamiento/modelos
```

La dirección del mapping es:

```text
campo_canónico: columna_física
```

Ejemplo:

```yaml
mapping:
  contracts:
    id_contrato: NRO_CONTRATO
    id_proveedor: COD_PROV
    id_entidad: SEC_EJEC
    monto: IMP_ADJ
    fecha_contrato: FEC_SUSC
    modalidad: TIP_PROC
    objeto: DESC_OBJ
    categoria_principal: CAT_PRINC
```

Los modelos no necesitan conocer nombres físicos como `COD_PROV` o `IMP_ADJ`.

## Modos

### inference

Se usa para contratos actuales. No exige ground truth. Campos obligatorios de `contracts`:

- `id_contrato`
- `id_proveedor`
- `id_entidad`
- `monto`
- `fecha_contrato`
- `modalidad`
- `objeto`
- `categoria_principal`

Que una columna sea obligatoria significa que **debe existir en la fuente/mapping**. `monto`, `modalidad`, `objeto` y `categoria_principal` pueden contener nulos porque existe tratamiento/fallback explícito. Las claves estructurales y `fecha_contrato` no pueden llegar nulas.

`categoria_principal` es estructuralmente necesaria para el análisis de fraccionamiento porque permite resolver el contexto normativo; un valor nulo puede utilizar el fallback del proveedor de umbrales, pero la columna no debe desaparecer del contrato.

Los labels no forman parte del contrato de INFERENCE.

### training

Extiende el contrato anterior y exige:

- `label_favoritismo`
- `label_fraccionamiento`

Estos nombres son canónicos, no pueden ser nulos en TRAIN y deben provenir de un ground truth institucionalmente aprobado cuando la solución se implante con datos reales.

## Dominios canónicos

La integración define contratos para:

- `contracts`
- `suppliers`
- `entities`
- `officials`
- `payments`

`payments` forma parte del análisis de pagos, montos contractuales y modalidades mediante `src/analisis_pagos_modalidades.py`.

Las reglas canónicas están en `src/core/schemas.py`; la implementación equivalente para DataFrames Spark está en `src/core/schemas_spark.py`.

## Fuentes soportadas

### `local_csv`

Mantiene la reproducción local y fixtures de integración. El conector lee inicialmente como texto para preservar identificadores con ceros a la izquierda; el esquema canónico convierte después montos, fechas y booleanos.

Ruta de ejecución:

```text
CSV -> pandas -> mapping/validación canónica -> adaptador pandas→Spark cuando entra al ML operacional
```

### `sqlserver`

Usa `src/connectors/sqlserver.py`.

La configuración contiene únicamente el nombre de una variable de entorno:

```yaml
source:
  type: sqlserver
  connection_env: CGR_SOURCE_DATABASE_URL
```

La cadena real no se versiona. El entorno institucional debe proporcionar `pyodbc` y el driver ODBC aprobado.

El conector construye únicamente una proyección de identificadores configurados:

```text
SELECT columnas_configuradas FROM tabla_o_vista_configurada
```

No recibe SQL libre desde YAML. Para joins, filtros o consolidaciones complejas se recomienda publicar **vistas institucionales aprobadas** y mapearlas al esquema canónico.

Ruta operacional:

```text
SQL Server -> pandas -> mapping/validación canónica -> adaptador pandas→Spark -> MLlib
```

Este adapter es deliberado: no se presenta como procesamiento distribuido de la extracción SQL Server.

### `spark_sql`

Usa `src/connectors/spark_sql.py` y tablas/vistas accesibles mediante `SparkSession.table(...)`.

Esta ruta es **Spark-native end-to-end**:

```text
Spark SQL / Lakehouse
        -> Spark DataFrame
        -> mapping canónico Spark
        -> casteo y validación Spark
        -> FIT/TRANSFORM Spark
        -> feature engineering Spark
        -> MLlib
        -> Parquet distribuido
```

El conector devuelve un DataFrame Spark y no llama `toPandas()`. `src/ingestar_canonico.py` separa explícitamente `integrar()` (pandas) de `integrar_spark()`; intentar enviar `spark_sql` por la ruta pandas falla de forma explícita para evitar un collect accidental.

`src/core/schemas_spark.py` aplica mapping, tipos, conversiones inválidas y reglas de nulabilidad mediante expresiones/agregaciones Spark. Solo se colectan al driver resultados escalares de validación, no el dataset contractual.

## Preprocesamiento distribuido

Para `spark_sql`, TRAIN utiliza `src/spark/ajustar_preprocesamiento_spark.py`.

El FIT calcula de forma distribuida:

- mediana de monto por objeto;
- mediana global;
- moda de modalidad;
- moda de objeto;
- P99 de monto.

La dimensión `objeto -> mediana` puede ser grande, por lo que en la ruta operacional se persiste como **Parquet Spark** en vez de convertirla a un diccionario pandas/Python. El JSON del preprocesador conserva los escalares y marca que las medianas por objeto son externas. La promoción del candidate incorpora ambos artefactos al champion.

INFERENCE vuelve a leer ese Parquet con Spark y aplica el estado congelado sin `.fit()`.

## Salida distribuida

Cuando la fuente es `spark_sql`, los rankings detallados de INFERENCE se escriben como directorios Parquet distribuidos:

```text
ranking_riesgo_favoritismo_spark.parquet/
ranking_riesgo_fraccionamiento_spark.parquet/
```

Para fuentes pandas (`local_csv`/`sqlserver`), el PoC conserva CSV de archivo único por compatibilidad local.

La evidencia de serving registra, entre otros:

```text
input_engine
spark_native_ingestion
pandas_materialization
spark_mode
detail_outputs.format
```

En una corrida `spark_sql` válida se espera:

```text
input_engine = spark_native
spark_native_ingestion = true
pandas_materialization = false
detail_outputs.format = parquet_distributed
```

## Spark master y recursos

TRAIN/INFERENCE operacionales admiten:

```text
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
```

Si `CGR_SPARK_MASTER` no se define, el PoC usa `local[*]` como fallback local. La ruta histórica de reproducibilidad conserva `local[*]` deliberadamente.

En un entorno institucional el master, memoria, cores, dynamic allocation, catálogo, autenticación y demás opciones deben definirse por los mecanismos de la plataforma adoptada. La evidencia registra el `spark.sparkContext.master` efectivo.

## Configuración

Plantilla: `config/cgr.example.yaml`.

Copiarla a una ubicación privada/no versionada:

```bash
cp config/cgr.example.yaml config/cgr.yaml
```

Ejemplo abreviado:

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
    categoria_principal: CATEGORIA_PRINCIPAL_FUENTE
```

Los nombres son placeholders y no representan objetos reales CGR.

## Validación sin conectarse

```bash
python src/ingestar_canonico.py \
  --config config/cgr.example.yaml \
  --validate-only
```

Valida:

- estructura YAML;
- `source.type` (`local_csv`, `sqlserver`, `spark_sql`);
- modo (`training`/`inference`);
- dominios conocidos;
- campos canónicos;
- campos obligatorios;
- mappings duplicados;
- correspondencia mapping ↔ fuente;
- ausencia de secrets inline.

No abre conexión ni escribe datasets.

## Preview de integración

```bash
python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --output-dir /ruta/segura/integracion_preview
```

Para fuentes pandas el preview se materializa como CSV. Para `spark_sql`, `integrar_spark()` escribe directorios CSV distribuidos de preview y un manifest; no colecta el dataset al driver.

Cualquier preview con datos institucionales debe mantenerse fuera del repositorio público.

## Seguridad de configuración

El cargador rechaza secretos inline como:

- `password`
- `passwd`
- `pwd`
- `token`
- `secret`
- `api_key`
- `connection_string`

Las configuraciones versionables deben usar referencias `*_env`/`connection_env`. Esto no sustituye IAM, gestor de secretos ni políticas institucionales.

## TRAIN e INFERENCE

```text
TRAIN -> FIT preprocesamiento -> candidate -> promoción explícita -> champion

INFERENCE -> TRANSFORM congelado -> champion -> scores
```

TRAIN exige labels; INFERENCE no. INFERENCE no ejecuta `.fit()`, tuning ni reentrenamiento.

Referencia: [`Train_Inference.md`](Train_Inference.md).

## Pagos y modalidades

Cuando la configuración contiene `contracts + payments`:

```bash
python src/analisis_pagos_modalidades.py --config config/cgr.yaml
```

El módulo genera ratios de pago, demoras, estados analíticos y agregaciones de modalidades/régimen. La comparación de modalidad frente a cuantía es **referencial** y no determina legalidad ni irregularidad.

La configuración local reproducible usa `config/local-tdr.yaml`.

## Garantías de regresión

`tests/test_spark_native_integration.py` protege la frontera distribuida. Entre otras cosas verifica que:

- `spark_sql` devuelve `pyspark.sql.DataFrame`;
- mapping y validación no convierten a pandas;
- labels se tipan correctamente en TRAIN;
- valores físicos no convertibles fallan;
- medianas por objeto se persisten como Parquet;
- rankings spark-native se escriben como Parquet distribuido;
- `spark_sql.py`, TRAIN e INFERENCE no contengan `.toPandas()`;
- la ruta pandas rechace `spark_sql` para impedir collects implícitos.

## Alcance y límites

La capa de integración resuelve el **contrato de software** y ya ofrece una frontera Spark-native para Lakehouse/Spark SQL. Aun así, este repositorio no puede decidir o validar por sí solo:

- nombres/joins reales de tablas CGR;
- credenciales y permisos;
- diccionario/linaje institucional aprobado;
- ground truth;
- clúster y catálogo Spark institucional;
- particionamiento, performance y robustez al volumen real;
- política de secretos/identidad;
- umbrales productivos;
- SQL Server/SSRS real;
- DEV/QA/PROD, certificación o marcha blanca.

La existencia de una ruta distribuida elimina el cuello de botella pandas que tenía el adaptador anterior, pero **no sustituye las pruebas de carga y operación sobre la infraestructura institucional real**.

Estas responsabilidades permanecen en [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md).
