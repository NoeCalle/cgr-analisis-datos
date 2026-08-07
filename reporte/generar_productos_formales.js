const { Packer } = require('docx');
const fs = require('fs');
const {
  titulo, subtitulo, parrafo, vineta, tabla, documento,
} = require('./plantilla_docx');
const { e, pct, num, pen, modelo, syn, fav, frac, selFav, tuneFav, tuneFrac, p0 } = require('./evidencia');

const OUT = 'productos_formales';
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const rf = modelo('RandomForest');
const lr = modelo('RegresionLogistica');
const gb = modelo('GradientBoosting');
const hf = tuneFrac.metricas_holdout_final;
const p0i = p0.integridad_ocds;

function notaMetodologica() {
  return parrafo(
    'Nota metodológica: este es un prototipo independiente. Las métricas del benchmark sintético ' +
    'evalúan la coherencia del PoC y no estiman desempeño productivo. Las salidas sobre datos públicos ' +
    'son señales de priorización para revisión de auditor y no constituyen hallazgos ni determinaciones ' +
    'automáticas de irregularidad.'
  );
}

function informeProducto({ numero, nombre, resumen, introduccion, alcanzados, actividades, cumplimiento, dificultades, conclusiones, anexos = [] }) {
  return documento(numero, nombre, nombre, [
    titulo('Resumen Ejecutivo'), parrafo(resumen), notaMetodologica(),
    titulo('Índice'),
    parrafo('1. Introducción — 2. Objetivo — 3. Productos alcanzados — 4. Actividades realizadas — ' +
      '5. Grado de cumplimiento — 6. Dificultades y limitaciones — 7. Conclusiones y recomendaciones — 8. Anexos'),
    titulo('1. Introducción'), parrafo(introduccion),
    titulo('2. Objetivo'),
    parrafo('Desarrollar y validar una prueba de concepto de analítica de datos que priorice señales de posible ' +
      'favoritismo, posible fraccionamiento y vínculos proveedor-funcionario para apoyar la revisión del auditor.'),
    titulo('3. Productos Alcanzados'), ...alcanzados,
    titulo('4. Actividades Realizadas'), ...actividades,
    titulo('5. Grado de Cumplimiento del Producto'), parrafo(cumplimiento),
    titulo('6. Dificultades y Limitaciones Encontradas'), ...dificultades,
    titulo('7. Conclusiones y Recomendaciones'), parrafo(conclusiones),
    titulo('8. Anexos'), ...(anexos.length ? anexos : [parrafo('Código, datasets y evidencia machine-readable: ver repositorio indicado en la portada.')]),
  ]);
}

const p1 = documento(1, 'Plan de Trabajo', 'Plan de Trabajo', [
  titulo('1. Introducción'),
  parrafo('Plan de trabajo de una prueba de concepto independiente basada en el TDR público del Proyecto Interno 1.8.2. ' +
    'El repositorio no constituye una implementación oficial ni cuenta con aprobación institucional de la CGR.'),
  titulo('2. Objetivo'),
  parrafo('Construir un PoC reproducible que cubra preparación de datos, selección y evaluación de modelos, análisis de vínculos, ' +
    'orquestación, trazabilidad y artefactos de reporting, diferenciando claramente lo demostrado localmente de las dependencias institucionales.'),
  titulo('3. Productos a Alcanzar'),
  tabla(['N°', 'Producto', 'Alcance'], [
    ['1', 'Plan de Trabajo', 'Metodología, alcance y cronograma de referencia'],
    ['2', 'Preprocesamiento — Favoritismo', 'Limpieza y features proveedor-entidad'],
    ['3', 'Modelo — Favoritismo', 'Comparación de algoritmos y selección'],
    ['4', 'Entrenamiento/Validación — Favoritismo', 'CV, tuning, métricas y explicabilidad'],
    ['5', 'Preprocesamiento — Fraccionamiento', 'Ventanas temporales y contexto normativo'],
    ['6', 'Modelo — Fraccionamiento', 'Anomalías + regla interpretable + holdout'],
    ['7', 'Informe Final', 'Consolidación, limitaciones y ruta institucional'],
  ], [700, 4200, 3900]),
  titulo('4. Enfoque de Ejecución'),
  vineta('Pipeline sintético reproducible con publicación Bronce → Plata → Oro.'),
  vineta('Validación de integridad OCDS sobre datos públicos, separada del benchmark sintético.'),
  vineta('CI de regresión y smoke para reconstrucción de datasets y selección de modelos.'),
  vineta('Documentación generada desde outputs/evidencia_documental.json, evitando cifras copiadas a mano.'),
  titulo('5. Cronograma de Referencia del TDR'),
  tabla(['Producto', 'Plazo'], [
    ['1', '7 días'], ['2', '30 días'], ['3', '60 días'], ['4', '90 días'],
    ['5', '120 días'], ['6', '150 días'], ['7', '180 días'],
  ], [4400, 4400]),
  titulo('6. Estado Actual del PoC'),
  parrafo('P0 de integridad OCDS cerrado. Núcleo técnico P1 endurecido con validación independiente, CI, separación Plata/Oro, ' +
    'Airflow con entorno de proyecto, promoción humana de modelos y evidencia documental automática.'),
  notaMetodologica(),
]);

const p2 = informeProducto({
  numero: 2,
  nombre: 'Limpieza y Preprocesamiento — Favoritismo',
  resumen: `Se procesaron ${num(syn.contratos)} contratos sintéticos para construir ${num(fav.pares_proveedor_entidad)} pares proveedor-entidad, ` +
    `con ${num(fav.positivos_sembrados)} positivos sembrados. El dataset incorpora features separadas para Contratación Directa y Comparación de Precios.`,
  introduccion: 'Cubre limpieza, transformación y feature engineering del caso de uso de priorización de posible favoritismo.',
  alcanzados: [
    vineta(`Calidad base: ${num(syn.valores_nulos_totales)} valores nulos distribuidos en ${num(syn.filas_con_algun_nulo)} filas; la imputación se ejecuta de forma reproducible.`),
    vineta(`Tratamiento de monto: percentil 99 = ${pen(syn.p99_monto_pen)}; ${num(syn.registros_sobre_p99)} registros quedan identificados para capping en la transformación.`),
    vineta('Codificación y normalización reproducibles; las modalidades se preservan sin convertir Comparación de Precios en sinónimo de Contratación Directa.'),
    vineta('Features proveedor-entidad: volumen, monto, diversidad de objetos, concentración, funcionarios distintos, actividad temporal, intensidad contractual y variables separadas por modalidad.'),
    vineta('El dataset analítico se publica en lakehouse/plata/dataset_favoritismo.csv y es la entrada preferente de los modelos.'),
  ],
  actividades: [
    vineta('Generación determinística del benchmark sintético con hard negatives.'),
    vineta('EDA, limpieza, imputación, capping, codificación y feature engineering.'),
    vineta('Publicación en capa Plata y validación automática de esquema en GitHub Actions.'),
  ],
  cumplimiento: 'Núcleo técnico completado para el PoC y cubierto por CI. No equivale a certificación con datos internos CGR.',
  dificultades: [
    vineta('El ground truth es sintético; sirve para probar el pipeline, no para estimar precisión real.'),
    vineta('La validación institucional requiere fuentes internas, reglas de negocio acordadas y etiquetado por auditores.'),
  ],
  conclusiones: 'El preprocesamiento es reproducible y ahora evita una de las principales fuentes de sesgo normativo del diseño anterior: colapsar modalidades distintas en una sola variable.',
});

const p3 = informeProducto({
  numero: 3,
  nombre: 'Selección y Desarrollo del Modelo — Favoritismo',
  resumen: `Se compararon tres candidatos con las mismas particiones out-of-fold. Random Forest obtuvo el mayor AUC-PR (${rf.auc_pr.toFixed(3)}), ` +
    `por encima de Regresión Logística (${lr.auc_pr.toFixed(3)}) y Gradient Boosting (${gb.auc_pr.toFixed(3)}).`,
  introduccion: 'Cubre la selección fundamentada del algoritmo supervisado para priorizar pares proveedor-entidad con señales de posible favoritismo.',
  alcanzados: [
    vineta(`Diseño de comparación: ${selFav.diseno}; criterio primario: ${selFav.criterio_primario}.`),
    vineta(`Random Forest: AUC-PR ${rf.auc_pr.toFixed(3)}, AUC-ROC ${rf.auc_roc.toFixed(3)}, F1 ${rf.f1.toFixed(3)}.`),
    vineta(`Regresión Logística: AUC-PR ${lr.auc_pr.toFixed(3)}; Gradient Boosting: AUC-PR ${gb.auc_pr.toFixed(3)}.`),
    vineta(`Configuración final seleccionada por tuning: ${tuneFav.mejor_configuracion.n_estimators} árboles, profundidad ${tuneFav.mejor_configuracion.max_depth}, min_samples_leaf ${tuneFav.mejor_configuracion.min_samples_leaf}.`),
    vineta('La selección queda persistida en JSON y puede ser consumida por el entrenamiento final; ya no depende de parámetros escritos manualmente en el informe.'),
  ],
  actividades: [
    vineta('Predicciones out-of-fold con StratifiedKFold de 3 particiones.'),
    vineta('Comparación ejecutable de Regresión Logística, Random Forest y Gradient Boosting.'),
    vineta('Grid search de Random Forest usando AUC-PR por el fuerte desbalance de clase.'),
  ],
  cumplimiento: 'Selección técnica completada para el benchmark sintético, con evidencia versionada y reproducible.',
  dificultades: [
    vineta(`Solo existen ${num(fav.positivos_sembrados)} positivos sintéticos; las métricas tienen incertidumbre alta.`),
  ],
  conclusiones: 'Random Forest es el candidato preferido del PoC por AUC-PR y por su capacidad de explicación con SHAP. La elección debe reevaluarse con ground truth real antes de producción.',
});

const p4 = informeProducto({
  numero: 4,
  nombre: 'Entrenamiento y Validación — Favoritismo',
  resumen: `La validación vigente evita el resultado artificialmente perfecto de versiones anteriores. Random Forest alcanza AUC-PR OOF ${rf.auc_pr.toFixed(3)}, ` +
    `AUC-ROC ${rf.auc_roc.toFixed(3)}, precision ${pct(rf.precision)}, recall ${pct(rf.recall)} y F1 ${rf.f1.toFixed(3)}.`,
  introduccion: 'Cubre entrenamiento, validación cruzada, tuning e interpretabilidad del modelo supervisado.',
  alcanzados: [
    vineta(`Benchmark: ${num(selFav.n_registros)} pares, ${num(selFav.positivos)} positivos sintéticos.`),
    vineta(`Métricas OOF Random Forest: AUC-PR ${rf.auc_pr.toFixed(3)}, AUC-ROC ${rf.auc_roc.toFixed(3)}, precision ${pct(rf.precision)}, recall ${pct(rf.recall)}, F1 ${rf.f1.toFixed(3)}.`),
    vineta(`Tuning CV: mejor AUC-PR medio ${tuneFav.mejor_auc_pr_cv.toFixed(3)} con ${tuneFav.mejor_configuracion.n_estimators} árboles y profundidad ${tuneFav.mejor_configuracion.max_depth}.`),
    vineta('SHAP se mantiene como mecanismo de explicación global e individual del Random Forest.'),
    vineta('La evidencia se versiona en outputs/comparacion_modelos_favoritismo.json y outputs/tuning_favoritismo_resumen.json.'),
  ],
  actividades: [
    vineta('Validación out-of-fold con particiones estratificadas.'),
    vineta('Tuning sistemático y persistencia de configuración.'),
    vineta('Generación de ranking y artefactos de explicación para revisión humana.'),
  ],
  cumplimiento: 'Núcleo de validación completado para el PoC. No se afirma desempeño productivo ni certificación institucional.',
  dificultades: [
    vineta('La clase positiva es muy pequeña; AUC-PR y F1 deben leerse como indicadores del benchmark, no como garantías.'),
  ],
  conclusiones: 'La nueva validación es deliberadamente más exigente y creíble que la versión anterior. El modelo prioriza revisión; no determina favoritismo.',
});

const p5 = informeProducto({
  numero: 5,
  nombre: 'Limpieza y Preprocesamiento — Fraccionamiento',
  resumen: `Se generaron ${num(frac.grupos_proveedor_entidad_objeto)} grupos proveedor-entidad-objeto, con ${num(frac.positivos_sembrados)} positivos sembrados, ` +
    'usando ventanas temporales y umbrales normativos dependientes de fecha y categoría.',
  introduccion: 'Cubre feature engineering específico para señales de posible fraccionamiento, evitando un umbral fijo universal.',
  alcanzados: [
    vineta('Ventana móvil de 15 días por proveedor-entidad-objeto.'),
    vineta('Monto acumulado en ventana, frecuencia contractual y proporción de montos bajo el umbral aplicable.'),
    vineta('La categoría estructurada goods/services/works tiene prioridad sobre inferencias por texto cuando está disponible.'),
    vineta('El motor normativo contempla el período analizado y el cambio de régimen desde 22/04/2025; no usa S/400 mil como regla general.'),
    vineta('Dataset publicado en lakehouse/plata/dataset_fraccionamiento.csv.'),
  ],
  actividades: [
    vineta('Cálculo de features temporales y normativas.'),
    vineta('Pruebas de regresión para categorías, fechas y umbrales.'),
    vineta('Publicación en Plata y smoke test automático.'),
  ],
  cumplimiento: 'Feature engineering técnico completado para el PoC.',
  dificultades: [
    vineta('La ventana de 15 días es una heurística de priorización; por sí sola no prueba fraccionamiento.'),
    vineta('La normativa debe mantenerse parametrizada y revisada ante cambios legales o reglamentarios.'),
  ],
  conclusiones: 'La combinación de contexto temporal, objeto y régimen normativo es más defendible que una comparación con un tope fijo.',
});

const p6 = informeProducto({
  numero: 6,
  nombre: 'Selección y Desarrollo del Modelo — Fraccionamiento',
  resumen: `Isolation Forest se selecciona como detector no supervisado del PoC, pero el holdout independiente muestra una limitación importante: ` +
    `AUC-PR ${hf.auc_pr.toFixed(3)} y F1 ${hf.f1.toFixed(3)}. Por ello el resultado debe tratarse como priorización de revisión, no como hallazgo.`,
  introduccion: 'Cubre selección, tuning y evaluación de detección de anomalías para compras repetitivas o potencialmente divididas.',
  alcanzados: [
    vineta(`Dataset: ${num(tuneFrac.n_total)} grupos y ${num(tuneFrac.positivos_total)} positivos sintéticos.`),
    vineta(`Diseño: ${tuneFrac.diseno}.`),
    vineta(`Métrica primaria de tuning: ${tuneFrac.metrica_seleccion}.`),
    vineta(`Mejor configuración: ${tuneFrac.mejor_configuracion.n_estimators} estimadores, max_samples ${tuneFrac.mejor_configuracion.max_samples}, contamination ${tuneFrac.mejor_configuracion.contamination}.`),
    vineta(`Holdout final: AUC-ROC ${hf.auc_roc.toFixed(3)}, AUC-PR ${hf.auc_pr.toFixed(3)}, precision ${pct(hf.precision)}, recall ${pct(hf.recall)}, F1 ${hf.f1.toFixed(3)}.`),
    vineta(`El modelo marcó ${num(hf.anomalias_predichas)} anomalías entre ${num(hf.n_test)} registros de holdout, con ${num(hf.positivos_test)} positivos.`),
    vineta('La regla interpretable se conserva como señal complementaria de caja blanca, no como prueba jurídica automática.'),
  ],
  actividades: [
    vineta('Separación del holdout final antes del tuning.'),
    vineta('Validaciones repetidas solo sobre desarrollo y selección por AUC-PR.'),
    vineta('Evaluación única sobre holdout final con AUC-ROC, AUC-PR, precision, recall, F1 y recall@K.'),
  ],
  cumplimiento: 'Validación independiente implementada. El resultado no justifica afirmar que el detector esté listo para producción.',
  dificultades: [
    vineta(`Solo ${num(tuneFrac.positivos_total)} positivos sintéticos; recall@K resulta especialmente inestable.`),
    vineta('El alto recall con baja precision muestra que el detector genera bastantes falsos positivos en este benchmark.'),
  ],
  conclusiones: 'La principal conclusión ya no es que una regla tenga “100% de precisión”, sino que el detector no supervisado necesita más ground truth y revisión humana. AUC-PR es la métrica más informativa en este escenario desbalanceado.',
});

const p7 = documento(7, 'Informe Final', 'Informe Final', [
  titulo('Resumen Ejecutivo'),
  parrafo(`El PoC integra un benchmark sintético reproducible y una validación separada de integridad sobre datos públicos OCDS/OECE. ` +
    `La reconstrucción correcta produce ${num(p0i.contratos_analiticos_validos)} contratos analíticos a partir de ${num(p0i.contratos_crudos)} contratos crudos, ` +
    `excluyendo ${num(p0i.contratos_excluidos_sin_adjudicacion_resoluble)} registros sin vínculo award/supplier resoluble.`),
  notaMetodologica(),

  titulo('1. Resultados Vigentes del Benchmark Sintético'),
  tabla(['Componente', 'Resultado vigente'], [
    ['Favoritismo — comparación', `Random Forest AUC-PR ${rf.auc_pr.toFixed(3)}; LR ${lr.auc_pr.toFixed(3)}; Gradient Boosting ${gb.auc_pr.toFixed(3)}`],
    ['Favoritismo — tuning', `${tuneFav.mejor_configuracion.n_estimators} árboles, profundidad ${tuneFav.mejor_configuracion.max_depth}; AUC-PR CV ${tuneFav.mejor_auc_pr_cv.toFixed(3)}`],
    ['Fraccionamiento — holdout', `AUC-ROC ${hf.auc_roc.toFixed(3)}; AUC-PR ${hf.auc_pr.toFixed(3)}; precision ${pct(hf.precision)}; F1 ${hf.f1.toFixed(3)}`],
  ], [3600, 5200]),

  titulo('2. Validación de Integridad sobre Datos Públicos OCDS/OECE'),
  vineta(`Relación aplicada: ${p0.integridad_ocds.regla_relacional}.`),
  vineta(`Contratos analíticos válidos: ${num(p0i.contratos_analiticos_validos)}.`),
  vineta(`Adjudicatarios distintos presentes en contratos: ${num(p0i.adjudicatarios_distintos_en_contratos)}.`),
  vineta(`Entidades distintas: ${num(p0i.entidades_distintas_en_contratos)}.`),
  vineta(`Categorías OCDS: goods ${num(p0i.categorias_ocds.goods)}, services ${num(p0i.categorias_ocds.services)}, works ${num(p0i.categorias_ocds.works)}.`),
  vineta(`Monto total procesado en la reconstrucción: ${pen(p0i.monto_total_pen, 2)}.`),
  parrafo('Los rankings reales identificables se mantienen fuera del repositorio público. La evidencia versionada es agregada y auditable.'),

  titulo('3. Arquitectura y Reproducibilidad'),
  vineta('Airflow orquesta generación → Bronce → preprocesamiento/features → Plata → selección/modelado → Oro → manifiesto.'),
  vineta('Los modelos consumen preferentemente Plata; reporting consume Oro.'),
  vineta('GitHub Actions reconstruye el benchmark, ejecuta pruebas y vuelve a correr la selección/tuning.'),
  vineta('run_manifest.json y evidencia_documental.json separan resultados observados de afirmaciones manuales.'),
  vineta('Delta Lake local demuestra operaciones transaccionales/time travel mientras las versiones estén retenidas; VACUUM puede purgar archivos antiguos.'),

  titulo('4. Autoevaluación y Gobernanza del Modelo'),
  parrafo('La autoevaluación usa PSI y un recall mínimo explícito. Si se activa reentrenamiento, el sistema genera un modelo candidato y lo evalúa en un holdout del lote nuevo que no participó en su entrenamiento. La promoción automática está deshabilitada: requiere revisión/aprobación humana.'),

  titulo('5. Estado Frente al Entorno Institucional'),
  tabla(['Demostrado en el PoC', 'Pendiente / dependencia institucional'], [
    ['EDA, features, sklearn/Spark local, GraphFrames, Airflow local, Bronce/Plata/Oro local, Delta local, RDL/T-SQL, CI', 'Datamart CGR, DEV/QA/PROD, Git/CI institucional, servidores SQL/SSRS/SSAS/Power BI institucionales'],
    ['Validación sintética y OCDS pública', 'Ground truth real etiquetado y certificación funcional por auditores'],
    ['Modelo candidato con gate humano', 'Proceso institucional de aprobación/promoción y operación en marcha blanca'],
    ['HMS local / Spark local', 'HDFS/YARN distribuido sobre infraestructura CGR'],
  ], [4400, 4400]),

  titulo('6. Conclusiones y Recomendaciones'),
  parrafo('El PoC demuestra viabilidad técnica y, tras la segunda auditoría, también hace visibles sus límites. Random Forest es el mejor candidato del benchmark de favoritismo; el detector de fraccionamiento presenta una AUC-PR baja en holdout y no debe presentarse como clasificador de irregularidades. La siguiente fase útil requiere datos reales etiquetados, reglas validadas con auditores y despliegue controlado en el entorno institucional.'),

  titulo('7. Evidencia y Trazabilidad'),
  vineta('outputs/evidencia_documental.json — fuente única de cifras de estos documentos.'),
  vineta('outputs/comparacion_modelos_favoritismo.json — comparación OOF de candidatos.'),
  vineta('outputs/tuning_favoritismo_resumen.json — configuración de Random Forest.'),
  vineta('outputs/tuning_fraccionamiento_resumen.json — diseño y métricas de holdout.'),
  vineta('outputs/validacion_p0_datos_reales.json — integridad Contract → Award → Supplier y conteos OCDS.'),
  vineta(`Commit de evidencia: ${e.git_commit || 'no disponible en el entorno de generación'}.`),
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
  console.log('Los 7 productos fueron regenerados desde evidencia_documental.json.');
})();
