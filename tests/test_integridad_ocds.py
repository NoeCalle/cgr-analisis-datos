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


def test_cada_contrato_toma_suppliers_de_su_award_y_no_del_proceso():
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
        {"main_ocid": "ocds-1", "awards_id": "A1", "identifier_id": "RUC-1"},
        {"main_ocid": "ocds-1", "awards_id": "A2", "identifier_id": "RUC-2"},
        {"main_ocid": "ocds-1", "awards_id": "A2", "identifier_id": "RUC-3"},
    ])

    out = construir_contratos(_main().iloc[[0]], contracts, awards, awards_suppliers)

    c1 = out.loc[out["id_contrato_fuente"] == "C1"].iloc[0]
    c2 = out.loc[out["id_contrato_fuente"] == "C2"].iloc[0]

    assert c1["id_proveedor"] == "RUC-1"
    assert not bool(c1["es_consorcio"])
    assert bool(c2["es_consorcio"])
    assert c2["n_integrantes_consorcio"] == 2
    assert set(c2["integrantes_consorcio"].split(";")) == {"RUC-2", "RUC-3"}


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
        {"main_ocid": "ocds-1", "awards_id": "A1", "identifier_id": "RUC-1"},
        {"main_ocid": "ocds-2", "awards_id": "A1", "identifier_id": "RUC-2"},
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
        {"main_ocid": "ocds-1", "awards_id": "A1", "identifier_id": "RUC-1"},
    ])

    out = construir_contratos(_main().iloc[[0]], contracts, awards, awards_suppliers)

    assert len(out) == 1
    assert out.iloc[0]["id_contrato_fuente"] == "C1"
    assert out.iloc[0]["id_proveedor"] == "RUC-1"
