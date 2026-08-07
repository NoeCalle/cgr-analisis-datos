const { Packer } = require('docx');
const fs = require('fs');
const {
  titulo, subtitulo, parrafo, vineta, tabla, documento,
} = require('./plantilla_docx');
const { e, pct, num, pen, modelo, syn, fav, frac, selFav, tuneFav, tuneFrac, p0 } = require('./evidencia');

const rf = modelo('RandomForest');
const lr = modelo('RegresionLogistica');
const gb = modelo('GradientBoosting');
const hf = tuneFrac.metricas_holdout_final;
const p0i = p0.integridad_ocds;
const p0a = p0.analisis_regenerado;

const doc = documento('TÉCNICO', 'Reporte Técnico Consolidado', 'Reporte Técnico Consolidado del Prototipo', [
  titulo('Resumen Ejecutivo'),
  parrafo(
    'Este documento consolida el estado verificable del prototipo independiente del Módulo de Análisis de Datos. ' +
    'La versión actual corrige las principales brechas detectadas durante la auditoría técnica: integridad OCDS, ' +
    'modelado normativo, validación independiente, reproducibilidad de Airflow, gobernanza de reentrenamiento, ' +
    'trazabilidad y documentación basada en evidencia automática.'
  ),
  parrafo(e.naturaleza),

  titulo('1. Alcance y Separación de Evidencias'),
  parrafo('El proyecto mantiene dos ejercicios claramente separados:'),
  vineta('Benchmark sintético: permite probar end-to-end limpieza, features, selección de algoritmos, tuning, ranking, explicabilidad, grafos y MLOps con ground truth sembrado.'),
  vineta('Validación con datos públicos OCDS/OECE: verifica principalmente integridad relacional, escalabilidad del pipeline y generación de señales sin ground truth real.'),
  parrafo('No se mezclan las métricas del benchmark sintético con los resultados sobre datos públicos. En particular, ningún ranking real se presenta como evidencia de irregularidad.'),

  titulo('2. Arquitectura del PoC'),
  parrafo('Flujo implementado: fuentes → Bronce → limpieza/feature engineering → Plata → selección/modelado → Oro → trazabilidad/documentación.'),
  tabla(['Capa / componente', 'Función en el PoC', 'Estado'], [
    ['Bronce', 'Ingesta local de fuentes', 'Implementado localmente'],
    ['Plata', 'Datos limpios y features consumidos por modelos', 'Implementado y usado por sklearn/Spark'],
    ['Oro', 'Rankings/salidas para reporting', 'Implementado localmente'],
    ['Airflow', 'Orquestación', 'DAGs implementados; Python de proyecto separado'],
    ['GitHub Actions', 'Regresión y smoke', 'Activo en cada push/PR'],
    ['Delta Lake', 'ACID/time travel local', 'Demostrado con retención explícita'],
    ['GraphFrames', 'Análisis de red', 'Demostrado en escenario sintético'],
    ['SSRS', 'Artefactos de reporting', 'RDL + T-SQL preparados; servidor institucional no ejecutado'],
  ], [2600, 4000, 2200]),

  titulo('3. Preparación del Benchmark Sintético'),
  tabla(['Métrica', 'Valor'], [
    ['Contratos sintéticos', num(syn.contratos)],
    ['Valores nulos totales en fuente', num(syn.valores_nulos_totales)],
    ['Filas con al menos un nulo', num(syn.filas_con_algun_nulo)],
    ['Percentil 99 del monto', pen(syn.p99_monto_pen)],
    ['Registros sobre P99', num(syn.registros_sobre_p99)],
    ['Pares proveedor-entidad para favoritismo', num(fav.pares_proveedor_entidad)],
    ['Positivos sembrados de favoritismo', num(fav.positivos_sembrados)],
    ['Grupos proveedor-entidad-objeto para fraccionamiento', num(frac.grupos_proveedor_entidad_objeto)],
    ['Positivos sembrados de fraccionamiento', num(frac.positivos_sembrados)],
  ], [4700, 4100]),
  parrafo('El generador sintético incorpora hard negatives para evitar que el modelo aprenda únicamente un patrón trivial. También incorpora una categoría principal estructurada para distinguir goods/services/works y reducir ambigüedades del texto contractual.'),

  titulo('4. Modelo de Priorización de Posible Favoritismo'),
  subtitulo('4.1 Comparación de algoritmos'),
  parrafo(`Se compararon ${selFav.resultados.length} candidatos con ${selFav.diseno}. La métrica primaria fue ${selFav.criterio_primario}.`),
  tabla(['Modelo', 'AUC-PR', 'AUC-ROC', 'Precision', 'Recall', 'F1'], [
    ['Random Forest', rf.auc_pr.toFixed(3), rf.auc_roc.toFixed(3), pct(rf.precision), pct(rf.recall), rf.f1.toFixed(3)],
    ['Regresión Logística', lr.auc_pr.toFixed(3), lr.auc_roc.toFixed(3), pct(lr.precision), pct(lr.recall), lr.f1.toFixed(3)],
    ['Gradient Boosting', gb.auc_pr.toFixed(3), gb.auc_roc.toFixed(3), pct(gb.precision), pct(gb.recall), gb.f1.toFixed(3)],
  ], [2300, 1300, 1300, 1300, 1300, 1300]),
  parrafo('Random Forest es el mejor candidato del benchmark por AUC-PR. A diferencia de versiones antiguas, el resultado ya no es perfecto: esto refleja mejor la dificultad introducida por los hard negatives y evita sobreinterpretar el experimento.'),

  subtitulo('4.2 Tuning y configuración'),
  tabla(['Elemento', 'Resultado'], [
    ['Métrica de selección', tuneFav.metrica_seleccion],
    ['Validación', tuneFav.cv],
    ['n_estimators', String(tuneFav.mejor_configuracion.n_estimators)],
    ['max_depth', String(tuneFav.mejor_configuracion.max_depth)],
    ['min_samples_leaf', String(tuneFav.mejor_configuracion.min_samples_leaf)],
    ['Mejor AUC-PR CV', tuneFav.mejor_auc_pr_cv.toFixed(3)],
  ], [3800, 5000]),
  parrafo('Contratación Directa y Comparación de Precios se mantienen como variables separadas. El modelo no impone que ambas tengan la misma naturaleza competitiva.'),

  subtitulo('4.3 Interpretabilidad'),
  parrafo('La implementación mantiene SHAP para explicabilidad global e individual del Random Forest. Las explicaciones sirven como soporte al auditor para entender por qué un par fue priorizado; no transforman el score en una determinación de responsabilidad.'),

  titulo('5. Detección de Señales de Posible Fraccionamiento'),
  subtitulo('5.1 Feature engineering y normativa'),
  parrafo('El pipeline usa ventanas móviles de 15 días, frecuencia, monto acumulado y proporción de montos bajo el umbral aplicable. El umbral depende de fecha y categoría; se eliminó el supuesto de S/400 mil como regla general. Cuando existe categoría estructurada goods/services/works, esta tiene prioridad sobre inferencias por texto.'),

  subtitulo('5.2 Diseño de validación'),
  parrafo(`${tuneFrac.diseno}. La selección se realiza por ${tuneFrac.metrica_seleccion}; recall@K queda como métrica secundaria por su alta varianza con pocos positivos.`),
  tabla(['Métrica holdout', 'Resultado'], [
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
  parrafo('La diferencia entre AUC-ROC y AUC-PR es importante: el ranking separa parcialmente los extremos, pero el rendimiento sobre la clase positiva es débil. Con precision baja y un número relevante de anomalías predichas, el detector no debe presentarse como clasificador de fraccionamiento real.'),
  parrafo('La regla interpretable se conserva como señal complementaria de caja blanca. Una coincidencia con la regla indica prioridad de revisión, no prueba jurídica de fraccionamiento.'),

  titulo('6. Análisis de Vínculos'),
  parrafo('El PoC implementa un grafo proveedor-funcionario sobre datos sintéticos enriquecidos, tanto con networkx como con GraphFrames. La señal de contacto compartido es un ejemplo técnico del numeral de análisis de grafos; en una implementación real requeriría fuentes institucionales autorizadas y criterios de calidad/privacidad definidos.'),
  parrafo(`En la reconstrucción pública OCDS se evaluaron ${num(p0a.pares_proveedor_entidad_evaluados_para_vinculos_organizacionales)} pares para vínculos organizacionales y se obtuvieron ${num(p0a.senales_por_telefono_o_direccion_compartidos)} señales por teléfono/dirección compartidos con los campos públicos disponibles.`),

  titulo('7. Validación de Integridad con Datos Públicos OCDS/OECE'),
  parrafo(`La regla relacional aplicada es: ${p0.integridad_ocds.regla_relacional}. El supplier se asigna a través del award relacionado con cada contrato y no a nivel de todo el proceso.`),
  tabla(['Métrica', 'Resultado'], [
    ['Contratos crudos', num(p0i.contratos_crudos)],
    ['Contratos analíticos válidos', num(p0i.contratos_analiticos_validos)],
    ['Excluidos sin adjudicación resoluble', num(p0i.contratos_excluidos_sin_adjudicacion_resoluble)],
    ['Adjudicatarios distintos', num(p0i.adjudicatarios_distintos_en_contratos)],
    ['Consorcios/adjudicatarios tipo consorcio', num(p0i.consorcios_adjudicatarios_distintos_en_contratos)],
    ['Entidades distintas', num(p0i.entidades_distintas_en_contratos)],
    ['Monto total', pen(p0i.monto_total_pen, 2)],
    ['Rango de fechas', `${p0i.fecha_contrato_min} a ${p0i.fecha_contrato_max}`],
  ], [4700, 4100]),
  tabla(['Categoría OCDS', 'Contratos'], [
    ['goods', num(p0i.categorias_ocds.goods)],
    ['services', num(p0i.categorias_ocds.services)],
    ['works', num(p0i.categorias_ocds.works)],
  ], [4400, 4400]),
  parrafo(`El conteo antiguo de ${num(p0.comparacion_con_ejecucion_obsoleta.conteo_contratos_anterior)} fue descartado. La reconstrucción vigente contiene ${num(p0.comparacion_con_ejecucion_obsoleta.conteo_contratos_corregido)} contratos analíticos. Los rankings reales identificables de la ejecución anterior fueron retirados del repositorio público.`),

  titulo('8. Airflow, CI y Reproducibilidad'),
  vineta('Airflow corre en un entorno virtual separado; los BashOperator ejecutan el Python del proyecto mediante CGR_PROJECT_PYTHON o .venv/bin/python.'),
  vineta('GitHub Actions ejecuta pytest, reconstruye los sintéticos, publica Plata, compara algoritmos y ejecuta ambos tunings.'),
  vineta('Los resúmenes de selección/tuning se guardan en JSON y se suben como artifact de CI.'),
  vineta('La documentación se genera después de construir evidencia_documental.json; por diseño no contiene números independientes de esa fuente.'),

  titulo('9. Autoevaluación, Reentrenamiento y Gate de Promoción'),
  parrafo('El mecanismo de autoevaluación revisa Population Stability Index y un umbral absoluto de recall mínimo. Si se dispara una actualización, el lote nuevo se separa en datos de actualización y holdout. El candidato se entrena con la porción de actualización y se evalúa sobre el holdout. La promoción automática está deshabilitada; cualquier reemplazo del modelo productivo exige revisión/aprobación humana.'),

  titulo('10. Delta Lake, HMS y Componentes Spark'),
  vineta('Delta Lake: demostración local de UPDATE/ACID, time travel y Change Data Feed.'),
  vineta('Limitación de retención: el historial solo es recuperable mientras los archivos de versiones estén retenidos; VACUUM puede purgarlos.'),
  vineta('HMS: catálogo local con backend embebido como PoC; no equivale al HMS MySQL institucional.'),
  vineta('Spark MLlib y GraphFrames: probados en modo local. No equivalen a un clúster institucional ni validan rendimiento distribuido en infraestructura CGR.'),

  titulo('11. Reporting SSRS'),
  parrafo('El repositorio contiene un esquema T-SQL y un archivo RDL real como artefactos de despliegue. No se afirma que exista una ejecución sobre SQL Server/SSRS institucional: esa integración depende del entorno CGR.'),

  titulo('12. Componentes No Demostrados'),
  ...e.estado_componentes.dependencia_institucional_no_demostrada.map((x) => vineta(x)),

  titulo('13. Evaluación del Estado del PoC'),
  tabla(['Dimensión', 'Evaluación'], [
    ['Integridad de datos públicos', 'P0 cerrado: Contract → Award → Supplier corregido y probado'],
    ['Modelado favoritismo', `Candidato seleccionado con evidencia OOF; AUC-PR ${rf.auc_pr.toFixed(3)}`],
    ['Modelado fraccionamiento', `Limitación visible; AUC-PR holdout ${hf.auc_pr.toFixed(3)}`],
    ['Reproducibilidad', 'CI + Plata/Oro + evidencia JSON + entorno Airflow separado'],
    ['Gobernanza ML', 'Modelo candidato; promoción humana requerida'],
    ['Producción institucional', 'No demostrada; requiere infraestructura, datos y certificación CGR'],
  ], [3500, 5300]),

  titulo('14. Recomendaciones para una Fase Piloto'),
  vineta('Conseguir ground truth real etiquetado y acordar definiciones operativas con auditores.'),
  vineta('Recalcular precision/recall/AUC-PR con particiones temporales o por entidad/proveedor que reflejen el uso real.'),
  vineta('Calibrar umbrales de priorización según capacidad de revisión y costo de falsos positivos.'),
  vineta('Versionar reglas normativas con vigencia, fuente oficial y pruebas unitarias.'),
  vineta('Desplegar primero en DEV/QA, con auditoría de accesos, linaje y revisión humana obligatoria.'),
  vineta('Mantener rankings reales identificables fuera de repositorios públicos y con controles de acceso institucionales.'),

  titulo('15. Trazabilidad de la Versión'),
  vineta(`Commit utilizado por la evidencia: ${e.git_commit || 'no disponible'}.`),
  vineta('Fuente única documental: outputs/evidencia_documental.json.'),
  vineta('Comparación de algoritmos: outputs/comparacion_modelos_favoritismo.json.'),
  vineta('Tuning favoritismo: outputs/tuning_favoritismo_resumen.json.'),
  vineta('Tuning fraccionamiento: outputs/tuning_fraccionamiento_resumen.json.'),
  vineta('Validación OCDS: outputs/validacion_p0_datos_reales.json.'),

  titulo('16. Conclusión'),
  parrafo('El prototipo es hoy más fuerte precisamente porque dejó de presentar resultados perfectos o alcances institucionales no demostrados. La arquitectura y el pipeline son técnicamente defendibles como PoC; el Random Forest es el mejor candidato del benchmark de favoritismo; y el detector de fraccionamiento revela una limitación cuantitativa que debe resolverse con mejor ground truth y calibración. La siguiente etapa razonable es una prueba piloto controlada con datos internos, participación de auditores y gobierno formal del ciclo de vida del modelo.'),
]);

(async () => {
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync('Reporte_Tecnico_Prototipo_CGR_1.8.2.docx', buf);
  console.log('Generado: Reporte_Tecnico_Prototipo_CGR_1.8.2.docx desde evidencia_documental.json');
})();
