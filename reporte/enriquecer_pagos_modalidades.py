"""Añade el análisis Sprint 4 a los DOCX formales antes de actualizar índices.

El contenido se deriva exclusivamente de ``outputs/analisis_pagos_modalidades.json``.
No modifica la evidencia histórica del RC1 ni usa datos SIAF reales.
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
EVIDENCIA = ROOT / "outputs/analisis_pagos_modalidades.json"
CHART_RATIO = ROOT / "outputs/charts/11_ratio_pago_contrato.png"
CHART_MODALIDADES = ROOT / "outputs/charts/12_modalidades_regimen.png"

DESTINOS = [
    ROOT / "reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx",
    ROOT / "reporte/productos_formales/Producto_07_Informe_Final.docx",
    ROOT / "reporte/productos_formales/Producto_01_Plan_de_Trabajo.docx",
]

MARCADOR = "ANEXO TÉCNICO SPRINT 4 — ANÁLISIS DE PAGOS Y MODALIDADES"


def _formatear_parrafo(parrafo, negrita=False):
    parrafo.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    parrafo.paragraph_format.space_after = Pt(3)
    for run in parrafo.runs:
        run.font.name = "Arial"
        run.font.size = Pt(11)
        run.bold = negrita or run.bold


def _agregar_heading(doc, texto: str, nivel: int = 1):
    p = doc.add_heading(texto, level=nivel)
    _formatear_parrafo(p, negrita=True)
    return p


def _agregar_texto(doc, texto: str):
    p = doc.add_paragraph(texto)
    _formatear_parrafo(p)
    return p


def _agregar_tabla(doc, pagos: dict, modalidades: dict):
    estados = pagos.get("estado_pago_contratos", {})
    clasif = modalidades.get("clasificacion_modalidad", {})
    filas = [
        ("Pagos sintéticos", pagos.get("payments_rows")),
        ("Contratos analizados", pagos.get("contracts_rows")),
        ("Pagos huérfanos", pagos.get("orphan_payments")),
        ("Contratos con pago parcial", estados.get("pago_parcial", 0)),
        ("Contratos pendientes sin pago", estados.get("pendiente_sin_pago", 0)),
        ("Señales de sobrepago a revisar", estados.get("sobrepago_senal_revisar", 0)),
        ("Demora P90 devengado→pagado (días)", pagos.get("dias_devengado_a_pagado_p90")),
        ("Modalidades especiales no inferibles solo por cuantía", clasif.get("especial_no_inferible_por_cuantia", 0)),
        ("Modalidades que requieren revisión de contexto", clasif.get("requiere_revision_contexto", 0)),
    ]
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Indicador"
    table.rows[0].cells[1].text = "Resultado"
    for etiqueta, valor in filas:
        cells = table.add_row().cells
        cells[0].text = str(etiqueta)
        cells[1].text = "N/D" if valor is None else str(valor)
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                _formatear_parrafo(p)
    return table


def enriquecer(ruta: Path, evidencia: dict):
    if not ruta.exists():
        raise FileNotFoundError(ruta)
    doc = Document(ruta)
    texto_existente = "\n".join(p.text for p in doc.paragraphs)
    if MARCADOR in texto_existente:
        return False

    pagos = evidencia["payments"]
    modalidades = evidencia["modalidades"]

    _agregar_heading(doc, MARCADOR, 1)
    _agregar_texto(
        doc,
        "Este anexo cubre la actividad del TDR referida al análisis estadístico y exploratorio de patrones de pagos, montos contractuales y modalidades de contratación. La evidencia del PoC usa pagos sintéticos vinculados a contratos sintéticos; no representa información SIAF real ni determina la legalidad de una modalidad.",
    )
    _agregar_heading(doc, "Resultados reproducibles", 2)
    _agregar_tabla(doc, pagos, modalidades)
    _agregar_texto(
        doc,
        "La clasificación de modalidades frente a cuantía es únicamente referencial. Contratación Directa, Comparación de Precios, Subasta Inversa, acuerdos marco y otros supuestos pueden depender de condiciones jurídicas o de mercado que no se deducen del monto por sí solo. Por ello, 'requiere revisión de contexto' no equivale a irregularidad.",
    )

    if CHART_RATIO.exists():
        _agregar_heading(doc, "Distribución de pagos", 2)
        p = doc.add_paragraph()
        p.alignment = 1
        p.add_run().add_picture(str(CHART_RATIO), width=Inches(6.1))
        _formatear_parrafo(p)
    if CHART_MODALIDADES.exists():
        _agregar_heading(doc, "Modalidades por régimen", 2)
        p = doc.add_paragraph()
        p.alignment = 1
        p.add_run().add_picture(str(CHART_MODALIDADES), width=Inches(6.1))
        _formatear_parrafo(p)

    _agregar_heading(doc, "Limitación institucional", 2)
    _agregar_texto(
        doc,
        "El cierre literal con pagos SIAF/SEACE institucionales, diccionarios reales, validación jurídica/funcional y permisos de consulta depende de la CGR y se mantiene registrado en el catálogo de dependencias institucionales.",
    )
    doc.save(ruta)
    return True


def main():
    evidencia = json.loads(EVIDENCIA.read_text(encoding="utf-8"))
    modificados = 0
    for ruta in DESTINOS:
        if enriquecer(ruta, evidencia):
            modificados += 1
            print(f"Enriquecido: {ruta.relative_to(ROOT)}")
        else:
            print(f"Ya contenía anexo Sprint 4: {ruta.relative_to(ROOT)}")
    print(f"DOCX enriquecidos Sprint 4: {modificados}/{len(DESTINOS)}")


if __name__ == "__main__":
    main()
