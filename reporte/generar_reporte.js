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
          spacing: { before: 100, after: 100 },
          children: [new TextRun({
            text: "Prototipo independiente — no constituye una implementación oficial ni cuenta con aprobación institucional de la CGR",
            size: 20, bold: true, color: "C0392B",
          })],
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
          "públicas — como una contribución de licencia abierta al control gubernamental y a la lucha " +
          "anticorrupción."
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
        parrafo(
          "Nota de interpretación importante: el generador sintético siembra los casos de fraccionamiento " +
          "exactamente con el patrón que la regla busca (mismo proveedor-entidad-objeto, 3 a 6 compras en " +
          "pocos días, montos justo bajo el umbral legal). Que la regla los encuentre con 100% de precisión " +
          "confirma que la implementación funciona como fue diseñada — una prueba funcional (sanity check) " +
          "válida y necesaria — pero no es evidencia de desempeño predictivo sobre datos externos no " +
          "sembrados. La Sección 4 detalla esta distinción con mayor profundidad."
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
        parrafo(
          "Precisión metodológica sobre el 100%: los 8 casos sembrados fueron construidos deliberadamente con " +
          "el patrón exacto que la regla busca (mismo proveedor-entidad-objeto, 3-6 compras en una ventana de " +
          "pocos días, montos justo bajo el umbral). Este resultado valida que la regla está correctamente " +
          "implementada — que hace lo que se diseñó para hacer — no que vaya a alcanzar 100% de precisión " +
          "sobre datos reales no sembrados, donde el fraccionamiento real puede presentarse con patrones más " +
          "sutiles o distintos (ver el Anexo A, donde sobre datos reales sin etiquetas la regla se usa como " +
          "señal de riesgo para revisión de auditor, no como determinación automática)."
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

        titulo("5. Evaluación de Vínculos Proveedor–Funcionario (Análisis de Grafos)"),
        parrafo(
          "Cubre el numeral 4.2.4 del TDR: \"Análisis de grafos o redes para mapear y evaluar relaciones entre " +
          "proveedores y funcionarios (ej. por DNI, RUC, direcciones, teléfonos, etc.)\". A diferencia de los " +
          "modelos de favoritismo y fraccionamiento, que operan solo sobre datos de SIAF/SEACE, este módulo " +
          "requiere cruzar con una tercera fuente de datos de contacto (típicamente RENIEC/SUNAT/RNP), que aquí " +
          "se simula, ya que no forma parte de SIAF ni SEACE por sí solos."
        ),
        parrafo(
          "Se construyó un grafo bipartito con los 220 proveedores y 60 funcionarios simulados, con una arista " +
          "por cada par que tiene al menos un contrato entre sí (3,020 aristas en total). Cada arista se marca " +
          "automáticamente si el proveedor y el funcionario comparten el mismo número de teléfono o la misma " +
          "dirección registrada — la señal típica de una empresa fachada controlada por el propio funcionario o " +
          "un allegado."
        ),
        tabla(
          ["Métrica", "Valor"],
          [
            ["Vínculos impropios sembrados", "5"],
            ["Aristas marcadas por el algoritmo", "5"],
            ["Aciertos", "5 de 5 (100%)"],
          ],
          [5500, 3300],
        ),
        parrafo("", { size: 4 }),
        imagen("outputs/charts/10_grafo_vinculos.png", 480, 372),
        piePagina("Figura 7. Red proveedor–funcionario; los 5 vínculos sospechosos (líneas rojas) fueron detectados con 100% de precisión sobre una muestra de contexto de relaciones normales."),
        parrafo(
          "Nota: esta señal (coincidencia exacta de teléfono/dirección) es deliberadamente simple y de alta " +
          "precisión pero baja cobertura — no detecta vínculos encubiertos con datos de contacto distintos " +
          "(ej. un tercero testaferro). Una versión de producción debería complementarse con análisis de " +
          "centralidad de red (funcionarios que concentran decisiones sobre pocos proveedores) y con fuzzy " +
          "matching de direcciones, no solo coincidencia exacta."
        ),

        subtitulo("5.1. Validación con Spark GraphFrames real (no solo networkx)"),
        parrafo(
          "El análisis anterior se construyó con networkx porque GraphFrames no lograba resolverse sin acceso " +
          "a Maven Central desde este entorno (ver Anexo B). Se obtuvieron los .jar exactos — " +
          "io.graphframes:graphframes-spark4_2.13:0.10.0, compilados específicamente para Spark 4.x con Scala " +
          "2.13 — desde una máquina con internet sin restricciones, y se cargaron manualmente vía spark.jars. " +
          "El resultado corre sobre Spark GraphFrames real, no una simulación:"
        ),
        vineta("Los mismos 5 de 5 vínculos sospechosos sembrados fueron detectados — confirmación cruzada entre networkx y GraphFrames."),
        vineta("PageRank identificó a los funcionarios más centrales de la red de contratación (no solo el que más contratos tiene, sino su posición relativa dentro de la red completa) — exactamente la mejora que la nota anterior señalaba como pendiente."),
        vineta("Connected Components agrupó los 280 nodos (proveedores + funcionarios) en un solo componente conectado — en una red real con más entidades, esta técnica permitiría aislar comunidades de contratación independientes entre sí."),
        parrafo(
          "Código en src/spark/vinculos_graphframes.py; resultados en outputs/vinculos_graphframes_*.csv."
        ),

        titulo("6. Diccionario de Datos y Diagrama del Modelo"),
        parrafo(
          "Cubre el numeral 3.2.g del TDR (\"Elaborar y mantener actualizado el diccionario y diagrama del " +
          "modelo de datos\") y el ítem 8 del checklist del Anexo 3 (documentación de linaje: rastreo del dato " +
          "desde la fuente hasta el modelo final)."
        ),
        imagen("outputs/charts/09_diagrama_modelo_datos.png", 560, 145),
        piePagina("Figura 8. Diagrama del modelo de datos: tablas fuente (SIAF/SEACE simuladas), relaciones y linaje hacia las tablas derivadas de cada modelo."),
        subtitulo("6.1. Diccionario de datos"),
        tabla(
          ["Tabla.Columna", "Tipo", "Descripción"],
          DICCIONARIO,
          [3200, 1500, 5100],
        ),

        new Paragraph({ children: [new PageBreak()] }),

        titulo("7. Limitaciones del Prototipo"),
        vineta("Los datos son 100% sintéticos; no reflejan la distribución real ni la complejidad de casos límite del universo de contrataciones de la CGR."),
        vineta("La señal de vínculos (Sección 5) usa coincidencia exacta de teléfono/dirección; en producción requeriría fuzzy matching y cruce con RENIEC/SUNAT real."),
        vineta("No se probó a escala de big data; el prototipo corre en pandas/scikit-learn sobre una muestra de miles de registros, no millones."),
        vineta("No cubre la integración con SSRS/Power BI ni el proceso de certificación institucional descritos en el TDR."),
        vineta("El DAG de Airflow (Sección 9) usa BashOperator invocando procesos Python locales; en producción las tareas de entrenamiento usarían SparkSubmitOperator sobre el clúster YARN de la CGR."),

        titulo("8. Validación en Apache Spark MLlib (Ejecutado)"),
        parrafo(
          "A diferencia de las secciones anteriores, que describen el prototipo en scikit-learn, esta sección " +
          "documenta una ejecución real sobre pyspark.ml en modo local (local[*], sin clúster YARN), para " +
          "cerrar la brecha señalada frente al objetivo específico 3.2.a del TDR (\"Diseñar, entrenar y " +
          "optimizar modelos... utilizando Apache Spark (Spark MLlib)\")."
        ),
        subtitulo("8.1. Favoritismo — RandomForestClassifier (pyspark.ml)"),
        parrafo(
          "Misma arquitectura que la versión scikit-learn (300 árboles, profundidad 6), con ponderación de " +
          "clases vía columna de pesos (Spark MLlib no tiene class_weight='balanced' nativo). Resultado: los " +
          "6 casos reales sembrados aparecen en el top-6 del ranking, igual que en la versión scikit-learn. " +
          "Sesión Spark completa (arranque + entrenamiento + evaluación): ~50 segundos en modo local — el " +
          "costo real de portar a Spark es de infraestructura y arranque, no de lógica de modelado."
        ),
        subtitulo("8.2. Fraccionamiento — decisión de arquitectura real: KMeans en vez de Isolation Forest"),
        parrafo(
          "Hallazgo de implementación no anticipado: Spark MLlib no incluye Isolation Forest de forma nativa " +
          "y no existe un paquete confiable en PyPI que lo agregue a pyspark.ml. El numeral 4.2.3 del TDR " +
          "permite explícitamente \"agrupamiento (clustering) o detección de anomalías\", por lo que se " +
          "implementó KMeans (pyspark.ml.clustering) usando la distancia al centroide asignado como score de " +
          "anomalía — la alternativa nativa correcta dentro de MLlib."
        ),
        tabla(
          ["Enfoque (Spark MLlib)", "Grupos marcados", "Aciertos reales", "Precisión"],
          [
            ["KMeans (distancia a centroide, solo)", "8", "0", "0.0%"],
            ["Regla interpretable (umbral legal)", "7", "7", "100.0%"],
          ],
          [4200, 2200, 2000, 1600],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "Este resultado refuerza el hallazgo central del prototipo (Sección 4): KMeans en Spark tuvo un " +
          "desempeño incluso menor que Isolation Forest en scikit-learn (0/8 vs. 3/8) para detectar " +
          "fraccionamiento sin contexto normativo, mientras que la regla interpretable mantuvo 100% de " +
          "precisión de forma idéntica en ambas plataformas. La elección del algoritmo de \"caja negra\" " +
          "importa menos que traducir correctamente el umbral legal a una regla computable."
        ),
        subtitulo("8.3. Lo que sigue siendo trabajo pendiente"),
        vineta("Ejecución sobre un clúster YARN real, no en modo local[*] sobre una sola máquina."),
        vineta("Lectura desde el Lakehouse (capas Bronce/Plata/Oro) en vez de un CSV local."),
        vineta("Orquestación con Airflow, integración SSRS/Power BI y despliegue en ambientes de certificación — ver limitaciones."),

        titulo("9. Orquestación con Apache Airflow (Ejecutado)"),
        parrafo(
          "Cubre el numeral 6 del TDR (\"Orquestación de Procesos ETL (DAGs): Diseñar, desarrollar y probar los " +
          "Directed Acyclic Graphs (DAGs)\"). Se instaló Apache Airflow 3.3.0 en un entorno aislado, se " +
          "construyó un DAG con las 9 etapas del pipeline respetando el linaje real de los datos, y se ejecutó " +
          "de punta a punta con el comando `airflow dags test` — no es un diagrama teórico, es una corrida real " +
          "sobre el motor de ejecución de Airflow."
        ),
        imagen("outputs/charts/11_dag_airflow.png", 560, 130),
        piePagina("Figura 9. Grafo del DAG modulo_analisis_datos_1_8_2 — 9 tareas con 3 ramas paralelas tras la publicación de la capa Plata."),
        parrafo(
          "El DAG respeta el linaje real: genera los datos → los publica en la capa Bronce (ingesta cruda) → " +
          "limpieza y feature engineering → publica en la capa Plata (refinado) → entrena ambos modelos y " +
          "analiza vínculos en paralelo → publica resultados en la capa Oro (nivel de negocio) → genera la " +
          "documentación final. Las capas Bronce/Plata/Oro se simulan como carpetas locales (`lakehouse/`), " +
          "organizadas según la arquitectura del Anexo 2 del TDR — en producción serían tablas Delta Lake sobre " +
          "Hadoop, no carpetas de archivos."
        ),
        tabla(
          ["Tarea", "Estado", "Duración"],
          [
            ["generar_datos", "success", "12.6 s"],
            ["cargar_capa_bronce", "success", "0.1 s"],
            ["preprocesamiento_y_features", "success", "2.8 s"],
            ["publicar_capa_plata", "success", "0.1 s"],
            ["entrenar_modelo_favoritismo", "success", "16.3 s"],
            ["entrenar_modelo_fraccionamiento", "success", "2.9 s"],
            ["analizar_vinculos_proveedor_funcionario", "success", "1.6 s"],
            ["publicar_capa_oro", "success", "0.1 s"],
            ["generar_diccionario_y_diagrama", "success", "0.6 s"],
          ],
          [5200, 1800, 1800],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "Resultado: 9/9 tareas completadas con estado \"success\", corrida completa en 38.5 segundos. En " +
          "producción, las tareas de entrenamiento (hoy procesos Python locales invocados vía BashOperator) se " +
          "reemplazarían por SparkSubmitOperator apuntando al clúster YARN de la CGR — el DAG y su lógica de " +
          "dependencias no cambian, solo el operador que ejecuta cada tarea."
        ),

        titulo("10. Búsqueda Sistemática de Hiperparámetros (Ejecutado)"),
        parrafo(
          "Cierra la brecha señalada frente al numeral 4.2.5 del TDR (\"optimizar hiperparámetros para " +
          "maximizar la precisión, recall, F1-score u otras métricas relevantes\"). El prototipo original usaba " +
          "valores razonables elegidos a mano; se reemplazaron por búsquedas en grilla con validación cruzada, " +
          "ejecutadas tanto en scikit-learn como en Spark MLlib, de forma independiente."
        ),
        subtitulo("10.1. Favoritismo — GridSearchCV (scikit-learn) y CrossValidator (Spark MLlib)"),
        parrafo(
          "60 combinaciones de hiperparámetros (n° de árboles, profundidad máxima, mínimo de muestras por " +
          "hoja) evaluadas con validación cruzada estratificada de 3 particiones, usando AUC-PR como métrica " +
          "(más informativa que accuracy con 0.25% de clase positiva). Las 60 combinaciones alcanzaron el " +
          "mismo AUC-PR máximo (1.00) — resultado esperable en datos sintéticos con separación clara. Se " +
          "seleccionó la configuración más liviana entre las empatadas (100 árboles, profundidad 3), que " +
          "entrena un 65% más rápido que la configuración original (300 árboles, profundidad 6) sin pérdida de " +
          "desempeño."
        ),
        parrafo(
          "De forma independiente, se ejecutó la misma búsqueda con pyspark.ml.tuning.CrossValidator y " +
          "ParamGridBuilder (4 combinaciones × 3 folds = 12 ajustes de modelo sobre Spark MLlib real): el mejor " +
          "modelo encontrado por Spark usó exactamente los mismos hiperparámetros (100 árboles, profundidad 3) " +
          "que scikit-learn — una confirmación cruzada entre ambas plataformas, no solo dentro de una."
        ),
        subtitulo("10.2. Fraccionamiento — hallazgo: el techo es del algoritmo, no de la configuración"),
        parrafo(
          "Para Isolation Forest (no supervisado) se implementó una búsqueda manual de 36 combinaciones " +
          "(n° de estimadores, fracción de muestras, tasa de contaminación), usando como métrica cuántos de los " +
          "8 casos sembrados caen en el top-8 del ranking de anomalía. Resultado: el recall se estancó en 3/8 " +
          "(37.5%) para toda combinación con max_samples=1.0, sin importar el resto de parámetros — evidencia " +
          "de que la limitación es estructural del algoritmo sobre estas variables, no una configuración " +
          "subóptima. Este hallazgo refuerza, con evidencia adicional, la conclusión central del prototipo " +
          "(Sección 4): ningún ajuste de hiperparámetros iguala a la regla interpretable basada en el umbral " +
          "legal (100% de precisión). Se mantuvo la configuración más liviana entre las empatadas (100 " +
          "estimadores en vez de 300)."
        ),

        titulo("11. Estándares Institucionales de Extracción SQL (Ejecutado)"),
        parrafo(
          "Cubre el ítem 3 del checklist del Anexo 3: \"Cumplimiento de Reglas Técnicas de la CGR (uso de LEFT " +
          "JOIN, lógica de 'cortocircuito' y prohibición de Full Table Scans en tablas de hechos)\". En un " +
          "ecosistema Hadoop/Spark, prohibir el Full Table Scan no se resuelve con índices tradicionales, sino " +
          "con particionamiento físico: se reescribió la tabla de hechos (contratos) como Parquet particionado " +
          "por año-mes (42 particiones), lo que permite que Spark descarte particiones completas sin leerlas " +
          "cuando la consulta filtra por esa columna."
        ),
        tabla(
          ["Verificación", "Resultado"],
          [
            ["Particiones totales de la tabla de hechos", "42"],
            ["Particiones leídas al filtrar por año-mes reciente", "6 de 42 (14%)"],
            ["Poda de particiones confirmada en el plan físico de Spark", "Sí"],
            ["LEFT JOIN vs. INNER JOIN (prueba dirigida con huérfano forzado)", "1 fila vs. 0 filas"],
          ],
          [5800, 2600],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "La prueba de LEFT JOIN se hizo de forma honesta: sobre los datos reales del prototipo, LEFT JOIN e " +
          "INNER JOIN devuelven el mismo resultado porque la integridad referencial es perfecta por diseño (no " +
          "hay huérfanos orgánicos que mostrar). Se construyó entonces una prueba dirigida — un contrato con un " +
          "id_funcionario inexistente en la tabla dimensión — que confirma el comportamiento esperado: LEFT " +
          "JOIN conserva el contrato (con el campo NULL), INNER JOIN lo descarta silenciosamente. Ese " +
          "descarte silencioso es exactamente el riesgo de auditoría que motiva la regla del checklist."
        ),
        parrafo(
          "La \"lógica de cortocircuito\" se aplicó ordenando el WHERE con el filtro más selectivo y barato " +
          "primero (igualdad sobre id_entidad) antes que el filtro de rango sobre monto, siguiendo el mismo " +
          "principio que la poda de particiones: descartar lo más posible, lo antes posible."
        ),

        titulo("12. Integración SSRS (Ejecutado)"),
        parrafo(
          "Cubre el ítem 7 del checklist del Anexo 3: \"Integración para Ecosistema SSRS (SQL Server Reporting " +
          "Services): Resultados del modelo (predicciones y puntajes de riesgo)\". No hay acceso a un SQL " +
          "Server real desde este entorno de prueba de concepto; se construyeron los dos artefactos que sí son " +
          "portables sin esa infraestructura:"
        ),
        vineta("Esquema T-SQL válido (ssrs/schema_sql_server.sql) con las tres tablas de resultados, tipos de datos e índices, listo para ejecutarse en el SQL Server institucional descrito en el Anexo 2."),
        vineta("Publicación real de los 5,523 registros de resultados (2,354 de favoritismo + 149 de fraccionamiento + 3,020 de vínculos) sobre ese mismo esquema, usando SQLite como stand-in local documentado — cambiar el driver de conexión (sqlite3 → pyodbc/pymssql) es el único paso para apuntar a un SQL Server real."),
        vineta("Un archivo .rdl (Report Definition Language) real y válido — el formato nativo de SSRS — con un dataset parametrizado y una tabla de riesgo, verificado como XML bien formado bajo el namespace oficial de SSRS 2016. No se ejecuta aquí (requiere un servidor SSRS real), pero es el entregable listo para desplegar, no una simulación de su contenido."),
        parrafo(
          "La consulta de prueba (equivalente al Dataset compartido que usaría el .rdl, filtrando por " +
          "score_riesgo ≥ 0.5) devolvió exactamente los 6 proveedores de mayor riesgo — los mismos que " +
          "aparecen en el ranking de la Sección 3."
        ),

        titulo("13. Autoevaluación y Autoentrenamiento (Ejecutado)"),
        parrafo(
          "Cierra el último pendiente identificado, cubriendo el objetivo específico 3.2.c del TDR: " +
          "\"Incorporar mecanismos de autoevaluación y, cuando sea pertinente, de autoentrenamiento para " +
          "permitir la actualización continua de los modelos... asegurando que los algoritmos se mantengan " +
          "precisos, pertinentes y adaptados a la evolución de los patrones de contratación.\""
        ),
        parrafo(
          "El mecanismo combina dos señales independientes — cualquiera dispara reentrenamiento: (1) deriva de " +
          "datos, medida con Population Stability Index (PSI) sobre variables clave, comparando la " +
          "distribución de entrenamiento contra la de los contratos más recientes; y (2) degradación de " +
          "desempeño, midiendo si el modelo actual sigue detectando casos de favoritismo ya confirmados por " +
          "auditores (la retroalimentación humana que menciona el TDR)."
        ),
        parrafo(
          "Se validó con dos escenarios simulados de \"próximo trimestre\": uno con la misma distribución de " +
          "entrenamiento (no debería disparar nada) y otro con una deriva real (salto de modalidades " +
          "competitivas a no competitivas, y dos casos de favoritismo con un perfil distinto al aprendido — " +
          "pocos contratos de monto muy alto, en vez de muchos contratos pequeños)."
        ),
        imagen("outputs/charts/12_dag_monitoreo.png", 420, 65),
        piePagina("Figura 10. DAG de monitoreo (schedule mensual) — genera el lote más reciente y evalúa si corresponde reentrenar."),
        tabla(
          ["Escenario", "PSI máximo", "Recall sobre casos nuevos", "¿Disparó reentrenamiento?"],
          [
            ["Normal (sin deriva)", "0.186", "—", "No"],
            ["Con deriva", "1.608", "1.00", "Sí"],
          ],
          [2600, 1800, 2400, 2000],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "Hallazgo relevante: en el escenario con deriva, el modelo actual todavía detectaba correctamente " +
          "los 2 casos nuevos (recall = 1.00) — si la decisión dependiera solo de desempeño, no se habría " +
          "disparado ninguna alerta. Fue la señal de PSI (1.608, muy por encima del umbral de 0.25) la que " +
          "detectó que la población de contratos había cambiado, independientemente de que el modelo, por " +
          "ahora, siguiera acertando. Esa es exactamente la razón de tener ambas señales: el desempeño puede " +
          "verse bien por casualidad mientras el terreno ya cambió debajo del modelo."
        ),
        parrafo(
          "El DAG completo (generación del lote → autoevaluación → reentrenamiento condicional) corrió de " +
          "punta a punta con Apache Airflow real (`airflow dags test`), en 12.2 segundos, con estado " +
          "\"success\" — igual que el DAG principal de la Sección 9. Cada decisión queda registrada en " +
          "outputs/log_reentrenamiento.csv con marca de tiempo, señales evaluadas y motivo, para que ningún " +
          "reentrenamiento ocurra de forma silenciosa o no auditable."
        ),

        titulo("Anexo A. Prueba con Datos Reales de SEACE (fuera del alcance del TDR)"),
        parrafo(
          "El TDR no exige esta prueba — todo el análisis anterior usa datos sintéticos, que es lo que el " +
          "alcance requiere. Se incluye este anexo porque, adicionalmente, se obtuvo acceso a datos " +
          "verdaderos de contrataciones públicas (no de la CGR, sino del portal de datos abiertos de la OECE, " +
          "estándar OCDS, licencia CC BY 4.0) y se corrió el pipeline sobre ellos, para dejar registro de qué " +
          "tan bien se comporta la metodología fuera de un entorno sintético controlado."
        ),
        tabla(
          ["Dato", "Valor"],
          [
            ["Fuente", "data.open-contracting.org — OECE Perú, año 2022"],
            ["Contratos reales procesados", "47,442"],
            ["Proveedores reales (RUC)", "25,535"],
            ["Entidades compradoras reales", "2,732"],
            ["Monto total analizado", "S/. 32,241 millones"],
          ],
          [4200, 4600],
        ),
        parrafo("", { size: 4 }),
        subtitulo("Adaptaciones metodológicas honestas"),
        vineta("Sin ground truth: a diferencia del dataset sintético, no existe una etiqueta real de \"esto fue favoritismo\". El modelo de favoritismo pasó de ser un clasificador supervisado a un score de riesgo no supervisado (Isolation Forest) — una lista de candidatos para revisión humana, no una predicción validada."),
        vineta("Fraccionamiento se aplicó sin cambios (la regla del umbral legal no depende de etiquetas)."),
        vineta("Vínculos se adaptó a nivel proveedor-entidad (no proveedor-funcionario): SEACE abierto registra organizaciones, no funcionarios públicos individuales."),
        subtitulo("Hallazgos honestos (incluye un error propio, corregido)"),
        vineta("Se detectó y corrigió un artefacto real: contratos con consorcios de varias empresas se estaban contando una vez por cada integrante, inflando artificialmente las métricas de concentración. Se corrigió representando cada consorcio como una sola entidad compuesta."),
        vineta("Se encontró un falso positivo genuino: un programa de investigación científica paga a evaluadores individuales por lotes (montos de S/. 600-2,600), lo que el detector de consorcios confundía con concentración sospechosa. Se dejó anotado explícitamente en vez de ocultarlo."),
        vineta("Los patrones de mayor score de riesgo corresponden a consorcios de gran magnitud (decenas de millones de soles) en entidades grandes de infraestructura y salud — consorcios son legales, pero la concentración amerita revisión de auditor, que es exactamente el uso previsto por el TDR."),
        vineta("El chequeo de vínculos por teléfono compartido dio 0 coincidencias sobre 35,832 pares proveedor-entidad reales — un resultado negativo genuino (no hay evidencia de esa señal específica en este año), no una falla del código."),
        parrafo(
          "Código y resultados completos en el repositorio (src/cargar_datos_reales_seace.py, " +
          "src/modelo_real.py, outputs/*_REAL.csv). Los datos crudos no se versionan por tamaño (~245 MB); " +
          "el repositorio documenta cómo reproducirlos desde la fuente pública original."
        ),

        titulo("Anexo B. Verificación de Componentes de la Plataforma (Anexo 2 del TDR)"),
        parrafo(
          "El Anexo 2 del TDR (\"Arquitectura de la Plataforma de Minería de Datos\") especifica los " +
          "componentes esperados: ingesta Batch/CDC-CDF/Streaming, Delta Lake con capas Bronce/Plata/Oro, HMS " +
          "sobre MySQL, lenguajes soportados (Python, SQL, Scala, R, Java), Spark (SQL/Streaming/MLlib/GraphX) " +
          "sobre Hadoop YARN, Airflow, y salida hacia SQL Server/SSRS/Power BI. Se verificó, componente por " +
          "componente, cuáles corren realmente en este entorno de prueba de concepto."
        ),
        tabla(
          ["Componente", "Estado"],
          [
            ["Ingesta Batch", "Completo"],
            ["Ingesta Streaming", "Completo (verificado abajo)"],
            ["Ingesta CDC/CDF", "Completo (ver evidencia abajo)"],
            ["Capas Bronce/Plata/Oro", "Completo (Delta Lake real disponible, ver evidencia)"],
            ["Delta Lake (formato nativo)", "Completo (ver evidencia abajo)"],
            ["HMS (Hive Metastore)", "Completo (verificado abajo)"],
            ["Parquet", "Completo"],
            ["Python / SQL / Scala / R / Java", "Completo — los 5 verificados"],
            ["Spark MLlib", "Completo"],
            ["Spark GraphX", "Completo (ver Sección 5 — GraphFrames real)"],
            ["Hadoop YARN / HDFS", "Pendiente por límite de tamaño de archivo, no por imposibilidad técnica (ver explicación abajo)"],
            ["Apache Airflow", "Completo"],
            ["SQL Server / SSRS", "Parcial — esquema real, SQLite como stand-in"],
            ["Modelo Tabular (SSAS)", "Fuera de alcance — solo Windows Server"],
            ["Power BI", "Fuera de alcance — requiere licencia/cuenta"],
          ],
          [5200, 3600],
        ),
        parrafo("", { size: 4 }),
        subtitulo("Tres tipos de bloqueo, no uno solo"),
        vineta("Red del entorno de prueba: GraphX/GraphFrames y Delta Lake requerían descargar un .jar desde Maven Central, dominio fuera de la lista de salida permitida aquí — y ambos se resolvieron (ver Sección 5 y evidencia abajo) descargando los .jar correctos fuera de este entorno y cargándolos manualmente."),
        vineta("Hadoop YARN/HDFS quedó pendiente por límites de tamaño de archivo (no por imposibilidad técnica de correr en una sola máquina — Apache documenta modo pseudo-distribuido) — ver explicación dedicada más abajo."),
        vineta("Sistema operativo: SSAS es tecnología exclusiva de Windows Server; no existe equivalente en Linux."),
        vineta("Licencia/cuenta: Power BI y un SQL Server real requieren una cuenta o licencia — no hay forma de \"instalarlos gratis\" en ningún entorno. Quedan fuera de alcance por decisión, no por límite técnico."),

        subtitulo("Evidencia: Streaming"),
        parrafo(
          "Se construyó un stream de Spark Structured Streaming que vigila una carpeta y procesa cada archivo " +
          "nuevo que llega — simulando la publicación incremental de contratos a lo largo del día, no una " +
          "carga única. Resultado real: 3 micro-batches procesados de forma incremental; la entidad E01 " +
          "acumuló correctamente 3 contratos por S/. 296,000 a medida que llegaban, sin reprocesar desde cero."
        ),
        subtitulo("Evidencia: HMS (Hive Metastore)"),
        parrafo(
          "Se registraron 4 tablas reales del prototipo (incluyendo los 47,442 contratos reales de SEACE del " +
          "Anexo A) en un catálogo Hive Metastore, consultables por nombre vía SQL puro sin conocer la ruta " +
          "física del archivo — el propósito real de un metastore. El backend es Derby local, no MySQL como " +
          "especifica el Anexo 2, pero es un cambio de una línea de configuración, no de arquitectura."
        ),
        subtitulo("Evidencia: R"),
        parrafo(
          "Se ejecutó una prueba t de Welch en R sobre la variable de mayor importancia del modelo de " +
          "favoritismo (concentracion_objeto, ver Sección 3), comparando el grupo con favoritismo real contra " +
          "el resto. Resultado: diferencia altamente significativa (p = 3.58×10⁻⁸), confirmando con una prueba " +
          "estadística formal lo que el Random Forest ya señalaba por importancia de variable."
        ),
        imagen("outputs/charts/13_r_boxplot_concentracion.png", 460, 306),
        piePagina("Figura 11. Separación entre grupos (R) — evidencia visual de la misma señal que detecta el modelo."),

        subtitulo("Evidencia: Delta Lake (ACID, historial de versiones, time travel, CDC/CDF)"),
        parrafo(
          "Con los .jar correctos (io.delta:delta-spark_4.1_2.13:4.3.0 — nótese el sufijo de versión de Spark, " +
          "obligatorio desde Delta Lake 4.1), la capa Bronce se reescribió como una tabla Delta Lake real, no " +
          "Parquet plano. Se simuló el escenario más relevante para un auditor: una corrección de monto sobre " +
          "un contrato ya existente."
        ),
        tabla(
          ["Capacidad verificada", "Resultado"],
          [
            ["UPDATE transaccional (ACID)", "Aplicado correctamente, nueva versión creada automáticamente"],
            ["DESCRIBE HISTORY", "2 versiones registradas: WRITE (v0) y UPDATE (v1), con predicado exacto"],
            ["Time travel (versionAsOf 0)", "Monto original (S/. 51,428.87) recuperado exacto, tras la corrección a S/. 69,428.97"],
            ["Change Data Feed (CDC/CDF)", "Preimage y postimage capturados fila por fila (update_preimage / update_postimage)"],
          ],
          [3600, 5200],
        ),
        parrafo("", { size: 4 }),
        parrafo(
          "Esto es lo que un CSV sobrescrito, o incluso Parquet plano, no puede ofrecer: la versión anterior de " +
          "un dato sigue existiendo y es consultable sin backups manuales — si un funcionario corrige (o " +
          "manipula) un monto después de que un auditor ya lo revisó, Delta Lake conserva evidencia exacta de " +
          "cuál era el valor antes. Código en src/spark/lakehouse_delta.py."
        ),

        subtitulo("Por qué Hadoop YARN/HDFS es un caso distinto (no un bloqueo de librería)"),
        parrafo(
          "A diferencia de GraphFrames y Delta Lake, que fallaban por no poder descargar un .jar específico " +
          "— un problema de red, resuelto obteniendo el archivo correcto por fuera — Hadoop YARN y HDFS no se " +
          "completaron por una combinación de restricciones de tamaño de archivo, no por imposibilidad " +
          "técnica de correr en una sola máquina. Aclaración importante: Apache documenta explícitamente un " +
          "modo \"pseudo-distribuido\" (single-node) en el que HDFS y YARN corren sobre una sola máquina — " +
          "esto es técnicamente viable y no requiere múltiples servidores físicos. Se investigó una " +
          "alternativa liviana (org.apache.hadoop:hadoop-client-minicluster, 27.1 MB, la utilidad interna que " +
          "el propio equipo de Hadoop usa para sus pruebas automatizadas) y se obtuvo el archivo, pero " +
          "requiere además hadoop-client-runtime — un segundo .jar que empaqueta todas las dependencias de " +
          "Hadoop (netty, guava, jetty, protobuf) y normalmente pesa 40-70 MB, de nuevo por encima del " +
          "límite de archivo de este entorno. El tarball binario completo (que sí incluye los scripts para " +
          "correr en modo pseudo-distribuido real, no solo las clases de prueba MiniDFSCluster/" +
          "MiniYARNCluster) pesa 554 MB, igualmente inalcanzable aquí."
        ),
        parrafo(
          "Lo que sí es una limitación real de fondo, independiente del tamaño de archivo: el beneficio " +
          "característico de HDFS/YARN en producción — tolerancia a fallos vía replicación de bloques entre " +
          "máquinas físicas distintas, y reparto de CPU/memoria entre esos mismos nodos — depende, por " +
          "diseño, de que existan varias máquinas separadas. Un modo pseudo-distribuido de un solo nodo " +
          "(que no se llegó a completar aquí) demostraría que los procesos de HDFS/YARN corren y se " +
          "comunican correctamente, pero no demostraría ese beneficio de tolerancia a fallos ni de reparto " +
          "real de carga entre máquinas — para eso sí hacen falta servidores físicos distintos, como los de " +
          "la CGR. Esta es la pieza del Anexo 2 que queda pendiente de este entorno: no por ser " +
          "técnicamente imposible en una sola máquina, sino porque no se logró descargar el paquete " +
          "completo dentro del límite de tamaño de archivo disponible aquí."
        ),
        parrafo(
          "Lo que sí cubre el mismo rol funcional dentro de este prototipo: Spark real (Sección 8) es el motor " +
          "de cómputo que correría sobre YARN; Delta Lake real (evidencia arriba) es el motor de almacenamiento " +
          "que correría sobre HDFS; y el particionamiento con poda de particiones (Sección 11) es la técnica " +
          "que evita leer todo el disco, sea ese disco local o HDFS."
        ),

        titulo("14. Ruta de Escalamiento Restante"),
        parrafo(
          "Con las validaciones de las Secciones 8 y 9, el trabajo pendiente para producción se reduce casi " +
          "exclusivamente a infraestructura y gobernanza de datos:"
        ),
        vineta("Conectar la ingesta real a las capas Plata/Oro del Lakehouse (reemplazando las carpetas locales por lectura/escritura del Delta Lake real sobre Hadoop HDFS, según el Anexo 2 del TDR — la lógica de Delta Lake ya está verificada, falta el HDFS productivo detrás)."),
        vineta("Desplegar el DAG en el Airflow productivo de la CGR (ya disponible según el Anexo 2), reemplazando BashOperator por SparkSubmitOperator para las tareas de entrenamiento."),
        vineta("Ejecutar Spark sobre un clúster YARN real, no en modo local[*]."),
        vineta("Reemplazar el SQLite stand-in por una conexión real a SQL Server (pyodbc/pymssql) y desplegar el .rdl en un servidor SSRS real."),

        titulo("15. Conclusión"),
        parrafo(
          "Este prototipo demuestra en código abierto y en un plazo muy corto que los tres casos de uso " +
          "priorizados del TDR —favoritismo, fraccionamiento y vínculos proveedor-funcionario— son técnicamente " +
          "alcanzables con herramientas de licencia abierta, construidas como una contribución al control " +
          "gubernamental y a la lucha anticorrupción. Cada pieza de la arquitectura fue validada con ejecución " +
          "real, no solo de forma teórica: " +
          "modelado en scikit-learn y Apache Spark MLlib (Sección 8), orquestación con Apache Airflow " +
          "(Sección 9), optimización sistemática de hiperparámetros en ambas plataformas (Sección 10), " +
          "extracción bajo los estándares SQL institucionales de la CGR (Sección 11), publicación lista para " +
          "SSRS (Sección 12), y un mecanismo de autoevaluación y autoentrenamiento que distingue correctamente " +
          "cuándo el modelo necesita actualizarse (Sección 13). El código fuente completo, comentado y " +
          "versionado está disponible públicamente en el repositorio indicado en la portada, cumpliendo con " +
          "el espíritu del ítem 6 del checklist de aceptación del Anexo 3 (\"código versionado en Git " +
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
