const {
  Document, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, ImageRun,
  Header, Footer, PageNumber, VerticalAlign,
} = require("docx");
const fs = require("fs");

const NEGRO = "000000";
const GRIS = "666666";
const GRIS_CLARO = "E7E6E6";
const A4 = { width: 11906, height: 16838 };
const MARGEN = 1440; // 1 pulgada, apto para impresión a doble cara.
const FUENTE = "Arial";
const TAMANO = 22; // 11 pt: docx usa half-points.
const LINEA_SIMPLE = 240;

const CONSULTORIA =
  'CONTRATACIÓN DE UN CONSULTOR CIENTÍFICO DE DATOS PARA EL DESARROLLO DEL "MÓDULO DE ANÁLISIS DE DATOS PARA DAR SOPORTE A LOS AUDITORES DURANTE LA EJECUCIÓN DE LOS SERVICIOS DE CONTROL" EN EL SISTEMA INTEGRADO DE CONTROL DEL PROYECTO INTERNO 1.8.2';
const CONSULTOR = "Noé Calle";
const REPO_URL = "https://github.com/NoeCalle/cgr-analisis-datos";
const NATURALEZA =
  "PROTOTIPO INDEPENDIENTE - no constituye una implementación oficial ni cuenta con aprobación institucional de la CGR.";

const ACRONIMOS_BASE = [
  ["AUC-PR", "Área bajo la curva Precision-Recall"],
  ["AUC-ROC", "Área bajo la curva Receiver Operating Characteristic"],
  ["CGR", "Contraloría General de la República"],
  ["CI", "Integración continua (Continuous Integration)"],
  ["CV", "Validación cruzada (Cross-Validation)"],
  ["DAG", "Grafo acíclico dirigido (Directed Acyclic Graph)"],
  ["EDA", "Análisis exploratorio de datos"],
  ["ETL", "Extracción, transformación y carga"],
  ["HDFS", "Hadoop Distributed File System"],
  ["ML", "Machine Learning"],
  ["MLlib", "Biblioteca de Machine Learning de Apache Spark"],
  ["OCDS", "Open Contracting Data Standard"],
  ["OECE", "Organismo Especializado para las Contrataciones Públicas Eficientes"],
  ["PoC", "Prueba de concepto (Proof of Concept)"],
  ["PSI", "Population Stability Index"],
  ["SHAP", "SHapley Additive exPlanations"],
  ["SSRS", "SQL Server Reporting Services"],
  ["TDR", "Términos de Referencia"],
];

const GLOSARIO_BASE = [
  ["Benchmark sintético", "Conjunto de datos artificial con casos sembrados, usado para verificar el comportamiento del prototipo sin asumir desempeño productivo."],
  ["Feature engineering", "Creación o transformación de variables analíticas a partir de los datos de origen."],
  ["Ground truth", "Etiqueta de referencia usada para evaluar un modelo. En el PoC las etiquetas son sintéticas; el ground truth real requiere validación institucional."],
  ["Hard negative", "Caso negativo diseñado para parecerse a un positivo y evitar una separación artificialmente trivial."],
  ["Holdout", "Partición reservada que no participa en el ajuste de parámetros y se usa para una evaluación independiente."],
  ["Lakehouse", "Arquitectura que combina almacenamiento de datos a escala con capacidades de gestión y consulta analítica."],
  ["Señal de priorización", "Indicador para ordenar casos que merecen revisión humana; no constituye por sí mismo un hallazgo ni una determinación jurídica."],
];

const REFERENCIAS_BASE = [
  "Contraloría General de la República. Términos de Referencia de la consultoría del Proyecto Interno 1.8.2, mayo de 2026.",
  "Open Contracting Partnership. Open Contracting Data Standard (OCDS) y publicación de datos abiertos utilizada por el prototipo.",
  "Organismo Especializado para las Contrataciones Públicas Eficientes (OECE). Datos abiertos de contratación pública empleados en la validación independiente.",
  "Apache Software Foundation. Documentación de Apache Spark y Spark MLlib.",
  "scikit-learn developers. Documentación de scikit-learn para clasificación, validación y detección de anomalías.",
  "Lundberg, S. M. y Lee, S.-I. A Unified Approach to Interpreting Model Predictions. 2017.",
];

function run(text, opciones = {}) {
  return new TextRun({ text: String(text), font: FUENTE, size: TAMANO, color: NEGRO, ...opciones });
}

function espaciado({ before = 0, after = 0 } = {}) {
  return { before, after, line: LINEA_SIMPLE };
}

function titulo(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [run(text, { bold: true })],
    spacing: espaciado({ before: 240, after: 120 }),
  });
}

function subtitulo(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [run(text, { bold: true })],
    spacing: espaciado({ before: 180, after: 80 }),
  });
}

function parrafo(text, opciones = {}) {
  return new Paragraph({
    alignment: opciones.alignment || AlignmentType.JUSTIFIED,
    children: [run(text, opciones.run || {})],
    spacing: espaciado({ after: opciones.after === undefined ? 80 : opciones.after }),
    keepNext: Boolean(opciones.keepNext),
  });
}

function parrafoCentrado(text, opciones = {}) {
  return parrafo(text, { ...opciones, alignment: AlignmentType.CENTER });
}

function vineta(text) {
  return new Paragraph({
    children: [run(text)],
    bullet: { level: 0 },
    spacing: espaciado({ after: 50 }),
  });
}

function marcadorIndice() {
  return new Paragraph({
    children: [run("[[TOC]]")],
    spacing: espaciado({ after: 120 }),
  });
}

function listaIndice(tituloLista, items) {
  if (!items || !items.length) return [];
  return [
    titulo(tituloLista),
    ...items.map((item, i) => parrafo(`${i + 1}. ${item}`, { alignment: AlignmentType.LEFT, after: 35 })),
  ];
}

function celda(text, { header = false, width, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: GRIS_CLARO } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 55, bottom: 55, left: 80, right: 80 },
    children: [new Paragraph({
      alignment: align,
      children: [run(text, { bold: header })],
      spacing: espaciado(),
    })],
  });
}

function tabla(headers, rows, widths) {
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({
        tableHeader: true,
        cantSplit: true,
        children: headers.map((h, i) => celda(h, { header: true, width: widths[i] })),
      }),
      ...rows.map((r) => new TableRow({
        cantSplit: true,
        children: r.map((c, i) => celda(c, {
          width: widths[i],
          align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
        })),
      })),
    ],
  });
}

function leyendaTabla(numero, text) {
  return parrafoCentrado(`Tabla ${numero}. ${text}`, { run: { bold: true }, after: 45, keepNext: true });
}

function tablaConTitulo(numero, text, headers, rows, widths) {
  return [leyendaTabla(numero, text), tabla(headers, rows, widths)];
}

function imagen(path, width, height) {
  if (!fs.existsSync(path)) {
    return parrafoCentrado(`[Gráfico no disponible en la ejecución: ${path}]`, { run: { italics: true } });
  }
  return new Paragraph({
    children: [new ImageRun({
      type: "png",
      data: fs.readFileSync(path),
      transformation: { width, height },
    })],
    alignment: AlignmentType.CENTER,
    keepNext: true,
    // No fijar line-height aquí: una altura de línea de 12 pt recorta las
    // imágenes inline en LibreOffice. El cuerpo del texto conserva espacio simple.
    spacing: { after: 40 },
  });
}

function leyendaFigura(numero, text) {
  return parrafoCentrado(`Gráfico ${numero}. ${text}`, { run: { bold: true }, after: 35, keepNext: true });
}

function imagenConTitulo(numero, text, path, width, height, fuente = "Elaboración propia a partir de la evidencia reproducible del PoC.") {
  return [
    leyendaFigura(numero, text),
    imagen(path, width, height),
    parrafoCentrado(`Fuente: ${fuente}`, { run: { italics: true, color: GRIS }, after: 90 }),
  ];
}

function listaAcronimos(items = ACRONIMOS_BASE) {
  return [
    titulo("Lista de Abreviaturas y Acrónimos"),
    tabla(["Sigla", "Significado"], items, [1800, 7000]),
  ];
}

function glosario(items = GLOSARIO_BASE) {
  return [
    titulo("Glosario"),
    tabla(["Término", "Definición"], items, [2500, 6300]),
  ];
}

function referencias(items = REFERENCIAS_BASE) {
  return [
    titulo("Referencias Bibliográficas"),
    ...items.map((x) => vineta(x)),
  ];
}

function frontMatter({ tablas = [], graficos = [], acronimos = ACRONIMOS_BASE, terminos = GLOSARIO_BASE } = {}) {
  return [
    marcadorIndice(),
    ...listaIndice("Índice de Tablas o Cuadros", tablas),
    ...listaIndice("Índice de Gráficos", graficos),
    ...listaAcronimos(acronimos),
    ...glosario(terminos),
  ];
}

function pieNumerado() {
  return new Footer({
    children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [run("Página "), new TextRun({ children: [PageNumber.CURRENT], font: FUENTE, size: TAMANO, color: NEGRO })],
      spacing: espaciado(),
    })],
  });
}

function portada(numeroProducto, nombreProducto) {
  const etiqueta = numeroProducto === "TÉCNICO" ? "INFORME FINAL / REPORTE TÉCNICO" : `PRODUCTO N.° ${numeroProducto}`;
  return {
    properties: {
      page: { size: A4, margin: { top: MARGEN, bottom: MARGEN, left: MARGEN, right: MARGEN } },
    },
    footers: { default: pieNumerado() },
    children: [
      new Paragraph({ text: "", spacing: espaciado({ before: 400 }) }),
      parrafoCentrado("CONTRALORÍA GENERAL DE LA REPÚBLICA", { run: { bold: true }, after: 160 }),
      parrafoCentrado("[Espacio reservado para el logo oficial CGR en una entrega institucional autorizada]", { run: { italics: true, color: GRIS }, after: 180 }),
      parrafoCentrado(etiqueta, { run: { bold: true }, after: 180 }),
      parrafoCentrado(nombreProducto, { run: { bold: true }, after: 260 }),
      parrafoCentrado("Nombre de la consultoría:", { run: { bold: true }, after: 30 }),
      parrafoCentrado(CONSULTORIA, { after: 260 }),
      parrafoCentrado("Consultor:", { run: { bold: true }, after: 30 }),
      parrafoCentrado(CONSULTOR, { after: 240 }),
      parrafoCentrado(NATURALEZA, { run: { bold: true }, after: 260 }),
      parrafoCentrado("Repositorio de código y documentación:", { run: { bold: true }, after: 30 }),
      parrafoCentrado(REPO_URL, { after: 240 }),
      parrafoCentrado("Fecha de presentación: agosto de 2026"),
    ],
  };
}

function seccionContenido(nombreProducto, children) {
  return {
    properties: {
      page: { size: A4, margin: { top: MARGEN, bottom: MARGEN, left: MARGEN, right: MARGEN } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [run(nombreProducto, { color: GRIS })],
          spacing: espaciado({ after: 30 }),
        })],
      }),
    },
    footers: { default: pieNumerado() },
    children,
  };
}

function documento(numeroProducto, nombreCorto, nombreLargo, contenido) {
  return new Document({
    creator: CONSULTOR,
    title: `${nombreCorto} - Prototipo independiente CGR 1.8.2`,
    description: NATURALEZA,
    styles: {
      default: { document: { run: { font: FUENTE, size: TAMANO, color: NEGRO } } },
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: FUENTE, size: TAMANO, bold: true, color: NEGRO },
          paragraph: { spacing: espaciado({ before: 240, after: 120 }), outlineLevel: 0 },
        },
        {
          id: "Heading2",
          name: "Heading 2",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { font: FUENTE, size: TAMANO, bold: true, color: NEGRO },
          paragraph: { spacing: espaciado({ before: 180, after: 80 }), outlineLevel: 1 },
        },
      ],
    },
    sections: [portada(numeroProducto, nombreLargo), seccionContenido(nombreCorto, contenido)],
  });
}

module.exports = {
  NEGRO, GRIS, FUENTE, TAMANO, CONSULTORIA, CONSULTOR, NATURALEZA, REPO_URL,
  ACRONIMOS_BASE, GLOSARIO_BASE, REFERENCIAS_BASE,
  titulo, subtitulo, parrafo, parrafoCentrado, vineta, marcadorIndice, listaIndice,
  tabla, tablaConTitulo, imagen, imagenConTitulo, listaAcronimos, glosario, referencias,
  frontMatter, documento, Paragraph,
};
