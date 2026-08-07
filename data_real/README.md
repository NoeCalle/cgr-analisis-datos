# Datos reales de SEACE (OCDS)

Este pipeline corresponde al Anexo A del reporte técnico y a la Sección 10
del Producto 7 (Informe Final) — una prueba adicional fuera del alcance
formal del TDR (que usa datos sintéticos), incluida para observar cómo se
comporta la metodología sobre datos verdaderos.

## Estado de integridad — regenerado 2026-08-07

El pipeline fue corregido y ejecutado nuevamente respetando la relación OCDS:

`Contract(main_ocid, awardID) -> Award(main_ocid, id) -> awards_suppliers(main_ocid, awards_id)`

Resultado de la ejecución P0:

- contratos crudos: **47,510**
- contratos con adjudicación y supplier resolubles: **47,254**
- contratos excluidos por no poder resolver su adjudicación/supplier: **256**
- adjudicatarios distintos presentes en contratos: **25,861**
- entidades distintas: **2,732**
- categorías OCDS: 23,630 `goods`, 18,584 `services`, 5,040 `works`
- rango de fecha de firma encontrado: 2018-09-18 a 2024-11-08

La ejecución anterior reportaba 47,442 contratos y usaba una asociación
supplier-proceso que podía mezclar proveedores de adjudicaciones distintas.
Esos artefactos fueron retirados del repositorio. El resumen agregado,
hashes de las fuentes y resultados de validación se conservan en
`outputs/validacion_p0_datos_reales.json`.

## Política de publicación de datos reales

Los archivos crudos y los derivados identificables **no se versionan** en este
repositorio público. Se excluyen vía `.gitignore`:

- `main.csv`
- `contracts.csv`
- `awards.csv`
- `awards_suppliers.csv`
- `parties.csv`
- `sources.csv`
- `contratos_reales.csv`
- `proveedores_reales.csv`
- `entidades_reales.csv`
- rankings `*_REAL.csv`

Esto permite reproducir localmente la prueba sin publicar rankings que asocien
RUC/proveedores reales con señales de riesgo fuera de su contexto metodológico.
Las señales generadas por el prototipo **no constituyen hallazgos ni
acusaciones de irregularidad**.

## Fuente

Portal de Datos Abiertos de la OECE (Perú), estándar OCDS.
Licencia de datos: Creative Commons Attribution 4.0 International (CC BY 4.0).
Descarga utilizada: https://data.open-contracting.org/en/publication/135

## Cómo reproducir

1. Descargar y descomprimir el paquete OCDS.
2. Colocar en `data_real/` como mínimo:
   - `main.csv`
   - `contracts.csv`
   - `awards.csv`
   - `awards_suppliers.csv`
   - `parties.csv`
3. Ejecutar `python3 src/cargar_datos_reales_seace.py`.
4. La clave analítica del contrato será `OCID::contract.id`; no se asume que
   `contract.id` sea una clave global fuera de su proceso OCDS.
5. Los contratos cuyo award/supplier no pueda resolverse se excluyen del
   análisis proveedor-dependiente y se contabilizan explícitamente.
6. Ejecutar `pytest -q` para validar las pruebas de integridad y normativa.
7. Ejecutar `python3 src/modelo_real.py` para producir localmente los rankings.

## Adjudicatarios y consorcios

En el archivo `awards_suppliers.csv` de esta publicación hay normalmente un
supplier por adjudicación. Muchos consorcios aparecen como **una entidad
adjudicataria propia**, por ejemplo con razón social `CONSORCIO ...`; por eso
no se deben reconstruir agrupando todas las parties supplier de un OCID.

El loader conserva directamente la identidad publicada por
`awards_suppliers`. Si otra publicación OCDS trajera realmente más de un
supplier para una misma adjudicación, el código genera una identidad compuesta
determinística para ese award sin mezclar suppliers de adjudicaciones distintas.

## Categoría contractual y motor normativo

Se conserva `tender_mainProcurementCategory` como `categoria_principal` y se
prioriza esa clasificación estructurada (`goods`, `services`, `works`) para el
motor normativo. El texto libre es solo un fallback conservador.

Aunque la publicación analizada es principalmente 2022, los contratos que
contiene tienen fechas de firma desde 2018 hasta 2024. Por ello
`src/umbrales_normativos.py` incluye también los topes históricos 2018-2021 y
falla explícitamente ante un año no parametrizado en vez de aproximarlo.

## Limitaciones documentadas

- OCDS abierto no incluye funcionarios públicos individuales; el análisis real
  de vínculos solo puede adaptarse a nivel proveedor-entidad con esta fuente.
- No existen etiquetas reales de favoritismo/fraccionamiento. Los rankings son
  señales estadísticas de priorización y no permiten estimar precisión real ni
  afirmar la existencia de una irregularidad.
- Los datos de contacto dependen de la completitud publicada por la fuente.
- La categoría temática `objeto` se deriva de texto libre para EDA; no sustituye
  `categoria_principal` para decidir `works` frente a `goods/services`.
- La revisión de la competitividad de cada modalidad y la validación ML más
  rigurosa forman parte de la fase P1 del plan de cierre de brechas.
