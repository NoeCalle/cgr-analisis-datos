# Integración de datos — Sprint 1

Este documento describe la primera capa *institution-ready* del PoC. El objetivo es desacoplar los modelos de los nombres físicos de tablas y columnas de cualquier fuente externa.

> El repositorio sigue siendo un prototipo independiente. Los nombres de tablas/columnas de `config/cgr.example.yaml` son marcadores de posición y no representan el esquema real de la CGR.

## Principio

El código de ML trabaja contra un **esquema canónico**. Cada institución adapta su fuente mediante configuración:

`fuente física -> connector -> mapping YAML -> esquema canónico -> preprocesamiento/modelos`

La dirección del mapping es siempre:

`campo_canónico: columna_física`

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

Con este mapping, los modelos no necesitan conocer `COD_PROV`, `IMP_ADJ` ni ningún nombre institucional.

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

Que una columna sea obligatoria significa que **debe existir en la fuente/mapping**. En esta capa de entrada se permiten nulos en campos que el quality gate ya sabe tratar (`monto`, `modalidad`, `objeto`); no se imputan silenciosamente aquí. Las claves estructurales (`id_contrato`, `id_proveedor`, `id_entidad`) y `fecha_contrato` no pueden llegar nulas porque no existe una recuperación segura genérica.

Los labels no forman parte del contrato obligatorio de inferencia.

### training

Extiende el contrato anterior y exige:

- `label_favoritismo`
- `label_fraccionamiento`

Estos nombres son canónicos y no pueden ser nulos en entrenamiento. Una fuente histórica puede mapear cualquier columna aprobada de ground truth a esos campos.

## Dominios canónicos

El Sprint 1 define contratos para:

- `contracts`
- `suppliers`
- `entities`
- `officials`
- `payments`

`payments` queda preparado como contrato de integración; su incorporación al análisis funcional se realizará en una fase posterior si corresponde.

## Fuentes soportadas por la capa de integración

### local_csv

Mantiene la reproducción actual del PoC. Configuración ejecutable: `config/local.yaml`. El conector lee inicialmente como texto para conservar identificadores con ceros a la izquierda; el esquema canónico convierte después montos, fechas y booleanos.

### sqlserver

Usa `src/connectors/sqlserver.py`. La configuración solo contiene el nombre de una variable de entorno, por ejemplo:

```yaml
source:
  type: sqlserver
  connection_env: CGR_SOURCE_DATABASE_URL
```

La cadena real no se versiona. El entorno institucional deberá proporcionar `pyodbc` y el driver ODBC aprobado. Tablas y columnas se tratan como identificadores T-SQL escapados, no como fragmentos de SQL libre.

### spark_sql

Usa tablas o vistas accesibles mediante `SparkSession.table`. El conector no fuerza `local[*]`; toma la configuración del entorno Spark que lo ejecute y selecciona columnas mediante la API de DataFrame.

## Validación sin conectarse

La plantilla institucional puede validarse sin disponer de infraestructura:

```bash
python src/ingestar_canonico.py --config config/cgr.example.yaml --validate-only
```

Esto comprueba estructura, dominios, campos canónicos, mappings duplicados, correspondencia entre mappings y fuentes y ausencia de secrets inline.

## Preview local end-to-end

```bash
python src/ingestar_canonico.py --config config/local.yaml
```

Por defecto genera un preview regenerable en `outputs/integracion_canonica/`. Esa ruta está ignorada por Git porque una configuración institucional podría producir datos sensibles.

## Seguridad de configuración

El cargador rechaza claves de credenciales inline como `password`, `token`, `secret`, `api_key` o `connection_string`. La configuración versionada debe usar referencias `*_env`/`connection_env`.

`config/cgr.yaml` y `config/*.local.yaml` están ignorados por Git.

## Qué todavía no hace este Sprint 1

Este sprint **no** sustituye aún el DAG sintético ni separa el entrenamiento de la inferencia de los modelos existentes. Tampoco publica directamente en infraestructura CGR. Esas transformaciones pertenecen a los siguientes sprints.

El criterio de cierre de Sprint 1 es más acotado: una fuente con nombres arbitrarios debe poder convertirse al contrato canónico mediante configuración, sin editar el código de ML.
