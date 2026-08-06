"""
Carga de datos REALES de SEACE (Sistema Electrónico de Contrataciones del
Estado), obtenidos del portal público de datos abiertos OCDS de la OECE
(https://data.open-contracting.org/en/publication/135), año 2022,
licencia CC BY 4.0.

A diferencia de src/generar_datos.py (sintético), este script transforma
datos reales de contrataciones públicas del Perú al mismo esquema que usa
el resto del pipeline (contratos_siaf_seace.csv), permitiendo correr el
prototipo completo sobre datos verdaderos.

LIMITACIÓN IMPORTANTE Y DOCUMENTADA: el estándar OCDS registra
organizaciones (compradores y proveedores), NO funcionarios públicos
individuales. No existe un campo "funcionario responsable" en SEACE
abierto — esa información, si existe, estaría en sistemas internos de
cada entidad, no en datos abiertos. Por eso este dataset NO incluye
id_funcionario; el análisis de vínculos (src/vinculos_reales.py) se
adapta a nivel organizacional en vez de proveedor-funcionario.
"""

import re
import pandas as pd

RUTA = "data_real"

# Clasificador de "objeto" por palabras clave sobre la descripción real del
# contrato — SEACE abierto no trae una categoría fija como el dataset
# sintético, así que se deriva de texto libre. Orden = prioridad de match.
CATEGORIAS_OBJETO = [
    ("Salud y medicamentos", r"salud|m[ée]dic|hospital|medicamento|farmac|quir[uú]rgic|cl[ií]nic|sanitari|reactivo|laboratorio|inmunohematolog|traslado.*pacientes"),
    ("Obra vial y construcción", r"obra|v[ií]al|carretera|pavimenta|construcci[oó]n|infraestructura|rehabilitaci[oó]n"),
    ("Limpieza y vigilancia", r"limpieza|vigilancia|seguridad f[ií]sica|guardian[ií]a|residuos s[oó]lidos"),
    ("Equipos informáticos y tecnología", r"inform[aá]tic|computad|software|licencia.*(microsoft|windows)|tecnolog[ií]a"),
    ("Consultoría y servicios profesionales", r"consultor[ií]a|asesor[ií]a|perito|honorarios profesionales|expediente t[eé]cnico|notificaci[oó]n"),
    ("Alimentación", r"aliment|v[ií]veres|raciones|desayuno escolar|qali warma|leche evaporada"),
    ("Transporte y combustible", r"transporte|combustible|gasolina|petr[oó]leo|flete"),
    ("Mantenimiento de infraestructura", r"mantenimiento|reparaci[oó]n"),
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


def cargar_crudos():
    main = pd.read_csv(f"{RUTA}/main.csv")
    contracts = pd.read_csv(f"{RUTA}/contracts.csv")
    parties = pd.read_csv(f"{RUTA}/parties.csv")
    return main, contracts, parties


def construir_entidades(parties):
    compradores = parties[parties["roles"] == "buyer,procuringEntity"].drop_duplicates("id")
    entidades = compradores.rename(columns={
        "id": "id_entidad", "name": "nombre_entidad",
        "address_streetAddress": "direccion", "contactPoint_telephone": "telefono",
    })[["id_entidad", "nombre_entidad", "direccion", "telefono", "address_department"]]
    return entidades


def construir_proveedores(parties):
    proveedores = parties[parties["roles"].str.contains("supplier", na=False)].copy()
    proveedores = proveedores.drop_duplicates("identifier_id")
    proveedores = proveedores.rename(columns={
        "identifier_id": "id_proveedor", "name": "razon_social",
        "address_streetAddress": "direccion", "contactPoint_telephone": "telefono",
    })[["id_proveedor", "razon_social", "direccion", "telefono"]]
    proveedores = proveedores.dropna(subset=["id_proveedor"])
    return proveedores


def construir_contratos(main, contracts, parties):
    """Un contrato = una fila. Cuando varias empresas postulan juntas
    (consorcio), NO se explota en una fila por integrante — eso infla
    artificialmente los conteos de concentración y fraccionamiento (se
    verificó el caso real: un contrato con 23 empresas tageadas como
    'supplier' generaba 23 filas idénticas). Se representa el consorcio
    como una única entidad compuesta, igual que aparecería en un reporte
    real de auditoría ("Consorcio X-Y-Z")."""
    suppliers = parties[parties["roles"].str.contains("supplier", na=False)][
        ["main_ocid", "identifier_id", "name"]
    ].dropna(subset=["identifier_id"])

    def agrupar_consorcio(g):
        rucs = sorted(g["identifier_id"].astype(str).unique())
        if len(rucs) == 1:
            return pd.Series({"id_proveedor": rucs[0], "es_consorcio": False, "n_integrantes": 1})
        nombre_compuesto = "CONSORCIO:" + "+".join(rucs[:3]) + ("+..." if len(rucs) > 3 else "")
        return pd.Series({"id_proveedor": nombre_compuesto, "es_consorcio": True, "n_integrantes": len(rucs)})

    suppliers_por_proceso = suppliers.groupby("main_ocid").apply(agrupar_consorcio, include_groups=False).reset_index()

    base = contracts.merge(
        main[["ocid", "buyer_id", "tender_procurementMethodDetails", "tender_mainProcurementCategory"]],
        left_on="main_ocid", right_on="ocid", how="left",
    )
    base = base.merge(suppliers_por_proceso, on="main_ocid", how="inner")

    df = pd.DataFrame({
        "id_contrato": base["id"],
        "id_proveedor": base["id_proveedor"],
        "es_consorcio": base["es_consorcio"],
        "n_integrantes_consorcio": base["n_integrantes"],
        "id_entidad": base["buyer_id"],
        "modalidad": base["tender_procurementMethodDetails"],
        "objeto": base["description"].apply(categorizar_objeto),
        "monto": base["value_amount"],
        "fecha_contrato": pd.to_datetime(base["dateSigned"], utc=True).dt.tz_localize(None),
    })
    df = df.dropna(subset=["monto", "fecha_contrato", "id_entidad", "id_proveedor"])
    df = df[df["monto"] > 0]
    df = df.drop_duplicates(subset=["id_contrato"])  # un contrato = una fila, garantizado
    return df


def main():
    print("Cargando archivos crudos (esto toma unos segundos por el tamaño)...")
    main_df, contracts, parties = cargar_crudos()
    print(f"  main: {len(main_df):,} procesos | contracts: {len(contracts):,} | parties: {len(parties):,}")

    entidades = construir_entidades(parties)
    proveedores = construir_proveedores(parties)
    contratos = construir_contratos(main_df, contracts, parties)

    entidades.to_csv("data_real/entidades_reales.csv", index=False)
    proveedores.to_csv("data_real/proveedores_reales.csv", index=False)
    contratos.to_csv("data_real/contratos_reales.csv", index=False)

    print(f"\nEntidades (compradoras) reales: {len(entidades):,}")
    print(f"Proveedores reales (con RUC): {len(proveedores):,}")
    print(f"Contratos reales construidos: {len(contratos):,}")
    print(f"\nDistribución de 'objeto' derivado por palabras clave:")
    print(contratos["objeto"].value_counts())
    print(f"\nDistribución de modalidad:")
    print(contratos["modalidad"].value_counts())
    print(f"\nRango de fechas: {contratos['fecha_contrato'].min()} a {contratos['fecha_contrato'].max()}")
    print(f"Monto total: S/. {contratos['monto'].sum():,.0f}")


if __name__ == "__main__":
    main()
