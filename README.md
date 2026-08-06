# Módulo de Análisis de Datos — Prototipo (Proyecto Interno CGR 1.8.2)

Prototipo funcional construido para demostrar viabilidad técnica del
"Módulo de análisis de datos para dar soporte a los auditores durante la
ejecución de los servicios de control", descrito en el TDR de contratación
de un Consultor Científico de Datos (Contraloría General de la República,
Mayo 2026).

**Objetivo del prototipo:** demostrar que el pipeline de detección de
favoritismo y fraccionamiento en contrataciones públicas puede construirse
rápidamente con herramientas open source, antes de comprometer una
consultoría de S/. 72,000 por 180 días.

## Estado
🚧 En construcción — ver commits para avance por producto.

## Estructura
- `data/` — datos sintéticos que simulan la integración SIAF/SEACE
- `src/` — código fuente (ETL, EDA, modelos)
- `outputs/` — gráficos y modelos entrenados

## Nota sobre datos
Todos los datos en este repositorio son **sintéticos**, generados para
fines de demostración. No contienen información real de proveedores,
funcionarios ni entidades públicas.

## Escalamiento a producción
Este prototipo usa pandas/scikit-learn por velocidad de desarrollo. La
lógica es directamente portable a Apache Spark MLlib (`pyspark.ml`) sobre
el Lakehouse Hadoop descrito en el Anexo 2 del TDR cuando se conecte a
datos reales de volumen productivo.

## Productos formales (Anexo 01)
La carpeta `reporte/productos_formales/` contiene los 7 productos del TDR
como documentos .docx separados, cada uno con la estructura exacta que
exige el Anexo 01 (carátula, resumen ejecutivo, índice, introducción,
objetivo, productos alcanzados, actividades, grado de cumplimiento,
dificultades, conclusiones, anexos). El `reporte/Reporte_Tecnico_*.docx`
en la raíz de `reporte/` es un documento único consolidado, útil para
lectura rápida; los 7 productos son la versión formal equivalente al
formato que la CGR usaría para evaluar entregables reales.
