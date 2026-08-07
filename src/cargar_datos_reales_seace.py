"""
Carga de datos REALES de SEACE/OECE en formato OCDS CSV.

Fuente: https://data.open-contracting.org/en/publication/135 (CC BY 4.0).

Corrección P0 de integridad relacional (agosto 2026):
la asociación proveedor-contrato se construye respetando el grafo OCDS:

    Contract(main_ocid, awardID) -> Award(main_ocid, id)
                                -> awards_suppliers(main_ocid, awards_id)

La versión anterior agrupaba todas las parties con rol supplier por OCID y las
asignaba a todos los contratos del proceso. Eso es incorrecto cuando un proceso
tiene múltiples adjudicaciones. También se usa una clave de contrato compuesta
OCID + contract.id, porque contract.id solo es único dentro del proceso OCDS.

LIMITACIÓN: OCDS abierto no contiene funcionarios públicos individuales. El
análisis proveedor-funcionario real requiere fuentes internas/adicionales de CGR.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

RUTA = Path("data_real")

CATEGORIAS_OBJETO = [
    ("Salud y medicamentos", r"salud|m[ée]dic|hospital|medicamento|farmac|quir[uú]rgic|cl[ií]nic|sanitari|reactivo|laboratorio|inmunohematolog|traslado.*pacientes"),
    # Mantenimiento se evalúa antes de obra para evitar clasificar como obra
    # un servicio que solo menciona la palabra infraestructura.
    ("Mantenimiento de infraestructura", r"mantenimiento|reparaci[oó]n"),
    ("Obra vial y construcción", r"\bobra\b|v[ií]al|carretera|pavimenta|construcci[oó]n|rehabilitaci[oó]n.*(?:vial|carretera|obra)"),
    ("Limpieza y vigilancia", r"limpieza|vigilancia|seguridad f[ií]sica|guardian[ií]a|residuos s[oó]lidos"),
    ("Equipos informáticos y tecnología", r"inform[aá]tic|computad|software|licencia.*(microsoft|windows)|tecnolog[ií]a"),
    ("Consultoría y servicios profesionales", r"consultor[ií]a|asesor[ií]a|perito|honorarios profesionales|expediente t[eé]cnico|notificaci[oó]n"),
    ("Alimentación", r"aliment|v[ií]veres|raciones|desayuno escolar|qali warma|leche evaporada"),
    ("Transporte y combustible", r"transporte|combustible|gasolina|petr[oó]leo|flete"),
    ("Capacitación", r"capacitaci[oó]n|curso|taller de formaci[oó]n"),
    ("Vestuario y uniformes", r"uniforme|vestuario|indumentaria"),
    ("Materiales de construcción", r"cemento|fierro|agregado|material.*construcci[oó]n|arena|hormig[oó]n|ladrillo|brida"),
    ("Bienes de oficina", r"[uú]til.*oficina|papeler[ií]a|mobiliario"),
    ("Agropecuario", r"agr[ií]cola|agropecuario|semilla|hijuelo|pesca artesanal|tractor"),
    ("Maquinaria y equipos", r"maquinaria|equipo.*producci[oó]n|generador|motor"),
]


def categorizar_objeto(descripcion):
    if pd.isna(descripcion):
        return "Otros bienes y servicios"
    texto = str(descripcion).lower()
    for categoria, patron in CATEGORIAS_OBJETO:
        if re.search(patron, texto):
            return categoria
    return "Otros bienes y servicios"


def _leer_csv_requerido(nombre: str) -> pd.DataFrame:
    ruta = RUTA / nombre
    if not ruta.exists():
        raise FileNotFoundError(
            f"Falta {ruta}. Descargar y descomprimir el CSV anual de OCP/OECE; "
            "ver data_real/README.md."
        )
    return pd.read_csv(ruta, low_memory=False)


def cargar_crudos():
    """Carga tablas mínimas necesarias para preservar relaciones OCDS."""
    main = _leer_csv_requerido("main.csv")
    contracts = _leer_csv_requerido("contracts.csv")
    awards = _leer_csv_requerido("awards.csv")
    awards_suppliers = _leer_csv_requerido("awards_suppliers.csv")
    parties = _leer_csv_requerido("parties.csv")
    return main, contracts, awards, awards_suppliers, parties


def _roles_contiene(serie: pd.Series, rol: str) -> pd.Series:
    """Busca un rol independientemente del orden/serialización de la lista."""
    patron = rf"(?:^|[,;\s\[\]'\"]){re.escape(rol)}(?:$|[,;\s\[\]'\"])"
    return serie.astype("string").str.contains(patron, regex=True, na=False)


def construir_entidades(parties):
    roles = parties.get("roles", pd.Series(index=parties.index, dtype="string"))
    compradores = parties[_roles_contiene(roles, "buyer") | _roles_contiene(roles, "procuringEntity")].copy()
    compradores = compradores.drop_duplicates("id")
    rename = {
        "id": "id_entidad", "name": "nombre_entidad",
        "address_streetAddress": "direccion", "contactPoint_telephone": "telefono",
    }
    compradores = compradores.rename(columns=rename)
    columnas = ["id_entidad", "nombre_entidad", "direccion", "telefono", "address_department"]
    for col in columnas:
        if col not in compradores:
            compradores[col] = pd.NA
    return compradores[columnas]


def construir_proveedores(parties):
    """Catálogo individual de suppliers para datos de contacto/razón social."""
    roles = parties.get("roles", pd.Series(index=parties.index, dtype="string"))
    proveedores = parties[_roles_contiene(roles, "supplier")].copy()
    if "identifier_id" not in proveedores:
        proveedores["identifier_id"] = proveedores.get("id")
    proveedores = proveedores.dropna(subset=["identifier_id"]).drop_duplicates("identifier_id")
    proveedores = proveedores.rename(columns={
        "identifier_id": "id_proveedor", "name": "razon_social",
        "address_streetAddress": "direccion", "contactPoint_telephone": "telefono",
    })
    columnas = ["id_proveedor", "razon_social", "direccion", "telefono"]
    for col in columnas:
        if col not in proveedores:
            proveedores[col] = pd.NA
    return proveedores[columnas]


def _columna_supplier_id(awards_suppliers: pd.DataFrame) -> str:
    """Localiza el identificador del supplier en el CSV aplanado de OCP."""
    for candidato in ("identifier_id", "id"):
        if candidato in awards_suppliers.columns:
            return candidato
    raise KeyError(
        "awards_suppliers.csv no contiene identifier_id ni id; revisar el esquema de la descarga OCP."
    )


def _agrupar_suppliers_por_award(awards_suppliers: pd.DataFrame) -> pd.DataFrame:
    requeridas = {"main_ocid", "awards_id"}
    faltantes = requeridas - set(awards_suppliers.columns)
    if faltantes:
        raise KeyError(
            f"awards_suppliers.csv no contiene columnas padre requeridas: {sorted(faltantes)}"
        )

    supplier_id_col = _columna_supplier_id(awards_suppliers)
    sup = awards_suppliers[["main_ocid", "awards_id", supplier_id_col]].copy()
    sup = sup.rename(columns={supplier_id_col: "supplier_id"})
    sup = sup.dropna(subset=["main_ocid", "awards_id", "supplier_id"])
    sup["main_ocid"] = sup["main_ocid"].astype("string")
    sup["awards_id"] = sup["awards_id"].astype("string")
    sup["supplier_id"] = sup["supplier_id"].astype("string")
    sup = sup.drop_duplicates(["main_ocid", "awards_id", "supplier_id"])

    filas = []
    for (ocid, award_id), g in sup.groupby(["main_ocid", "awards_id"], sort=False):
        ids = sorted(g["supplier_id"].dropna().astype(str).unique())
        if not ids:
            continue
        if len(ids) == 1:
            id_proveedor = ids[0]
            es_consorcio = False
        else:
            # Identificador estable y sin colisiones por truncar la lista de RUC.
            digest = hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:16]
            id_proveedor = f"CONSORCIO:{digest}"
            es_consorcio = True
        filas.append({
            "main_ocid": str(ocid),
            "award_id": str(award_id),
            "id_proveedor": id_proveedor,
            "es_consorcio": es_consorcio,
            "n_integrantes": len(ids),
            "integrantes_consorcio": ";".join(ids) if len(ids) > 1 else pd.NA,
        })
    return pd.DataFrame(filas)


def construir_contratos(main, contracts, awards, awards_suppliers):
    """Construye una fila por contrato con el supplier de SU adjudicación.

    Contratos sin awardID válido o sin suppliers vinculados se excluyen del
    dataset analítico proveedor-dependiente y se reportan, en vez de asignarles
    por aproximación todos los suppliers del proceso.
    """
    for nombre, df, columnas in (
        ("main.csv", main, {"ocid", "buyer_id"}),
        ("contracts.csv", contracts, {"main_ocid", "id", "awardID", "value_amount", "dateSigned"}),
        ("awards.csv", awards, {"main_ocid", "id"}),
    ):
        faltantes = columnas - set(df.columns)
        if faltantes:
            raise KeyError(f"{nombre} no contiene columnas requeridas: {sorted(faltantes)}")

    main_cols = [
        "ocid", "buyer_id", "tender_procurementMethodDetails", "tender_mainProcurementCategory"
    ]
    main_sel = main.copy()
    for col in main_cols:
        if col not in main_sel:
            main_sel[col] = pd.NA
    main_sel = main_sel[main_cols].drop_duplicates("ocid")

    c = contracts.copy()
    c["main_ocid"] = c["main_ocid"].astype("string")
    c["id"] = c["id"].astype("string")
    c["awardID"] = c["awardID"].astype("string")

    a = awards[["main_ocid", "id"]].copy().rename(columns={"id": "award_id"})
    a["main_ocid"] = a["main_ocid"].astype("string")
    a["award_id"] = a["award_id"].astype("string")
    a = a.drop_duplicates(["main_ocid", "award_id"])

    suppliers_por_award = _agrupar_suppliers_por_award(awards_suppliers)

    base = c.merge(
        main_sel,
        left_on="main_ocid", right_on="ocid", how="left", validate="many_to_one",
    )
    base = base.merge(
        a,
        left_on=["main_ocid", "awardID"], right_on=["main_ocid", "award_id"],
        how="left", validate="many_to_one",
    )

    n_sin_award = int(base["award_id"].isna().sum())
    base = base.merge(
        suppliers_por_award,
        on=["main_ocid", "award_id"], how="left", validate="many_to_one",
    )
    n_sin_supplier = int(base["id_proveedor"].isna().sum())

    descripcion = base["description"] if "description" in base else pd.Series(pd.NA, index=base.index)
    categoria_principal = base["tender_mainProcurementCategory"]

    df = pd.DataFrame({
        # OCDS: contract.id es único dentro del proceso; la clave analítica debe
        # incluir el OCID para no colisionar entre procesos.
        "id_contrato": base["main_ocid"].astype(str) + "::" + base["id"].astype(str),
        "id_contrato_fuente": base["id"],
        "ocid": base["main_ocid"],
        "award_id": base["award_id"],
        "id_proveedor": base["id_proveedor"],
        "es_consorcio": base["es_consorcio"],
        "n_integrantes_consorcio": base["n_integrantes"],
        "integrantes_consorcio": base["integrantes_consorcio"],
        "id_entidad": base["buyer_id"],
        "modalidad": base["tender_procurementMethodDetails"],
        "categoria_principal": categoria_principal,
        "descripcion_contrato": descripcion,
        "objeto": descripcion.apply(categorizar_objeto),
        "monto": pd.to_numeric(base["value_amount"], errors="coerce"),
        "fecha_contrato": pd.to_datetime(base["dateSigned"], errors="coerce", utc=True).dt.tz_localize(None),
    })

    antes = len(df)
    df = df.dropna(subset=["monto", "fecha_contrato", "id_entidad", "id_proveedor", "award_id"])
    df = df[df["monto"] > 0]
    df = df.drop_duplicates(subset=["id_contrato"])

    print("\nIntegridad OCDS contrato → adjudicación → supplier:")
    print(f"  Contratos crudos: {len(contracts):,}")
    print(f"  Sin awardID/adjudicación resoluble: {n_sin_award:,}")
    print(f"  Sin supplier resoluble para su adjudicación: {n_sin_supplier:,}")
    print(f"  Excluidos por vínculo/campos críticos/monto: {antes - len(df):,}")
    print(f"  Contratos analíticos válidos: {len(df):,}")
    print(f"  Clave compuesta OCID::contract.id única: {df['id_contrato'].is_unique}")
    return df


def main():
    print("Cargando archivos crudos OCDS...")
    main_df, contracts, awards, awards_suppliers, parties = cargar_crudos()
    print(
        f"  main: {len(main_df):,} | contracts: {len(contracts):,} | "
        f"awards: {len(awards):,} | awards_suppliers: {len(awards_suppliers):,} | "
        f"parties: {len(parties):,}"
    )

    entidades = construir_entidades(parties)
    proveedores = construir_proveedores(parties)
    contratos = construir_contratos(main_df, contracts, awards, awards_suppliers)

    entidades.to_csv(RUTA / "entidades_reales.csv", index=False)
    proveedores.to_csv(RUTA / "proveedores_reales.csv", index=False)
    contratos.to_csv(RUTA / "contratos_reales.csv", index=False)

    print(f"\nEntidades compradoras: {len(entidades):,}")
    print(f"Proveedores individuales en parties: {len(proveedores):,}")
    print(f"Contratos reales analíticos: {len(contratos):,}")
    print(f"Consorcios adjudicatarios distintos: {contratos.loc[contratos['es_consorcio'] == True, 'id_proveedor'].nunique():,}")
    print("\nDistribución de categoría OCDS:")
    print(contratos["categoria_principal"].value_counts(dropna=False))
    print("\nDistribución de objeto derivado:")
    print(contratos["objeto"].value_counts())
    print("\nDistribución de modalidad:")
    print(contratos["modalidad"].value_counts())
    print(f"\nRango de fechas: {contratos['fecha_contrato'].min()} a {contratos['fecha_contrato'].max()}")
    print(f"Monto total: S/. {contratos['monto'].sum():,.0f}")


if __name__ == "__main__":
    main()
