const {
  Document, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, ImageRun, PageBreak,
  Header, Footer, PageNumber, VerticalAlign,
} = require("docx");
const fs = require("fs");

const AZUL = "1F4E79";
const ROJO = "C0392B";
const A4 = { width: 11906, height: 16838 };

const CONSULTORIA = '"Módulo de Análisis de Datos para Dar Soporte a los Auditores Durante la ' +
  'Ejecución de los Servicios de Control" — Proyecto Interno 1.8.2';
const CONSULTOR = "Prototipo independiente elaborado como prueba de concepto (proof of concept) — no constituye una postulación formal, una implementación oficial, ni cuenta con aprobación institucional de la CGR";
const REPO_URL = "https://github.com/NoeCalle/cgr-analisis-datos";

function titulo(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 260, after: 140 } });
}
function subtitulo(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 180, after: 90 } });
}
function parrafo(text) {
  return new Paragraph({ children: [new TextRun({ text, size: 21 })], spacing: { after: 140 } });
}
function vineta(text) {
  return new Paragraph({ children: [new TextRun({ text, size: 21 })], bullet: { level: 0 }, spacing: { after: 70 } });
}
function imagen(path, width, height) {
  return new Paragraph({
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path), transformation: { width, height } })],
    alignment: AlignmentType.CENTER, spacing: { after: 90 },
  });
}
function piePagina(texto) {
  return new Paragraph({
    children: [new TextRun({ text: texto, italics: true, size: 17, color: "666666" })],
    alignment: AlignmentType.CENTER, spacing: { before: 50, after: 180 },
  });
}
function celda(text, { header = false, width, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: AZUL } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold: header, color: header ? "FFFFFF" : "000000", size: 19 })],
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
        children: r.map((c, i) => celda(c, { width: widths[i], align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER })),
      })),
    ],
  });
}

function portada(numeroProducto, nombreProducto) {
  const etiqueta = numeroProducto === "TÉCNICO" ? "REPORTE TÉCNICO" : `PRODUCTO N° ${numeroProducto}`;
  return {
    properties: { page: { size: A4 } },
    children: [
      new Paragraph({ text: "", spacing: { before: 1400 } }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: etiqueta, bold: true, size: 26, color: AZUL })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 150, after: 300 },
        children: [new TextRun({ text: nombreProducto, bold: true, size: 30 })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 600 },
        children: [new TextRun({ text: CONSULTORIA, size: 21, italics: true })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 700 },
        children: [new TextRun({ text: CONSULTOR, size: 19 })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 900 },
        children: [new TextRun({ text: "Repositorio de código fuente:", bold: true, size: 18 })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: REPO_URL, size: 18, color: AZUL })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { before: 1000 },
        children: [new TextRun({ text: "Agosto 2026", size: 18 })],
      }),
    ],
  };
}

function seccionContenido(nombreProducto, children) {
  return {
    properties: { page: { size: A4 } },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: nombreProducto, size: 15, color: "888888" })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "Página ", size: 17 }), new TextRun({ children: [PageNumber.CURRENT], size: 17 })],
        })],
      }),
    },
    children,
  };
}

function documento(numeroProducto, nombreCorto, nombreLargo, contenido) {
  return new Document({
    styles: { default: { document: { run: { font: "Arial", size: 21 } } } },
    sections: [portada(numeroProducto, nombreLargo), seccionContenido(nombreCorto, contenido)],
  });
}

module.exports = {
  AZUL, ROJO, titulo, subtitulo, parrafo, vineta, imagen, piePagina, tabla, documento, PageBreak, Paragraph,
};
