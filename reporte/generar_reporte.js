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
  'El TDR establece como objetivo disponer datos procesados y filtrados de fuentes externas e internas y desarrollar modelos de Machine Learning para identificar casos atípicos y patrones de riesgo relevantes para la labor del auditor. El presente informe documenta cómo ese objetivo se implementa en un prototipo independiente, reproducible y preparado para integración institucional sin atribuirle aprobación CGR.';

function f3(v) {
  return Number(v).toFixed(3);
}

const doc = documento('TÉCNICO', 'Informe Final Técnico Consolidado', 'Informe Final Técnico Consolidado del Prototipo', [
  titulo('Resumen Ejecutivo'),
  parrafo(
    'El Módulo de Análisis de Datos implementa una arquitectura reproducible para integrar información contractual, validar su calidad, construir señales de posible favoritismo y fraccionamiento, analizar vínculos y pagos, y priorizar casos para revisión humana. El perfil operacional utiliza Apache Spark MLlib: Random Forest para favoritismo y StandardScaler + KMeans + distancia al centroide para fraccionamiento. La selección/evaluación de ambos modelos está separada de TRAIN, la promoción es explícita, INFERENCE no reentrena y el monitor se liga al champion activo.'
  ),
  parrafo(
    'Las implementaciones sklearn se mantienen como benchmarks metodológicos y soporte de explicabilidad; no se presentan como los modelos servidos. Las métricas sintéticas verifican consistencia del pipeline y no constituyen estimaciones de desempeño productivo. Las salidas son señales de priorización y no hallazgos ni determinaciones automáticas de irregularidad.'
  ),
  ...frontMatter({
    tablas: [
      'Arquitectura y decisiones principales',
      'Modelos operacionales y métricas holdout',
      'Comparación metodológica sklearn de favoritismo',
      'Benchmark complementario Isolation Forest',
      'Validación OCDS/OECE',
      'MLOps, monitoreo y seguridad',
      'Estado frente a dependencias institucionales',
    ],
    graficos: [
      'Diagrama del modelo de datos',
      'Importancia de variables de favoritismo',
      'Señales de posible fraccionamiento',
      'Red proveedor-funcionario sintética',
    ],
  }),

  titulo('1. Introducción'),
  parrafo(
    'La documentación técnica se organiza alrededor del estado vigente de la herramienta: qué problema resuelve, qué contrato de datos utiliza, qué modelos sirve, cómo se evalúan, cómo se promueven y qué controles evitan leakage, train-serving skew o publicación de resultados con artefactos inconsistentes. El historial de correcciones se conserva en Git y pull requests; no es necesario para comprender la arquitectura actual.'
  ),
  parrafo(
    'El repositorio no utiliza accesos internos CGR. Las fuentes, ground truth, identidades, clúster, DEV/QA/PROD, SQL Server/SSRS real, criterios de aceptación, certificación, marcha blanca y transferencia formal permanecen como dependencias institucionales.'
  ),

  titulo('2. Objetivo de Consultoría'),
  parrafo(OBJETIVO_TDR),

  titulo('3. Productos Alcanzados'),

  subtitulo('3.1 Arquitectura de la herramienta'),
  parrafo(
    'Las fuentes se desacoplan mediante conectores y mappings YAML hacia un esquema canónico. Después del mapping/casteo se ejecutan quality gates antes de feature engineering. TRAIN ajusta y congela el preprocesador; INFERENCE reutiliza ese estado sin FIT. El model registry separa perfiles sklearn y spark_mllib, y el perfil operacional objetivo es spark_mllib.'
  ),
  ...tablaConTitulo(1, 'Arquitectura y decisiones principales', ['Decisión', 'Fundamento'], [
    ['Esquema canónico', 'Evita acoplar modelos a nombres físicos de tablas/columnas.'],
    ['Quality gates antes del modelado', 'Impiden que duplicados, claves rotas o montos inválidos generen señales artificiales.'],
    ['FIT solo en TRAIN', 'Evita train-serving skew y mantiene inferencia reproducible.'],
    ['monto_capped en favoritismo', 'Limita influencia de extremos mediante P99 aprendido solo en TRAIN.'],
    ['Monto original en fraccionamiento', 'Preserva la semántica de comparación con cuantías normativas.'],
    ['spark_sql distribuido', 'Evita materializar el corpus contractual en pandas/driver.'],
    ['Promoción separada de TRAIN', 'Impide que entrenar cambie serving automáticamente.'],
    ['Champion store versionado', 'Permite verificar conjuntos completos y ejecutar rollback explícito.'],
  ], [3000, 5800]),
  ...imagenConTitulo(1, 'Diagrama del modelo de datos', '../outputs/charts/09_diagrama_modelo_datos.png', 610, 360),

  subtitulo('3.2 Contrato de datos y preprocesamiento'),
  parrafo(
    'El contrato canónico soporta contracts, suppliers, entities, officials y payments. INFERENCE exige los atributos estructurales de contracts, pero no labels. TRAIN añade label_favoritismo y label_fraccionamiento. El preprocesador aprende medianas, modas y P99 durante TRAIN y se congela para serving.'
  ),
  vineta('Contratación Directa y Comparación de Precios se modelan como variables separadas.'),
  vineta('Favoritismo agrega señales por proveedor-entidad.'),
  vineta('Fraccionamiento agrega por proveedor-entidad-objeto_familia.'),
  vineta('objeto_familia aplica normalización lexical conservadora y auditable.'),
  vineta('Cantidad y monto de la ventana de 15 días proceden del mismo intervalo seleccionado.'),

  subtitulo('3.3 Modelos operacionales Spark MLlib'),
  ...tablaConTitulo(2, 'Modelos operacionales y métricas holdout', ['Caso', 'Modelo', 'AUC-PR', 'AUC-ROC', 'Precision', 'Recall', 'F1', 'Recall@K'], [
    [
      'Favoritismo',
      `RandomForest (numTrees=${sparkFavEval.mejor_configuracion.numTrees}, maxDepth=${sparkFavEval.mejor_configuracion.maxDepth})`,
      f3(favHoldout.auc_pr), f3(favHoldout.auc_roc), f3(favHoldout.precision),
      f3(favHoldout.recall), f3(favHoldout.f1), f3(favHoldout.recall_at_k),
    ],
    [
      'Fraccionamiento',
      `StandardScaler + KMeans (k=${sparkFracEval.mejor_configuracion.k})`,
      f3(fracHoldout.auc_pr), f3(fracHoldout.auc_roc), f3(fracHoldout.precision),
      f3(fracHoldout.recall), f3(fracHoldout.f1), f3(fracHoldout.recall_at_k),
    ],
  ], [1200, 2200, 900, 900, 900, 900, 900, 900]),
  parrafo(
    `Favoritismo reserva ${num(sparkFavEval.n_holdout)} pares para holdout antes del FIT del preprocesador y usa AUC-PR como métrica primaria por desbalance. Fraccionamiento reserva ${num(sparkFracEval.n_holdout)} grupos; KMeans se ajusta sin labels y las etiquetas se usan para seleccionar/evaluar la capacidad de priorización del ranking.`
  ),
  parrafo(
    'Las métricas anteriores corresponden al benchmark sintético/local de la evidencia vigente. Deben utilizarse para verificar el método y el pipeline, no para afirmar precisión sobre expedientes institucionales.'
  ),

  subtitulo('3.4 Benchmarks complementarios e interpretabilidad'),
  ...tablaConTitulo(3, 'Comparación metodológica sklearn de favoritismo', ['Modelo', 'AUC-PR', 'AUC-ROC', 'Precision', 'Recall', 'F1'], [
    ['Random Forest', f3(rf.auc_pr), f3(rf.auc_roc), pct(rf.precision), pct(rf.recall), f3(rf.f1)],
    ['Regresión Logística', f3(lr.auc_pr), f3(lr.auc_roc), pct(lr.precision), pct(lr.recall), f3(lr.f1)],
    ['Gradient Boosting', f3(gb.auc_pr), f3(gb.auc_roc), pct(gb.precision), pct(gb.recall), f3(gb.f1)],
  ], [2200, 1300, 1300, 1300, 1300, 1300]),
  parrafo('La comparación sklearn no define el champion; se conserva para contrastar familias de modelos y para evidencia SHAP. La Feature Importance del Random Forest Spark es la explicación directamente ligada al modelo servido.'),
  ...imagenConTitulo(2, 'Importancia de variables de favoritismo', '../outputs/charts/05_importancia_favoritismo.png', 610, 350),
  ...tablaConTitulo(4, 'Benchmark complementario Isolation Forest', ['Elemento', 'Resultado'], [
    ['Rol', 'Benchmark sklearn de compatibilidad; no es el modelo servido.'],
    ['AUC-PR holdout', f3(isoHoldout.auc_pr)],
    ['AUC-ROC holdout', f3(isoHoldout.auc_roc)],
    ['F1 holdout', f3(isoHoldout.f1)],
    ['Recall@K holdout', f3(isoHoldout.recall_at_k)],
  ], [4400, 4400]),
  ...imagenConTitulo(3, 'Señales de posible fraccionamiento', '../outputs/charts/06_deteccion_fraccionamiento.png', 610, 350),

  subtitulo('3.5 Evaluación, fingerprint y TRAIN'),
  parrafo(
    'Los evaluadores Spark registran el fingerprint SHA-256 del corpus canónico. TRAIN exige que las evidencias de favoritismo y fraccionamiento correspondan al mismo fingerprint. La selección ocurre en desarrollo y el holdout final no se utiliza para reconfigurar el modelo.'
  ),
  parrafo(
    'Cuando source.type=spark_sql, la evaluación dispone de ruta distribuida: integrar_spark, split, FIT/TRANSFORM, features y métricas permanecen en Spark. Las observaciones no se materializan con toPandas. Este contrato permite que la evidencia requerida por TRAIN exista también sobre un corpus Spark institucional.'
  ),

  subtitulo('3.6 TRAIN, candidate, champion e INFERENCE'),
  parrafo(
    'TRAIN produce un candidate y no cambia el champion. La promoción valida rutas y hashes, publica un conjunto versionado y actualiza el registry solo después del gate de integridad. INFERENCE verifica el champion antes del scoring y antes de publicar; los rankings se generan inicialmente en staging.'
  ),
  vineta('INFERENCE no consume labels.'),
  vineta('INFERENCE no ejecuta FIT, training ni tuning.'),
  vineta('La promoción técnica del PoC no equivale a aprobación institucional.'),
  vineta('El registry conserva historial para rollback explícito.'),

  subtitulo('3.7 Monitoreo y mantenimiento'),
  ...tablaConTitulo(5, 'MLOps, monitoreo y seguridad', ['Control', 'Comportamiento vigente'], [
    ['Champion monitorizado', 'El monitor lee el perfil spark_mllib activo del registry.'],
    ['Drift favoritismo', 'PSI sobre features seleccionadas.'],
    ['Drift fraccionamiento', 'PSI de features y distribución de score_anomalia.'],
    ['Desempeño', 'Recall@K cuando existen labels válidos.'],
    ['Reentrenamiento', 'Puede generar candidate; no existe autopromoción.'],
    ['Integridad', 'SHA-256 de candidate/champion y verificación antes/después de inference.'],
    ['CI', 'Tests no privilegiados separados del job con escritura persistente.'],
    ['Datos reales', 'Rankings identificables y datasets crudos fuera del repositorio público.'],
  ], [3000, 5800]),
  parrafo(`El resumen de monitoreo mantiene automatic_promotion=${String(monitorChampion.automatic_promotion)}. Un lote sin labels puede aportar evidencia de drift, pero no debe convertirse automáticamente en ground truth.`),

  subtitulo('3.8 GraphFrames y vínculos'),
  parrafo(
    'La herramienta incorpora NetworkX/GraphFrames para representar relaciones proveedor-funcionario cuando las variables necesarias están disponibles. La evidencia pública utiliza datos sintéticos para no afirmar vínculos institucionales no observados.'
  ),
  ...imagenConTitulo(4, 'Red proveedor-funcionario sintética', '../outputs/charts/10_grafo_vinculos.png', 610, 410),
  parrafo(`Evidencia GraphFrames registrada: ${graphframes.n_vertices ?? 'N/D'} vértices y ${graphframes.n_aristas ?? 'N/D'} aristas.`),

  subtitulo('3.9 Datos públicos OCDS/OECE'),
  parrafo(
    'La prueba con datos abiertos utiliza la relación Contract(main_ocid, awardID) -> Award(main_ocid, id) -> awards_suppliers(main_ocid, awards_id), porque el adjudicatario debe resolverse respecto de la adjudicación vinculada al contrato.'
  ),
  ...tablaConTitulo(6, 'Validación OCDS/OECE', ['Indicador', 'Resultado'], [
    ['Contratos crudos', num(p0i.contratos_crudos)],
    ['Contratos analíticos con award/supplier resoluble', num(p0i.contratos_analiticos_validos)],
    ['Excluidos sin relación resoluble', num(p0i.contratos_excluidos_sin_adjudicacion_resoluble)],
    ['Adjudicatarios distintos', num(p0i.adjudicatarios_distintos_en_contratos)],
    ['Entidades distintas', num(p0i.entidades_distintas_en_contratos)],
    ['Rango de fechas', `${p0i.fecha_contrato_min} a ${p0i.fecha_contrato_max}`],
  ], [5200, 3600]),
  parrafo(
    `La evidencia reproducible contiene ${num(p0i.contratos_analiticos_validos)} contratos analíticos válidos. Como no existen etiquetas institucionales de favoritismo/fraccionamiento, esta prueba verifica portabilidad de features y reglas, pero no valida el champion.`
  ),

  subtitulo('3.10 Airflow, reporting y documentación'),
  vineta('DAGs separados para reproducibilidad, TRAIN, INFERENCE y monitoreo.'),
  vineta('TRAIN/INFERENCE aceptan master Spark configurable; spark_sql mantiene DataFrame Spark hasta Parquet distribuido.'),
  vineta('SQL Server/SSRS se entrega como contrato DDL, vistas, roles de referencia y RDL con Shared Data Source.'),
  vineta('Los Productos 1-7 y este informe se generan desde evidencia machine-readable.'),
  vineta('Diccionario, linaje, run manifest, model registry y auditorías completan la trazabilidad.'),

  subtitulo('3.11 Estado frente al TDR y dependencias institucionales'),
  ...tablaConTitulo(7, 'Estado frente a dependencias institucionales', ['Área', 'Estado'], [
    ['EDA, calidad, preprocesamiento y feature engineering', 'Implementado y reproducible.'],
    ['Favoritismo', 'Random Forest Spark con CV/tuning/holdout propios.'],
    ['Fraccionamiento', 'KMeans Spark con selección/holdout propios + señal interpretable.'],
    ['Integración distribuida', 'spark_sql Spark-native; performance productiva pendiente de clúster real.'],
    ['Grafos', 'GraphFrames reproducible con escenario sintético.'],
    ['MLOps', 'Candidate/champion, hashes, promoción explícita, rollback e inference sin retraining.'],
    ['Reporting', 'Contrato SQL Server/SSRS preparado; despliegue institucional pendiente.'],
    ['Seguridad/DEV/QA/PROD', 'Controles de repo implementados; identidad/infraestructura real pendiente.'],
    ['Ground truth y umbrales productivos', 'Dependencia institucional.'],
    ['Certificación, marcha blanca y transferencia formal', 'Dependencia institucional.'],
  ], [3800, 5000]),
  parrafo('Las dependencias institucionales se mantienen explícitas para evitar que un PoC reproducible sea presentado como una implantación productiva certificada.'),

  titulo('4. Conclusiones y Recomendaciones'),
  parrafo(
    'El resultado es una herramienta de priorización con contratos técnicos claros: esquema canónico, quality gates, preprocesamiento congelado, modelos Spark evaluados con holdout independiente, evidence fingerprinting, candidate/champion separados, promoción explícita, inference sin training, monitoreo registry-aware y reporting desacoplado de infraestructura. La documentación principal explica estas decisiones y su fundamento, mientras el historial de desarrollo queda relegado a Git/PR y notas de release.'
  ),
  parrafo(
    'Para una adopción institucional se recomienda mantener intacta la separación evaluación/TRAIN/promoción/INFERENCE, ejecutar evaluación sobre el mismo corpus real que alimentará TRAIN, definir ground truth y criterios de aceptación con auditores, y validar capacidad, seguridad, observabilidad y reporting en DEV/QA/PROD antes de cualquier marcha blanca.'
  ),

  titulo('5. Anexos'),
  vineta('README.md — descripción funcional y decisiones de diseño.'),
  vineta('docs/Arquitectura_MLOps.md — model lifecycle, registry, promotion y rollback.'),
  vineta('docs/Evaluacion_Spark_y_Performance.md — evaluación distribuida y límites de performance.'),
  vineta('docs/Seguridad_y_Gobernanza.md — seguridad y controles demostrables.'),
  vineta('docs/Integracion_Datos.md — contrato de fuentes y mappings.'),
  vineta('docs/Auditoria_TDR_Completo.md — matriz de evidencia frente al TDR.'),
  vineta('docs/Dependencias_Institucionales_CGR.md — dependencias de cierre institucional.'),
  vineta('outputs/model_registry.json — perfil activo, champion y artefactos.'),
  vineta('outputs/run_manifest.json y outputs/linaje_datos.csv — trazabilidad reproducible.'),
  ...referencias(),
]);

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync('Reporte_Tecnico_Prototipo_CGR_1.8.2.docx', buffer);
  console.log('Generado: Reporte_Tecnico_Prototipo_CGR_1.8.2.docx');
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
