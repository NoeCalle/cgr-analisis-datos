# Integración SSRS — PoC independiente

Este directorio contiene el contrato de integración preparado para el criterio 7 del Anexo 3 del TDR público. El PoC valida localmente la forma de las salidas y la consistencia entre Oro, tablas de reporting y RDL; **no afirma un despliegue ejecutado en SQL Server/SSRS de la CGR**.

## Artefactos

- `schema_sql_server.sql`: DDL T-SQL, restricciones, índices y vistas estables de consumo.
- `security_roles_template.sql`: plantilla revisable de mínimo privilegio para publicación y lectura de reporting; no crea logins ni sustituye políticas CGR.
- `ReporteRiesgoFavoritismo.rdl`: reporte SSRS para señales de posible favoritismo.
- `ReporteRiesgoFraccionamiento.rdl`: reporte SSRS para señales de posible fraccionamiento.
- `reportes.db`: stand-in SQLite regenerable y no versionado.
- `../outputs/ssrs_publicacion_manifest.json`: evidencia de la publicación local, conteos, hashes de las fuentes Oro y dependencias institucionales pendientes.

## Contrato de datos

El reporting consume exclusivamente salidas Oro del PoC:

- `lakehouse/oro/ranking_riesgo_favoritismo.csv` → `PrediccionesFavoritismo` → `vw_SSRS_Favoritismo`.
- `lakehouse/oro/ranking_riesgo_fraccionamiento.csv` → `PrediccionesFraccionamiento` → `vw_SSRS_Fraccionamiento`.
- `lakehouse/oro/ranking_vinculos_proveedor_funcionario.csv` → `VinculosProveedorFuncionario` → `vw_SSRS_VinculosProveedorFuncionario`.

La publicación local valida claves primarias, columnas obligatorias, porcentajes en `[0,1]`, score de favoritismo en `[0,1]`, conteos no negativos y consultas equivalentes a los datasets de los RDL.

## Datasource compartido

Los RDL **no contienen hostname, catálogo ni credenciales**. Ambos referencian el datasource compartido `CGR_ModuloAnalisis`. En cada ambiente (DEV/QA/PROD), SSRS debe vincular ese nombre a un Shared Data Source administrado fuera del RDL, con servidor, catálogo, autenticación y cifrado aprobados para ese ambiente.

Esto evita que un cambio de infraestructura obligue a modificar los reportes y reduce el riesgo de versionar información de conexión.

## Reproducir

Desde la raíz del repositorio, después de generar Oro:

```bash
python src/publicar_ssrs.py
```

Luego puede inspeccionarse `outputs/ssrs_publicacion_manifest.json`. La base `ssrs/reportes.db` se genera solo para smoke tests y está en `.gitignore`.

## Mínimo privilegio

`security_roles_template.sql` separa dos capacidades de referencia:

- `CGR_Analisis_ReportReader`: `SELECT` únicamente sobre las vistas de reporting;
- `CGR_Analisis_Publisher`: DML únicamente sobre las tres tablas destino del módulo.

La identidad que lea SIAF/SEACE debe ser distinta y mantenerse en **SELECT-only** sobre las vistas/tablas autorizadas. El principal que ejecute DDL/despliegue debe ser también separado. La plantilla no se ejecuta automáticamente y debe revisarse con DBA/Seguridad CGR.

## Paso institucional pendiente

Para cerrar literalmente el criterio en CGR todavía se requiere:

1. revisar y ejecutar DDL/roles en SQL Server institucional;
2. crear el Shared Data Source `CGR_ModuloAnalisis` por ambiente, con cifrado/autenticación aprobados;
3. desplegar los RDL en SSRS institucional;
4. asignar principals reales a roles autorizados y validar permisos efectivos;
5. ejecutar pruebas en DEV/QA/PROD y registrar evidencia de operación/rendimiento.

Por ello el estado del criterio 7 es **🟡 PoC verificable / 🔵 cierre institucional pendiente**, no “producción completada”.
