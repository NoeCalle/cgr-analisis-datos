"""Pruebas del contrato local SQL/SSRS del Anexo 3, ítem 7."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from publicar_ssrs import (
    crear_base,
    preparar_favoritismo,
    preparar_fraccionamiento,
    preparar_vinculos,
    validar_publicacion,
)

ROOT = Path(__file__).resolve().parents[1]


def test_rdl_son_xml_validos_y_consumen_vistas_del_contrato():
    casos = {
        "ReporteRiesgoFavoritismo.rdl": "vw_SSRS_Favoritismo",
        "ReporteRiesgoFraccionamiento.rdl": "vw_SSRS_Fraccionamiento",
    }
    for nombre, vista in casos.items():
        path = ROOT / "ssrs" / nombre
        ET.parse(path)
        texto = path.read_text(encoding="utf-8")
        assert vista in texto
        assert "SRV-CGR-SQL" in texto
        assert "señal" in texto.lower() or "señales" in texto.lower()


def test_schema_sql_server_define_restricciones_y_vistas():
    sql = (ROOT / "ssrs" / "schema_sql_server.sql").read_text(encoding="utf-8")
    assert "CREATE OR ALTER VIEW dbo.vw_SSRS_Favoritismo" in sql
    assert "CREATE OR ALTER VIEW dbo.vw_SSRS_Fraccionamiento" in sql
    assert "CHECK (score_riesgo BETWEEN 0 AND 1)" in sql
    assert "CHECK (pct_bajo_umbral BETWEEN 0 AND 1)" in sql
    assert "IX_Favoritismo_Score" in sql
    assert "IX_Fraccionamiento_Score" in sql


def test_publicacion_local_carga_y_valida_los_tres_contratos(tmp_path):
    fecha = "2026-08-08T00:00:00+00:00"
    fav, _ = preparar_favoritismo(fecha)
    frac, _ = preparar_fraccionamiento(fecha)
    vinc, _ = preparar_vinculos(fecha)

    con = crear_base(tmp_path / "reportes.db")
    try:
        fav.to_sql("PrediccionesFavoritismo", con, if_exists="append", index=False)
        frac.to_sql("PrediccionesFraccionamiento", con, if_exists="append", index=False)
        vinc.to_sql("VinculosProveedorFuncionario", con, if_exists="append", index=False)
        con.commit()
        evidencia = validar_publicacion(con, {
            "PrediccionesFavoritismo": len(fav),
            "PrediccionesFraccionamiento": len(frac),
            "VinculosProveedorFuncionario": len(vinc),
        })
    finally:
        con.close()

    assert evidencia["conteos_tablas"]["PrediccionesFavoritismo"] == len(fav)
    assert evidencia["conteos_tablas"]["PrediccionesFraccionamiento"] == len(frac)
    assert evidencia["conteos_tablas"]["VinculosProveedorFuncionario"] == len(vinc)
