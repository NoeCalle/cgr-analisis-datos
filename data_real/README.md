# Datos reales de SEACE (OCDS)

Este pipeline corresponde al Anexo A del reporte técnico y a la Sección 10
del Producto 7 (Informe Final) — una prueba adicional fuera del alcance
formal del TDR (que usa datos sintéticos), incluida para dejar registro de
cómo se comporta la metodología sobre datos verdaderos.

Los archivos crudos (main.csv, contracts.csv, awards.csv, parties.csv) NO
están versionados aquí por su tamaño (~245 MB combinados) — se excluyen
vía .gitignore.

## Fuente
Portal de Datos Abiertos de la OECE (Perú), estándar OCDS, año 2022.
Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
Descarga: https://data.open-contracting.org/en/publication/135

## Cómo reproducir
1. Descargar el año deseado en formato CSV desde el enlace de arriba.
2. Descomprimir (.tar.gz) y colocar main.csv, contracts.csv, awards.csv
   y parties.csv en esta carpeta (data_real/).
3. Ejecutar: `python3 src/cargar_datos_reales_seace.py`
4. Esto genera entidades_reales.csv, proveedores_reales.csv y
   contratos_reales.csv (sí versionados, son el resultado ya procesado).
5. Ejecutar: `python3 src/modelo_real.py` para correr el análisis.

## Limitaciones documentadas de este dataset real
- No incluye funcionarios públicos individuales (OCDS registra
  organizaciones, no personas) — el módulo de vínculos se adapta a nivel
  proveedor-entidad, no proveedor-funcionario.
- Los proveedores tienen teléfono publicado (100%) pero nunca dirección
  (0%) — solo la entidad compradora publica dirección.
- La categoría "objeto" se deriva de la descripción en texto libre del
  contrato mediante palabras clave; ~56% cae en "Otros bienes y
  servicios" por la enorme diversidad real del gasto público (no es un
  error de datos, es la naturaleza del texto libre).
- Sin etiquetas de favoritismo/fraccionamiento reales — no hay ground
  truth para validar precisión; los resultados son señales estadísticas
  para revisión de un auditor, no hallazgos confirmados.
