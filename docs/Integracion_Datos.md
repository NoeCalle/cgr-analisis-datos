# Integración de datos — referencia técnica

Este documento describe la capa de integración configurable del PoC. Su objetivo es desacoplar los modelos de los nombres físicos de tablas y columnas de cualquier fuente externa o institucional.

> El repositorio sigue siendo un prototipo independiente. Los nombres de tablas/columnas de `config/cgr.example.yaml` son marcadores de posición y no representan el esquema real de la CGR.

Para el procedimiento completo de aterrizaje en infraestructura institucional, consultar [`Manual_Aterrizaje_Institucional_CGR.md`](Manual_Aterrizaje_Institucional_CGR.md).

## Principio

El código de ML trabaja contra un **esquema canónico**. Cada fuente se adapta mediante configuración:

```text
fuente física -> connector -> mapping YAML -> esquema canónico -> preprocesamiento/modelos
```

La dirección del mapping es siempre:

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
```

Con este mapping, los modelos no necesitan conocer `COD_PROV`, `IMP_ADJ` ni ningún otro nombre institucional.

## Modos

### inference

Es el modo para contratos actuales. No exige ground truth. Campos mínimos de `contracts`:

- `id_contrato`
- `id_proveedor`
- `id_entidad`
- `monto`
- `fecha_contrato`
- `modalidad`
- `objeto`

Que una columna sea obligatoria significa que **debe existir en la fuente/mapping**. Se permiten nulos en campos que el quality gate/preprocesamiento trata explícitamente (`monto`, `modalidad`, `objeto`). Las claves estructurales (`id_contrato`, `id_proveedor`, `id_entidad`) y `fecha_contrato` no pueden llegar nulas porque no existe una recuperación genérica segura.

Los labels no forman parte del contrato obligatorio de inferencia.

### training

Extiende el contrato anterior y exige:

- `label_favoritismo`
- `label_fraccionamiento`

Estos nombres son canónicos y no pueden ser nulos en entrenamiento. Una fuente histórica puede mapear cualquier columna de ground truth institucionalmente aprobada a esos campos.

## Dominios canónicos

La integración define contratos para:

- `contracts`
- `suppliers`
- `entities`
- `officials`
- `payments`

`payments` ya forma parte del análisis funcional de pagos, montos contractuales y modalidades. Su uso requiere `contracts + payments` y se ejecuta mediante `src/analisis_pagos_modalidades.py`.

El esquema exacto y las reglas de nulabilidad están en `src/core/schemas.py`.

## Fuentes soportadas

### local_csv

Mantiene la reproducción del PoC y permite fixtures/control de integración. Configuración ejecutable: `config/local.yaml`.

El conector lee inicialmente como texto para conservar identificadores con ceros a la izquierda; el esquema canónico convierte después montos, fechas y booleanos.

### sqlserver

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

No recibe SQL libre desde el YAML. Para joins, filtros o consolidaciones complejas, se recomienda publicar **vistas institucionales aprobadas** y mapearlas al esquema canónico.

### spark_sql

Usa `src/connectors/spark_sql.py` y tablas/vistas accesibles mediante `SparkSession.table`.

El conector no fija el master al crear su propia sesión y selecciona columnas mediante la API DataFrame. Sin embargo, la implementación pública actual termina materializando el resultado canónico con `toPandas()` porque `ingestar_canonico.py` comparte el mismo contrato pandas con `local_csv` y `sqlserver`.

Por tanto:

- el **entrenamiento y scoring de los modelos sí se ejecutan con Apache Spark MLlib**;
- el adaptador canónico público **no es todavía Spark-native end-to-end para volúmenes masivos**;
- `spark_sql` es adecuado para validación de integración y volúmenes que puedan materializarse de forma segura en el driver;
- una implantación institucional de gran volumen debe sustituir/extender esta frontera por un adaptador canónico Spark nativo o materializar previamente vistas/tablas canónicas dentro del Lakehouse institucional.

Ese endurecimiento no cambia las features ni los modelos: cambia únicamente cómo se materializa el contrato canónico antes del pipeline MLlib. Su diseño final debe validarse contra la topología, seguridad y tamaño real de los datos CGR.

## Configuración

La plantilla institucional es `config/cgr.example.yaml`.

Se recomienda copiarla a una ubicación/configuración privada:

```bash
cp config/cgr.example.yaml config/cgr.yaml
```

`config/cgr.yaml` y `config/*.local.yaml` están ignorados por Git.

La estructura general es:

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
```

Los nombres de objetos del ejemplo no representan objetos reales de CGR.

## Validación sin conectarse

```bash
python src/ingestar_canonico.py \
  --config config/cgr.example.yaml \
  --validate-only
```

Esto comprueba:

- estructura YAML;
- `source.type` válido (`local_csv`, `sqlserver`, `spark_sql`);
- modo válido (`training`, `inference`);
- dominios conocidos;
- campos canónicos;
- campos obligatorios de contracts;
- mappings duplicados;
- mappings con fuente configurada;
- ausencia de secrets inline.

No abre conexión ni escribe datasets.

## Preview end-to-end

Ejemplo local:

```bash
python src/ingestar_canonico.py --config config/local.yaml
```

Ejemplo institucional DEV, usando un directorio seguro fuera del repo:

```bash
python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --output-dir /ruta/segura/integracion_preview
```

El manifest contiene modo, tipo de fuente, dominios, filas y columnas. El preview no debe versionarse cuando contenga información institucional.

## Seguridad de configuración

El cargador rechaza claves de credenciales inline como:

- `password`
- `passwd`
- `pwd`
- `token`
- `secret`
- `api_key`
- `connection_string`

Las configuraciones versionables deben usar referencias `*_env`/`connection_env`.

El rechazo de secretos en YAML es una defensa del PoC, no sustituye el gestor de secretos, IAM ni las políticas institucionales.

## TRAIN e INFERENCE

La integración canónica alimenta las rutas operacionales separadas:

```text
TRAIN -> FIT preprocesamiento -> candidate -> promoción explícita -> champion

INFERENCE -> TRANSFORM congelado -> champion -> scores
```

TRAIN exige labels; INFERENCE no. INFERENCE no debe ejecutar `.fit()`, tuning ni reentrenamiento.

La sesión Spark operacional admite:

```text
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
```

Si `CGR_SPARK_MASTER` no se define, el PoC usa `local[*]` como fallback para ejecución local. En un despliegue institucional debe definirse el master aprobado (`yarn`, Kubernetes u otro valor válido para la plataforma adoptada). La corrida registra el master efectivo obtenido de `spark.sparkContext.master`.

Referencia: [`Train_Inference.md`](Train_Inference.md).

## Pagos y modalidades

Cuando la configuración contiene `contracts + payments`:

```bash
python src/analisis_pagos_modalidades.py --config config/cgr.yaml
```

El análisis genera ratios de pago, demoras, estados analíticos y agregaciones de modalidades/régimen. La comparación de modalidad frente a cuantía es **referencial** y no determina legalidad ni irregularidad.

La configuración local reproducible usa `config/local-tdr.yaml`.

## Alcance y límites

La capa de integración resuelve el **contrato de software** para desacoplar fuentes y modelos. No puede decidir desde este repositorio:

- nombres/joins reales de tablas CGR;
- credenciales y permisos;
- diccionario/linaje institucional aprobado;
- ground truth;
- infraestructura Spark/HDFS/YARN;
- política de secretos/identidad;
- umbrales productivos;
- SQL Server/SSRS real;
- DEV/QA/PROD, certificación o marcha blanca.

Además, la versión pública mantiene la frontera `Spark SQL -> pandas -> Spark MLlib` descrita arriba. Antes de afirmar escalabilidad distribuida end-to-end con datos institucionales debe validarse o reemplazarse esa frontera en el entorno CGR.

Esas responsabilidades permanecen documentadas en [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md).
