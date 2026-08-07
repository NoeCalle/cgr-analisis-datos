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
  parrafo(
    "Actualización: la orquestación de estas actividades se implementó y ejecutó realmente con Apache " +
    "Airflow — dos DAGs reales (modulo_analisis_datos_1_8_2 y monitoreo_reentrenamiento_1_8_2), no solo " +
    "planificados en este documento. Ver Producto 7, Sección 5, para el detalle y la evidencia de ejecución."
  ),

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
    vineta("No se tuvo acceso a datos reales de SIAF/SEACE al momento de este producto; se trabajó con un dataset sintético diseñado para replicar su estructura y distribución esperada."),
    vineta("La imputación por mediana/moda es una estrategia conservadora; en producción debería evaluarse imputación más sofisticada (KNN, modelos predictivos) según la calidad real de los datos de la CGR."),
  ],
  conclusiones: "El pipeline de limpieza y feature engineering es reproducible. Actualización posterior a este " +
    "producto: se validó tanto en Spark DataFrames real (Producto 7, Sección 4) bajo los estándares SQL " +
    "institucionales (LEFT JOIN, poda de particiones — Producto 7, Sección 6), como sobre 47,442 contratos " +
    "reales de SEACE obtenidos del portal de datos abiertos de la OECE (Producto 7, Sección 10).",
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
    vineta("Arquitectura: 300 árboles, profundidad máxima 6 (para limitar sobreajuste dado el tamaño de la clase positiva), class_weight='balanced'. Actualización: una búsqueda sistemática posterior (Producto 4) confirmó 100 árboles/profundidad 3 como igual de efectivo y ~65% más rápido de entrenar — arquitectura final ajustada en base a esa evidencia."),
    vineta("Reporte de implementación: implementado y ejecutado en scikit-learn Y en Spark MLlib real (pyspark.ml.classification.RandomForestClassifier) — no solo 'portable', sino corrido y verificado en ambas plataformas (ver Producto 7, Sección 4)."),
    vineta("Parámetros de entrenamiento documentados en el código fuente (src/modelo_favoritismo.py y src/spark/modelo_favoritismo_spark.py)."),
  ],
  actividades: [
    vineta("Análisis comparativo de algoritmos candidatos sobre el dataset del Producto 2."),
    vineta("Definición de la arquitectura final y sus hiperparámetros."),
    vineta("Documentación de la lógica de negocio detrás de cada variable predictora."),
  ],
  cumplimiento: "Se completó la selección y el diseño de arquitectura del modelo. La implementación se realizó " +
    "en scikit-learn y posteriormente se ejecutó y validó en Spark MLlib real (ver Producto 7, Sección 4) — la " +
    "migración ya no es una actividad pendiente.",
  dificultades: [
    vineta("Al momento de este producto no se había validado en Spark real; esto se resolvió en una etapa posterior (Producto 7) obteniendo los .jar necesarios directamente de Maven Central."),
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
    vineta("Ajuste de hiperparámetros: búsqueda sistemática en grilla (GridSearchCV, 60 combinaciones, validación cruzada estratificada de 3 particiones) confirmó que 100 árboles/profundidad 3 igualan el AUC-PR máximo (1.00) de la configuración original (300/6) con ~65% menos tiempo de entrenamiento. Confirmado de forma independiente con pyspark.ml.tuning.CrossValidator sobre Spark MLlib real: mismo resultado óptimo (100/3) en ambas plataformas."),
    vineta("Persistencia del modelo: outputs/models/modelo_favoritismo_rf.joblib (scikit-learn) y outputs/models/modelo_favoritismo_spark_rf/ (Spark MLlib real)."),
    vineta("Análisis comparativo: desempeño perfecto sobre datos sintéticos con separación clara, reproducido de forma idéntica en Spark MLlib real (AUC-ROC 1.00, 6/6 casos en el top-6). Se documenta explícitamente que este resultado es esperable en datos sembrados y no debe interpretarse como el desempeño esperado sobre datos reales de producción."),
    vineta("Documentación técnica completa: artefactos SHAP (resumen global e individual) para sustentar hallazgos ante auditores — ver Figuras 1 y 2. Resultados publicados en un esquema listo para SSRS (tabla PrediccionesFavoritismo, ver Producto 7 Sección 6)."),
  ],
  actividades: [
    vineta("Entrenamiento del modelo final sobre el dataset completo (2,354 registros), en scikit-learn y en Spark MLlib real."),
    vineta("Validación cruzada estratificada (scikit-learn) y CrossValidator (Spark MLlib) para la búsqueda de hiperparámetros."),
    vineta("Generación de valores SHAP (TreeExplainer) y ranking de riesgo para los 2,354 pares proveedor-entidad."),
  ],
  cumplimiento: "100% de las actividades de entrenamiento, validación e interpretabilidad fueron completadas, " +
    "incluyendo la ejecución real en Spark MLlib (no solo scikit-learn) y la búsqueda sistemática de " +
    "hiperparámetros en ambas plataformas. El ranking de riesgo generado está listo para revisión por un " +
    "auditor y publicado en un esquema tipo SQL Server.",
  dificultades: [
    vineta("El desempeño perfecto en datos sintéticos no es representativo del desempeño esperado en producción; se recomienda repetir esta validación íntegramente al conectar datos reales (ver Producto 7, Sección 10, donde se corrió una versión no supervisada equivalente sobre 47,442 contratos reales de SEACE)."),
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
    "para este caso de uso, como se confirma en el Producto 6. Esta lógica se reprodujo sin cambios sobre " +
    "Spark real (ventanas móviles vía Window functions) y sobre 47,442 contratos reales de SEACE — ver " +
    "Producto 7, Secciones 4 y 10.",
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
    vineta("Reporte de implementación: prototipo en scikit-learn (IsolationForest). Actualización: se ejecutó también en Spark MLlib real usando KMeans (pyspark.ml.clustering), ya que MLlib no tiene Isolation Forest nativo y no existe un paquete confiable que lo agregue sin acceso a Maven. Resultado real en Spark: 0/8 casos detectados (peor que Isolation Forest, que detectó 3/8) — ver Producto 7, Sección 4."),
    vineta("Documentación de parámetros: ver src/modelo_fraccionamiento.py y src/spark/modelo_fraccionamiento_spark.py."),
  ],
  actividades: [
    vineta("Entrenamiento del modelo de detección de anomalías sobre el dataset del Producto 5, en scikit-learn y en Spark MLlib real."),
    vineta("Diseño y prueba de la regla interpretable basada en el umbral normativo, reproducida sin cambios en ambas plataformas."),
    vineta("Comparación cuantitativa entre los tres enfoques — Isolation Forest, KMeans en Spark, y la regla (ver Producto 7)."),
  ],
  cumplimiento: "100% completado, incluyendo la validación en Spark MLlib real. El hallazgo se reforzó con " +
    "evidencia adicional: ni Isolation Forest ni KMeans (ambos algoritmos estadísticos, en dos plataformas " +
    "distintas) igualan la precisión de la regla interpretable — documentado explícitamente en el Producto 7.",
  dificultades: [
    vineta("Spark MLlib no incluye una implementación nativa de Isolation Forest, y el paquete GraphFrames/Delta que sí requerían Maven se resolvieron por separado (ver Producto 7) — pero Isolation Forest en sí no tiene equivalente instalable en MLlib, por lo que se usó KMeans como sustituto nativo, con peor resultado (0/8 vs. 3/8), reforzando aún más la conclusión de este producto."),
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
    "Este Informe Final consolida el cierre de la consultoría de prueba de concepto. Además de los 6 " +
    "productos anteriores, este documento incorpora todo lo construido después de la primera versión: " +
    "validación real en Apache Spark MLlib, orquestación real con Apache Airflow (2 DAGs), búsqueda " +
    "sistemática de hiperparámetros confirmada en ambas plataformas, extracción bajo estándares SQL " +
    "institucionales, publicación lista para SSRS, un mecanismo real de autoevaluación y autoentrenamiento, " +
    "análisis de vínculos con GraphFrames real, Delta Lake real (ACID, time travel, CDC/CDF), y una prueba " +
    "adicional (fuera del alcance formal del TDR) sobre 47,442 contratos reales de contrataciones públicas " +
    "del Perú."
  ),

  titulo("Índice"),
  parrafo("1. Introducción — 2. Objetivo — 3. Productos alcanzados — 4. Validación en Apache Spark MLlib — " +
    "5. Orquestación con Apache Airflow — 6. Estándares SQL y publicación SSRS — 7. Autoevaluación y " +
    "autoentrenamiento — 8. Vínculos con GraphFrames real — 9. Delta Lake real — 10. Validación con datos " +
    "reales de SEACE — 11. Verificación de componentes de la plataforma — 12. Manual de implementación — " +
    "13. Plan de monitoreo y mantenimiento — 14. Transferencia de conocimiento — 15. Repositorio de código — " +
    "16. Conclusiones y recomendaciones — 17. Anexos"),

  titulo("1. Introducción"),
  parrafo(
    "Documento de cierre de la consultoría de prueba de concepto para el \"Módulo de análisis de datos para " +
    "dar soporte a los auditores durante la ejecución de los servicios de control\" del Proyecto Interno 1.8.2."
  ),

  titulo("2. Objetivo"),
  parrafo(
    "Consolidar los resultados de los 7 productos y de todo el trabajo adicional realizado, dejar " +
    "documentado el estado técnico real del prototipo (con evidencia de ejecución, no solo teórica), y " +
    "establecer la ruta de trabajo hacia una versión de producción sobre la infraestructura institucional de " +
    "la CGR."
  ),

  titulo("3. Productos Alcanzados"),
  tabla(
    ["N°", "Producto / Componente", "Estado"],
    [
      ["1", "Plan de Trabajo", "Completo"],
      ["2", "Limpieza y preprocesamiento — Favoritismo", "Completo"],
      ["3", "Selección y desarrollo del modelo — Favoritismo", "Completo"],
      ["4", "Entrenamiento y validación — Favoritismo (AUC-ROC 1.00, sklearn y Spark)", "Completo"],
      ["5", "Limpieza y preprocesamiento — Fraccionamiento", "Completo"],
      ["6", "Selección y desarrollo del modelo — Fraccionamiento", "Completo"],
      ["7", "Informe Final (este documento)", "Completo"],
      ["—", "Vínculos proveedor-funcionario (networkx Y GraphFrames real)", "Completo (adicional)"],
      ["—", "Diccionario de datos y diagrama del modelo", "Completo (adicional)"],
      ["—", "Apache Spark MLlib real (no solo portable)", "Completo (adicional)"],
      ["—", "Apache Airflow real (2 DAGs, 18 tareas, 100% éxito)", "Completo (adicional)"],
      ["—", "Búsqueda sistemática de hiperparámetros (sklearn + Spark)", "Completo (adicional)"],
      ["—", "Estándares SQL institucionales (LEFT JOIN, poda de particiones)", "Completo (adicional)"],
      ["—", "Integración SSRS (esquema + .rdl real)", "Completo (adicional)"],
      ["—", "Autoevaluación y autoentrenamiento (PSI + reentrenamiento)", "Completo (adicional)"],
      ["—", "Delta Lake real (ACID, time travel, CDC/CDF)", "Completo (adicional)"],
      ["—", "Validación sobre 47,442 contratos reales de SEACE", "Completo (fuera de alcance del TDR)"],
      ["—", "Hadoop YARN / HDFS", "Fuera de alcance por naturaleza (requiere red física real)"],
    ],
    [700, 5500, 2600],
  ),

  titulo("4. Validación en Apache Spark MLlib (Favoritismo y Fraccionamiento)"),
  parrafo(
    "Se ejecutó la lógica de ambos modelos sobre pyspark.ml en modo local, no solo scikit-learn. Para " +
    "favoritismo, RandomForestClassifier reprodujo el mismo resultado (6/6 casos, AUC-ROC 1.00). Para " +
    "fraccionamiento, al no existir Isolation Forest nativo en MLlib, se usó KMeans — con peor resultado, lo " +
    "que refuerza el hallazgo central del prototipo."
  ),
  tabla(
    ["Enfoque", "Grupos/casos marcados", "Aciertos reales", "Precisión"],
    [
      ["Isolation Forest, scikit-learn (solo)", "8", "3", "37.5%"],
      ["KMeans, Spark MLlib real (solo)", "8", "0", "0.0%"],
      ["Regla interpretable (umbral legal, ambas plataformas)", "7", "7", "100.0%"],
    ],
    [4000, 2200, 1600, 1400],
  ),
  parrafo("", { size: 4 }),
  parrafo(
    "Nota metodológica: los 8 casos de fraccionamiento sembrados tienen exactamente el patrón que la regla " +
    "busca (mismo proveedor-entidad-objeto, compras repetidas en pocos días, montos bajo el umbral). El " +
    "100% confirma que la regla está correctamente implementada, no que vaya a repetir ese desempeño sobre " +
    "fraccionamiento real no sembrado — ver Producto 7, Sección 10, donde se aplica como señal de riesgo " +
    "sobre datos reales sin etiquetas, no como determinación automática."
  ),
  parrafo("", { size: 4 }),
  parrafo(
    "Búsqueda de hiperparámetros: GridSearchCV (60 combinaciones, scikit-learn) y CrossValidator " +
    "(pyspark.ml.tuning, 12 ajustes) confirmaron de forma independiente la misma configuración óptima " +
    "(100 árboles, profundidad 3) para favoritismo — coincidencia cruzada entre ambas plataformas."
  ),

  titulo("5. Orquestación con Apache Airflow"),
  parrafo(
    "Se construyeron y ejecutaron 2 DAGs reales con `airflow dags test` (no solo diseñados en papel):"
  ),
  tabla(
    ["DAG", "Tareas", "Resultado"],
    [
      ["modulo_analisis_datos_1_8_2", "9 (generación → bronce → plata → modelos → grafos → oro → docs)", "9/9 success, 38.5s"],
      ["monitoreo_reentrenamiento_1_8_2", "2 (generar lote → autoevaluar y reentrenar)", "2/2 success, 12.2s"],
    ],
    [3600, 3800, 1800],
  ),
  parrafo("", { size: 4 }),
  parrafo("Código en airflow_home/dags/. Ambos DAGs respetan el linaje real de los datos, con ramas paralelas donde corresponde."),

  titulo("6. Estándares SQL Institucionales y Publicación para SSRS"),
  vineta("LEFT JOIN explícito + poda de particiones (Spark particionado por año-mes): 6 de 42 particiones leídas al filtrar por fecha reciente (14%), evitando Full Table Scan sobre la tabla de hechos."),
  vineta("Prueba dirigida de LEFT JOIN vs. INNER JOIN con un huérfano forzado: 1 fila vs. 0 filas — confirma que LEFT JOIN no descarta contratos silenciosamente."),
  vineta("Esquema T-SQL real (ssrs/schema_sql_server.sql) con las 3 tablas de resultados, publicado sobre SQLite como stand-in documentado (5,523 registros cargados) y un archivo .rdl real y válido, listo para desplegar en un servidor SSRS."),

  titulo("7. Autoevaluación y Autoentrenamiento (Ejecutado)"),
  parrafo(
    "A diferencia de la primera versión de este Informe Final, donde esto era solo una recomendación " +
    "textual, se implementó y ejecutó realmente: un mecanismo de dos señales (Population Stability Index + " +
    "degradación de recall) que decide si reentrenar, orquestado por el segundo DAG de Airflow (Sección 5)."
  ),
  tabla(
    ["Escenario", "PSI máximo", "¿Disparó reentrenamiento?"],
    [
      ["Normal (sin deriva)", "0.186", "No"],
      ["Con deriva simulada", "1.608", "Sí — reentrenado automáticamente"],
    ],
    [3600, 2400, 3200],
  ),
  parrafo("", { size: 4 }),
  parrafo(
    "Cada decisión queda registrada en outputs/log_reentrenamiento.csv con marca de tiempo, señales " +
    "evaluadas y motivo — ningún reentrenamiento ocurre de forma silenciosa."
  ),

  titulo("8. Vínculos Proveedor-Funcionario con GraphFrames Real"),
  parrafo(
    "El análisis de vínculos (numeral 4.2.4) se validó de forma cruzada en dos motores: networkx (Producto " +
    "original) y Spark GraphFrames real (io.graphframes:graphframes-spark4_2.13:0.10.0). Ambos detectaron " +
    "los mismos 5 de 5 vínculos sospechosos sembrados. GraphFrames además calculó PageRank (centralidad de " +
    "funcionarios en la red) y Connected Components — capacidades que networkx no ofrece a escala distribuida."
  ),

  titulo("9. Delta Lake Real (ACID, Time Travel, CDC/CDF)"),
  parrafo(
    "La capa Bronce se reescribió como tabla Delta Lake real (no Parquet plano), simulando el escenario más " +
    "relevante para un auditor: una corrección de monto sobre un contrato ya existente."
  ),
  tabla(
    ["Capacidad", "Resultado"],
    [
      ["UPDATE transaccional (ACID)", "Aplicado, nueva versión creada automáticamente"],
      ["Time travel a la versión anterior", "Monto original recuperado exacto tras la corrección"],
      ["Change Data Feed (CDC/CDF)", "Preimage y postimage capturados fila por fila"],
    ],
    [3400, 5400],
  ),

  titulo("10. Validación con Datos Reales de SEACE (fuera del alcance del TDR)"),
  parrafo(
    "Adicional al alcance formal del TDR (que usa datos sintéticos): se obtuvieron datos públicos reales de " +
    "contrataciones del Estado peruano (portal OCDS de la OECE, licencia CC BY 4.0, año 2022) y se corrió el " +
    "pipeline completo sobre ellos — 47,442 contratos reales, 25,535 proveedores, 2,732 entidades, S/. " +
    "32,241 millones analizados. Se detectó y corrigió un artefacto propio (consorcios contados varias " +
    "veces) y un falso positivo genuino (pagos individuales agrupados mal clasificados como consorcio) — " +
    "documentado con transparencia, no ocultado."
  ),

  titulo("11. Verificación de Componentes de la Plataforma (Anexo 2 del TDR)"),
  parrafo(
    "De 18 componentes especificados en el Anexo 2 (\"Arquitectura de la Plataforma de Minería de Datos\"), " +
    "se verificaron como completos: ingesta Batch y Streaming, HMS (Hive Metastore embebido), Parquet, los " +
    "5 lenguajes soportados (Python/SQL/Scala/R/Java, incluyendo R con una prueba t de Welch real), Spark " +
    "MLlib, Spark GraphX (vía GraphFrames), Airflow, Delta Lake y CDC/CDF."
  ),
  parrafo(
    "Hadoop YARN/HDFS queda pendiente por una combinación de límites de tamaño de archivo, no por " +
    "imposibilidad técnica de correr en una sola máquina: Apache documenta explícitamente un modo " +
    "pseudo-distribuido (single-node) para HDFS/YARN. Se investigó la utilidad oficial " +
    "hadoop-client-minicluster (la que usa el propio equipo de Hadoop para pruebas, 27.1 MB, obtenida), " +
    "pero requiere un segundo archivo (hadoop-client-runtime, 40-70 MB) que excede el límite de subida de " +
    "este entorno; el tarball binario completo (554 MB) también. Lo que sí es una limitación de fondo: el " +
    "beneficio característico de HDFS/YARN en producción (replicación tolerante a fallos, reparto de " +
    "recursos entre nodos) requiere, por diseño, varias máquinas físicas distintas — algo que ni siquiera " +
    "un modo pseudo-distribuido completado en este entorno demostraría."
  ),
  parrafo(
    "SQL Server real, SSAS y Power BI quedan fuera de alcance por decisión — requieren licencia o cuenta, y " +
    "el prototipo se construye enteramente con herramientas de licencia abierta."
  ),

  titulo("12. Manual de Implementación"),
  parrafo("Orden de ejecución para reproducir el prototipo completo desde cero:"),
  vineta("1-7: generar_datos.py → eda.py → preprocesamiento.py → modelo_favoritismo.py → modelo_fraccionamiento.py → modelo_grafos.py → generar_diccionario_diagrama.py."),
  vineta("8. Orquestado end-to-end vía Airflow: airflow dags test modulo_analisis_datos_1_8_2 (reemplaza los pasos 1-7 en producción)."),
  vineta("9. src/spark/*.py — versiones Spark MLlib real (favoritismo, fraccionamiento, vínculos con GraphFrames, estándares SQL, Delta Lake)."),
  vineta("10. src/autoevaluacion.py — orquestado vía airflow dags test monitoreo_reentrenamiento_1_8_2."),
  vineta("11. src/publicar_ssrs.py — publica resultados en el esquema SQL."),
  vineta("12. reporte/generar_reporte.js y reporte/generar_productos_formales.js (node) — generan toda la documentación."),

  titulo("13. Plan de Monitoreo y Mantenimiento"),
  parrafo(
    "Ya no es solo una recomendación: el mecanismo de autoevaluación (Sección 7) está implementado y " +
    "orquestado con Airflow en modo mensual (schedule=\"@monthly\"). Se recomienda para producción: " +
    "(1) desplegar el DAG de monitoreo en el Airflow productivo de la CGR, (2) conectar el lote 'nuevo' a la " +
    "ingesta real de SEACE en vez de datos simulados, y (3) revisar periódicamente los umbrales de PSI y " +
    "recall según la experiencia acumulada de los auditores."
  ),

  titulo("14. Transferencia de Conocimiento"),
  parrafo(
    "Todo el código fuente está comentado en español, con docstrings que referencian el numeral específico " +
    "del TDR que cada módulo cubre. Se recomienda una sesión de walkthrough técnico con el equipo de la " +
    "Subgerencia de Sistemas de Información y Analítica de Datos antes de cualquier decisión de continuar o " +
    "no con una consultoría formal."
  ),

  titulo("15. Repositorio de Código"),
  parrafo(
    "Repositorio público en GitHub (ver portada): data/, src/ (incluye src/spark/ para las versiones Spark " +
    "real), outputs/, airflow_home/dags/, ssrs/, jars/ (GraphFrames y Delta Lake, descargados de Maven " +
    "Central), data_real/ (pipeline sobre datos reales), y reporte/. Historial de commits documenta el " +
    "avance de cada pieza, incluyendo los intentos fallidos documentados con honestidad (ej. las dos rutas " +
    "de GraphFrames que no funcionaron antes de encontrar la correcta)."
  ),

  titulo("16. Conclusiones y Recomendaciones"),
  parrafo(
    "El prototipo demuestra que los tres casos de uso priorizados del TDR son técnicamente alcanzables con " +
    "herramientas de licencia abierta, construidas como una contribución al control gubernamental y a la " +
    "lucha anticorrupción, con evidencia de " +
    "ejecución real en cada pieza de la arquitectura del Anexo 2 — no solo en la lógica de los modelos. El " +
    "hallazgo más relevante se mantiene y se reforzó con más evidencia: ni Isolation Forest ni KMeans " +
    "(en dos plataformas distintas) igualan a la regla interpretable basada en el umbral legal — el valor " +
    "está en traducir la normativa a reglas computables, no solo en la sofisticación del modelo. Se " +
    "recomienda una fase piloto con datos reales de la CGR, supervisada por auditores, antes de cualquier " +
    "despliegue en producción."
  ),

  titulo("17. Anexos"),
  parrafo("Ver Productos 1 a 6 para el detalle metodológico de cada etapa base, y el repositorio de código indicado en la portada para el detalle completo de las mejoras posteriores."),
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
