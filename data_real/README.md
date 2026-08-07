# Datos reales de SEACE (OCDS)

Este pipeline corresponde al Anexo A del reporte técnico y a la Sección 10
del Producto 7 (Informe Final) — una prueba adicional fuera del alcance
formal del TDR (que usa datos sintéticos), incluida para dejar registro de
cómo se comporta la metodología sobre datos verdaderos.

> **Estado de integridad (agosto 2026):** el pipeline fue corregido para
> respetar la relación OCDS `Contract -> Award -> Supplier`. Los CSV
> procesados y rankings `*_REAL.csv` que hayan sido generados con una versión
> anterior deben considerarse **artefactos históricos/stale** hasta volver a
> ejecutar la carga con los crudos indicados abajo. No deben interpretarse
> como resultados vigentes ni como hallazgos confirmados.

Los archivos crudos (`main.csv`, `contracts.csv`, `awards.csv`,
`awards_suppliers.csv`, `parties.csv`) NO se versionan aquí por su tamaño; se
excluyen vía `.gitignore`.

## Fuente
Portal de Datos Abiertos de la OECE (Perú), estándar OCDS, año 2022.
Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
Descarga: https://data.open-contracting.org/en/publication/135

## Cómo reproducir
1. Descargar el año deseado en formato CSV desde el enlace de arriba.
2. Descomprimir el paquete y colocar en `data_real/` como mínimo:
   - `main.csv`
   - `contracts.csv`
   - `awards.csv`
   - `awards_suppliers.csv`
   - `parties.csv`
3. Ejecutar: `python3 src/cargar_datos_reales_seace.py`.
4. El script reconstruye cada contrato mediante la cadena:
   `contract(main_ocid, awardID) -> award(main_ocid, id) -> suppliers del award`.
5. La clave analítica del contrato es `OCID::contract.id`, porque el `id` del
   contrato es local al proceso OCDS y no debe asumirse globalmente único.
6. Los contratos cuyo award/supplier no pueda resolverse se excluyen del
   dataset proveedor-dependiente y se reportan explícitamente; no se les asigna
   un proveedor por aproximación.
7. Ejecutar `pytest -q` para validar las pruebas de integridad y normativa.
8. Ejecutar `python3 src/modelo_real.py` para regenerar los rankings reales.

## Consorcios
Un consorcio solo se construye cuando **una misma adjudicación** tiene más de
un supplier. El identificador compuesto se genera con un hash determinístico
del conjunto completo de integrantes; la lista completa queda en
`integrantes_consorcio`. Esto evita colisiones por truncar la lista visible.

## Categoría contractual y umbrales
Se conserva `tender_mainProcurementCategory` como `categoria_principal` y se
prioriza esa clasificación estructurada (`goods`, `services`, `works`) para el
motor normativo. Las reglas por texto libre quedan como fallback cuando la
fuente no trae una categoría estructurada.

## Limitaciones documentadas de este dataset real
- No incluye funcionarios públicos individuales (OCDS registra
  organizaciones, no personas) — el módulo de vínculos se adapta a nivel
  proveedor-entidad, no proveedor-funcionario.
- Los datos de contacto dependen de la completitud publicada por la fuente.
- La categoría temática `objeto` sigue derivándose de la descripción en texto
  libre para análisis exploratorio; no sustituye `categoria_principal` para
  decidir si una contratación es `works` frente a `goods/services`.
- Sin etiquetas reales de favoritismo/fraccionamiento no existe ground truth
  para validar precisión. Los resultados son **señales para revisión por
  auditor**, no determinaciones ni hallazgos confirmados.
