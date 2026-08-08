# Integración SSRS — PoC independiente

Este directorio contiene el contrato de integración preparado para el criterio 7 del Anexo 3 del TDR público. El PoC valida localmente la forma de las salidas y la consistencia entre Oro, tablas de reporting y RDL; **no afirma un despliegue ejecutado en SQL Server/SSRS de la CGR**.

## Artefactos

- `schema_sql_server.sql`: DDL T-SQL, restricciones, índices y vistas estables de consumo.
- `ReporteRiesgoFavoritismo.rdl`: reporte SSRS para señales de posible favoritismo.
- `ReporteRiesgoFraccionamiento.rdl`: reporte SSRS para señales de posible fraccionamiento.
- `reportes.db`: stand-in SQLite regenerable y no versionado.
- `../outputs/ssrs_publicacion_manifest.json`: evidencia de la publicación local, conteos, hashes de las fuentes Oro y dependencias institucionales pendientes.

## Contrato de datos

El reporting consume exclusivamente salidas Oro del PoC:

- `lakehouse/oro/ranking_riesgo_favoritismo.csv` → `PrediccionesFavoritismo` → `vw_SSRS_Favoritismo`.
- `lakehouse/oro/ranking_riesgo_fraccionamiento.csv` → `PrediccionesFraccionamiento` → `vw_SSRS_Fraccionamiento`.
- `lakehouse/oro/ranking_vinculos_proveedor_funcionario.csv` → `VinculosProveedorFuncionario`.

La publicación local valida claves primarias, columnas obligatorias, porcentajes en `[0,1]`, score de favoritismo en `[0,1]`, conteos no negativos y consultas equivalentes a los datasets de los RDL.

## Reproducir

Desde la raíz del repositorio, después de generar Oro:

```bash
python src/publicar_ssrs.py
```

Luego puede inspeccionarse `outputs/ssrs_publicacion_manifest.json`. La base `ssrs/reportes.db` se genera solo para smoke tests y está en `.gitignore`.

## Paso institucional pendiente

Para cerrar literalmente el criterio en CGR todavía se requiere:

1. ejecutar el DDL en SQL Server institucional;
2. configurar la cadena de conexión y autenticación autorizada;
3. desplegar los RDL en SSRS institucional;
4. validar permisos y resultados con usuarios CGR;
5. ejecutar pruebas en DEV/QA/PROD y registrar evidencia de operación/rendimiento.

Por ello el estado del criterio 7 es **🟡 PoC verificable / 🔵 cierre institucional pendiente**, no “producción completada”.
