const { Packer } = require("docx");
const fs = require("fs");
const {
  titulo, subtitulo, parrafo, vineta, imagen, piePagina, tabla, documento, PageBreak, Paragraph,
} = require("./plantilla_docx");

const OUT = "productos_formales";
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT);

const salto = () => new Paragraph({ children: [new PageBreak()] });

// ===========================================================================
// PRODUCTO 1 — Plan de Trabajo (estructura Anexo 01, numeral II.1)
// ===========================================================================
const p1 = documento(1, "Plan de Trabajo", "Plan de Trabajo", [
  titulo("Índice"),
  parrafo("1. Introducción — 2. Objetivo de la consultoría — 3. Productos a alcanzar — " +
    "4. Actividades a cumplir por producto — 5. Cronograma — 6. Anexos"),

  titulo("1. Introducción"),
  parrafo(
    "El presente Plan de Trabajo detalla la metodología y el cronograma para el desarrollo del " +
    "\"Módulo de análisis de datos para dar soporte a los auditores durante la ejecución de los servicios de " +
    "control\", en el marco del Proyecto Interno 1.8.2 (Sistema Integrado de Control) de la Contraloría " +
    "General de la República (CGR)."
  ),

  titulo("2. Objetivo de la Consultoría"),
  parrafo(
    "Desarrollar modelos de ciencia de datos y machine learning que permitan la identificación temprana de " +
    "proveedores favorecidos, la detección de fraccionamiento indebido del gasto público, y la evaluación de " +
    "vínculos impropios entre proveedores y funcionarios, a partir de datos de contrataciones públicas."
  ),

  titulo("3. Productos a Alcanzar"),
  tabla(
    ["N°", "Producto", "Contenido principal"],
    [
      ["1", "Plan de Trabajo", "Metodología y cronograma (este documento)"],
      ["2", "Limpieza y preprocesamiento — Favoritismo", "Imputación, outliers, encoding, feature engineering"],
      ["3", "Selección y desarrollo del modelo — Favoritismo", "Arquitectura, algoritmo, parámetros"],
      ["4", "Entrenamiento y validación — Favoritismo", "Métricas, validación cruzada, interpretabilidad SHAP"],
      ["5", "Limpieza y preprocesamiento — Fraccionamiento", "Features de ventana temporal, umbral normativo"],
      ["6", "Selección y desarrollo del modelo — Fraccionamiento", "Isolation Forest + regla interpretable"],
      ["7", "Informe Final", "Entrenamiento/validación, manual, plan de monitoreo, transferencia"],
    ],
    [700, 4200, 3900],
  ),

  titulo("4. Actividades a Cumplir por Producto"),
  vineta("Producto 1: Definición de alcance, generación del dataset de trabajo, estructura del repositorio."),
  vineta("Productos 2 y 5: Análisis exploratorio, limpieza, codificación y generación de variables derivadas para cada caso de uso."),
  vineta("Productos 3 y 6: Evaluación de algoritmos candidatos, selección fundamentada, diseño de arquitectura."),
  vineta("Productos 4 y 7: Entrenamiento, validación cruzada, generación de artefactos de explicabilidad, documentación de cierre."),
  vineta("Transversal: análisis de vínculos proveedor-funcionario (numeral 4.2.4) y documentación de linaje de datos (checklist Anexo 3)."),

  titulo("5. Cronograma"),
  parrafo(
    "El TDR original contempla 180 días calendario distribuidos como se muestra a continuación. Este " +
    "prototipo se construyó de forma acelerada como prueba de concepto; el cronograma se presenta como " +
    "referencia de los hitos formales que aplicarían en una consultoría regular."
  ),
  tabla(
    ["Producto", "Plazo (TDR original)"],
    [
      ["Primer Producto", "7 días calendario"],
      ["Segundo Producto", "30 días calendario"],
      ["Tercer Producto", "60 días calendario"],
      ["Cuarto Producto", "90 días calendario"],
      ["Quinto Producto", "120 días calendario"],
      ["Sexto Producto", "150 días calendario"],
      ["Séptimo Producto", "180 días calendario"],
    ],
    [4400, 4400],
  ),

  titulo("6. Anexos"),
  parrafo(`Código fuente y datos: repositorio público en GitHub (ver portada).`),
]);

// ===========================================================================
// Helper para Productos 2, 3, 4, 5, 6 (estructura Anexo 01, numeral II.2)
// ===========================================================================
function informeProducto({ numero, nombre, resumen, introduccion, alcanzados, actividades, cumplimiento, dificultades, conclusiones, figuras }) {
  const children = [
    titulo("Resumen Ejecutivo"),
    parrafo(resumen),
    titulo("Índice"),
    parrafo("1. Introducción — 2. Objetivo de la consultoría — 3. Productos alcanzados — " +
      "4. Actividades realizadas — 5. Grado de cumplimiento — 6. Dificultades y limitaciones — " +
      "7. Conclusiones y recomendaciones — 8. Anexos"),
    titulo("1. Introducción"),
    parrafo(introduccion),
    titulo("2. Objetivo de la Consultoría"),
    parrafo(
      "Desarrollar modelos de ciencia de datos y machine learning que permitan la identificación temprana de " +
      "proveedores favorecidos, la detección de fraccionamiento indebido del gasto público, y la evaluación de " +
      "vínculos impropios entre proveedores y funcionarios."
    ),
    titulo("3. Productos Alcanzados"),
    ...alcanzados,
    titulo("4. Actividades Realizadas"),
    ...actividades,
    titulo("5. Grado de Cumplimiento del Producto"),
    parrafo(cumplimiento),
    titulo("6. Dificultades y Limitaciones Encontradas"),
    ...dificultades,
    titulo("7. Conclusiones y Recomendaciones"),
    parrafo(conclusiones),
    titulo("8. Anexos"),
  ];
  if (figuras) children.push(...figuras);
  else children.push(parrafo("Código fuente y datasets: ver repositorio indicado en la portada."));
  return documento(numero, nombre, nombre, children);
}

// --- PRODUCTO 2 ---
const p2 = informeProducto({
  numero: 2, nombre: "Limpieza y Preprocesamiento — Favoritismo",
  resumen: "Se procesaron 3,603 contratos sintéticos que simulan la integración SIAF/SEACE, corrigiendo " +
    "239 valores nulos y capando 37 valores atípicos, para construir un dataset agregado de 2,354 pares " +
    "proveedor-entidad listo para modelar riesgo de favoritismo.",
  introduccion: "Este documento cubre el numeral 4.1.4 (Limpieza y Transformación) y 4.1.5 (Enriquecimiento y " +
    "Generación de Características) del TDR, aplicados al caso de uso de identificación de proveedores favoritos.",
  alcanzados: [
    vineta("Imputación de valores faltantes: monto → mediana por tipo de objeto contractual; variables categóricas → moda (239 valores nulos corregidos, 6.44% de los registros)."),
    vineta("Tratamiento de outliers: winsorización al percentil 99 (S/. 534,351) — se capan, no se eliminan, para no perder señal de auditoría (37 registros afectados)."),
    vineta("Codificación de variables categóricas: One-Hot Encoding sobre la modalidad de contratación."),
    vineta("Normalización: estandarización (z-score) del monto contractual."),
    vineta("Feature engineering (nivel proveedor-entidad): n° de contratos, monto total y promedio, concentración de objeto contractual, % de modalidades no competitivas, n° de funcionarios distintos, días de actividad, contratos por mes, monto por funcionario."),
    vineta("División de datos: el dataset resultante (2,354 pares) se usa íntegramente en validación cruzada estratificada en el Producto 4, dada la escasez natural de la clase positiva."),
  ],
  actividades: [
    vineta("Ejecución de src/generar_datos.py — generación del dataset base de contrataciones."),
    vineta("Ejecución de src/eda.py — análisis exploratorio (distribuciones, modalidades, concentración de proveedores)."),
    vineta("Ejecución de src/preprocesamiento.py — limpieza, codificación y generación del dataset dataset_favoritismo.csv."),
  ],
  cumplimiento: "100% de las actividades de limpieza y feature engineering planificadas para este producto " +
    "fueron completadas sobre el dataset sintético. El dataset resultante reproduce correctamente los 6 casos " +
    "de favoritismo sembrados como grupos de mayor concentración de contratos.",
  dificultades: [
    vineta("No se tuvo acceso a datos reales de SIAF/SEACE; se trabajó con un dataset sintético diseñado para replicar su estructura y distribución esperada."),
    vineta("La imputación por mediana/moda es una estrategia conservadora; en producción debería evaluarse imputación más sofisticada (KNN, modelos predictivos) según la calidad real de los datos de la CGR."),
  ],
  conclusiones: "El pipeline de limpieza y feature engineering es reproducible y está listo para recibir datos " +
    "reales sin cambios estructurales mayores. Se recomienda, para producción, migrar esta etapa a Spark " +
    "DataFrames sobre la capa Plata/Oro del Lakehouse institucional.",
});

// --- PRODUCTO 3 ---
const p3 = informeProducto({
  numero: 3, nombre: "Selección y Desarrollo del Modelo — Favoritismo",
  resumen: "Se evaluó y seleccionó un modelo Random Forest para la identificación de proveedores favoritos, " +
    "por su balance entre precisión, interpretabilidad y bajo riesgo de sobreajuste con una clase positiva " +
    "minoritaria (0.25% de los pares proveedor-entidad).",
  introduccion: "Cubre el numeral 4.2.1 y 4.2.2 del TDR: diseño y selección de algoritmos de Machine Learning " +
    "para la identificación de favoritismo mediante modelos de clasificación o de puntuación de riesgo.",
  alcanzados: [
    vineta("Documentación de patrones identificados: concentración de contratos en un subconjunto de proveedores (hasta 32 contratos por proveedor), predominancia de Adjudicación Simplificada (33%) y Comparación de Precios (29%) sobre modalidades competitivas."),
    vineta("Análisis estadístico de variables clave: distribución log-normal de montos, con 7.7% de contratos identificados como outliers por el método IQR."),
    vineta("Propuesta fundamentada: se evaluaron Regresión Logística, Gradient Boosting y Random Forest. Se eligió Random Forest por su robustez ante variables correlacionadas, su soporte nativo para pesos balanceados de clase, y su compatibilidad directa con RandomForestClassifier de Spark MLlib para escalamiento futuro."),
    vineta("Arquitectura: 300 árboles, profundidad máxima 6 (para limitar sobreajuste dado el tamaño de la clase positiva), class_weight='balanced'."),
    vineta("Reporte de implementación: prototipo desarrollado en scikit-learn (RandomForestClassifier); arquitectura directamente portable a pyspark.ml.classification.RandomForestClassifier."),
    vineta("Parámetros de entrenamiento documentados en el código fuente (src/modelo_favoritismo.py, constante FEATURES y configuración del modelo)."),
  ],
  actividades: [
    vineta("Análisis comparativo de algoritmos candidatos sobre el dataset del Producto 2."),
    vineta("Definición de la arquitectura final y sus hiperparámetros."),
    vineta("Documentación de la lógica de negocio detrás de cada variable predictora."),
  ],
  cumplimiento: "Se completó la selección y el diseño de arquitectura del modelo. La implementación se realizó " +
    "en scikit-learn como prueba de concepto; la migración a Spark MLlib queda como actividad de la fase de " +
    "producción (ver Sección 8 del Informe Final, Producto 7).",
  dificultades: [
    vineta("No se dispuso de un clúster Hadoop/Spark productivo para validar el rendimiento a escala de big data; la arquitectura se validó funcionalmente en modo local."),
  ],
  conclusiones: "Random Forest ofrece el mejor balance entre desempeño e interpretabilidad para este caso de " +
    "uso. Se recomienda mantener esta elección en producción, complementada con SHAP (ver Producto 4) para " +
    "sustentar hallazgos ante auditores.",
});

// --- PRODUCTO 4 ---
const p4 = informeProducto({
  numero: 4, nombre: "Entrenamiento y Validación — Favoritismo",
  resumen: "El modelo entrenado alcanzó AUC-ROC y AUC-PR de 1.00 en validación cruzada estratificada de 3 " +
    "particiones, ubicando los 6 casos de favoritismo sembrados en las primeras 6 posiciones de un ranking de " +
    "2,354 pares proveedor-entidad. Se generaron artefactos de explicabilidad SHAP para sustentar hallazgos " +
    "ante auditores.",
  introduccion: "Cubre el numeral 4.2.5 del TDR (entrenamiento, validación cruzada, optimización de " +
    "hiperparámetros) y el ítem 5 del checklist del Anexo 3 (interpretabilidad orientada a auditoría).",
  alcanzados: [
    vineta("Métricas de evaluación (validación cruzada estratificada, 3 particiones): AUC-ROC = 1.00, AUC-PR = 1.00."),
    vineta("Registro de experimentos: validación cruzada estratificada elegida específicamente por la escasez de la clase positiva (6 de 2,354 registros), garantizando al menos 1-2 casos positivos por partición de prueba."),
    vineta("Ajuste de hiperparámetros: profundidad máxima limitada a 6 y ponderación balanceada de clases, para evitar sobreajuste dado el tamaño reducido de la clase positiva; se documenta como oportunidad de mejora una búsqueda sistemática (Grid/Random Search) con datos reales de mayor volumen."),
    vineta("Persistencia del modelo: outputs/models/modelo_favoritismo_rf.joblib."),
    vineta("Análisis comparativo: desempeño perfecto sobre datos sintéticos con separación clara; se documenta explícitamente que este resultado es esperable en datos sembrados y no debe interpretarse como el desempeño esperado sobre datos reales de producción."),
    vineta("Documentación técnica completa: artefactos SHAP (resumen global e individual) para sustentar hallazgos ante auditores — ver Figuras 1 y 2."),
  ],
  actividades: [
    vineta("Entrenamiento del modelo final sobre el dataset completo (2,354 registros)."),
    vineta("Validación cruzada estratificada y cálculo de métricas robustas a desbalance de clases."),
    vineta("Generación de valores SHAP (TreeExplainer) y ranking de riesgo para los 2,354 pares proveedor-entidad."),
  ],
  cumplimiento: "100% de las actividades de entrenamiento, validación e interpretabilidad fueron completadas. " +
    "El ranking de riesgo generado (outputs/ranking_riesgo_favoritismo.csv) está listo para revisión por un " +
    "auditor.",
  dificultades: [
    vineta("El desempeño perfecto en datos sintéticos no es representativo del desempeño esperado en producción; se recomienda repetir esta validación íntegramente al conectar datos reales."),
  ],
  conclusiones: "El modelo y sus artefactos de explicabilidad están listos para una prueba piloto con datos " +
    "reales supervisada por un auditor de la CGR.",
  figuras: [
    imagen("../outputs/charts/07_shap_summary_favoritismo.png", 440, 302),
    piePagina("Figura 1. Impacto SHAP por variable — vista global."),
    imagen("../outputs/charts/08_shap_waterfall_caso.png", 440, 325),
    piePagina("Figura 2. Explicación SHAP individual del caso de mayor riesgo."),
  ],
});

// --- PRODUCTO 5 ---
const p5 = informeProducto({
  numero: 5, nombre: "Limpieza y Preprocesamiento — Fraccionamiento",
  resumen: "Se construyeron 149 grupos proveedor-entidad-objeto (con 2 o más contratos) con variables de " +
    "ventana temporal, a partir del mismo dataset limpio del Producto 2, orientadas específicamente a la " +
    "detección de compras divididas.",
  introduccion: "Cubre el numeral 4.1.4 y 4.1.5 del TDR aplicados al caso de uso de detección de " +
    "fraccionamiento, incorporando el umbral normativo de Adjudicación Simplificada (S/. 400,000) como " +
    "variable derivada.",
  alcanzados: [
    vineta("Reutilización de la limpieza base del Producto 2 (mismos 239 valores nulos imputados, mismo tratamiento de outliers)."),
    vineta("Feature engineering específico: máximo de contratos del grupo en cualquier ventana móvil de 15 días; suma de montos en esa ventana; % de contratos con monto justo debajo del umbral de Adjudicación Simplificada."),
    vineta("Agrupación a nivel proveedor+entidad+objeto contractual (149 grupos con 2 o más contratos, de un total de miles de combinaciones posibles)."),
    vineta("División de datos: el dataset se usa íntegramente para detección de anomalías no supervisada (Producto 6), no requiere partición train/test tradicional."),
  ],
  actividades: [
    vineta("Ejecución de src/preprocesamiento.py, función features_fraccionamiento()."),
    vineta("Cálculo de ventanas deslizantes de 15 días por grupo proveedor-entidad-objeto."),
  ],
  cumplimiento: "100% completado. El dataset resultante recupera correctamente los 8 casos de fraccionamiento " +
    "sembrados como grupos de alta frecuencia de contratación en ventanas cortas.",
  dificultades: [
    vineta("El umbral de S/. 400,000 usado corresponde a la Adjudicación Simplificada vigente a la fecha de este prototipo; debe mantenerse actualizado según la normativa vigente (Ley 32069 / OECE) en producción."),
  ],
  conclusiones: "La variable de ventana temporal combinada con el umbral normativo es la señal más fuerte " +
    "para este caso de uso, como se confirma en el Producto 6.",
});

// --- PRODUCTO 6 ---
const p6 = informeProducto({
  numero: 6, nombre: "Selección y Desarrollo del Modelo — Fraccionamiento",
  resumen: "Se optó por combinar un modelo no supervisado de detección de anomalías (Isolation Forest) con " +
    "una regla de negocio explícita basada en el umbral legal de Adjudicación Simplificada, tras confirmar " +
    "que el modelo estadístico puro por sí solo es insuficiente.",
  introduccion: "Cubre el numeral 4.2.1 y 4.2.3 del TDR: técnicas de agrupamiento o detección de anomalías " +
    "para identificar patrones de compras repetitivas o divididas.",
  alcanzados: [
    vineta("Propuesta fundamentada: se evaluó clustering (K-Means) y detección de anomalías (Isolation Forest); se eligió Isolation Forest por no requerir definir a priori el número de grupos, adecuado para un fenómeno de baja frecuencia como el fraccionamiento."),
    vineta("Arquitectura: Isolation Forest con 300 estimadores, contaminación estimada dinámicamente según la proporción esperada de casos atípicos."),
    vineta("Complemento interpretable: regla explícita (≥3 contratos en ventana de 15 días Y ≥70% de montos bajo el umbral legal), incorporada como artefacto de \"caja blanca\" adicional al modelo estadístico."),
    vineta("Reporte de implementación: prototipo en scikit-learn (IsolationForest); en Spark MLlib el equivalente es KMeans o Bucketed Random Projection LSH sobre pyspark.ml, dado que MLlib no incluye Isolation Forest de forma nativa — se documenta como decisión de arquitectura a validar en la fase de producción."),
    vineta("Documentación de parámetros: ver src/modelo_fraccionamiento.py, constante FEATURES y configuración del modelo."),
  ],
  actividades: [
    vineta("Entrenamiento del modelo de detección de anomalías sobre el dataset del Producto 5."),
    vineta("Diseño y prueba de la regla interpretable basada en el umbral normativo."),
    vineta("Comparación cuantitativa entre ambos enfoques (ver Producto 7)."),
  ],
  cumplimiento: "100% completado. Se identificó que el modelo estadístico puro requiere complemento con " +
    "reglas de negocio para alcanzar precisión aceptable — hallazgo documentado explícitamente en el Producto 7.",
  dificultades: [
    vineta("Spark MLlib no incluye una implementación nativa de Isolation Forest; la migración a producción requiere evaluar alternativas (KMeans, LSH) o una implementación distribuida de terceros compatible con Spark."),
  ],
  conclusiones: "El enfoque combinado (modelo + regla normativa) es el recomendado para producción, no el " +
    "modelo estadístico de forma aislada.",
});

// ===========================================================================
// PRODUCTO 7 — Informe Final (estructura Anexo 01, numeral II.3)
// ===========================================================================
const p7 = documento(7, "Informe Final", "Informe Final", [
  titulo("Resumen Ejecutivo"),
  parrafo(
    "Este Informe Final consolida el entrenamiento y validación del modelo de fraccionamiento, y cierra la " +
    "consultoría con el manual de implementación, el plan de monitoreo, la transferencia de conocimiento y el " +
    "estado del repositorio de código. El prototipo completo cubre los tres casos de uso priorizados por el " +
    "TDR (favoritismo, fraccionamiento y vínculos proveedor-funcionario) más un módulo de análisis de vínculos " +
    "no exigido explícitamente en el cronograma pero sí en el numeral 4.2.4."
  ),

  titulo("Índice"),
  parrafo("1. Introducción — 2. Objetivo — 3. Productos alcanzados — 4. Entrenamiento y validación del " +
    "modelo de fraccionamiento — 5. Manual de implementación — 6. Plan de monitoreo y mantenimiento — " +
    "7. Transferencia de conocimiento — 8. Repositorio de código — 9. Conclusiones y recomendaciones — 10. Anexos"),

  titulo("1. Introducción"),
  parrafo(
    "Documento de cierre de la consultoría de prueba de concepto para el \"Módulo de análisis de datos para " +
    "dar soporte a los auditores durante la ejecución de los servicios de control\" del Proyecto Interno 1.8.2."
  ),

  titulo("2. Objetivo"),
  parrafo(
    "Consolidar los resultados de los 7 productos, dejar documentado el estado técnico del prototipo, y " +
    "establecer la ruta de trabajo hacia una versión de producción sobre la infraestructura institucional de " +
    "la CGR."
  ),

  titulo("3. Productos Alcanzados"),
  tabla(
    ["N°", "Producto", "Estado"],
    [
      ["1", "Plan de Trabajo", "Completo"],
      ["2", "Limpieza y preprocesamiento — Favoritismo", "Completo"],
      ["3", "Selección y desarrollo del modelo — Favoritismo", "Completo"],
      ["4", "Entrenamiento y validación — Favoritismo (AUC-ROC 1.00)", "Completo"],
      ["5", "Limpieza y preprocesamiento — Fraccionamiento", "Completo"],
      ["6", "Selección y desarrollo del modelo — Fraccionamiento", "Completo"],
      ["7", "Informe Final (este documento)", "Completo"],
      ["—", "Análisis de vínculos proveedor-funcionario (numeral 4.2.4)", "Completo (adicional)"],
      ["—", "Diccionario de datos y diagrama del modelo (numeral 3.2.g)", "Completo (adicional)"],
    ],
    [700, 6000, 2100],
  ),

  titulo("4. Entrenamiento y Validación del Modelo de Fraccionamiento"),
  parrafo(
    "Se comparó el desempeño del modelo estadístico puro contra la regla interpretable basada en el umbral " +
    "legal de Adjudicación Simplificada, sobre 149 grupos proveedor-entidad-objeto con 8 casos de " +
    "fraccionamiento sembrados."
  ),
  tabla(
    ["Enfoque", "Grupos marcados", "Aciertos reales", "Precisión"],
    [
      ["Isolation Forest (solo)", "8", "3", "37.5%"],
      ["Regla interpretable (umbral legal)", "7", "7", "100.0%"],
      ["Combinado (modelo Y regla)", "2", "2", "100.0%"],
    ],
    [3400, 2000, 2000, 1400],
  ),
  parrafo(
    "Hallazgo principal de la consultoría: el conocimiento normativo del dominio (el umbral legal exacto) " +
    "aporta más precisión que el modelo estadístico por sí solo. Se recomienda que el modelo de producción " +
    "priorice la regla interpretable como filtro principal, usando el score de anomalía como señal secundaria " +
    "de refuerzo, no al revés."
  ),

  titulo("5. Manual de Implementación"),
  parrafo("Orden de ejecución de los scripts para reproducir el prototipo completo desde cero:"),
  vineta("1. src/generar_datos.py — genera el dataset base de contrataciones."),
  vineta("2. src/eda.py — análisis exploratorio (opcional, no genera datos para pasos posteriores)."),
  vineta("3. src/preprocesamiento.py — limpieza y generación de los datasets de favoritismo y fraccionamiento."),
  vineta("4. src/modelo_favoritismo.py — entrena el modelo, genera SHAP y el ranking de riesgo."),
  vineta("5. src/modelo_fraccionamiento.py — entrena el modelo y evalúa la regla interpretable."),
  vineta("6. src/modelo_grafos.py — construye el grafo de vínculos proveedor-funcionario."),
  vineta("7. src/generar_diccionario_diagrama.py — genera el diccionario de datos y el diagrama ER."),
  vineta("8. reporte/generar_reporte.js (node) — consolida todo en el reporte técnico único."),

  titulo("6. Plan de Monitoreo y Mantenimiento"),
  parrafo(
    "Corresponde al numeral 3.2.c del TDR (\"Estrategias de sostenibilidad del modelo\"). Se recomienda: " +
    "(1) reentrenamiento periódico (trimestral o ante cambios normativos de umbrales), (2) monitoreo de " +
    "data drift comparando la distribución de nuevas contrataciones contra la distribución de entrenamiento, " +
    "y (3) retroalimentación activa de auditores marcando falsos positivos/negativos, para reetiquetar casos y " +
    "reentrenar — mecanismo de auto-mejora que reemplaza la falta de ground truth histórico."
  ),

  titulo("7. Transferencia de Conocimiento"),
  parrafo(
    "Todo el código fuente está comentado en español, con docstrings que referencian el numeral específico " +
    "del TDR que cada módulo cubre, para facilitar la revisión por personal no especializado en ciencia de " +
    "datos. Se recomienda una sesión de walkthrough técnico con el equipo de la Subgerencia de Sistemas de " +
    "Información y Analítica de Datos antes de cualquier decisión de continuar o no con una consultoría formal."
  ),

  titulo("8. Repositorio de Código"),
  parrafo(
    "Repositorio público en GitHub (ver portada), organizado en carpetas data/ (datasets), src/ (scripts), " +
    "outputs/ (gráficos, modelos entrenados y rankings de riesgo) y reporte/ (generación de documentos). " +
    "Historial de commits documenta el avance producto por producto."
  ),

  titulo("9. Conclusiones y Recomendaciones"),
  parrafo(
    "El prototipo demuestra que los tres casos de uso priorizados del TDR son técnicamente alcanzables con " +
    "herramientas open source y en un plazo de desarrollo muy reducido frente a los 180 días previstos. El " +
    "hallazgo más relevante — que la regla normativa supera al modelo estadístico puro en el caso de " +
    "fraccionamiento — sugiere que gran parte del valor de esta consultoría está en la traducción del marco " +
    "legal a reglas computables, no únicamente en la sofisticación del modelo. Se recomienda una fase piloto " +
    "con datos reales, supervisada por auditores, antes de cualquier despliegue en producción."
  ),

  titulo("10. Anexos"),
  parrafo("Ver Productos 1 a 6 para el detalle metodológico completo de cada etapa, y el repositorio de código indicado en la portada."),
]);

// ===========================================================================
async function guardar(doc, nombreArchivo) {
  const buf = await Packer.toBuffer(doc);
  fs.writeFileSync(`${OUT}/${nombreArchivo}`, buf);
  console.log(`Generado: ${OUT}/${nombreArchivo}`);
}

(async () => {
  await guardar(p1, "Producto_01_Plan_de_Trabajo.docx");
  await guardar(p2, "Producto_02_Preprocesamiento_Favoritismo.docx");
  await guardar(p3, "Producto_03_Modelo_Favoritismo.docx");
  await guardar(p4, "Producto_04_Entrenamiento_Favoritismo.docx");
  await guardar(p5, "Producto_05_Preprocesamiento_Fraccionamiento.docx");
  await guardar(p6, "Producto_06_Modelo_Fraccionamiento.docx");
  await guardar(p7, "Producto_07_Informe_Final.docx");
  console.log("\nLos 7 productos formales fueron generados.");
})();
