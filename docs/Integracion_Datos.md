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

El conector no fuerza `local[*]`; toma el master/catálogo/seguridad del entorno Spark que lo ejecuta (`spark-submit`, Airflow, YARN, Kubernetes u otro mecanismo institucional). Selecciona columnas mediante la API DataFrame y devuelve el contrato para validación canónica.

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

Esas responsabilidades permanecen documentadas en [`Dependencias_Institucionales_CGR.md`](Dependencias_Institucionales_CGR.md).
