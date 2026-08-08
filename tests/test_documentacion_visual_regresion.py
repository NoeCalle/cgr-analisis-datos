from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PLANTILLA = ROOT / "reporte" / "plantilla_docx.js"


def test_parrafo_de_imagen_no_usa_interlineado_fijo():
    """Las imágenes inline se recortan si heredan line-height fijo de 12 pt."""
    source = PLANTILLA.read_text(encoding="utf-8")
    match = re.search(
        r"function imagen\(path, width, height\) \{(?P<body>.*?)\n\}\n\nfunction leyendaFigura",
        source,
        re.DOTALL,
    )
    assert match, "No se encontró el helper imagen() en la plantilla DOCX"
    body = match.group("body")
    assert "spacing: espaciado" not in body
    assert "spacing: { after: 40 }" in body


def test_imagenes_documentales_tienen_tamano_no_trivial():
    charts = ROOT / "outputs" / "charts"
    requeridas = [
        "01_distribucion_montos.png",
        "02_modalidades_contratacion.png",
        "03_concentracion_proveedores.png",
        "04_serie_temporal.png",
        "05_importancia_favoritismo.png",
        "06_deteccion_fraccionamiento.png",
        "07_shap_summary_favoritismo.png",
        "08_shap_waterfall_caso.png",
        "09_diagrama_modelo_datos.png",
        "10_grafo_vinculos.png",
        "11_dag_airflow.png",
    ]
    for nombre in requeridas:
        ruta = charts / nombre
        assert ruta.exists(), f"Falta gráfico documental: {nombre}"
        assert ruta.stat().st_size > 5_000, f"Gráfico documental sospechosamente pequeño: {nombre}"
