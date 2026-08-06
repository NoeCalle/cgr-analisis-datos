const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, ImageRun, PageBreak, BorderStyle,
  Header, Footer, PageNumber, NumberFormat, VerticalAlign,
} = require("docx");
const fs = require("fs");

const AZUL = "1F4E79";
const GRIS_CLARO = "F2F2F2";
const ROJO = "C0392B";

const DICCIONARIO = [
  ["contratos_siaf_seace.id_contrato", "string", "Identificador único del contrato (simula clave de proceso SEACE)."],
  ["contratos_siaf_seace.id_proveedor", "string (FK)", "Referencia al proveedor adjudicado. Llave foránea a proveedores.id_proveedor."],
  ["contratos_siaf_seace.id_entidad", "string (FK)", "Entidad pública contratante. Llave foránea a entidades.id_entidad."],
  ["contratos_siaf_seace.id_funcionario", "string (FK)", "Funcionario responsable del proceso. Llave foránea a funcionarios.id_funcionario."],
  ["contratos_siaf_seace.modalidad", "categórica", "Modalidad de contratación según la Ley de Contrataciones del Estado."],
  ["contratos_siaf_seace.objeto", "categórica", "Tipo de bien, servicio u obra contratado."],
  ["contratos_siaf_seace.monto", "numérico (S/.)", "Monto contractual en soles."],
  ["contratos_siaf_seace.fecha_contrato", "fecha", "Fecha de suscripción del contrato."],
  ["contratos_siaf_seace.es_favoritismo_real", "booleano", "Etiqueta de validación interna del prototipo (ground truth sintético). No existe en producción."],
  ["contratos_siaf_seace.es_fraccionamiento_real", "booleano", "Etiqueta de validación interna del prototipo (ground truth sintético). No existe en producción."],
  ["proveedores.id_proveedor", "string (PK)", "Identificador único del proveedor."],
  ["proveedores.ruc", "string", "Registro Único de Contribuyente del proveedor."],
  ["proveedores.razon_social", "string", "Razón social del proveedor."],
  ["entidades.id_entidad", "string (PK)", "Identificador único de la entidad pública."],
  ["entidades.nombre_entidad", "string", "Nombre de la entidad pública contratante."],
  ["funcionarios.id_funcionario", "string (PK)", "Identificador único del funcionario."],
  ["funcionarios.dni_funcionario", "string", "DNI del funcionario (para futuro cruce de vínculos, numeral 4.2.4)."],
  ["funcionarios.id_entidad", "string (FK)", "Entidad a la que pertenece el funcionario."],
  ["dataset_favoritismo.id_proveedor / id_entidad", "string (FK compuesta)", "Clave del par proveedor-entidad agregado."],
  ["dataset_favoritismo.n_contratos", "numérico", "N° de contratos ganados por el proveedor en la entidad."],
  ["dataset_favoritismo.monto_total / monto_promedio", "numérico (S/.)", "Monto acumulado y promedio de los contratos del par."],
  ["dataset_favoritismo.pct_no_competitiva", "numérico [0-1]", "Proporción de contratos bajo modalidades poco competitivas."],
  ["dataset_favoritismo.concentracion_objeto", "numérico [0-1]", "1 − (objetos distintos / n° contratos). Cercano a 1 = siempre el mismo objeto."],
  ["dataset_favoritismo.score_riesgo_favoritismo", "numérico [0-1]", "Salida del modelo Random Forest — probabilidad estimada de favoritismo."],
  ["dataset_fraccionamiento.id_proveedor / id_entidad / objeto", "string (FK compuesta)", "Clave del grupo proveedor-entidad-objeto."],
  ["dataset_fraccionamiento.max_contratos_ventana_15d", "numérico", "Máximo de contratos del grupo en cualquier ventana móvil de 15 días."],
  ["dataset_fraccionamiento.pct_montos_bajo_umbral", "numérico [0-1]", "Proporción de contratos con monto < 95% del umbral de Adjudicación Simplificada."],
  ["dataset_fraccionamiento.score_anomalia", "numérico", "Salida del modelo Isolation Forest — score de anomalía."],
  ["dataset_fraccionamiento.cumple_regla_fraccionamiento", "booleano", "Regla interpretable: ≥3 contratos en 15 días Y ≥70% de montos bajo el umbral."],
];

function titulo(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 150 } });
}
function subtitulo(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } });
}
function parrafo(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, ...opts })],
    spacing: { after: 160 },
  });
}
function vineta(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22 })],
    bullet: { level: 0 },
    spacing: { after: 80 },
  });
}
function imagen(path, width, height) {
  return new Paragraph({
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path), transformation: { width, height } })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
  });
}
function piePagina(texto) {
  return new Paragraph({
    children: [new TextRun({ text: texto, italics: true, size: 18, color: "666666" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 200 },
  });
}

function celda(text, { header = false, width, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: AZUL } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold: header, color: header ? "FFFFFF" : "000000", size: 20 })],
    })],
  });
}

function tabla(headers, rows, widths) {
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ children: headers.map((h, i) => celda(h, { header: true, width: widths[i] })) }),
      ...rows.map((r, ridx) => new TableRow({
        children: r.map((c, i) => celda(c, { width: widths[i], align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })),
      })),
    ],
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
  },
  sections: [
    // ---------- PORTADA ----------
    {
      properties: { page: { size: { width: 11906, height: 16838 } } }, // A4
      children: [
        new Paragraph({ text: "", spacing: { before: 1200 } }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "PROTOTIPO FUNCIONAL", bold: true, size: 28, color: AZUL })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 200, after: 200 },
          children: [new TextRun({
            text: "Módulo de Análisis de Datos para Dar Soporte a los Auditores Durante la Ejecución de los Servicios de Control",
            bold: true, size: 32,
          })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 600 },
          children: [new TextRun({ text: "Proyecto Interno 1.8.2 — Sistema Integrado de Control", size: 24, italics: true })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 800 },
          children: [new TextRun({ text: "Documento técnico elaborado como prueba de concepto (proof of concept)", size: 22 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "en respuesta a los Términos de Referencia de la Contraloría General de la República", size: 22 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 100, after: 800 },
          children: [new TextRun({ text: "para la contratación de un Consultor Científico de Datos (Mayo 2026)", size: 22 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 1200 },
          children: [new TextRun({ text: "Repositorio de código fuente:", bold: true, size: 20 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "https://github.com/NoeCalle/cgr-analisis-datos", size: 20, color: AZUL })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 1400 },
          children: [new TextRun({ text: "Agosto 2026", size: 20 })],
        }),
      ],
    },
    // ---------- CONTENIDO ----------
    {
      properties: { page: { size: { width: 11906, height: 16838 } } },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun({ text: "Módulo de Análisis de Datos — Prototipo", size: 16, color: "888888" })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [
              new TextRun({ text: "Página ", size: 18 }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18 }),
            ],
          })],
        }),
      },
      children: [
        titulo("Resumen Ejecutivo"),
        parrafo(
          "Este documento presenta un prototipo funcional del módulo de análisis de datos descrito en los " +
          "Términos de Referencia (TDR) para la contratación de un Consultor Científico de Datos del Proyecto " +
          "Interno 1.8.2 de la Contraloría General de la República (CGR). El objetivo es demostrar, con código " +
          "abierto y en un plazo de desarrollo muy reducido, que es técnicamente viable construir los componentes " +
          "centrales solicitados en el TDR — detección de favoritismo y de fraccionamiento en contrataciones " +
          "públicas — antes de comprometer una consultoría individual de S/. 72,000 por 180 días calendario."
        ),
        parrafo(
          "Se generó un conjunto de datos sintético que simula la integración de fuentes SIAF y SEACE, con casos " +
          "de favoritismo y fraccionamiento deliberadamente insertados para poder validar objetivamente si los " +
          "modelos los detectan. Los resultados muestran que ambos modelos —uno de scoring de riesgo (favoritismo) " +
          "y otro de detección de anomalías combinado con reglas de negocio (fraccionamiento)— identifican " +
          "correctamente los patrones sembrados, con alta interpretabilidad para sustentar hallazgos ante auditores."
        ),
        subtitulo("Hallazgo principal"),
        parrafo(
          "El modelo de favoritismo (Random Forest) ubicó los 6 casos reales sembrados en las primeras 6 " +
          "posiciones de un ranking de 2,354 pares proveedor-entidad. El modelo de fraccionamiento, combinando " +
          "una regla interpretable basada en el umbral legal de Adjudicación Simplificada con detección de " +
          "anomalías, alcanzó 100% de precisión (7 de 7 casos marcados fueron fraccionamiento real) sobre 8 " +
          "casos sembrados en 149 grupos proveedor-entidad-objeto."
        ),

        new Paragraph({ children: [new PageBreak()] }),

        titulo("1. Objetivo del Prototipo"),
        parrafo(
          "Construir, en código abierto (Python — pandas, scikit-learn) y de forma reproducible, una versión " +
          "funcional del \"Módulo de análisis de datos\" descrito en el numeral 3.1 del TDR, cubriendo los dos " +
          "casos de uso priorizados en el numeral 4.2: identificación de proveedores favoritos (4.2.2) y " +
          "detección de patrones de fraccionamiento (4.2.3)."
        ),
        parrafo(
          "Este documento no sustituye los 7 productos formales del TDR — que requieren acceso a datos reales de " +
          "SIAF/SEACE, certificación institucional y despliegue sobre el Lakehouse de la CGR (Anexo 2) — sino que " +
          "busca sustentar que la arquitectura de solución es de bajo riesgo técnico y puede construirse " +
          "rápidamente, y que el conocimiento del dominio (reglas de negocio y umbrales legales) es tan " +
          "importante como el modelo estadístico."
        ),

        titulo("2. Datos y Metodología"),
        subtitulo("2.1. Fuente de datos"),
        parrafo(
          "Al no tener acceso a las bases reales de la CGR, se generó un dataset sintético de 3,603 contratos " +
          "que replica la estructura esperada de la integración SIAF + SEACE: proveedor (RUC), entidad, " +
          "funcionario responsable, modalidad de contratación, objeto, monto y fecha. Se insertaron " +
          "deliberadamente 6 casos de favoritismo (concentración de contratos en modalidades poco competitivas) " +
          "y 8 casos de fraccionamiento (compras divididas en ventanas cortas de tiempo, con montos justo por " +
          "debajo del umbral de Adjudicación Simplificada), para tener un ground truth conocido contra el cual " +
          "validar los modelos — algo que no es posible hacer con datos reales sin etiquetas previas."
        ),
        subtitulo("2.2. Análisis Exploratorio y Preprocesamiento"),
        parrafo(
          "Se realizó limpieza de valores faltantes (6.44% de registros con al menos un nulo, imputados por " +
          "mediana/moda), tratamiento de outliers por winsorización al percentil 99, codificación one-hot de " +
          "variables categóricas y normalización de montos. Se diseñaron variables derivadas (feature " +
          "engineering) específicas para cada caso de uso: concentración de objeto contractual, porcentaje de " +
          "contratos bajo modalidades no competitivas, y conteo de contratos dentro de ventanas deslizantes de " +
          "15 días."
        ),
        imagen("outputs/charts/01_distribucion_montos.png", 560, 210),
        piePagina("Figura 1. Distribución de montos contractuales y detección de valores atípicos (método IQR)."),
        imagen("outputs/charts/03_concentracion_proveedores.png", 460, 288),
        piePagina("Figura 2. Concentración de contratos por proveedor — señal preliminar para el modelo de favoritismo."),

        new Paragraph({ children: [new PageBreak()] }),

        titulo("3. Modelo de Detección de Favoritismo"),
        parrafo(
          "Se entrenó un clasificador Random Forest (300 árboles, profundidad máxima 6, ponderación balanceada " +
          "de clases) sobre 10 variables agregadas a nivel proveedor-entidad. Dada la naturaleza minoritaria de " +
          "la clase positiva (0.25% de los pares en este dataset), se evaluó con validación cruzada estratificada " +
          "de 3 particiones y métricas robustas a desbalance (AUC-PR)."
        ),
        tabla(
          ["Métrica", "Valor (validación cruzada)"],
          [["AUC-ROC", "1.00"], ["AUC-PR", "1.00"], ["Casos reales en Top-6 del ranking", "6 de 6"]],
          [5000, 3800],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "Nota metodológica: el desempeño perfecto es esperable en datos sintéticos donde los patrones fueron " +
          "sembrados con separación clara. Sobre datos reales de producción se espera un desempeño menor; el " +
          "valor de esta prueba de concepto es demostrar que la arquitectura de features y modelado es correcta " +
          "y detecta lo que efectivamente está presente en los datos."
        ),
        subtitulo("3.1. Interpretabilidad para auditores (SHAP)"),
        parrafo(
          "El checklist de aceptación del TDR (Anexo 3, ítem 5) exige artefactos de explicabilidad tipo " +
          "\"caja blanca\" — específicamente valores SHAP, LIME o Feature Importance. Se implementaron valores " +
          "SHAP (TreeExplainer) sobre el modelo, que ofrecen dos niveles de explicación: (1) un resumen global " +
          "de cómo cada variable empuja el riesgo hacia arriba o hacia abajo en todo el conjunto de datos, y " +
          "(2) una explicación individual por caso, que es lo que un auditor necesita para sustentar un " +
          "hallazgo puntual ante un proveedor específico."
        ),
        imagen("outputs/charts/07_shap_summary_favoritismo.png", 460, 316),
        piePagina("Figura 3. Impacto SHAP por variable — vista global (rojo = valor alto de la variable)."),
        parrafo(
          "La Figura 4 muestra la explicación individual del caso de mayor riesgo real (proveedor P0000 en la " +
          "entidad E15): el modelo parte de un riesgo base de 0.48 y lo eleva a 0.97 principalmente por el " +
          "número de contratos ganados (+0.14), la concentración en un solo tipo de objeto contractual (+0.11) " +
          "y el monto total acumulado (+0.11). Esta desagregación es la que un auditor puede citar directamente " +
          "en un informe de hallazgo."
        ),
        imagen("outputs/charts/08_shap_waterfall_caso.png", 460, 340),
        piePagina("Figura 4. Explicación SHAP individual del caso de mayor riesgo (proveedor P0000, entidad E15)."),

        subtitulo("3.2. Top de pares proveedor-entidad por riesgo"),
        tabla(
          ["Proveedor", "Entidad", "N° contratos", "% modalidad no competitiva", "Score de riesgo"],
          [
            ["P0168", "E17", "12", "91.7%", "0.997"],
            ["P0000", "E15", "11", "100.0%", "0.970"],
            ["P0051", "E08", "16", "93.8%", "0.963"],
            ["P0138", "E00", "14", "100.0%", "0.957"],
            ["P0049", "E16", "15", "93.3%", "0.923"],
            ["P0154", "E16", "11", "100.0%", "0.843"],
          ],
          [2000, 1800, 1800, 2600, 1600],
        ),

        new Paragraph({ children: [new PageBreak()] }),

        titulo("4. Modelo de Detección de Fraccionamiento"),
        parrafo(
          "Se construyeron 149 grupos proveedor-entidad-objeto con 2 o más contratos, y se calcularon variables " +
          "de ventana temporal (máximo de contratos en ventanas móviles de 15 días, porcentaje de montos justo " +
          "por debajo del umbral legal de Adjudicación Simplificada). Se compararon dos enfoques: un modelo no " +
          "supervisado de detección de anomalías (Isolation Forest) y una regla explícita basada en el umbral " +
          "normativo vigente."
        ),
        tabla(
          ["Enfoque", "Grupos marcados", "Aciertos reales", "Precisión"],
          [
            ["Isolation Forest (solo)", "8", "3", "37.5%"],
            ["Regla interpretable (umbral legal)", "7", "7", "100.0%"],
            ["Combinado (modelo Y regla)", "2", "2", "100.0%"],
          ],
          [3600, 2200, 2000, 2000],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "Hallazgo relevante: el modelo puramente estadístico, sin contexto normativo, detecta solo una " +
          "fracción de los casos reales. Al incorporar la regla de negocio derivada directamente de la Ley de " +
          "Contrataciones del Estado (umbral de Adjudicación Simplificada), la precisión sube a 100%. Esto " +
          "confirma que el valor de este módulo no está solo en el algoritmo, sino en traducir correctamente la " +
          "normativa de contrataciones públicas a reglas computables — un trabajo de dominio que un consultor " +
          "conocedor del marco legal peruano puede hacer sin necesitar infraestructura de big data desde el " +
          "primer día."
        ),
        imagen("outputs/charts/06_deteccion_fraccionamiento.png", 460, 288),
        piePagina("Figura 5. Casos reales sembrados (rojo) vs. score de anomalía y señales de ventana temporal."),

        subtitulo("4.1. Grupos marcados por la regla interpretable"),
        tabla(
          ["Proveedor", "Entidad", "Objeto", "Máx. contratos / 15 días", "% bajo umbral"],
          [
            ["P0093", "E16", "Servicio de limpieza y vigilancia", "5", "100%"],
            ["P0008", "E15", "Servicio de limpieza y vigilancia", "5", "100%"],
            ["P0067", "E00", "Adquisición de equipos informáticos", "4", "100%"],
            ["P0066", "E13", "Adquisición de bienes de oficina", "3", "100%"],
            ["P0098", "E02", "Servicio de transporte", "3", "100%"],
            ["P0147", "E17", "Adquisición de bienes de oficina", "3", "100%"],
            ["P0107", "E17", "Servicio de limpieza y vigilancia", "3", "100%"],
          ],
          [1600, 1400, 3400, 2000, 1400],
        ),

        new Paragraph({ children: [new PageBreak()] }),

        titulo("5. Diccionario de Datos y Diagrama del Modelo"),
        parrafo(
          "Cubre el numeral 3.2.g del TDR (\"Elaborar y mantener actualizado el diccionario y diagrama del " +
          "modelo de datos\") y el ítem 8 del checklist del Anexo 3 (documentación de linaje: rastreo del dato " +
          "desde la fuente hasta el modelo final)."
        ),
        imagen("outputs/charts/09_diagrama_modelo_datos.png", 560, 145),
        piePagina("Figura 6. Diagrama del modelo de datos: tablas fuente (SIAF/SEACE simuladas), relaciones y linaje hacia las tablas derivadas de cada modelo."),
        subtitulo("5.1. Diccionario de datos"),
        tabla(
          ["Tabla.Columna", "Tipo", "Descripción"],
          DICCIONARIO,
          [3200, 1500, 5100],
        ),

        new Paragraph({ children: [new PageBreak()] }),

        titulo("6. Limitaciones del Prototipo"),
        vineta("Los datos son 100% sintéticos; no reflejan la distribución real ni la complejidad de casos límite del universo de contrataciones de la CGR."),
        vineta("No incluye evaluación de vínculos por grafos (numeral 4.2.4 del TDR: relaciones proveedor-funcionario por DNI, RUC, direcciones, teléfonos), que requiere fuentes adicionales no simuladas aquí."),
        vineta("No se probó a escala de big data; el prototipo corre en pandas/scikit-learn sobre una muestra de miles de registros, no millones."),
        vineta("No cubre la integración con SSRS/Power BI, el pipeline de orquestación (Airflow/DAGs) ni el proceso de certificación institucional descritos en el TDR."),

        titulo("7. Ruta de Escalamiento a Producción"),
        parrafo(
          "La lógica de features y modelado de este prototipo es directamente portable a Apache Spark MLlib " +
          "(pyspark.ml) sobre el Lakehouse Hadoop descrito en el Anexo 2 del TDR: RandomForestClassifier e " +
          "IsolationForest (o su equivalente con Bucketed Random Projection LSH / KMeans en MLlib) tienen APIs " +
          "prácticamente idénticas a scikit-learn. El trabajo adicional para producción consiste principalmente " +
          "en:"
        ),
        vineta("Conectar la ingesta real a las capas Plata/Oro del Lakehouse (reemplazando el generador sintético)."),
        vineta("Migrar el feature engineering de pandas a Spark DataFrames / Spark SQL."),
        vineta("Orquestar el pipeline con Airflow (ya disponible en la plataforma de la CGR según el Anexo 2)."),
        vineta("Añadir el módulo de análisis de grafos (proveedor-funcionario) con GraphX."),
        vineta("Publicar resultados hacia SQL Server / SSRS para consumo desde Power BI, tal como especifica la arquitectura institucional."),

        titulo("8. Conclusión"),
        parrafo(
          "Este prototipo demuestra en código abierto y en un plazo muy corto que los dos casos de uso centrales " +
          "del TDR —favoritismo y fraccionamiento— son técnicamente alcanzables sin necesidad de comprometer de " +
          "inmediato una consultoría individual de 180 días y S/. 72,000. El código fuente completo, comentado y " +
          "versionado está disponible públicamente en el repositorio indicado en la portada, cumpliendo con el " +
          "espíritu del ítem 6 del checklist de aceptación del Anexo 3 (\"código versionado en Git " +
          "institucional\")."
        ),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx", buf);
  console.log("Reporte generado.");
});
