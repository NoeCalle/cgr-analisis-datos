const { Packer } = require('docx');
const fs = require('fs');
const {
  titulo, subtitulo, parrafo, vineta, tablaConTitulo, imagenConTitulo,
  frontMatter, referencias, documento,
} = require('./plantilla_docx');
const { e, pct, num, pen, modelo, syn, fav, frac, selFav, tuneFav, tuneFrac, p0 } = require('./evidencia');

const rf = modelo('RandomForest');
const lr = modelo('RegresionLogistica');
const gb = modelo('GradientBoosting');
const hf = tuneFrac.metricas_holdout_final;
const p0i = p0.integridad_ocds;
const p0a = p0.analisis_regenerado;
const manifest = e.run_manifest || {};
const sparkFav = manifest.spark_favoritismo || {};
const sparkFrac = manifest.spark_fraccionamiento || {};
const graphframes = manifest.graphframes || {};

const OBJETIVO_TDR =
  'El TDR establece como objetivo disponer datos procesados y filtrados de fuentes externas e internas y desarrollar modelos de Machine Learning para identificar casos atípicos y patrones de riesgo relevantes para la labor del auditor. Este informe documenta el grado en que dicho objetivo puede demostrarse mediante un prototipo independiente y reproducible.';

const doc = documento('TÉCNICO', 'Informe Final Técnico Consolidado', 'Informe Final Técnico Consolidado del Prototipo', [
  titulo('Resumen Ejecutivo'),
  parrafo(
    'El prototipo independiente del Módulo de Análisis de Datos implementa un pipeline reproducible para preparación de datos, priorización de señales de posible favoritismo y fraccionamiento, análisis de vínculos, Spark MLlib, GraphFrames, Airflow, Lakehouse local, trazabilidad y generación automática de documentación. ' +
    'La auditoría técnica del repositorio corrigió la integridad OCDS, la semántica de modalidades, el leakage metodológico, la gobernanza de reentrenamiento y la deriva entre código y documentos. Las salidas son señales para revisión humana y no constituyen hallazgos.'
  ),
  parrafo(e.naturaleza),
  ...frontMatter({
    tablas: [
      'Estado de componentes del prototipo',
      'Resumen del benchmark sintético',
      'Comparación de modelos de favoritismo',
      'Métricas holdout de fraccionamiento',
      'Validación de integridad OCDS/OECE',
      'Evidencia Spark y GraphFrames',
      'Matriz de cierre: PoC frente a dependencias institucionales',
    ],
    graficos: [
      'Diagrama del modelo de datos',
      'Resumen SHAP de favoritismo',
      'Detección de señales de fraccionamiento',
      'Red proveedor-funcionario sintética',
    ],
  }),

  titulo('1. Introducción'),
  parrafo(
    'Este Informe Final consolida únicamente evidencia que puede reproducirse desde el repositorio público. Mantiene separados dos ejercicios: un benchmark sintético con ground truth sembrado, destinado a validar el pipeline de extremo a extremo; y una validación con datos públicos OCDS/OECE, destinada a comprobar integridad relacional y escalabilidad del procesamiento sin asumir ground truth de irregularidad.'
  ),
  parrafo(
    'La documentación no atribuye al PoC capacidades que dependan de infraestructura o aprobación institucional. Datamart, fuentes internas, HDFS/YARN distribuido, ambientes DEV/QA/PROD, SQL Server/SSRS institucional, certificación funcional, marcha blanca y transferencia efectiva permanecen identificados como dependencias CGR.'
  ),

  titulo('2. Objetivo de Consultoría'),
  parrafo(OBJETIVO_TDR),

  titulo('3. Productos Alcanzados'),

  subtitulo('3.1 Arquitectura, datos y trazabilidad'),
  parrafo('El flujo implementado es fuentes -> Bronce -> limpieza/feature engineering -> Plata -> modelos sklearn/Spark/GraphFrames -> Oro -> diccionario/linaje -> run_manifest.json -> evidencia_documental.json -> documentación formal.'),
  ...tablaConTitulo(1, 'Estado de componentes del prototipo', ['Componente', 'Estado verificable'], [
    ['Bronce/Plata/Oro', 'Simulación local funcional; modelos consumen Plata y Oro contiene salidas downstream.'],
    ['Airflow', 'DAG principal con ramas sklearn, Spark MLlib y GraphFrames; runtime del proyecto separado.'],
    ['GitHub Actions', 'pytest + smoke end-to-end + generación/validación documental.'],
    ['Spark MLlib', 'Ejecución real local[*] con Java 17 y PySpark versionado.'],
    ['GraphFrames', 'Ejecución real sobre datos de contacto sintéticos publicados en Plata.'],
    ['Linaje', 'outputs/linaje_datos.csv: fuente -> transformación -> Plata -> feature -> implementación -> Oro.'],
    ['MLOps', 'run_manifest.json con commit, versiones, hashes, parámetros y artefactos; promoción humana de candidatos.'],
  ], [2800, 6000]),
  ...imagenConTitulo(1, 'Diagrama del modelo de datos', '../outputs/charts/09_diagrama_modelo_datos.png', 610, 360),

  subtitulo('3.2 Preparación y benchmark sintético'),
  ...tablaConTitulo(2, 'Resumen del benchmark sintético', ['Métrica', 'Resultado'], [
    ['Contratos sintéticos', num(syn.contratos)],
    ['Valores nulos totales', num(syn.valores_nulos_totales)],
    ['Filas con algún nulo', num(syn.filas_con_algun_nulo)],
    ['Percentil 99 del monto', pen(syn.p99_monto_pen)],
    ['Pares proveedor-entidad', num(fav.pares_proveedor_entidad)],
    ['Positivos sintéticos de favoritismo', num(fav.positivos_sembrados)],
    ['Grupos proveedor-entidad-objeto', num(frac.grupos_proveedor_entidad_objeto)],
    ['Positivos sintéticos de fraccionamiento', num(frac.positivos_sembrados)],
  ], [4800, 4000]),
  parrafo('El generador incorpora hard negatives y una categoría contractual estructurada goods/services/works para reducir separación trivial y ambigüedad normativa.'),

  subtitulo('3.3 Modelo de priorización de posible favoritismo'),
  parrafo(`Se compararon ${selFav.resultados.length} algoritmos con ${selFav.diseno}. La métrica primaria es ${selFav.criterio_primario}.`),
  ...tablaConTitulo(3, 'Comparación de modelos de favoritismo', ['Modelo', 'AUC-PR', 'AUC-ROC', 'Precision', 'Recall', 'F1'], [
    ['Random Forest', rf.auc_pr.toFixed(3), rf.auc_roc.toFixed(3), pct(rf.precision), pct(rf.recall), rf.f1.toFixed(3)],
    ['Regresión Logística', lr.auc_pr.toFixed(3), lr.auc_roc.toFixed(3), pct(lr.precision), pct(lr.recall), lr.f1.toFixed(3)],
    ['Gradient Boosting', gb.auc_pr.toFixed(3), gb.auc_roc.toFixed(3), pct(gb.precision), pct(gb.recall), gb.f1.toFixed(3)],
  ], [2200, 1300, 1300, 1300, 1300, 1300]),
  parrafo(`Random Forest conserva el mayor AUC-PR. El tuning selecciona n_estimators=${tuneFav.mejor_configuracion.n_estimators}, max_depth=${tuneFav.mejor_configuracion.max_depth} y min_samples_leaf=${tuneFav.mejor_configuracion.min_samples_leaf}, con AUC-PR CV ${tuneFav.mejor_auc_pr_cv.toFixed(3)}.`),
  parrafo('Contratación Directa y Comparación de Precios permanecen como features separadas. SHAP aporta explicación global e individual sin convertir el score en una determinación de responsabilidad.'),
  ...imagenConTitulo(2, 'Resumen SHAP de favoritismo', '../outputs/charts/07_shap_summary_favoritismo.png', 610, 360),

  subtitulo('3.4 Modelo de priorización de posible fraccionamiento'),
  parrafo(`${tuneFrac.diseno}. La selección se realiza por ${tuneFrac.metrica_seleccion}; el holdout final no participa en tuning.`),
  ...tablaConTitulo(4, 'Métricas holdout de fraccionamiento', ['Métrica', 'Resultado'], [
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
  parrafo('La diferencia entre AUC-ROC y AUC-PR confirma que el detector separa parcialmente extremos, pero su desempeño sobre la clase positiva es débil. La regla interpretable de ventana temporal y cuantía se conserva únicamente como señal complementaria de caja blanca.'),
  ...imagenConTitulo(3, 'Detección de señales de posible fraccionamiento', '../outputs/charts/06_deteccion_fraccionamiento.png', 610, 350),

  subtitulo('3.5 Implementación Spark MLlib y GraphFrames'),
  ...tablaConTitulo(5, 'Evidencia Spark y GraphFrames', ['Componente', 'Evidencia reproducible'], [
    ['Favoritismo Spark', `${sparkFav.algoritmo || 'RandomForestClassifier'}; ${sparkFav.cv || 'CV'}; modo ${sparkFav.modo || 'local[*]'}; AUC-PR CV del sanity check ${sparkFav.auc_pr_cv === undefined ? 'N/D' : Number(sparkFav.auc_pr_cv).toFixed(3)}.`],
    ['Fraccionamiento Spark', `${sparkFrac.algoritmo || 'KMeans + distancia al centroide'}; k=${sparkFrac.k ?? 'N/D'}; modo ${sparkFrac.modo || 'local[*]'}.`],
    ['GraphFrames', `${graphframes.n_vertices ?? 'N/D'} vértices, ${graphframes.n_aristas ?? 'N/D'} aristas y ${graphframes.n_senales_vinculo_sinteticas ?? 'N/D'} señales sintéticas.`],
    ['Versiones', `PySpark ${manifest.entorno?.pyspark || 'N/D'}; GraphFrames ${manifest.entorno?.['graphframes-py'] || 'N/D'}; Java 17 en CI.`],
  ], [2800, 6000]),
  parrafo('La métrica Spark de favoritismo no se utiliza como estimación productiva porque el benchmark solo tiene seis positivos. La función de esta evidencia es demostrar que la arquitectura exigida por el TDR se ejecuta realmente con Spark MLlib en el PoC.'),
  ...imagenConTitulo(4, 'Red proveedor-funcionario sintética', '../outputs/charts/10_grafo_vinculos.png', 610, 420),

  subtitulo('3.6 Validación de integridad con datos públicos OCDS/OECE'),
  parrafo(`La relación analítica se reconstruyó como ${p0.integridad_ocds.regla_relacional}. El supplier se resuelve mediante el award relacionado con cada contrato y la clave analítica es ${p0.integridad_ocds.clave_contrato_analitica}.`),
  ...tablaConTitulo(6, 'Validación de integridad OCDS/OECE', ['Métrica', 'Resultado'], [
    ['Contratos crudos', num(p0i.contratos_crudos)],
    ['Contratos analíticos válidos', num(p0i.contratos_analiticos_validos)],
    ['Excluidos sin award/supplier resoluble', num(p0i.contratos_excluidos_sin_adjudicacion_resoluble)],
    ['Adjudicatarios distintos', num(p0i.adjudicatarios_distintos_en_contratos)],
    ['Consorcios distintos', num(p0i.consorcios_adjudicatarios_distintos_en_contratos)],
    ['Entidades distintas', num(p0i.entidades_distintas_en_contratos)],
    ['Monto total procesado', pen(p0i.monto_total_pen, 2)],
    ['Rango de fechas', `${p0i.fecha_contrato_min} a ${p0i.fecha_contrato_max}`],
    ['Grupos priorizados por señal de fraccionamiento', num(p0a.grupos_priorizados_por_senal_fraccionamiento)],
  ], [5200, 3600]),
  parrafo(`El conteo antiguo de ${num(p0.comparacion_con_ejecucion_obsoleta.conteo_contratos_anterior)} fue descartado; el conteo corregido es ${num(p0.comparacion_con_ejecucion_obsoleta.conteo_contratos_corregido)}. Los rankings reales identificables no se publican en el repositorio.`),

  subtitulo('3.7 Autoevaluación, mantenimiento y gobernanza'),
  vineta('Monitoreo de calidad y drift mediante controles de esquema y PSI.'),
  vineta('Evaluación de desempeño solo cuando exista ground truth nuevo y validado.'),
  vineta('Reentrenamiento genera un modelo candidato y lo evalúa en holdout independiente.'),
  vineta('Promoción automática deshabilitada; se requiere revisión y aprobación humana.'),
  vineta('Normativa parametrizada por fecha/categoría con pruebas de regresión.'),

  subtitulo('3.8 Reporting, documentación y reproducibilidad'),
  vineta('Esquema T-SQL y RDL de SSRS disponibles como artefactos de despliegue; servidor institucional no ejecutado.'),
  vineta('Diccionario y diagrama del modelo de datos regenerados automáticamente.'),
  vineta('run_manifest.json registra commit, versiones, hashes, parámetros, métricas y artefactos.'),
  vineta('outputs/linaje_datos.csv proporciona linaje explícito de fuente a salida Oro.'),
  vineta('Los Productos 1-7 y este Informe Final se generan desde evidencia_documental.json.'),

  subtitulo('3.9 Matriz de cierre frente al TDR'),
  ...tablaConTitulo(7, 'Matriz de cierre: PoC frente a dependencias institucionales', ['Área', 'Estado'], [
    ['EDA, limpieza y feature engineering', 'Implementado y reproducible.'],
    ['Favoritismo supervisado', 'Benchmark OOF/tuning/SHAP + Spark MLlib ejecutado.'],
    ['Fraccionamiento no supervisado', 'Isolation Forest con holdout + KMeans Spark + señal interpretable.'],
    ['Grafos', 'NetworkX + GraphFrames ejecutado con escenario sintético.'],
    ['Airflow/Lakehouse local', 'Implementado; HDFS/YARN/Datamart CGR pendiente.'],
    ['Autoevaluación', 'Candidato + gate humano; gobierno productivo CGR pendiente.'],
    ['SSRS', 'T-SQL + RDL preparados; servidor SQL/SSRS CGR pendiente.'],
    ['DEV/QA/PROD y certificación', 'Dependencia institucional CGR.'],
    ['Marcha blanca y transferencia efectiva', 'Dependencia contractual/institucional CGR.'],
    ['Ground truth real', 'Requiere etiquetado y validación por auditores.'],
  ], [3600, 5200]),

  titulo('4. Conclusiones y Recomendaciones'),
  parrafo('El prototipo demuestra viabilidad técnica y reproducibilidad sin ocultar sus límites. Random Forest es el candidato principal del benchmark de favoritismo por AUC-PR e interpretabilidad. En fraccionamiento, la baja AUC-PR del holdout impide presentar el detector como clasificador de irregularidades y refuerza la necesidad de revisión humana.'),
  parrafo('La arquitectura Spark ya está ejecutada y validada en CI local[*]; lo pendiente en esta área es rendimiento distribuido sobre infraestructura CGR. La reconstrucción OCDS Contract -> Award -> Supplier y la separación de modalidades corrigen las brechas de integridad más importantes detectadas en versiones previas.'),
  parrafo('Para una fase institucional se recomienda: obtener ground truth real etiquetado; validar reglas con auditores y especialistas normativos; desplegar primero en DEV/QA; medir AUC-PR/recall y tiempos con datos internos; calibrar capacidad de revisión; habilitar controles de acceso y linaje; y ejecutar certificación, marcha blanca y transferencia formal.'),

  titulo('5. Anexos'),
  vineta(`Commit utilizado por la evidencia: ${e.git_commit || 'no disponible en el entorno de generación'}.`),
  vineta('outputs/evidencia_documental.json - fuente única de cifras documentales.'),
  vineta('outputs/run_manifest.json - entorno, hashes, parámetros y artefactos.'),
  vineta('outputs/linaje_datos.csv - linaje de campos y features.'),
  vineta('data/diccionario_datos.csv - diccionario de datos.'),
  vineta('outputs/validacion_p0_datos_reales.json - integridad y conteos OCDS/OECE.'),
  vineta('outputs/spark_favoritismo_resumen.json y outputs/spark_fraccionamiento_resumen.json - evidencia Spark MLlib.'),
  vineta('outputs/graphframes_resumen.json - evidencia GraphFrames.'),
  vineta('Directorio ssrs/ - artefactos T-SQL y RDL del PoC.'),
  ...referencias(),
]);

(async () => {
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync('Reporte_Tecnico_Prototipo_CGR_1.8.2.docx', buf);
  console.log('Generado: Reporte_Tecnico_Prototipo_CGR_1.8.2.docx con estructura de Informe Final del Anexo 1');
})();
