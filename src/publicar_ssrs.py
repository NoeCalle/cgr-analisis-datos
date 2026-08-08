"""
Publicación local de resultados para consumo SSRS — Anexo 3, ítem 7.

La base SQLite es únicamente un stand-in reproducible para validar el contrato
de datos que después debe desplegarse en SQL Server/SSRS institucional. Las
entradas se consumen desde Oro; la publicación real en servidores CGR requiere
infraestructura, autenticación y credenciales institucionales.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

from rutas_datos import entrada_oro

DB_PATH = Path("ssrs/reportes.db")
MANIFEST_PATH = Path("outputs/ssrs_publicacion_manifest.json")
RUN_MANIFEST_PATH = Path("outputs/run_manifest.json")

SCHEMA_SQLITE = """
CREATE TABLE PrediccionesFavoritismo (
    id_proveedor TEXT NOT NULL, id_entidad TEXT NOT NULL,
    n_contratos INTEGER NOT NULL CHECK (n_contratos >= 0),
    monto_total REAL NOT NULL CHECK (monto_total >= 0),
    pct_contratacion_directa REAL NOT NULL CHECK (pct_contratacion_directa BETWEEN 0 AND 1),
    pct_comparacion_precios REAL NOT NULL CHECK (pct_comparacion_precios BETWEEN 0 AND 1),
    score_riesgo REAL NOT NULL CHECK (score_riesgo BETWEEN 0 AND 1),
    fecha_calculo TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_entidad)
);
CREATE TABLE PrediccionesFraccionamiento (
    id_proveedor TEXT NOT NULL, id_entidad TEXT NOT NULL, objeto TEXT NOT NULL,
    max_contratos_ventana INTEGER NOT NULL CHECK (max_contratos_ventana >= 0),
    pct_bajo_umbral REAL NOT NULL CHECK (pct_bajo_umbral BETWEEN 0 AND 1),
    score_anomalia REAL NOT NULL,
    senal_priorizacion INTEGER NOT NULL CHECK (senal_priorizacion IN (0, 1)),
    fecha_calculo TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_entidad, objeto)
);
CREATE TABLE VinculosProveedorFuncionario (
    id_proveedor TEXT NOT NULL, id_funcionario TEXT NOT NULL,
    n_contratos INTEGER NOT NULL CHECK (n_contratos >= 0),
    comparte_telefono INTEGER NOT NULL CHECK (comparte_telefono IN (0, 1)),
    comparte_direccion INTEGER NOT NULL CHECK (comparte_direccion IN (0, 1)),
    fecha_calculo TEXT NOT NULL,
    PRIMARY KEY (id_proveedor, id_funcionario)
);
CREATE INDEX IX_Favoritismo_Score ON PrediccionesFavoritismo (score_riesgo DESC);
CREATE INDEX IX_Fraccionamiento_Score ON PrediccionesFraccionamiento (score_anomalia DESC);
CREATE VIEW vw_SSRS_Favoritismo AS
    SELECT id_proveedor, id_entidad, n_contratos, monto_total,
           pct_contratacion_directa, pct_comparacion_precios,
           score_riesgo, fecha_calculo
    FROM PrediccionesFavoritismo;
CREATE VIEW vw_SSRS_Fraccionamiento AS
    SELECT id_proveedor, id_entidad, objeto, max_contratos_ventana,
           pct_bajo_umbral, score_anomalia, senal_priorizacion, fecha_calculo
    FROM PrediccionesFraccionamiento;
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fecha_ejecucion() -> str:
    if RUN_MANIFEST_PATH.exists():
        with RUN_MANIFEST_PATH.open(encoding="utf-8") as f:
            manifest = json.load(f)
        if manifest.get("generado_utc"):
            return manifest["generado_utc"]
    return pd.Timestamp.now("UTC").isoformat()


def _validar_columnas(df: pd.DataFrame, requeridas: list[str], nombre: str) -> None:
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise ValueError(f"{nombre}: faltan columnas requeridas para SSRS: {faltantes}")


def _validar_pk(df: pd.DataFrame, pk: list[str], nombre: str) -> None:
    if df[pk].isnull().any().any():
        raise ValueError(f"{nombre}: la clave {pk} contiene nulos")
    duplicados = int(df.duplicated(pk).sum())
    if duplicados:
        raise ValueError(f"{nombre}: {duplicados} claves duplicadas en {pk}")


def _validar_rango_01(df: pd.DataFrame, columnas: list[str], nombre: str) -> None:
    for col in columnas:
        serie = pd.to_numeric(df[col], errors="coerce")
        if serie.isna().any() or not serie.between(0, 1).all():
            raise ValueError(f"{nombre}: {col} debe estar íntegramente en [0, 1]")


def preparar_favoritismo(fecha: str) -> tuple[pd.DataFrame, Path]:
    origen = entrada_oro("ranking_riesgo_favoritismo.csv")
    df = pd.read_csv(origen).rename(columns={"score_riesgo_favoritismo": "score_riesgo"})
    cols = [
        "id_proveedor", "id_entidad", "n_contratos", "monto_total",
        "pct_contratacion_directa", "pct_comparacion_precios", "score_riesgo",
    ]
    _validar_columnas(df, cols, "Favoritismo")
    _validar_pk(df, ["id_proveedor", "id_entidad"], "Favoritismo")
    _validar_rango_01(
        df,
        ["pct_contratacion_directa", "pct_comparacion_precios", "score_riesgo"],
        "Favoritismo",
    )
    if (df["n_contratos"] < 0).any() or (df["monto_total"] < 0).any():
        raise ValueError("Favoritismo: n_contratos y monto_total deben ser no negativos")
    df = df[cols].copy()
    df["fecha_calculo"] = fecha
    return df, Path(origen)


def preparar_fraccionamiento(fecha: str) -> tuple[pd.DataFrame, Path]:
    origen = entrada_oro("ranking_riesgo_fraccionamiento.csv")
    df = pd.read_csv(origen).rename(columns={
        "max_contratos_ventana_15d": "max_contratos_ventana",
        "pct_montos_bajo_umbral": "pct_bajo_umbral",
        "cumple_regla_fraccionamiento": "senal_priorizacion",
        "senal_priorizacion_fraccionamiento": "senal_priorizacion",
    })
    cols = [
        "id_proveedor", "id_entidad", "objeto", "max_contratos_ventana",
        "pct_bajo_umbral", "score_anomalia", "senal_priorizacion",
    ]
    _validar_columnas(df, cols, "Fraccionamiento")
    _validar_pk(df, ["id_proveedor", "id_entidad", "objeto"], "Fraccionamiento")
    _validar_rango_01(df, ["pct_bajo_umbral"], "Fraccionamiento")
    if (df["max_contratos_ventana"] < 0).any():
        raise ValueError("Fraccionamiento: max_contratos_ventana debe ser no negativo")
    df = df[cols].copy()
    df["senal_priorizacion"] = df["senal_priorizacion"].astype(bool).astype(int)
    df["fecha_calculo"] = fecha
    return df, Path(origen)


def preparar_vinculos(fecha: str) -> tuple[pd.DataFrame, Path]:
    origen = entrada_oro("ranking_vinculos_proveedor_funcionario.csv")
    df = pd.read_csv(origen)
    cols = [
        "id_proveedor", "id_funcionario", "n_contratos",
        "comparte_telefono", "comparte_direccion",
    ]
    _validar_columnas(df, cols, "Vínculos")
    _validar_pk(df, ["id_proveedor", "id_funcionario"], "Vínculos")
    if (df["n_contratos"] < 0).any():
        raise ValueError("Vínculos: n_contratos debe ser no negativo")
    df = df[cols].copy()
    for col in ["comparte_telefono", "comparte_direccion"]:
        df[col] = df[col].astype(bool).astype(int)
    df["fecha_calculo"] = fecha
    return df, Path(origen)


def crear_base(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA_SQLITE)
    con.commit()
    return con


def validar_publicacion(con: sqlite3.Connection, esperados: dict[str, int]) -> dict:
    consultas = {
        "PrediccionesFavoritismo": "SELECT COUNT(*) FROM PrediccionesFavoritismo",
        "PrediccionesFraccionamiento": "SELECT COUNT(*) FROM PrediccionesFraccionamiento",
        "VinculosProveedorFuncionario": "SELECT COUNT(*) FROM VinculosProveedorFuncionario",
    }
    conteos = {}
    for tabla, sql in consultas.items():
        conteo = int(con.execute(sql).fetchone()[0])
        conteos[tabla] = conteo
        if conteo != esperados[tabla]:
            raise AssertionError(f"{tabla}: esperado {esperados[tabla]}, publicado {conteo}")

    fav = pd.read_sql(
        "SELECT * FROM vw_SSRS_Favoritismo WHERE score_riesgo >= 0.5 ORDER BY score_riesgo DESC",
        con,
    )
    frac = pd.read_sql(
        "SELECT * FROM vw_SSRS_Fraccionamiento ORDER BY score_anomalia DESC LIMIT 25",
        con,
    )
    if not fav.empty and not fav["score_riesgo"].is_monotonic_decreasing:
        raise AssertionError("DatasetFavoritismo SSRS no conserva orden descendente por score")
    if not frac.empty and not frac["score_anomalia"].is_monotonic_decreasing:
        raise AssertionError("DatasetFraccionamiento SSRS no conserva orden descendente por score")

    return {
        "conteos_tablas": conteos,
        "consulta_smoke_favoritismo_umbral_0_5": int(len(fav)),
        "consulta_smoke_fraccionamiento_top_25": int(len(frac)),
    }


def escribir_manifest(fecha: str, fuentes: dict[str, Path], validacion: dict) -> None:
    run_commit = None
    if RUN_MANIFEST_PATH.exists():
        with RUN_MANIFEST_PATH.open(encoding="utf-8") as f:
            run_commit = json.load(f).get("git_commit")

    payload = {
        "schema_version": 1,
        "fecha_ejecucion": fecha,
        "git_commit_evidencia": run_commit,
        "naturaleza": "stand-in SQLite para validar contrato SSRS; SQL Server/SSRS CGR no ejecutado",
        "fuentes_oro": {
            nombre: {"ruta": str(path), "sha256": sha256(path)}
            for nombre, path in fuentes.items()
        },
        "validacion": validacion,
        "artefactos_sql_server": [
            "ssrs/schema_sql_server.sql",
            "ssrs/ReporteRiesgoFavoritismo.rdl",
            "ssrs/ReporteRiesgoFraccionamiento.rdl",
        ],
        "pendiente_institucional": [
            "cadena de conexión y autenticación CGR",
            "ejecución del DDL en SQL Server institucional",
            "despliegue de RDL en SSRS institucional",
            "pruebas de permisos, rendimiento y operación en DEV/QA/PROD CGR",
        ],
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    fecha = fecha_ejecucion()
    fav, fuente_fav = preparar_favoritismo(fecha)
    frac, fuente_frac = preparar_fraccionamiento(fecha)
    vinc, fuente_vinc = preparar_vinculos(fecha)

    con = crear_base()
    try:
        fav.to_sql("PrediccionesFavoritismo", con, if_exists="append", index=False)
        frac.to_sql("PrediccionesFraccionamiento", con, if_exists="append", index=False)
        vinc.to_sql("VinculosProveedorFuncionario", con, if_exists="append", index=False)
        con.commit()
        validacion = validar_publicacion(con, {
            "PrediccionesFavoritismo": len(fav),
            "PrediccionesFraccionamiento": len(frac),
            "VinculosProveedorFuncionario": len(vinc),
        })
    finally:
        con.close()

    escribir_manifest(
        fecha,
        {
            "favoritismo": fuente_fav,
            "fraccionamiento": fuente_frac,
            "vinculos": fuente_vinc,
        },
        validacion,
    )
    print(f"Publicación SSRS PoC validada: {DB_PATH}")
    print(f"Manifiesto: {MANIFEST_PATH}")
    print("SQL Server/SSRS institucional permanece como dependencia CGR.")


if __name__ == "__main__":
    main()
