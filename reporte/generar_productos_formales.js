const { Packer } = require('docx');
const fs = require('fs');
const {
  titulo, subtitulo, parrafo, vineta, tablaConTitulo, imagenConTitulo,
  frontMatter, referencias, documento,
} = require('./plantilla_docx');
const {
  e, pct, num, pen, modelo, syn, fav, frac, selFav, tuneFav, tuneFrac,
  sparkFavEval, sparkFracEval, monitorChampion, p0,
} = require('./evidencia');

const OUT = 'productos_formales';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
for (const name of fs.readdirSync(OUT)) {
  if (/^Producto_.*\.docx$/i.test(name)) fs.rmSync(`${OUT}/${name}`);
}

const rf = modelo('RandomForest');
const lr = modelo('RegresionLogistica');
const gb = modelo('GradientBoosting');
const favHoldout = sparkFavEval.metricas_holdout_final;
const fracHoldout = sparkFracEval.metricas_holdout_final;
const isoHoldout = tuneFrac.metricas_holdout_final;
const p0i = p0.integridad_ocds;
const manifest = e.run_manifest || {};
const graphframes = manifest.graphframes || {};

const OBJETIVO_TDR =
  'El TDR tomado como referencia plantea disponer datos procesados y filtrados de fuentes externas e internas y desarrollar modelos de Machine Learning que permitan identificar casos atípicos y patrones de riesgo relevantes para la labor del auditor. Este repositorio demuestra ese objetivo como prototipo independiente y reproducible, sin atribuirse aprobación o despliegue institucional CGR.';

const LIMITACION =
  'Las métricas obtenidas con el benchmark sintético verifican coherencia metodológica y funcionamiento reproducible del pipeline; no estiman por sí solas desempeño productivo. Las salidas son señales de priorización para revisión humana y no constituyen hallazgos ni determinaciones automáticas de irregularidad.';

function f3(v) {
  return Number(v).toFixed(3);
}

function notaMetodologica() {
  return parrafo(`Nota metodológica: ${LIMITACION}`);
}

function anexosBase(extra = []) {
  return [
    vineta('Repositorio, código y documentación técnica: https://github.com/NoeCalle/cgr-analisis-datos'),
    vineta('Fuente machine-readable de cifras documentales: outputs/evidencia_documental.json.'),
    vineta('Trazabilidad: outputs/run_manifest.json, outputs/linaje_datos.csv y outputs/model_registry.json.'),
    vineta('Arquitectura MLOps: docs/Arquitectura_MLOps.md.'),
    vineta('Evaluación Spark y performance: docs/Evaluacion_Spark_y_Performance.md.'),
    ...extra,
  ];
}

function informeProducto({
  numero, nombre, resumen, introduccion, alcanzados, actividades, cumplimiento,
  dificultades, conclusiones, tablas = [], graficos = [], anexos = [],
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
    ...referencias(),
  ]);
}

// -----------------------------------------------------------------------------
// Producto 1 — Plan de Trabajo
// -----------------------------------------------------------------------------
const p1 = documento(1, 'Plan de Trabajo', 'Plan de Trabajo', [
  ...frontMatter({
    tablas: [
      'Productos y propósito técnico',
      'Actividades principales por producto',
      'Cronograma contractual de referencia',
    ],
    graficos: [],
  }),
  titulo('1. Introducción'),
  parrafo(
    'El plan organiza una prueba de concepto independiente basada en el TDR público del Proyecto Interno 1.8.2. El trabajo se estructura por contratos técnicos verificables: integración canónica, calidad de datos, feature engineering, evaluación, modelos Spark MLlib, grafos, TRAIN/INFERENCE, monitoreo, trazabilidad y reporting. Las actividades que requieren accesos, infraestructura o conformidad CGR se mantienen como dependencias institucionales.'
  ),
  titulo('2. Objetivo de Consultoría'),
  parrafo(OBJETIVO_TDR),
  titulo('3. Productos a Alcanzar'),
  ...tablaConTitulo(1, 'Productos y propósito técnico', ['N.°', 'Producto', 'Propósito'], [
    ['1', 'Plan de Trabajo', 'Metodología, actividades, cronograma y criterios de evidencia.'],
    ['2', 'Preprocesamiento - Favoritismo', 'Calidad, limpieza, estado FIT/TRANSFORM y features proveedor-entidad.'],
    ['3', 'Modelo - Favoritismo', 'Selección metodológica, Random Forest Spark MLlib e interpretabilidad.'],
    ['4', 'Entrenamiento/Validación - Favoritismo', 'CV, tuning, holdout, candidate/champion y métricas.'],
    ['5', 'Preprocesamiento - Fraccionamiento', 'Objeto-familia, ventanas coherentes y contexto normativo.'],
    ['6', 'Modelo - Fraccionamiento', 'KMeans Spark, distancia al centroide, holdout y señal interpretable.'],
    ['7', 'Informe Final', 'Integración, MLOps, monitoreo, reporting, seguridad y ruta institucional.'],
  ], [700, 3000, 5100]),
  titulo('4. Actividades a Cumplir por Cada Producto'),
  ...tablaConTitulo(2, 'Actividades principales por producto', ['Producto', 'Actividades'], [
    ['1', 'Definir alcance, evidencia, dependencias y criterios de aceptación verificables.'],
    ['2', 'Integrar datos, aplicar quality gates, ajustar preprocesador y construir features de favoritismo.'],
    ['3', 'Comparar algoritmos, justificar Random Forest y ejecutar implementación Apache Spark MLlib.'],
    ['4', 'Reservar holdout antes del FIT, ejecutar CV/tuning, documentar métricas y persistencia.'],
    ['5', 'Normalizar objetos, construir ventanas de 15 días y resolver referencias normativas.'],
    ['6', 'Seleccionar k en desarrollo, evaluar KMeans en holdout y conservar benchmark complementario.'],
    ['7', 'Documentar TRAIN/INFERENCE, registry, monitoreo, Airflow, SQL Server/SSRS, seguridad y transferencia.'],
  ], [1200, 7600]),
  titulo('5. Cronograma'),
  parrafo('Plazos contractuales de referencia del TDR, contados desde el día siguiente de la suscripción del contrato:'),
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
    vineta('La auditoría integral del TDR distingue evidencia reproducible de dependencias institucionales.'),
    vineta('La descripción funcional vigente se encuentra en README.md; la historia de cambios permanece en Git/PR.'),
  ]),
  ...referencias(),
]);

// -----------------------------------------------------------------------------
// Producto 2 — Preprocesamiento Favoritismo
// -----------------------------------------------------------------------------
const p2 = informeProducto({
  numero: 2,
  nombre: 'Preprocesamiento para Identificación de Proveedores Favoritos',
  resumen: `El benchmark reproducible contiene ${num(syn.contratos)} contratos y produce ${num(fav.pares_proveedor_entidad)} pares proveedor-entidad. El contrato operacional separa FIT y TRANSFORM, congela estadísticas aprendidas y utiliza monto_capped para limitar la influencia de extremos monetarios en favoritismo.`,
  introduccion: 'Este producto documenta cómo se transforma el contrato canónico en variables aptas para el modelo de favoritismo y por qué el preprocesamiento se ajusta únicamente durante TRAIN.',
  tablas: ['Estado y decisiones del preprocesamiento de favoritismo'],
  graficos: ['Distribución de montos contractuales', 'Modalidades de contratación del benchmark'],
  alcanzados: [
    subtitulo('3.1 Contrato FIT/TRANSFORM'),
    parrafo('TRAIN aprende medianas por objeto, mediana global, modas y P99. INFERENCE recibe ese estado congelado y no recalcula parámetros con el lote actual. Esta separación evita train-serving skew y preserva trazabilidad.'),
    subtitulo('3.2 Tratamiento de montos'),
    parrafo('Favoritismo utiliza monto_capped con un límite P99 aprendido en TRAIN. La decisión reduce la dominancia de valores monetarios extremos sobre agregados sin introducir información del lote de inferencia.'),
    ...tablaConTitulo(1, 'Estado y decisiones del preprocesamiento de favoritismo', ['Elemento', 'Evidencia/decisión'], [
      ['Contratos sintéticos', num(syn.contratos)],
      ['P99 del monto', pen(syn.p99_monto_pen)],
      ['Pares proveedor-entidad', num(fav.pares_proveedor_entidad)],
      ['Positivos sintéticos', num(fav.positivos_sembrados)],
      ['Modalidades', 'Contratación Directa y Comparación de Precios se conservan como variables separadas.'],
      ['Estado de serving', 'Preprocesador congelado; INFERENCE no ejecuta FIT.'],
    ], [3300, 5500]),
    ...imagenConTitulo(1, 'Distribución de montos contractuales', '../outputs/charts/01_distribucion_montos.png', 610, 350),
    ...imagenConTitulo(2, 'Modalidades de contratación del benchmark', '../outputs/charts/02_modalidades_contratacion.png', 610, 350),
    subtitulo('3.3 Feature engineering'),
    vineta('Número de contratos, monto total y promedio por proveedor-entidad.'),
    vineta('Número de objetos únicos y concentración temática.'),
    vineta('Porcentaje de Contratación Directa y Comparación de Precios por separado.'),
    vineta('Funcionarios distintos, días de actividad, contratos por mes y monto por funcionario.'),
  ],
  actividades: [
    vineta('Aplicación del contrato canónico y quality gates antes del modelado.'),
    vineta('Ajuste de estadísticas únicamente sobre datos de TRAIN/desarrollo.'),
    vineta('Transformación reproducible y construcción de features.'),
    vineta('Validación automática de schema, labels y consistencia pandas/Spark.'),
  ],
  cumplimiento: 'El contrato de preprocesamiento y features está implementado y probado en el PoC. La recalibración sobre distribuciones institucionales requiere fuentes y ground truth CGR.',
  dificultades: [
    vineta('El ground truth del benchmark es sintético y no representa desempeño real.'),
    vineta('Las reglas de calidad de negocio específicas de SIAF/SEACE dependen del diccionario institucional aprobado.'),
  ],
  conclusiones: 'La separación FIT/TRANSFORM y el uso de monto_capped permiten que la inferencia aplique exactamente el estado aprendido durante entrenamiento. Se recomienda conservar ese contrato al integrar fuentes institucionales.',
});

// -----------------------------------------------------------------------------
// Producto 3 — Modelo Favoritismo
// -----------------------------------------------------------------------------
const p3 = informeProducto({
  numero: 3,
  nombre: 'Selección del Algoritmo y Modelo para Identificación de Proveedores Favoritos',
  resumen: `El serving objetivo utiliza Apache Spark MLlib con RandomForestClassificationModel. La evaluación operacional reserva un holdout antes del FIT y selecciona hiperparámetros únicamente sobre desarrollo; el benchmark sklearn permanece como comparación metodológica y soporte SHAP.`,
  introduccion: 'Este producto fundamenta la selección del algoritmo y diferencia explícitamente el modelo servido de los benchmarks de compatibilidad.',
  tablas: ['Comparación metodológica sklearn', 'Modelo Spark MLlib servido'],
  graficos: ['Concentración de proveedores por entidad', 'Importancia/explicabilidad de variables'],
  alcanzados: [
    subtitulo('3.1 Patrones y unidad analítica'),
    parrafo('El riesgo se prioriza a nivel proveedor-entidad mediante frecuencia, montos, diversidad de objetos, modalidad, temporalidad y relación con funcionarios disponibles.'),
    ...imagenConTitulo(1, 'Concentración de proveedores por entidad', '../outputs/charts/03_concentracion_proveedores.png', 610, 350),
    subtitulo('3.2 Comparación metodológica'),
    ...tablaConTitulo(1, 'Comparación metodológica sklearn', ['Modelo', 'AUC-PR', 'AUC-ROC', 'Precision', 'Recall', 'F1'], [
      ['Random Forest', f3(rf.auc_pr), f3(rf.auc_roc), pct(rf.precision), pct(rf.recall), f3(rf.f1)],
      ['Regresión Logística', f3(lr.auc_pr), f3(lr.auc_roc), pct(lr.precision), pct(lr.recall), f3(lr.f1)],
      ['Gradient Boosting', f3(gb.auc_pr), f3(gb.auc_roc), pct(gb.precision), pct(gb.recall), f3(gb.f1)],
    ], [2200, 1300, 1300, 1300, 1300, 1300]),
    parrafo('AUC-PR se prioriza por el desbalance de la clase positiva. El benchmark sklearn permite comparar familias de modelos y producir SHAP, pero no define el champion activo.'),
    subtitulo('3.3 Modelo operacional Apache Spark MLlib'),
    ...tablaConTitulo(2, 'Modelo Spark MLlib servido', ['Elemento', 'Evidencia'], [
      ['Framework', 'PySpark / Apache Spark MLlib'],
      ['Algoritmo', sparkFavEval.algorithm || 'RandomForestClassificationModel'],
      ['Pipeline', sparkFavEval.pipeline],
      ['Monto', sparkFavEval.amount_source],
      ['CV', sparkFavEval.cv],
      ['Holdout', `${num(sparkFavEval.n_holdout)} pares; ${num(sparkFavEval.positivos_holdout)} positivos sintéticos`],
      ['AUC-PR holdout', f3(favHoldout.auc_pr)],
      ['Recall@K holdout', f3(favHoldout.recall_at_k)],
      ['Configuración', `numTrees=${sparkFavEval.mejor_configuracion.numTrees}; maxDepth=${sparkFavEval.mejor_configuracion.maxDepth}`],
    ], [3000, 5800]),
    parrafo('Random Forest se utiliza porque representa relaciones no lineales, admite ponderación ante desbalance y proporciona Feature Importance directamente ligada al modelo Spark servido.'),
    subtitulo('3.4 Interpretabilidad'),
    parrafo('La Feature Importance del champion Spark constituye evidencia principal de variables utilizadas. SHAP sobre el benchmark sklearn se conserva como explicación complementaria y no sustituye la evidencia del modelo servido.'),
    ...imagenConTitulo(2, 'Importancia de variables del benchmark de favoritismo', '../outputs/charts/05_importancia_favoritismo.png', 610, 350),
  ],
  actividades: [
    vineta('Comparación de Regresión Logística, Random Forest y Gradient Boosting.'),
    vineta('Selección/tuning con AUC-PR en desarrollo.'),
    vineta('Implementación RandomForestClassificationModel con Apache Spark MLlib.'),
    vineta('Registro de Feature Importance y evidencia PySpark reproducible.'),
  ],
  cumplimiento: 'La selección, implementación MLlib y evaluación del pipeline servido son reproducibles. La aceptación productiva necesita ground truth, umbrales y pruebas institucionales.',
  dificultades: [
    vineta('El benchmark sintético puede ser más separable que un corpus institucional.'),
    vineta('La estabilidad por periodo/segmento debe validarse con datos históricos CGR.'),
  ],
  conclusiones: 'Random Forest Spark es el modelo operacional del PoC para favoritismo; sklearn se mantiene como benchmark/explicabilidad. Las métricas sintéticas no deben extrapolarse como desempeño productivo.',
});

// -----------------------------------------------------------------------------
// Producto 4 — Entrenamiento y validación Favoritismo
// -----------------------------------------------------------------------------
const p4 = informeProducto({
  numero: 4,
  nombre: 'Entrenamiento y Validación del Modelo de Proveedores Favoritos',
  resumen: `La evaluación Spark reserva ${num(sparkFavEval.n_holdout)} pares proveedor-entidad para holdout final antes de ajustar el preprocesador. El candidate TRAIN solo puede consumir evidencia del mismo fingerprint de corpus y no modifica el champion hasta una promoción explícita.`,
  introduccion: 'Este producto documenta la separación entre selección, evaluación final, TRAIN, candidate y champion, evitando leakage y cambios silenciosos de serving.',
  tablas: ['Métricas holdout del Random Forest Spark', 'Controles del ciclo de modelo'],
  graficos: ['SHAP complementario de favoritismo'],
  alcanzados: [
    subtitulo('3.1 Diseño de evaluación'),
    parrafo(`Desarrollo: ${num(sparkFavEval.n_desarrollo)} pares con ${num(sparkFavEval.positivos_desarrollo)} positivos. Holdout: ${num(sparkFavEval.n_holdout)} pares con ${num(sparkFavEval.positivos_holdout)} positivos. El holdout se reserva antes del FIT y no participa en tuning.`),
    ...tablaConTitulo(1, 'Métricas holdout del Random Forest Spark', ['Métrica', 'Resultado'], [
      ['Accuracy', f3(favHoldout.accuracy)],
      ['AUC-PR', f3(favHoldout.auc_pr)],
      ['AUC-ROC', f3(favHoldout.auc_roc)],
      ['Precision', f3(favHoldout.precision)],
      ['Recall', f3(favHoldout.recall)],
      ['F1', f3(favHoldout.f1)],
      ['Recall@K', f3(favHoldout.recall_at_k)],
    ], [4400, 4400]),
    parrafo('Los resultados corresponden al benchmark sintético/local de la evidencia vigente. Una métrica alta valida el escenario de prueba, no garantiza generalización institucional.'),
    subtitulo('3.2 Candidate, champion y fingerprint'),
    ...tablaConTitulo(2, 'Controles del ciclo de modelo', ['Control', 'Decisión'], [
      ['Fingerprint', 'La evidencia y TRAIN deben corresponder al mismo corpus canónico.'],
      ['Candidate', 'TRAIN genera artefactos candidatos y no cambia serving.'],
      ['Promoción', 'Operación separada, explícita y con verificación SHA-256.'],
      ['Champion', 'Se almacena/versiona como conjunto coherente de artefactos.'],
      ['INFERENCE', 'No consume labels, FIT ni tuning.'],
      ['Rollback', 'Vuelve a un champion histórico cuyos hashes sean válidos.'],
    ], [3000, 5800]),
    subtitulo('3.3 Explicabilidad complementaria'),
    ...imagenConTitulo(1, 'Resumen SHAP del benchmark sklearn', '../outputs/charts/07_shap_summary_favoritismo.png', 610, 350),
  ],
  actividades: [
    vineta('Reserva del holdout antes del FIT del preprocesador.'),
    vineta('CV/tuning únicamente sobre desarrollo.'),
    vineta('Cálculo de métricas agregadas y recall@K.'),
    vineta('Vinculación de evaluación y TRAIN mediante fingerprint SHA-256.'),
    vineta('Persistencia candidate/champion con hashes y promoción explícita.'),
  ],
  cumplimiento: 'La metodología de evaluación y el contrato MLOps están implementados. Los umbrales productivos y la autoridad de promoción deben ser definidos institucionalmente.',
  dificultades: [
    vineta('El holdout sintético no reemplaza validación temporal o por segmentos sobre casos CGR.'),
    vineta('La aprobación de un modelo requiere criterios funcionales además de métricas estadísticas.'),
  ],
  conclusiones: 'El ciclo evita usar el holdout para selección y evita que TRAIN cambie el modelo servido. En una adopción CGR se debe mantener la misma separación y agregar gates institucionales.',
});

// -----------------------------------------------------------------------------
// Producto 5 — Preprocesamiento Fraccionamiento
// -----------------------------------------------------------------------------
const p5 = informeProducto({
  numero: 5,
  nombre: 'Preprocesamiento para Detección de Posible Fraccionamiento',
  resumen: `El feature engineering agrupa contratos por proveedor-entidad-objeto_familia y calcula cantidad y monto sobre una misma ventana de 15 días. Fraccionamiento conserva el monto original para mantener el significado de las comparaciones con cuantías normativas.`,
  introduccion: 'Este producto documenta el contrato temporal, lexical y normativo previo al modelo de fraccionamiento.',
  tablas: ['Features principales de fraccionamiento'],
  graficos: ['Serie temporal del benchmark de contratación'],
  alcanzados: [
    subtitulo('3.1 Objeto-familia'),
    parrafo('La firma objeto_familia aplica una normalización lexical conservadora y sinónimos controlados. Su propósito es agrupar variaciones menores sin depender de embeddings opacos y conservando trazabilidad reproducible.'),
    subtitulo('3.2 Ventana coherente de 15 días'),
    parrafo('max_contratos_ventana_15d y monto_total_ventana_15d proceden de la misma ventana seleccionada. Esto evita presentar dos indicadores como si describieran un mismo episodio cuando pertenecen a intervalos distintos.'),
    subtitulo('3.3 Contexto normativo'),
    parrafo('La categoría estructurada goods/services/works tiene prioridad cuando existe. El texto libre funciona como fallback conservador. Las cuantías se parametrizan por fecha/categoría y no se aproximan para periodos desconocidos.'),
    ...tablaConTitulo(1, 'Features principales de fraccionamiento', ['Feature', 'Interpretación'], [
      ['n_contratos_grupo', 'Cantidad total de contratos del grupo proveedor-entidad-familia.'],
      ['max_contratos_ventana_15d', 'Mayor concentración de contratos dentro de una ventana de 15 días.'],
      ['monto_total_ventana_15d', 'Monto acumulado de esa misma ventana seleccionada.'],
      ['pct_montos_bajo_umbral', 'Proporción de montos cercanos por debajo de la cuantía parametrizada.'],
      ['monto_total_grupo', 'Monto acumulado del grupo analítico.'],
    ], [3300, 5500]),
    ...imagenConTitulo(1, 'Serie temporal del benchmark de contratación', '../outputs/charts/04_serie_temporal.png', 610, 350),
    subtitulo('3.4 División para evaluación'),
    parrafo(`El evaluador Spark reserva ${num(sparkFracEval.n_holdout)} grupos para holdout final y mantiene ${num(sparkFracEval.n_desarrollo)} en desarrollo. La unidad de split incluye proveedor, entidad y familia de objeto.`),
  ],
  actividades: [
    vineta('Normalización determinística de objetos contractuales.'),
    vineta('Cálculo de ventanas temporales con paridad pandas/Spark.'),
    vineta('Consulta de umbrales por fecha y categoría.'),
    vineta('Reserva de holdout antes del FIT del preprocesador.'),
  ],
  cumplimiento: 'El feature engineering temporal/normativo y la frontera pandas/Spark están implementados. La validación jurídica de cada caso requiere revisión funcional.',
  dificultades: [
    vineta('La ventana de 15 días es una heurística analítica y no una determinación jurídica por sí sola.'),
    vineta('La similitud lexical es deliberadamente conservadora; casos semánticos más complejos podrían requerir una estrategia institucional adicional.'),
  ],
  conclusiones: 'El preprocesamiento mantiene trazabilidad al agrupar variantes lexicales y garantiza que cantidad y monto describan el mismo intervalo. Esa coherencia debe preservarse en cualquier integración institucional.',
});

// -----------------------------------------------------------------------------
// Producto 6 — Modelo Fraccionamiento
// -----------------------------------------------------------------------------
const p6 = informeProducto({
  numero: 6,
  nombre: 'Selección del Algoritmo y Modelo para Detección de Posible Fraccionamiento',
  resumen: `El modelo servido utiliza Apache Spark MLlib con StandardScalerModel + KMeansModel y distancia al centroide. k se selecciona únicamente en desarrollo y el holdout final independiente obtiene AUC-PR ${f3(fracHoldout.auc_pr)}. Isolation Forest permanece como benchmark sklearn complementario y no define el champion.`,
  introduccion: 'Este producto presenta como evidencia principal el KMeans Spark realmente utilizado por el perfil operacional y separa sus métricas del benchmark Isolation Forest.',
  tablas: ['Evaluación holdout KMeans Spark', 'Benchmark Isolation Forest complementario'],
  graficos: ['Señales de posible fraccionamiento'],
  alcanzados: [
    subtitulo('3.1 Justificación del algoritmo'),
    parrafo('Apache Spark MLlib no incorpora Isolation Forest nativo. KMeans permite una implementación distribuible: StandardScaler normaliza las features, KMeans aprende centroides sin labels y la distancia al centroide se transforma en score de anomalía para ranking.'),
    subtitulo('3.2 Selección y holdout del KMeans servido'),
    ...tablaConTitulo(1, 'Evaluación holdout KMeans Spark', ['Métrica', 'Resultado'], [
      ['k seleccionado', String(sparkFracEval.mejor_configuracion.k)],
      ['Grupos desarrollo', num(sparkFracEval.n_desarrollo)],
      ['Positivos desarrollo', num(sparkFracEval.positivos_desarrollo)],
      ['Grupos holdout', num(sparkFracEval.n_holdout)],
      ['Positivos holdout', num(sparkFracEval.positivos_holdout)],
      ['AUC-PR', f3(fracHoldout.auc_pr)],
      ['AUC-ROC', f3(fracHoldout.auc_roc)],
      ['Precision', f3(fracHoldout.precision)],
      ['Recall', f3(fracHoldout.recall)],
      ['F1', f3(fracHoldout.f1)],
      ['Recall@K', f3(fracHoldout.recall_at_k)],
    ], [4400, 4400]),
    parrafo('Las etiquetas no se utilizan para ajustar KMeans; se utilizan para seleccionar/evaluar el ranking en el benchmark. El holdout no participa en la selección de k.'),
    subtitulo('3.3 Señal interpretable'),
    parrafo('El score de anomalía se complementa con una regla de caja blanca basada en concentración temporal y montos respecto de cuantías parametrizadas. Esta señal facilita revisión humana, pero no declara fraccionamiento.'),
    ...imagenConTitulo(1, 'Señales de posible fraccionamiento', '../outputs/charts/06_deteccion_fraccionamiento.png', 610, 350),
    subtitulo('3.4 Benchmark complementario'),
    ...tablaConTitulo(2, 'Benchmark Isolation Forest complementario', ['Elemento', 'Resultado'], [
      ['Rol', 'Comparación metodológica sklearn; no es el serving activo.'],
      ['AUC-PR holdout', f3(isoHoldout.auc_pr)],
      ['AUC-ROC holdout', f3(isoHoldout.auc_roc)],
      ['F1 holdout', f3(isoHoldout.f1)],
      ['Recall@K holdout', f3(isoHoldout.recall_at_k)],
    ], [4400, 4400]),
  ],
  actividades: [
    vineta('Evaluación de StandardScaler + KMeans + distancia al centroide.'),
    vineta('Selección de k únicamente sobre desarrollo.'),
    vineta('Evaluación final en holdout independiente.'),
    vineta('Comparación complementaria con Isolation Forest sin confundir sus métricas con el champion.'),
  ],
  cumplimiento: 'El modelo KMeans Spark dispone de selección y holdout propios. La calibración con ground truth real y el rendimiento distribuido deben validarse en infraestructura CGR.',
  dificultades: [
    vineta('El desbalance y el número limitado de positivos sintéticos hacen que las métricas sean variables.'),
    vineta('Un score de anomalía prioriza rareza estadística; la interpretación de irregularidad requiere contexto documental y jurídico.'),
  ],
  conclusiones: 'KMeans Spark es el modelo operacional de fraccionamiento del PoC. Isolation Forest se conserva como benchmark secundario; la evidencia principal del entregable corresponde al pipeline servido.',
});

// -----------------------------------------------------------------------------
// Producto 7 — Informe Final
// -----------------------------------------------------------------------------
const p7 = documento(7, 'Informe Final', 'Informe Final de la Consultoría - Prototipo Independiente', [
  titulo('Resumen Ejecutivo'),
  parrafo(
    'El prototipo integra datos mediante un esquema canónico, aplica quality gates, construye señales de posible favoritismo y fraccionamiento, ejecuta Random Forest y KMeans con Apache Spark MLlib, analiza vínculos con GraphFrames y separa evaluación, TRAIN, candidate, promoción, champion e INFERENCE. La documentación formal presenta como evidencia principal los modelos Spark servidos y conserva sklearn únicamente como benchmark/explicabilidad complementaria.'
  ),
  notaMetodologica(),
  ...frontMatter({
    tablas: ['Resumen de modelos operacionales', 'Plan de monitoreo y mantenimiento', 'Cierre frente a dependencias institucionales'],
    graficos: ['Diagrama del modelo de datos', 'Red proveedor-funcionario sintética'],
  }),
  titulo('1. Introducción'),
  parrafo('Este informe consolida el estado funcional de la herramienta y las decisiones técnicas que permiten reproducirla. La historia de correcciones se conserva en Git/PR y no forma parte de la descripción principal del sistema.'),
  titulo('2. Objetivo de Consultoría'),
  parrafo(OBJETIVO_TDR),
  titulo('3. Productos Alcanzados'),
  subtitulo('3.1 Arquitectura y modelos'),
  ...tablaConTitulo(1, 'Resumen de modelos operacionales', ['Caso', 'Modelo servido', 'Evaluación principal'], [
    ['Favoritismo', 'RandomForestClassificationModel - Spark MLlib', `AUC-PR holdout ${f3(favHoldout.auc_pr)}; recall@K ${f3(favHoldout.recall_at_k)}`],
    ['Fraccionamiento', `StandardScaler + KMeans (k=${sparkFracEval.mejor_configuracion.k}) - Spark MLlib`, `AUC-PR holdout ${f3(fracHoldout.auc_pr)}; recall@K ${f3(fracHoldout.recall_at_k)}`],
    ['Grafos', 'GraphFrames / NetworkX', 'Señales de vínculo para revisión humana.'],
  ], [2200, 3300, 3300]),
  parrafo('La ruta spark_sql mantiene DataFrames Spark en integración, validación, preprocesamiento, evaluación, TRAIN e INFERENCE y publica rankings distribuidos en Parquet.'),
  ...imagenConTitulo(1, 'Diagrama del modelo de datos', '../outputs/charts/09_diagrama_modelo_datos.png', 610, 360),
  subtitulo('3.2 Plan de monitoreo y mantenimiento'),
  ...tablaConTitulo(2, 'Plan de monitoreo y mantenimiento', ['Control', 'Tratamiento'], [
    ['Calidad de datos', 'Quality gates de esquema, unicidad, integridad referencial y rangos estructurales.'],
    ['Drift', 'PSI sobre features y distribución de score de fraccionamiento.'],
    ['Desempeño', 'Recall@K cuando existe ground truth nuevo y validado.'],
    ['Reentrenamiento', 'Genera candidate; requiere evaluación y no se promueve automáticamente.'],
    ['Integridad', 'SHA-256 antes/después de INFERENCE y promoción versionada.'],
    ['Normativa', 'Cuantías versionadas por fecha/categoría y regresiones automáticas.'],
  ], [3000, 5800]),
  parrafo(`El monitor se liga al champion activo del registry. Promoción automática: ${monitorChampion.automatic_promotion === false ? 'deshabilitada' : 'no permitida por contrato'}.`),
  subtitulo('3.3 Pruebas de integración y operación'),
  parrafo('Las pruebas de integración del repositorio cubren CI, Spark MLlib, GraphFrames, candidate/champion, inference, calidad de datos, generación documental y reporting local. Las pruebas de integración DEV/QA/PROD, carga, concurrencia, skew, seguridad y operación real requieren infraestructura institucional.'),
  subtitulo('3.4 Reporting y transferencia'),
  parrafo('El contrato SQL Server/SSRS se entrega como DDL, vistas, roles de referencia y RDL con Shared Data Source. La Transferencia de conocimiento se apoya en README, documentación técnica, diccionario, linaje, manifests y Productos 1-7; las sesiones y actas formales requieren participantes CGR.'),
  ...imagenConTitulo(2, 'Red proveedor-funcionario sintética', '../outputs/charts/10_grafo_vinculos.png', 610, 410),
  subtitulo('3.5 Certificación y marcha blanca'),
  parrafo('La certificación funcional, levantamiento de incidencias y marcha blanca no pueden acreditarse desde el repositorio público. Requieren usuarios, ambientes, fuentes y criterios de aceptación institucionales.'),
  subtitulo('3.6 Dependencias institucionales'),
  ...tablaConTitulo(3, 'Cierre frente a dependencias institucionales', ['Área', 'Estado'], [
    ['Software reproducible', 'Implementado y validado por CI.'],
    ['Ground truth real', 'Dependencia institucional.'],
    ['Spark/almacenamiento CGR', 'Dependencia institucional para performance y robustez.'],
    ['DEV/QA/PROD', 'Dependencia institucional.'],
    ['SQL Server/SSRS institucional', 'Contrato preparado; ejecución institucional pendiente.'],
    ['Certificación / marcha blanca', 'Dependencia institucional.'],
  ], [3600, 5200]),
  titulo('4. Conclusiones y Recomendaciones'),
  parrafo('La herramienta queda documentada como un sistema de priorización reproducible: esquema canónico, preprocesador congelado, modelos Spark con evaluación propia, registry versionado, promoción explícita, inference sin retraining y monitoreo ligado al champion. El siguiente nivel de evidencia requiere ground truth, infraestructura y validación funcional CGR; no debe inferirse producción certificada a partir de los resultados sintéticos.'),
  titulo('5. Anexos'),
  ...anexosBase([
    vineta(`Validación OCDS: ${num(p0i.contratos_analiticos_validos)} contratos analíticos con award/supplier resoluble.`),
    vineta(`GraphFrames: ${graphframes.n_vertices ?? 'N/D'} vértices y ${graphframes.n_aristas ?? 'N/D'} aristas en evidencia sintética.`),
    vineta('Dependencias institucionales: docs/Dependencias_Institucionales_CGR.md.'),
  ]),
  ...referencias(),
]);

const PRODUCTOS = [
  ['Producto_01_Plan_de_Trabajo.docx', p1],
  ['Producto_02_Preprocesamiento_Favoritismo.docx', p2],
  ['Producto_03_Modelo_Favoritismo.docx', p3],
  ['Producto_04_Entrenamiento_Favoritismo.docx', p4],
  ['Producto_05_Preprocesamiento_Fraccionamiento.docx', p5],
  ['Producto_06_Modelo_Fraccionamiento.docx', p6],
  ['Producto_07_Informe_Final.docx', p7],
];

async function main() {
  for (const [filename, doc] of PRODUCTOS) {
    const buffer = await Packer.toBuffer(doc);
    fs.writeFileSync(`${OUT}/${filename}`, buffer);
    console.log(`Generado: ${OUT}/${filename}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
