"""
Publicación de resultados para consumo SSRS — checklist Anexo 3, ítem 7.

Carga los rankings de riesgo (favoritismo, fraccionamiento, vínculos) en
un esquema relacional equivalente al de ssrs/schema_sql_server.sql. Se usa
SQLite como stand-in local (documentado, no oculto): no hay acceso a un
SQL Server real desde este entorno de prueba de concepto, pero el esquema,
los tipos de datos y las consultas son directamente portables — cambiar
la cadena de conexión de sqlite3 a pyodbc/pymssql es el único paso
adicional para apuntar a un SQL Server real de la CGR.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "ssrs/reportes.db"

# Traducción de tipos T-SQL -> SQLite (equivalentes, no una reinterpretación)
SCHEMA_SQLITE = """
CREATE TABLE PrediccionesFavoritismo (
    id_proveedor        TEXT NOT NULL,
    id_entidad          TEXT NOT NULL,
    n_contratos         INTEGER NOT NULL,
    monto_total         REAL NOT NULL,
    pct_no_competitiva  REAL NOT NULL,
    score_riesgo        REAL NOT NULL,
    fecha_calculo       TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_entidad)
);

CREATE TABLE PrediccionesFraccionamiento (
    id_proveedor            TEXT NOT NULL,
    id_entidad              TEXT NOT NULL,
    objeto                  TEXT NOT NULL,
    max_contratos_ventana   INTEGER NOT NULL,
    pct_bajo_umbral         REAL NOT NULL,
    score_anomalia          REAL NOT NULL,
    cumple_regla_legal      INTEGER NOT NULL,
    fecha_calculo           TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_entidad, objeto)
);

CREATE TABLE VinculosProveedorFuncionario (
    id_proveedor         TEXT NOT NULL,
    id_funcionario       TEXT NOT NULL,
    n_contratos          INTEGER NOT NULL,
    comparte_telefono    INTEGER NOT NULL,
    comparte_direccion   INTEGER NOT NULL,
    fecha_calculo        TEXT NOT NULL,
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
    df = pd.read_csv("outputs/ranking_riesgo_favoritismo.csv")
    df = df.rename(columns={"score_riesgo_favoritismo": "score_riesgo"})
    df["fecha_calculo"] = pd.Timestamp.now("UTC").isoformat()
    cols = ["id_proveedor", "id_entidad", "n_contratos", "monto_total",
            "pct_no_competitiva", "score_riesgo", "fecha_calculo"]
    df[cols].to_sql("PrediccionesFavoritismo", con, if_exists="append", index=False)
    print(f"PrediccionesFavoritismo: {len(df)} filas publicadas.")


def cargar_fraccionamiento(con):
    df = pd.read_csv("outputs/ranking_riesgo_fraccionamiento.csv")
    df = df.rename(columns={
        "max_contratos_ventana_15d": "max_contratos_ventana",
        "pct_montos_bajo_umbral": "pct_bajo_umbral",
        "cumple_regla_fraccionamiento": "cumple_regla_legal",
    })
    df["cumple_regla_legal"] = df["cumple_regla_legal"].astype(int)
    df["fecha_calculo"] = pd.Timestamp.now("UTC").isoformat()
    cols = ["id_proveedor", "id_entidad", "objeto", "max_contratos_ventana",
            "pct_bajo_umbral", "score_anomalia", "cumple_regla_legal", "fecha_calculo"]
    df[cols].to_sql("PrediccionesFraccionamiento", con, if_exists="append", index=False)
    print(f"PrediccionesFraccionamiento: {len(df)} filas publicadas.")


def cargar_vinculos(con):
    df = pd.read_csv("outputs/ranking_vinculos_proveedor_funcionario.csv")
    df["comparte_telefono"] = df["comparte_telefono"].astype(int)
    df["comparte_direccion"] = df["comparte_direccion"].astype(int)
    df["fecha_calculo"] = pd.Timestamp.now("UTC").isoformat()
    cols = ["id_proveedor", "id_funcionario", "n_contratos",
            "comparte_telefono", "comparte_direccion", "fecha_calculo"]
    df[cols].to_sql("VinculosProveedorFuncionario", con, if_exists="append", index=False)
    print(f"VinculosProveedorFuncionario: {len(df)} filas publicadas.")


def probar_consulta_ssrs(con):
    """La misma consulta que usaría un Dataset compartido de SSRS."""
    query = """
        SELECT id_proveedor, id_entidad, n_contratos, score_riesgo
        FROM PrediccionesFavoritismo
        WHERE score_riesgo >= 0.5
        ORDER BY score_riesgo DESC
    """
    resultado = pd.read_sql(query, con)
    print(f"\nConsulta de prueba (equivalente al Dataset de SSRS, @UmbralMinimo=0.5): "
          f"{len(resultado)} filas.")
    print(resultado.to_string(index=False))


def main():
    con = crear_base()
    cargar_favoritismo(con)
    cargar_fraccionamiento(con)
    cargar_vinculos(con)
    con.commit()
    probar_consulta_ssrs(con)
    con.close()
    print(f"\nBase publicada en {DB_PATH} — esquema equivalente a "
          f"ssrs/schema_sql_server.sql, listo para reemplazar sqlite3 por "
          f"pyodbc/pymssql apuntando al SQL Server real de la CGR.")


if __name__ == "__main__":
    main()
