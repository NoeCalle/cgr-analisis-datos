const { Packer } = require('docx');
const fs = require('fs');
const {
  titulo, subtitulo, parrafo, vineta, tablaConTitulo, imagenConTitulo,
  frontMatter, referencias, documento,
} = require('./plantilla_docx');
const { e, pct, num, pen, modelo, syn, fav, frac, selFav, tuneFav, tuneFrac, p0 } = require('./evidencia');

const OUT = 'productos_formales';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const rf = modelo('RandomForest');
const lr = modelo('RegresionLogistica');
const gb = modelo('GradientBoosting');
const hf = tuneFrac.metricas_holdout_final;
const p0i = p0.integridad_ocds;
const manifest = e.run_manifest || {};
const sparkFav = manifest.spark_favoritismo || {};
const sparkFrac = manifest.spark_fraccionamiento || {};
const graphframes = manifest.graphframes || {};

const OBJETIVO_TDR =
  'Objetivo de consultoría tomado como referencia del TDR: disponer datos procesados y filtrados de fuentes externas e internas, y desarrollar modelos de Machine Learning que permitan identificar casos atípicos y patrones de riesgo relevantes para la labor del auditor. En este repositorio dicho objetivo se desarrolla únicamente como prototipo independiente.';

function notaMetodologica() {
  return parrafo(
    'Nota metodológica: las métricas del benchmark sintético evalúan la coherencia del PoC y no estiman desempeño productivo. ' +
    'Las salidas sobre datos públicos son señales de priorización para revisión humana y no constituyen hallazgos ni determinaciones automáticas de irregularidad.'
  );
}

function anexosBase(extra = []) {
  return [
    vineta('Repositorio organizado con código, datasets sintéticos, evidencia reproducible y documentación: https://github.com/NoeCalle/cgr-analisis-datos'),
    vineta('Fuente única de cifras documentales: outputs/evidencia_documental.json.'),
    vineta('Trazabilidad de ejecución: outputs/run_manifest.json y outputs/linaje_datos.csv.'),
    ...extra,
  ];
}

function informeProducto({
  numero, nombre, resumen, introduccion, alcanzados, actividades, cumplimiento,
  dificultades, conclusiones, tablas = [], graficos = [], anexos = [], referenciasExtra = [],
}) {
  return documento(numero, nombre, nombre, [
    titulo('Resumen Ejecutivo'),
    parrafo(resumen),
    notaMetodologica(),
    ...frontMatter({ tablas, graficos }),
    titulo('1. Introducción'),
    parrafo(introduccion),
    titulo('2. Objetivo de Consultoría'),
    parrafo(OBJETIVO_TDR),
    titulo('3. Productos Alcanzados'),
    ...alcanzados,
    titulo('4. Actividades Realizadas'),
    ...actividades,
    titulo('5. Grado de Cumplimiento del Producto'),
    parrafo(cumplimiento),
    titulo('6. Dificultades y Limitaciones Encontradas'),
    ...dificultades,
    titulo('7. Conclusiones y Recomendaciones'),
    parrafo(conclusiones),
    titulo('8. Anexos'),
    ...anexosBase(anexos),
    ...referencias(undefined, referenciasExtra),
  ]);
}

// -----------------------------------------------------------------------------
// Producto 1 - Plan de Trabajo. Estructura literal del Anexo 1, II.1.
// -----------------------------------------------------------------------------
const p1 = documento(1, 'Plan de Trabajo', 'Plan de Trabajo', [
  ...frontMatter({
    tablas: [
      'Productos y alcance del plan de trabajo',
      'Actividades a cumplir por cada producto',
      'Cronograma contractual de referencia',
    ],
  }),
  titulo('1. Introducción'),
  parrafo(
    'El presente Plan de Trabajo organiza una prueba de concepto independiente basada en el TDR público del Proyecto Interno 1.8.2. ' +
    'El repositorio se orienta a demostrar, con evidencia reproducible, la preparación de datos, selección y validación de modelos, Spark MLlib, grafos, orquestación, trazabilidad y reporting, separando expresamente lo verificable fuera de CGR de las actividades que requieren infraestructura, accesos o usuarios institucionales.'
  ),
  titulo('2. Objetivo de Consultoría'),
  parrafo(OBJETIVO_TDR),
  titulo('3. Productos a Alcanzar'),
  ...tablaConTitulo(1, 'Productos y alcance del plan de trabajo', ['N.°', 'Producto', 'Alcance de referencia'], [
    ['1', 'Plan de Trabajo', 'Metodología, actividades, cronograma y criterios de cierre.'],
    ['2', 'Preprocesamiento - Favoritismo', 'Limpieza, transformación, feature engineering y división de datos.'],
    ['3', 'Modelo - Favoritismo', 'Patrones, análisis estadístico, selección, arquitectura, Spark MLlib y parámetros.'],
    ['4', 'Entrenamiento/Validación - Favoritismo', 'Métricas, experimentos, validación cruzada, tuning, persistencia e interpretabilidad.'],
    ['5', 'Preprocesamiento - Fraccionamiento', 'Limpieza, ventanas temporales, contexto normativo, features y división de datos.'],
    ['6', 'Modelo - Fraccionamiento', 'Selección, anomalías/clustering, arquitectura, Spark MLlib y parámetros.'],
    ['7', 'Entrenamiento/Validación y cierre técnico', 'Validación, despliegue documentado, integración, monitoreo, repositorio y ruta institucional.'],
  ], [650, 3100, 5050]),
  titulo('4. Actividades a Cumplir por Cada Producto'),
  ...tablaConTitulo(2, 'Actividades a cumplir por cada producto', ['Producto', 'Actividades principales'], [
    ['1', 'Planificar alcance, metodología, cronograma, evidencias y dependencias.'],
    ['2', 'EDA, imputación, outliers, transformación, normalización/codificación, features y división para favoritismo.'],
    ['3', 'Analizar patrones, comparar algoritmos, documentar arquitectura e implementar Random Forest con Spark MLlib.'],
    ['4', 'Validación OOF/CV, tuning, persistencia, SHAP, comparación de escenarios y documentación para certificación.'],
    ['5', 'EDA temporal, limpieza, motor normativo, ventanas, features y división para fraccionamiento.'],
    ['6', 'Tuning no supervisado, KMeans Spark MLlib, reglas interpretables, arquitectura y parámetros.'],
    ['7', 'Evaluación final, manual de despliegue, pruebas de integración local, pipeline, monitoreo, repositorio y plan de transferencia.'],
  ], [1200, 7600]),
  titulo('5. Cronograma'),
  parrafo('Plazos contractuales de referencia establecidos en el numeral 8 del TDR, contados desde el día siguiente de la suscripción del contrato:'),
  ...tablaConTitulo(3, 'Cronograma contractual de referencia', ['Producto', 'Plazo máximo'], [
    ['Primer Producto', '7 días calendario'],
    ['Segundo Producto', '30 días calendario'],
    ['Tercer Producto', '60 días calendario'],
    ['Cuarto Producto', '90 días calendario'],
    ['Quinto Producto', '120 días calendario'],
    ['Sexto Producto', '150 días calendario'],
    ['Séptimo Producto', '180 días calendario'],
  ], [4400, 4400]),
  titulo('6. Anexos'),
  ...anexosBase([
    vineta('Matriz de correspondencia TDR-PoC: README.md y documentación formal generada en este directorio.'),
    vineta('Los hitos institucionales DEV/QA/PROD, certificación, marcha blanca y transferencia efectiva se ejecutarán únicamente si existe entorno y coordinación CGR.'),
  ]),
  ...referencias(),
]);

// -----------------------------------------------------------------------------
// Producto 2 - Preprocesamiento Favoritismo.
// -----------------------------------------------------------------------------
const p2 = informeProducto({
  numero: 2,
  nombre: 'Limpieza y Preprocesamiento de Datos para Identificación de Proveedores Favoritos',
  resumen: `Se procesaron ${num(syn.contratos)} contratos sintéticos para construir ${num(fav.pares_proveedor_entidad)} pares proveedor-entidad, con ${num(fav.positivos_sembrados)} casos positivos sembrados. El flujo implementa limpieza, tratamiento de outliers, transformación, feature engineering y una división reproducible de datos.`,
  introduccion: 'Este producto documenta la preparación de datos previa al modelado de favoritismo y cubre los componentes de limpieza y preprocesamiento exigidos por el TDR.',
  tablas: ['Resumen de calidad y preparación del benchmark de favoritismo'],
  graficos: ['Distribución de montos contractuales', 'Modalidades de contratación del benchmark'],
  alcanzados: [
    subtitulo('3.1 Imputación y calidad de datos'),
    ...tablaConTitulo(1, 'Resumen de calidad y preparación del benchmark de favoritismo', ['Métrica', 'Resultado'], [
      ['Contratos sintéticos', num(syn.contratos)],
      ['Valores nulos totales en fuente', num(syn.valores_nulos_totales)],
      ['Filas con al menos un nulo', num(syn.filas_con_algun_nulo)],
      ['Percentil 99 del monto', pen(syn.p99_monto_pen)],
      ['Registros sobre P99', num(syn.registros_sobre_p99)],
      ['Pares proveedor-entidad', num(fav.pares_proveedor_entidad)],
      ['Positivos sintéticos', num(fav.positivos_sembrados)],
    ], [5000, 3800]),
    subtitulo('3.2 Tratamiento de outliers'),
    parrafo('Los montos extremos se identifican mediante el percentil 99 y se controlan en la transformación para impedir que valores aislados dominen el entrenamiento. La operación es determinística y queda cubierta por el pipeline reproducible.'),
    ...imagenConTitulo(1, 'Distribución de montos contractuales', '../outputs/charts/01_distribucion_montos.png', 610, 350),
    subtitulo('3.3 Codificación y normalización'),
    parrafo('Las variables numéricas se preparan de forma reproducible y las categorías se conservan con semántica explícita. Contratación Directa y Comparación de Precios se modelan como variables separadas, evitando equiparar procedimientos distintos.'),
    ...imagenConTitulo(2, 'Modalidades de contratación del benchmark', '../outputs/charts/02_modalidades_contratacion.png', 610, 350),
    subtitulo('3.4 Feature engineering'),
    vineta('Número de contratos, monto total y monto promedio por proveedor-entidad.'),
    vineta('Número de objetos únicos y concentración temática.'),
    vineta('Porcentaje de Contratación Directa y porcentaje de Comparación de Precios, por separado.'),
    vineta('Número de funcionarios distintos, días de actividad, contratos por mes y monto por funcionario.'),
    subtitulo('3.5 División y publicación de datos'),
    parrafo('El dataset analítico se publica en lakehouse/plata/dataset_favoritismo.csv. Las particiones de validación se realizan en las etapas de comparación y tuning con esquemas estratificados reproducibles.'),
  ],
  actividades: [
    vineta('Generación determinística del benchmark sintético con hard negatives.'),
    vineta('EDA, imputación, control de outliers, transformación y feature engineering.'),
    vineta('Publicación de datos limpios/features en capa Plata.'),
    vineta('Validación automática de columnas, conteos y etiquetas en GitHub Actions.'),
  ],
  cumplimiento: 'Cumplimiento técnico completo dentro del PoC. La sustitución de datos sintéticos por fuentes internas y su validación funcional dependen del entorno institucional CGR.',
  dificultades: [
    vineta('El ground truth es sintético; permite probar el pipeline pero no estimar desempeño real.'),
    vineta('La información abierta OCDS no contiene todos los atributos institucionales previstos por el TDR.'),
  ],
  conclusiones: 'El preprocesamiento de favoritismo es reproducible, auditable y coherente con la semántica de contratación. Se recomienda conservar esta separación de modalidades y recalibrar el feature engineering cuando exista ground truth validado por auditores.',
});

// -----------------------------------------------------------------------------
// Producto 3 - Selección y desarrollo Favoritismo + Spark MLlib.
// -----------------------------------------------------------------------------
const p3 = informeProducto({
  numero: 3,
  nombre: 'Selección del Algoritmo y Desarrollo del Modelo para Identificación de Proveedores Favoritos',
  resumen: `Se compararon Regresión Logística, Random Forest y Gradient Boosting con las mismas predicciones out-of-fold. Random Forest obtuvo el mayor AUC-PR (${rf.auc_pr.toFixed(3)}). La evidencia histórica de Spark MLlib se reproduce en local[*], mientras que la ruta operacional vigente admite master configurable y spark_sql Spark-native sin toPandas().`,
  introduccion: 'Este producto cubre patrones y tendencias, análisis estadístico, propuesta fundamentada de algoritmos, diseño/arquitectura, implementación Spark MLlib y parámetros de entrenamiento.',
  tablas: ['Comparación de algoritmos candidatos para favoritismo', 'Implementación Spark MLlib para favoritismo'],
  graficos: ['Concentración de proveedores por entidad', 'Diagrama del modelo de datos del PoC'],
  alcanzados: [
    subtitulo('3.1 Patrones y tendencias identificadas'),
    parrafo('El benchmark muestra concentración contractual por proveedor-entidad, diferencias entre modalidades y patrones temporales que justifican un enfoque de puntuación de riesgo a nivel agregado.'),
    ...imagenConTitulo(1, 'Concentración de proveedores por entidad', '../outputs/charts/03_concentracion_proveedores.png', 610, 350),
    subtitulo('3.2 Análisis estadístico de variables clave'),
    parrafo(`El dataset contiene ${num(selFav.n_registros)} pares proveedor-entidad y ${num(selFav.positivos)} positivos sintéticos. Debido al fuerte desbalance, AUC-PR se adopta como criterio primario; AUC-ROC, precision, recall y F1 se conservan como métricas complementarias.`),
    subtitulo('3.3 Propuesta fundamentada de algoritmos'),
    ...tablaConTitulo(1, 'Comparación de algoritmos candidatos para favoritismo', ['Modelo', 'AUC-PR', 'AUC-ROC', 'Precision', 'Recall', 'F1'], [
      ['Random Forest', rf.auc_pr.toFixed(3), rf.auc_roc.toFixed(3), pct(rf.precision), pct(rf.recall), rf.f1.toFixed(3)],
      ['Regresión Logística', lr.auc_pr.toFixed(3), lr.auc_roc.toFixed(3), pct(lr.precision), pct(lr.recall), lr.f1.toFixed(3)],
      ['Gradient Boosting', gb.auc_pr.toFixed(3), gb.auc_roc.toFixed(3), pct(gb.precision), pct(gb.recall), gb.f1.toFixed(3)],
    ], [2200, 1300, 1300, 1300, 1300, 1300]),
    parrafo('Random Forest se selecciona como candidato principal por AUC-PR y por su compatibilidad con explicabilidad basada en importancia de variables y SHAP.'),
    subtitulo('3.4 Diseño y arquitectura del modelo'),
    parrafo('El PoC conserva una ruta histórica fuente -> Bronce -> limpieza/feature engineering -> Plata -> benchmark -> Oro para reproducibilidad y una ruta operacional fuente canónica -> TRAIN/INFERENCE -> champion Spark -> scores. El serving operacional no depende de materializar la fuente spark_sql en pandas o en la Plata legacy.'),
    ...imagenConTitulo(2, 'Diagrama del modelo de datos del PoC', '../outputs/charts/09_diagrama_modelo_datos.png', 610, 360),
    subtitulo('3.5 Reporte de implementación usando Apache Spark MLlib'),
    ...tablaConTitulo(2, 'Implementación Spark MLlib para favoritismo', ['Elemento', 'Evidencia'], [
      ['Motor', sparkFav.motor || 'Apache Spark MLlib'],
      ['Modo', sparkFav.modo || 'local[*]'],
      ['Algoritmo', sparkFav.algoritmo || 'RandomForestClassifier'],
      ['Dataset', sparkFav.dataset || 'lakehouse/plata/contratos_procesados.csv'],
      ['Validación', sparkFav.cv || '3-fold estratificado determinístico'],
      ['Métrica', sparkFav.metrica_seleccion || 'AUC-PR CV'],
      ['AUC-PR CV del sanity check', sparkFav.auc_pr_cv === undefined ? 'N/D' : Number(sparkFav.auc_pr_cv).toFixed(3)],
      ['Advertencia', sparkFav.advertencia || 'Benchmark sintético; clúster CGR pendiente.'],
    ], [3300, 5500]),
    subtitulo('3.6 Parámetros de entrenamiento y configuraciones'),
    vineta(`sklearn Random Forest seleccionado: n_estimators=${tuneFav.mejor_configuracion.n_estimators}, max_depth=${tuneFav.mejor_configuracion.max_depth}, min_samples_leaf=${tuneFav.mejor_configuracion.min_samples_leaf}.`),
    vineta(`Spark MLlib Random Forest: numTrees=${sparkFav.mejor_configuracion?.numTrees ?? 'N/D'}, maxDepth=${sparkFav.mejor_configuracion?.maxDepth ?? 'N/D'}.`),
    vineta(`Versiones registradas en run_manifest.json: PySpark ${manifest.entorno?.pyspark || 'N/D'}; scikit-learn ${manifest.entorno?.['scikit-learn'] || 'N/D'}.`),
  ],
  actividades: [
    vineta('Comparación ejecutable con las mismas particiones out-of-fold.'),
    vineta('Grid search de Random Forest por AUC-PR.'),
    vineta('Implementación y ejecución real de RandomForestClassifier con Spark MLlib.'),
    vineta('Persistencia de rankings, configuración y resumen machine-readable en outputs/.'),
  ],
  cumplimiento: 'Contenido exigido por el TDR implementado y verificado para el PoC, con benchmark MLlib local reproducible y contrato operacional Spark-native. La validación de escalabilidad, carga y rendimiento sobre infraestructura institucional queda pendiente de la CGR.',
  dificultades: [
    vineta(`El benchmark contiene solo ${num(fav.positivos_sembrados)} positivos sintéticos; la métrica Spark CV tiene alta varianza y no se interpreta como desempeño productivo.`),
    vineta('La selección final en producción requiere datos internos y ground truth acordado con auditores.'),
  ],
  conclusiones: 'Random Forest es el candidato técnico preferido del PoC por AUC-PR e interpretabilidad. Spark MLlib forma parte tanto del benchmark histórico como del serving operacional; la validación de carga, rendimiento y umbrales productivos requiere el entorno CGR.',
});

// -----------------------------------------------------------------------------
// Producto 4 - Entrenamiento y validación Favoritismo.
// -----------------------------------------------------------------------------
const p4 = informeProducto({
  numero: 4,
  nombre: 'Entrenamiento y Validación del Modelo para Identificación de Proveedores Favoritos',
  resumen: `La validación vigente usa predicciones out-of-fold y tuning reproducible. Random Forest alcanza AUC-PR ${rf.auc_pr.toFixed(3)}, AUC-ROC ${rf.auc_roc.toFixed(3)}, precision ${pct(rf.precision)}, recall ${pct(rf.recall)} y F1 ${rf.f1.toFixed(3)} en el benchmark sintético.`,
  introduccion: 'Este producto documenta métricas iniciales, registro de experimentos, validación cruzada, tuning, persistencia, comparación de escenarios y documentación técnica para un eventual pase a certificación.',
  tablas: ['Métricas out-of-fold del modelo de favoritismo', 'Configuración de tuning del Random Forest'],
  graficos: ['Importancia de variables del Random Forest', 'Resumen SHAP de favoritismo', 'Explicación SHAP de un caso priorizado'],
  alcanzados: [
    subtitulo('3.1 Métricas de evaluación inicial'),
    ...tablaConTitulo(1, 'Métricas out-of-fold del modelo de favoritismo', ['Métrica', 'Resultado'], [
      ['AUC-PR', rf.auc_pr.toFixed(3)], ['AUC-ROC', rf.auc_roc.toFixed(3)],
      ['Precision', pct(rf.precision)], ['Recall', pct(rf.recall)], ['F1', rf.f1.toFixed(3)],
    ], [4400, 4400]),
    subtitulo('3.2 Registro de experimentos y pruebas'),
    parrafo('Los resultados de Regresión Logística, Random Forest y Gradient Boosting se almacenan en outputs/comparacion_modelos_favoritismo.json y .csv; la grilla de tuning y su resumen se almacenan en outputs/tuning_favoritismo_resultados.csv y outputs/tuning_favoritismo_resumen.json.'),
    subtitulo('3.3 Validación cruzada y evaluación exhaustiva'),
    parrafo(`${selFav.diseno}. La métrica primaria es ${selFav.criterio_primario}. La comparación usa exactamente las mismas particiones para todos los candidatos.`),
    subtitulo('3.4 Ajuste de hiperparámetros'),
    ...tablaConTitulo(2, 'Configuración de tuning del Random Forest', ['Elemento', 'Resultado'], [
      ['Métrica de selección', tuneFav.metrica_seleccion],
      ['Validación', tuneFav.cv],
      ['n_estimators', String(tuneFav.mejor_configuracion.n_estimators)],
      ['max_depth', String(tuneFav.mejor_configuracion.max_depth)],
      ['min_samples_leaf', String(tuneFav.mejor_configuracion.min_samples_leaf)],
      ['Mejor AUC-PR CV', tuneFav.mejor_auc_pr_cv.toFixed(3)],
    ], [4000, 4800]),
    subtitulo('3.5 Persistencia del modelo entrenado'),
    parrafo('El modelo sklearn seleccionado se persiste en outputs/models/modelo_favoritismo_rf.joblib. Los modelos Spark se regeneran en runtime y se versionan mediante sus configuraciones, métricas y rankings reproducibles, evitando binarios Spark con metadata no determinística.'),
    subtitulo('3.6 Análisis comparativo del rendimiento'),
    parrafo('El benchmark deliberadamente incluye hard negatives. La reducción respecto de resultados perfectos antiguos se considera una mejora metodológica, porque hace visible la incertidumbre y reduce el riesgo de sobreinterpretación.'),
    ...imagenConTitulo(1, 'Importancia de variables del Random Forest', '../outputs/charts/05_importancia_favoritismo.png', 610, 350),
    subtitulo('3.7 Interpretabilidad y documentación técnica'),
    ...imagenConTitulo(2, 'Resumen SHAP de favoritismo', '../outputs/charts/07_shap_summary_favoritismo.png', 610, 360),
    ...imagenConTitulo(3, 'Explicación SHAP de un caso priorizado', '../outputs/charts/08_shap_waterfall_caso.png', 610, 360),
    parrafo('La documentación para un eventual pase a certificación queda trazada mediante run_manifest.json, diccionario de datos, linaje, parámetros y métricas. La certificación formal depende de CGR.'),
  ],
  actividades: [
    vineta('Generación de predicciones OOF y comparación de candidatos.'),
    vineta('Tuning sistemático por AUC-PR y persistencia de configuración.'),
    vineta('Entrenamiento final y persistencia del Random Forest sklearn.'),
    vineta('Generación de importancia de variables y explicaciones SHAP globales e individuales.'),
  ],
  cumplimiento: 'Entrenamiento, validación, tuning, persistencia e interpretabilidad completados para el PoC. El pase por ambientes institucionales y la certificación funcional no pueden demostrarse fuera de CGR.',
  dificultades: [
    vineta('La clase positiva es pequeña y sintética; las métricas deben leerse como benchmark metodológico.'),
    vineta('No existe todavía ground truth real validado por auditores para medir generalización productiva.'),
  ],
  conclusiones: 'La validación es reproducible y metodológicamente más exigente. Se recomienda mantener AUC-PR como métrica primaria, conservar SHAP para explicabilidad y repetir la evaluación con particiones temporales o por entidad cuando exista ground truth institucional.',
});

// -----------------------------------------------------------------------------
// Producto 5 - Preprocesamiento Fraccionamiento.
// -----------------------------------------------------------------------------
const p5 = informeProducto({
  numero: 5,
  nombre: 'Limpieza y Preprocesamiento de Datos para Detección de Fraccionamiento',
  resumen: `Se construyeron ${num(frac.grupos_proveedor_entidad_objeto)} grupos proveedor-entidad-objeto con ${num(frac.positivos_sembrados)} positivos sintéticos. El feature engineering incorpora ventanas temporales y cuantías normativas dependientes de fecha y categoría, evitando un umbral fijo universal.`,
  introduccion: 'Este producto documenta la preparación de datos específica para posibles patrones de fraccionamiento, incluidos limpieza, transformación, feature engineering y división independiente para validación.',
  tablas: ['Features principales del dataset de fraccionamiento'],
  graficos: ['Serie temporal del benchmark de contratación'],
  alcanzados: [
    subtitulo('3.1 Imputación, outliers y transformación'),
    parrafo('El flujo reutiliza controles de calidad del dataset contractual y transforma montos y fechas en variables aptas para análisis temporal y detección de anomalías.'),
    subtitulo('3.2 Feature engineering temporal y normativo'),
    ...tablaConTitulo(1, 'Features principales del dataset de fraccionamiento', ['Feature', 'Interpretación'], [
      ['n_contratos_grupo', 'Número de contratos del grupo proveedor-entidad-objeto.'],
      ['max_contratos_ventana_15d', 'Máximo de contratos observados en una ventana móvil de 15 días.'],
      ['monto_total_ventana_15d', 'Monto acumulado dentro de la ventana de máxima concentración.'],
      ['pct_montos_bajo_umbral', 'Proporción de contratos bajo el 95% de la cuantía parametrizada para fecha/régimen/categoría.'],
      ['monto_total_grupo', 'Monto acumulado del grupo analítico.'],
    ], [3300, 5500]),
    parrafo('La categoría estructurada goods/services/works tiene prioridad sobre inferencias textuales para seleccionar el contexto normativo cuando está disponible.'),
    ...imagenConTitulo(1, 'Serie temporal del benchmark de contratación', '../outputs/charts/04_serie_temporal.png', 610, 350),
    subtitulo('3.3 División de los datos'),
    parrafo(`El diseño de evaluación separa un holdout final antes del tuning: ${tuneFrac.n_desarrollo} grupos quedan en desarrollo y ${hf.n_test} en holdout, impidiendo que el conjunto final participe en la selección de hiperparámetros.`),
    subtitulo('3.4 Publicación de capa Plata'),
    parrafo('El dataset resultante se publica en lakehouse/plata/dataset_fraccionamiento.csv y es consumido por la ruta sklearn y por la implementación Spark.'),
  ],
  actividades: [
    vineta('Cálculo de ventanas temporales y agregados por proveedor-entidad-objeto.'),
    vineta('Consulta del motor normativo parametrizado por fecha y categoría.'),
    vineta('Separación desarrollo/holdout antes del tuning.'),
    vineta('Pruebas de regresión para categorías, fechas, umbrales y semántica de señales.'),
  ],
  cumplimiento: 'Feature engineering, división y publicación en Plata completados para el PoC. La validación jurídica de reglas y fuentes internas depende de especialistas y sistemas CGR.',
  dificultades: [
    vineta('La ventana de 15 días es una heurística analítica configurable y no constituye por sí sola una regla jurídica.'),
    vineta('Las cuantías y regímenes deben mantenerse versionados frente a futuros cambios normativos.'),
  ],
  conclusiones: 'El preprocesamiento combina dimensión temporal, objeto contractual y contexto normativo, lo que resulta más defendible que aplicar un único tope monetario a todo el período analizado.',
});

// -----------------------------------------------------------------------------
// Producto 6 - Selección y desarrollo Fraccionamiento + Spark MLlib.
// -----------------------------------------------------------------------------
const p6 = informeProducto({
  numero: 6,
  nombre: 'Selección del Algoritmo y Desarrollo del Modelo para Detección de Fraccionamiento',
  resumen: `Isolation Forest se usa como detector no supervisado de referencia y Spark MLlib KMeans como implementación objetivo del TDR. El holdout independiente del benchmark sklearn muestra AUC-PR ${hf.auc_pr.toFixed(3)}, por lo que las salidas se tratan como priorización de revisión y no como clasificación de irregularidades.`,
  introduccion: 'Este producto cubre patrones, análisis estadístico, propuesta de algoritmos, arquitectura, implementación Spark MLlib y parámetros para la detección de patrones de compras anómalos.',
  tablas: ['Evaluación holdout de Isolation Forest', 'Implementación Spark MLlib para fraccionamiento'],
  graficos: ['Detección de señales de posible fraccionamiento'],
  alcanzados: [
    subtitulo('3.1 Patrones y tendencias identificadas'),
    parrafo('El caso de uso se caracteriza por grupos muy desbalanceados, concentración temporal y montos cercanos a cuantías de referencia. Estos patrones justifican combinar detección de anomalías con una señal interpretable de caja blanca.'),
    ...imagenConTitulo(1, 'Detección de señales de posible fraccionamiento', '../outputs/charts/06_deteccion_fraccionamiento.png', 610, 350),
    subtitulo('3.2 Análisis estadístico detallado'),
    ...tablaConTitulo(1, 'Evaluación holdout de Isolation Forest', ['Métrica', 'Resultado'], [
      ['Registros holdout', num(hf.n_test)],
      ['Positivos holdout', num(hf.positivos_test)],
      ['Anomalías predichas', num(hf.anomalias_predichas)],
      ['AUC-ROC', hf.auc_roc.toFixed(3)],
      ['AUC-PR', hf.auc_pr.toFixed(3)],
      ['Precision', pct(hf.precision)],
      ['Recall', pct(hf.recall)],
      ['F1', hf.f1.toFixed(3)],
      ['Recall@K', hf.recall_at_k.toFixed(3)],
    ], [4400, 4400]),
    subtitulo('3.3 Propuesta fundamentada de algoritmos'),
    parrafo('Isolation Forest permite un ranking de anomalía sin requerir una clase positiva abundante. Spark KMeans aporta una implementación de clustering acorde al énfasis del TDR en Spark MLlib. La regla interpretable complementa ambos enfoques y facilita revisión humana.'),
    subtitulo('3.4 Diseño y arquitectura'),
    parrafo('Los features se calculan desde Plata; la ruta sklearn evalúa Isolation Forest con holdout independiente, mientras la ruta Spark construye ventanas mediante Spark SQL y aplica KMeans MLlib. Los rankings se publican en Oro.'),
    subtitulo('3.5 Reporte de implementación usando Apache Spark MLlib'),
    ...tablaConTitulo(2, 'Implementación Spark MLlib para fraccionamiento', ['Elemento', 'Evidencia'], [
      ['Motor', sparkFrac.motor || 'Apache Spark MLlib'],
      ['Modo', sparkFrac.modo || 'local[*]'],
      ['Algoritmo', sparkFrac.algoritmo || 'KMeans + distancia al centroide'],
      ['k', sparkFrac.k === undefined ? 'N/D' : String(sparkFrac.k)],
      ['Dataset', sparkFrac.dataset || 'lakehouse/plata/contratos_procesados.csv'],
      ['Top-K aciertos sintéticos', sparkFrac.sanity_sintetico?.top_k_aciertos === undefined ? 'N/D' : String(sparkFrac.sanity_sintetico.top_k_aciertos)],
      ['Señal interpretable - positivos recuperados', sparkFrac.sanity_sintetico?.senal_interpretable_positivos === undefined ? 'N/D' : String(sparkFrac.sanity_sintetico.senal_interpretable_positivos)],
      ['Advertencia', sparkFrac.advertencia || 'Sanity check sintético; clúster CGR pendiente.'],
    ], [3300, 5500]),
    subtitulo('3.6 Parámetros y configuraciones'),
    vineta(`Isolation Forest: n_estimators=${tuneFrac.mejor_configuracion.n_estimators}, max_samples=${tuneFrac.mejor_configuracion.max_samples}, contamination=${tuneFrac.mejor_configuracion.contamination}.`),
    vineta(`Spark KMeans: k=${sparkFrac.k ?? 'N/D'}; features=${(sparkFrac.features || []).join(', ') || 'registradas en spark_fraccionamiento_resumen.json'}.`),
  ],
  actividades: [
    vineta('Separación de holdout final antes del tuning.'),
    vineta('Validaciones repetidas únicamente sobre desarrollo y selección por AUC-PR.'),
    vineta('Implementación de ventanas Spark SQL y KMeans con Spark MLlib.'),
    vineta('Publicación de ranking Spark y resumen JSON reproducible.'),
  ],
  cumplimiento: 'Selección y desarrollo completados en el PoC, incluida ejecución real con Spark MLlib. El rendimiento distribuido y la calibración sobre ground truth real requieren infraestructura y datos CGR.',
  dificultades: [
    vineta(`Solo existen ${num(tuneFrac.positivos_total)} positivos sintéticos y ${num(hf.positivos_test)} positivos en holdout; recall@K es especialmente inestable.`),
    vineta('La baja AUC-PR y baja precision del detector estadístico muestran que aún hay falsos positivos relevantes.'),
  ],
  conclusiones: 'El resultado principal es una arquitectura híbrida y honesta: detector no supervisado, clustering Spark y regla interpretable para priorización. Ninguna de estas señales debe convertirse automáticamente en un hallazgo de fraccionamiento.',
});

// -----------------------------------------------------------------------------
// Producto 7 - Informe Final. Estructura literal del Anexo 1, II.3.
// -----------------------------------------------------------------------------
const p7 = documento(7, 'Informe Final - Entrenamiento, Validación y Cierre Técnico', 'Informe Final - Entrenamiento, Validación y Cierre Técnico', [
  titulo('Resumen Ejecutivo'),
  parrafo(
    `El cierre técnico del PoC integra validación de favoritismo y fraccionamiento, ejecución Spark MLlib, GraphFrames, Airflow, capas Bronce/Plata/Oro, trazabilidad y documentación automática. ` +
    `La reconstrucción OCDS vigente contiene ${num(p0i.contratos_analiticos_validos)} contratos analíticos válidos a partir de ${num(p0i.contratos_crudos)} contratos crudos. ` +
    'Las actividades que exigen ambientes CGR, certificación funcional, marcha blanca y transferencia efectiva se identifican expresamente como dependencias institucionales.'
  ),
  notaMetodologica(),
  ...frontMatter({
    tablas: [
      'Métricas finales del benchmark de fraccionamiento',
      'Estado de los componentes de cierre del Séptimo Producto',
      'Plan de monitoreo y mantenimiento',
    ],
    graficos: ['Red proveedor-funcionario del escenario sintético', 'DAG principal de orquestación del PoC'],
  }),
  titulo('1. Introducción'),
  parrafo('El Séptimo Producto consolida entrenamiento y validación del caso de fraccionamiento y los documentos técnicos de cierre: implementación/despliegue, integración, pipeline, monitoreo, repositorio y transferencia. El presente documento mantiene separados los componentes ejecutables del PoC y aquellos que solo pueden completarse dentro de CGR.'),
  titulo('2. Objetivo de Consultoría'),
  parrafo(OBJETIVO_TDR),
  titulo('3. Productos Alcanzados'),
  subtitulo('3.1 Entrenamiento y validación del modelo de fraccionamiento'),
  ...tablaConTitulo(1, 'Métricas finales del benchmark de fraccionamiento', ['Métrica', 'Resultado'], [
    ['AUC-ROC holdout', hf.auc_roc.toFixed(3)],
    ['AUC-PR holdout', hf.auc_pr.toFixed(3)],
    ['Precision holdout', pct(hf.precision)],
    ['Recall holdout', pct(hf.recall)],
    ['F1 holdout', hf.f1.toFixed(3)],
    ['Recall@K holdout', hf.recall_at_k.toFixed(3)],
  ], [4400, 4400]),
  parrafo(`La configuración seleccionada es n_estimators=${tuneFrac.mejor_configuracion.n_estimators}, max_samples=${tuneFrac.mejor_configuracion.max_samples}, contamination=${tuneFrac.mejor_configuracion.contamination}. El modelo se persiste junto con su scaler en outputs/models/.`),
  subtitulo('3.2 Documentación técnica y manual de implementación/despliegue'),
  vineta('Entorno Python reproducible mediante requirements.txt; Spark usa Java 17 y PySpark fijado por versión.'),
  vineta('Ejecución de regresión: pytest -q.'),
  vineta('Pipeline local: generación -> Bronce -> preprocesamiento -> Plata -> modelos sklearn/Spark/GraphFrames -> Oro -> manifiesto -> documentación.'),
  vineta('Airflow usa CGR_PROJECT_PYTHON para separar el runtime del proyecto del entorno propio de Airflow.'),
  vineta('Los modelos candidatos no se promocionan automáticamente; la promoción requiere revisión humana.'),
  subtitulo('3.3 Pruebas de integración y validación del pipeline'),
  ...tablaConTitulo(2, 'Estado de los componentes de cierre del Séptimo Producto', ['Componente solicitado', 'Estado verificable del PoC'], [
    ['Registro de pruebas de integración', 'GitHub Actions ejecuta pytest y smoke end-to-end en cada push/PR.'],
    ['Validación del pipeline completo', 'Ejecutado desde Bronce/Plata hasta Spark, Oro, linaje, manifiesto y DOCX.'],
    ['Documentación para certificación/producción', 'Generada como PoC; certificación institucional pendiente.'],
    ['Incidencias en certificación', 'No aplicable fuera de ambientes CGR; no se inventan incidencias.'],
    ['Transferencia a usuarios técnicos/funcionales', 'Material y estructura disponibles; sesión efectiva pendiente de usuarios CGR.'],
    ['Repositorio organizado', 'Código, datasets sintéticos, evidencias, reportes y CI versionados en GitHub.'],
    ['Mejoras de marcha blanca', 'No existe marcha blanca institucional; se documentan mejoras derivadas de auditorías técnicas del PoC.'],
  ], [3600, 5200]),
  ...imagenConTitulo(1, 'Red proveedor-funcionario del escenario sintético', '../outputs/charts/10_grafo_vinculos.png', 610, 420),
  ...imagenConTitulo(2, 'DAG principal de orquestación del PoC', '../outputs/charts/11_dag_airflow.png', 610, 300),
  subtitulo('3.4 Plan de monitoreo y mantenimiento'),
  ...tablaConTitulo(3, 'Plan de monitoreo y mantenimiento', ['Control', 'Acción propuesta'], [
    ['Calidad de datos', 'Validar esquema, nulos, rangos y conteos antes del scoring.'],
    ['Drift', 'Calcular PSI sobre features clave y revisar cambios materiales.'],
    ['Desempeño', 'Medir AUC-PR/recall cuando exista ground truth nuevo y validado.'],
    ['Reentrenamiento', 'Generar modelo candidato; evaluar en holdout independiente; no promover automáticamente.'],
    ['Trazabilidad', 'Registrar commit, versiones, hashes, parámetros y artefactos en run_manifest.json.'],
    ['Normativa', 'Versionar cuantías y vigencias; ejecutar pruebas unitarias ante cada cambio.'],
  ], [2800, 6000]),
  subtitulo('3.5 Transferencia de conocimiento y mejoras'),
  parrafo('La documentación, README, diccionario, linaje, manifiesto, código comentado y productos formales constituyen material base para transferencia. La realización y acta de sesiones con usuarios técnicos/funcionales requiere coordinación y participantes CGR.'),
  vineta('Mejora aplicada: corrección de integridad OCDS Contract -> Award -> Supplier.'),
  vineta('Mejora aplicada: separación de Contratación Directa y Comparación de Precios.'),
  vineta('Mejora aplicada: holdout independiente para fraccionamiento y eliminación de leakage de tuning.'),
  vineta('Mejora aplicada: Spark MLlib y GraphFrames incorporados al pipeline canónico y al CI.'),
  vineta('Mejora aplicada: documentación regenerada automáticamente desde evidencia versionada.'),
  titulo('4. Conclusiones y Recomendaciones'),
  parrafo('El PoC queda técnicamente reproducible y con las principales brechas de integridad, modelado, Spark y trazabilidad cerradas. Random Forest es el candidato principal del benchmark de favoritismo; en fraccionamiento la baja AUC-PR del holdout obliga a mantener una interpretación prudente y revisión humana. Como siguiente paso institucional se recomienda validar ground truth con auditores, desplegar en DEV/QA, medir rendimiento distribuido y ejecutar certificación, marcha blanca y transferencia formal.'),
  titulo('5. Anexos'),
  ...anexosBase([
    vineta(`GraphFrames ejecutado: ${graphframes.n_vertices ?? 'N/D'} vértices y ${graphframes.n_aristas ?? 'N/D'} aristas en escenario sintético.`),
    vineta('Diccionario de datos: data/diccionario_datos.csv.'),
    vineta('Diagrama del modelo: outputs/charts/09_diagrama_modelo_datos.png.'),
    vineta('Artefactos SSRS PoC: directorio ssrs/.'),
  ]),
  ...referencias(),
]);

async function guardar(doc, nombreArchivo) {
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(`${OUT}/${nombreArchivo}`, buf);
  console.log(`Generado: ${OUT}/${nombreArchivo}`);
}

(async () => {
  await guardar(p1, 'Producto_01_Plan_de_Trabajo.docx');
  await guardar(p2, 'Producto_02_Preprocesamiento_Favoritismo.docx');
  await guardar(p3, 'Producto_03_Modelo_Favoritismo.docx');
  await guardar(p4, 'Producto_04_Entrenamiento_Favoritismo.docx');
  await guardar(p5, 'Producto_05_Preprocesamiento_Fraccionamiento.docx');
  await guardar(p6, 'Producto_06_Modelo_Fraccionamiento.docx');
  await guardar(p7, 'Producto_07_Informe_Final.docx');
  console.log('Los 7 productos fueron regenerados desde evidencia_documental.json con estructura del Anexo 1.');
})();
