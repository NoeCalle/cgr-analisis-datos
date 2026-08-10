# Quality gates del contrato canónico

Esta capa se ejecuta **después del mapping/casteo canónico y antes del feature engineering/modelado**. Su objetivo es impedir que errores estructurales de fuente generen señales artificiales de riesgo.

## Versión del contrato

El contrato canónico vigente es `contract_schema_version: 1`.

Las configuraciones versionadas del repositorio lo declaran explícitamente. Por compatibilidad, una configuración histórica sin ese campo se interpreta como v1; una versión distinta se rechaza hasta que exista una migración explícita.

El `integration_manifest.json` registra tanto la versión del manifest como `contract_schema_version`.

## Claves primarias

Se exige unicidad para:

| Dominio | Clave primaria canónica |
|---|---|
| `contracts` | `id_contrato` |
| `suppliers` | `id_proveedor` |
| `entities` | `id_entidad` |
| `officials` | `id_funcionario` |
| `payments` | `id_pago` |

Los identificadores presentes no pueden ser cadenas vacías ni solo espacios. Los duplicados se rechazan antes de TRAIN/INFERENCE.

## Integridad referencial

Cuando ambos dominios están configurados, se comprueban estas relaciones:

```text
contracts.id_proveedor   -> suppliers.id_proveedor
contracts.id_entidad     -> entities.id_entidad
contracts.id_funcionario -> officials.id_funcionario
payments.id_contrato     -> contracts.id_contrato
```

`contracts.id_funcionario` sigue siendo opcional a nivel de fila; solo se valida contra `officials` cuando existe valor no nulo.

Si el dominio padre no fue configurado —por ejemplo un TRAIN mínimo que contiene únicamente `contracts`— la relación queda registrada como `skipped_parent_not_configured`. No se presenta como validada.

## Reglas estructurales adicionales

En `contracts`, un `monto` no nulo no puede ser negativo. Los nulos permitidos por el contrato continúan siendo responsabilidad del preprocesamiento congelado.

Estas reglas no intentan sustituir controles de negocio institucionales más específicos. Fechas, estados SIAF, catálogos, reversas de pago, consistencia presupuestal y otras reglas deben validarse con el diccionario y semántica aprobados por CGR.

## Pandas y Spark

`local_csv` y `sqlserver` aplican los gates sobre DataFrames pandas.

`spark_sql` aplica los mismos controles con agregaciones y `left_anti joins` distribuidos. Solo se colectan escalares de control o una pequeña muestra de claves si existe un error; el dataset contractual no se convierte a pandas.

Además, el conteo de filas Spark utilizado por el manifest se obtiene dentro del mismo gate de unicidad, eliminando el `count()` completo separado que antes ejecutaba `integrar_spark()`.

## SQL Server y escala

El conector `sqlserver` actual es deliberadamente un adaptador:

```text
SQL Server -> pandas -> contrato canónico -> pandas→Spark -> MLlib
```

Debe usarse para validación y volúmenes acotados. No se presenta como extracción distribuida.

Para grandes volúmenes, la ruta preferida del PoC es:

```text
Lakehouse / Spark SQL -> Spark DataFrame -> contrato canónico -> MLlib
```

No se incorpora todavía un conector `spark_jdbc` genérico porque una implementación robusta depende de decisiones institucionales que este repositorio no conoce: driver JDBC aprobado, URL/autenticación, columna/límites de particionamiento, número de particiones, aislamiento de lectura y estándares de infraestructura CGR. Agregar esos valores ficticiamente daría una falsa sensación de cierre. Cuando se conozcan, puede implementarse un adapter Spark JDBC conservando exactamente el mismo contrato canónico y los mismos quality gates.

## Validación offline

`--validate-only` valida estructura y mappings sin abrir conexiones. Si un dominio se declara en `mapping`, ahora debe contener todos sus campos obligatorios mínimos. Una dimensión no disponible se omite completa; ya no se acepta una configuración parcial que diga `CONFIG OK` y luego falle al integrar el DataFrame real.

## Evidencia

Los resultados quedan disponibles en:

```text
integration_manifest.json
  contract_schema_version
  quality.status
  quality.domains
  quality.foreign_keys
```

Las regresiones principales están en:

- `tests/test_data_quality_gates.py`
- `tests/test_config_contract.py`
- `tests/test_integracion_datos.py`
- `tests/test_spark_native_integration.py`
