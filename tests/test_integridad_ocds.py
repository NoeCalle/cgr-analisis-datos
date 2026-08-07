"""Pruebas de regresión P0 para la integridad relacional OCDS."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cargar_datos_reales_seace import construir_contratos


def _main():
    return pd.DataFrame([
        {
            "ocid": "ocds-1",
            "buyer_id": "ENT-1",
            "tender_procurementMethodDetails": "Adjudicación Simplificada",
            "tender_mainProcurementCategory": "goods",
        },
        {
            "ocid": "ocds-2",
            "buyer_id": "ENT-2",
            "tender_procurementMethodDetails": "Licitación Pública",
            "tender_mainProcurementCategory": "works",
        },
    ])


def test_cada_contrato_toma_supplier_de_su_award_y_no_del_proceso():
    contracts = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "C1", "awardID": "A1", "value_amount": 100.0,
         "dateSigned": "2024-01-01", "description": "Bienes de oficina"},
        {"main_ocid": "ocds-1", "id": "C2", "awardID": "A2", "value_amount": 200.0,
         "dateSigned": "2024-01-02", "description": "Bienes de oficina"},
    ])
    awards = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "A1"},
        {"main_ocid": "ocds-1", "id": "A2"},
    ])
    awards_suppliers = pd.DataFrame([
        {"main_ocid": "ocds-1", "awards_id": "A1", "id": "PE-RUC-1", "name": "PROVEEDOR UNO"},
        {"main_ocid": "ocds-1", "awards_id": "A2", "id": "PE-RUC-2", "name": "PROVEEDOR DOS"},
    ])

    out = construir_contratos(_main().iloc[[0]], contracts, awards, awards_suppliers)

    c1 = out.loc[out["id_contrato_fuente"] == "C1"].iloc[0]
    c2 = out.loc[out["id_contrato_fuente"] == "C2"].iloc[0]

    assert c1["id_proveedor"] == "PE-RUC-1"
    assert c2["id_proveedor"] == "PE-RUC-2"
    assert not bool(c1["es_consorcio"])
    assert not bool(c2["es_consorcio"])


def test_consorcio_representado_como_un_supplier_se_conserva_como_entidad():
    contracts = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "C1", "awardID": "A1", "value_amount": 100.0,
         "dateSigned": "2024-01-01", "description": "Obra vial"},
    ])
    awards = pd.DataFrame([{"main_ocid": "ocds-1", "id": "A1"}])
    awards_suppliers = pd.DataFrame([
        {"main_ocid": "ocds-1", "awards_id": "A1", "id": "PE-RUC-532388", "name": "CONSORCIO EDUCATIVO NORTE"},
    ])

    out = construir_contratos(_main().iloc[[0]], contracts, awards, awards_suppliers)
    fila = out.iloc[0]

    assert fila["id_proveedor"] == "PE-RUC-532388"
    assert fila["razon_social_adjudicada"] == "CONSORCIO EDUCATIVO NORTE"
    assert bool(fila["es_consorcio"])
    assert pd.isna(fila["n_integrantes_consorcio"])


def test_multiples_suppliers_reales_en_un_award_generan_identidad_compuesta():
    contracts = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "C1", "awardID": "A1", "value_amount": 100.0,
         "dateSigned": "2024-01-01", "description": "Bienes"},
    ])
    awards = pd.DataFrame([{"main_ocid": "ocds-1", "id": "A1"}])
    awards_suppliers = pd.DataFrame([
        {"main_ocid": "ocds-1", "awards_id": "A1", "id": "PE-RUC-1", "name": "UNO"},
        {"main_ocid": "ocds-1", "awards_id": "A1", "id": "PE-RUC-2", "name": "DOS"},
    ])

    out = construir_contratos(_main().iloc[[0]], contracts, awards, awards_suppliers)
    fila = out.iloc[0]

    assert fila["id_proveedor"].startswith("MULTISUPPLIER:")
    assert bool(fila["es_consorcio"])
    assert fila["n_integrantes_consorcio"] == 2
    assert set(fila["integrantes_consorcio"].split(";")) == {"PE-RUC-1", "PE-RUC-2"}


def test_contract_id_se_hace_unico_con_ocid():
    contracts = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "C1", "awardID": "A1", "value_amount": 100.0,
         "dateSigned": "2024-01-01", "description": "Bienes"},
        {"main_ocid": "ocds-2", "id": "C1", "awardID": "A1", "value_amount": 300.0,
         "dateSigned": "2024-02-01", "description": "Obra vial"},
    ])
    awards = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "A1"},
        {"main_ocid": "ocds-2", "id": "A1"},
    ])
    awards_suppliers = pd.DataFrame([
        {"main_ocid": "ocds-1", "awards_id": "A1", "id": "PE-RUC-1", "name": "UNO"},
        {"main_ocid": "ocds-2", "awards_id": "A1", "id": "PE-RUC-2", "name": "DOS"},
    ])

    out = construir_contratos(_main(), contracts, awards, awards_suppliers)

    assert len(out) == 2
    assert out["id_contrato"].is_unique
    assert set(out["id_contrato"]) == {"ocds-1::C1", "ocds-2::C1"}


def test_contrato_sin_supplier_de_su_adjudicacion_no_recibe_supplier_de_otro_award():
    contracts = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "C1", "awardID": "A1", "value_amount": 100.0,
         "dateSigned": "2024-01-01", "description": "Bienes"},
        {"main_ocid": "ocds-1", "id": "C2", "awardID": "A2", "value_amount": 200.0,
         "dateSigned": "2024-01-02", "description": "Bienes"},
    ])
    awards = pd.DataFrame([
        {"main_ocid": "ocds-1", "id": "A1"},
        {"main_ocid": "ocds-1", "id": "A2"},
    ])
    awards_suppliers = pd.DataFrame([
        {"main_ocid": "ocds-1", "awards_id": "A1", "id": "PE-RUC-1", "name": "UNO"},
    ])

    out = construir_contratos(_main().iloc[[0]], contracts, awards, awards_suppliers)

    assert len(out) == 1
    assert out.iloc[0]["id_contrato_fuente"] == "C1"
    assert out.iloc[0]["id_proveedor"] == "PE-RUC-1"
