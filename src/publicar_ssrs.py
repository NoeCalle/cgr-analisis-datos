"""
Publicación de resultados para consumo SSRS — checklist Anexo 3, ítem 7.

SQLite es un stand-in local. Las entradas se leen preferentemente desde Oro,
que es la capa de consumo/reporting del PoC; `outputs/` queda como fallback
standalone. SQL Server/SSRS real requiere el ambiente institucional.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from rutas_datos import entrada_oro

DB_PATH = "ssrs/reportes.db"

SCHEMA_SQLITE = """
CREATE TABLE PrediccionesFavoritismo (
    id_proveedor TEXT NOT NULL, id_entidad TEXT NOT NULL,
    n_contratos INTEGER NOT NULL, monto_total REAL NOT NULL,
    pct_contratacion_directa REAL NOT NULL,
    pct_comparacion_precios REAL NOT NULL,
    score_riesgo REAL NOT NULL, fecha_calculo TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_entidad)
);
CREATE TABLE PrediccionesFraccionamiento (
    id_proveedor TEXT NOT NULL, id_entidad TEXT NOT NULL, objeto TEXT NOT NULL,
    max_contratos_ventana INTEGER NOT NULL, pct_bajo_umbral REAL NOT NULL,
    score_anomalia REAL NOT NULL, senal_priorizacion INTEGER NOT NULL,
    fecha_calculo TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_entidad, objeto)
);
CREATE TABLE VinculosProveedorFuncionario (
    id_proveedor TEXT NOT NULL, id_funcionario TEXT NOT NULL,
    n_contratos INTEGER NOT NULL, comparte_telefono INTEGER NOT NULL,
    comparte_direccion INTEGER NOT NULL, fecha_calculo TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_funcionario)
);
CREATE INDEX IX_Favoritismo_Score ON PrediccionesFavoritismo (score_riesgo DESC);
CREATE INDEX IX_Fraccionamiento_Score ON PrediccionesFraccionamiento (score_anomalia DESC);
"""


def crear_base(db_path=DB_PATH):
    Path(db_path).unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA_SQLITE)
    con.commit()
    return con


def cargar_favoritismo(con):
    df = pd.read_csv(entrada_oro("ranking_riesgo_favoritismo.csv"))
    df = df.rename(columns={"score_riesgo_favoritismo": "score_riesgo"})
    df["fecha_calculo"] = pd.Timestamp.now("UTC").isoformat()
    cols = [
        "id_proveedor", "id_entidad", "n_contratos", "monto_total",
        "pct_contratacion_directa", "pct_comparacion_precios", "score_riesgo", "fecha_calculo",
    ]
    df[cols].to_sql("PrediccionesFavoritismo", con, if_exists="append", index=False)


def cargar_fraccionamiento(con):
    df = pd.read_csv(entrada_oro("ranking_riesgo_fraccionamiento.csv"))
    df = df.rename(columns={
        "max_contratos_ventana_15d": "max_contratos_ventana",
        "pct_montos_bajo_umbral": "pct_bajo_umbral",
        "cumple_regla_fraccionamiento": "senal_priorizacion",
    })
    df["senal_priorizacion"] = df["senal_priorizacion"].astype(int)
    df["fecha_calculo"] = pd.Timestamp.now("UTC").isoformat()
    cols = [
        "id_proveedor", "id_entidad", "objeto", "max_contratos_ventana",
        "pct_bajo_umbral", "score_anomalia", "senal_priorizacion", "fecha_calculo",
    ]
    df[cols].to_sql("PrediccionesFraccionamiento", con, if_exists="append", index=False)


def cargar_vinculos(con):
    df = pd.read_csv(entrada_oro("ranking_vinculos_proveedor_funcionario.csv"))
    df["comparte_telefono"] = df["comparte_telefono"].astype(int)
    df["comparte_direccion"] = df["comparte_direccion"].astype(int)
    df["fecha_calculo"] = pd.Timestamp.now("UTC").isoformat()
    cols = [
        "id_proveedor", "id_funcionario", "n_contratos",
        "comparte_telefono", "comparte_direccion", "fecha_calculo",
    ]
    df[cols].to_sql("VinculosProveedorFuncionario", con, if_exists="append", index=False)


def probar_consulta_ssrs(con):
    resultado = pd.read_sql(
        """
        SELECT id_proveedor, id_entidad, n_contratos,
               pct_contratacion_directa, pct_comparacion_precios, score_riesgo
        FROM PrediccionesFavoritismo
        WHERE score_riesgo >= 0.5
        ORDER BY score_riesgo DESC
        """,
        con,
    )
    print(f"Consulta equivalente a Dataset SSRS: {len(resultado)} filas.")


def main():
    con = crear_base()
    cargar_favoritismo(con)
    cargar_fraccionamiento(con)
    cargar_vinculos(con)
    con.commit()
    probar_consulta_ssrs(con)
    con.close()
    print(f"Base PoC publicada en {DB_PATH}; integración institucional sigue pendiente.")


if __name__ == "__main__":
    main()
