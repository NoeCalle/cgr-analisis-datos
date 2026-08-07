"""
Pipeline de análisis sobre datos REALES de SEACE/OECE.

Los resultados son señales estadísticas para priorización de revisión; no son
hallazgos ni determinaciones de irregularidad.

Integridad P0: Contract -> Award -> Supplier, clave OCID::contract.id.
Corrección P1: Contratación Directa y Comparación de Precios se mantienen como
variables diferentes; no se agrupan bajo una etiqueta binaria de "no
competitiva".
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from umbrales_normativos import obtener_umbral


def cargar():
    return pd.read_csv("data_real/contratos_reales.csv", parse_dates=["fecha_contrato"])


# ---------------------------------------------------------------------------
# FAVORITISMO (no supervisado, señal de priorización)
# ---------------------------------------------------------------------------
def features_favoritismo_real(df):
    df = df.copy()
    df["es_contratacion_directa"] = df["modalidad"].eq("Contratación Directa")
    df["es_comparacion_precios"] = df["modalidad"].eq("Comparación de Precios")

    grp = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        monto_promedio=("monto", "mean"),
        n_objetos_unicos=("objeto", "nunique"),
        pct_contratacion_directa=("es_contratacion_directa", "mean"),
        pct_comparacion_precios=("es_comparacion_precios", "mean"),
        fecha_min=("fecha_contrato", "min"),
        fecha_max=("fecha_contrato", "max"),
    ).reset_index()

    grp = grp[grp["n_contratos"] >= 2]
    grp["dias_actividad"] = (grp["fecha_max"] - grp["fecha_min"]).dt.days.clip(lower=1)
    grp["concentracion_objeto"] = 1 - (grp["n_objetos_unicos"] / grp["n_contratos"])
    grp["contratos_por_mes"] = grp["n_contratos"] / (grp["dias_actividad"] / 30)
    return grp.drop(columns=["fecha_min", "fecha_max"])


def score_favoritismo_real(feats):
    cols = [
        "n_contratos", "monto_total", "monto_promedio",
        "pct_contratacion_directa", "pct_comparacion_precios",
        "concentracion_objeto", "contratos_por_mes",
    ]
    X = StandardScaler().fit_transform(feats[cols])
    modelo = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
    modelo.fit(X)
    feats = feats.copy()
    feats["score_riesgo"] = -modelo.decision_function(X)
    feats["posible_pago_individual_agrupado"] = feats["monto_promedio"] < 5000
    return feats.sort_values("score_riesgo", ascending=False)


# ---------------------------------------------------------------------------
# FRACCIONAMIENTO (señal de priorización, no conclusión jurídica)
# ---------------------------------------------------------------------------
def features_fraccionamiento_real(df):
    df = df.sort_values("fecha_contrato")
    grupos = df.groupby(["id_proveedor", "id_entidad", "objeto"])

    filas = []
    for (prov, ent, obj), g in grupos:
        if len(g) < 2:
            continue
        g = g.sort_values("fecha_contrato")
        max_n_ventana, max_monto_ventana = 1, g["monto"].iloc[0]
        for i in range(len(g)):
            fecha_i = g["fecha_contrato"].iloc[i]
            ventana = g[
                (g["fecha_contrato"] >= fecha_i)
                & (g["fecha_contrato"] <= fecha_i + pd.Timedelta(days=15))
            ]
            if len(ventana) > max_n_ventana:
                max_n_ventana = len(ventana)
                max_monto_ventana = ventana["monto"].sum()

        if "categoria_principal" in g.columns:
            umbrales_fila = g.apply(
                lambda r: obtener_umbral(
                    r["fecha_contrato"],
                    objeto=obj,
                    categoria_principal=r.get("categoria_principal"),
                ),
                axis=1,
            )
        else:
            umbrales_fila = g["fecha_contrato"].apply(lambda f: obtener_umbral(f, objeto=obj))

        pct_bajo_umbral = (g["monto"] < umbrales_fila * 0.95).mean()
        filas.append({
            "id_proveedor": prov,
            "id_entidad": ent,
            "objeto": obj,
            "n_contratos_grupo": len(g),
            "max_contratos_ventana_15d": max_n_ventana,
            "monto_total_ventana_15d": max_monto_ventana,
            "pct_montos_bajo_umbral": pct_bajo_umbral,
            "monto_total_grupo": g["monto"].sum(),
        })
    return pd.DataFrame(filas)


def aplicar_regla_fraccionamiento(feats):
    feats = feats.copy()
    feats["cumple_regla_fraccionamiento"] = (
        (feats["max_contratos_ventana_15d"] >= 3)
        & (feats["pct_montos_bajo_umbral"] >= 0.7)
    )
    return feats


# ---------------------------------------------------------------------------
# VÍNCULOS (adaptado a nivel organizacional — SIN funcionarios individuales)
# ---------------------------------------------------------------------------
def vinculos_organizacionales(df):
    proveedores = pd.read_csv("data_real/proveedores_reales.csv", dtype={"id_proveedor": "string"})
    entidades = pd.read_csv("data_real/entidades_reales.csv", dtype={"id_entidad": "string"})
    df = df.copy()
    df["id_proveedor"] = df["id_proveedor"].astype("string")
    df["id_entidad"] = df["id_entidad"].astype("string")

    pares = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"), monto_total=("monto", "sum"),
    ).reset_index()

    tel_prov = proveedores.set_index("id_proveedor")["telefono"]
    dir_prov = proveedores.set_index("id_proveedor")["direccion"]
    tel_ent = entidades.set_index("id_entidad")["telefono"]
    dir_ent = entidades.set_index("id_entidad")["direccion"]

    def coincide(a, b):
        return pd.notna(a) and pd.notna(b) and str(a).strip() == str(b).strip()

    pares["comparte_telefono"] = [
        coincide(tel_prov.get(p), tel_ent.get(e)) for p, e in zip(pares["id_proveedor"], pares["id_entidad"])
    ]
    pares["comparte_direccion"] = [
        coincide(dir_prov.get(p), dir_ent.get(e)) for p, e in zip(pares["id_proveedor"], pares["id_entidad"])
    ]
    pares["senal_organizacional"] = pares["comparte_telefono"] | pares["comparte_direccion"]
    return pares


def main():
    print("Cargando contratos reales regenerados...")
    df = cargar()
    print(
        f"{len(df):,} contratos analíticos, {df['id_proveedor'].nunique():,} adjudicatarios, "
        f"{df['id_entidad'].nunique():,} entidades\n"
    )

    fav = score_favoritismo_real(features_favoritismo_real(df))
    fav.to_csv("outputs/ranking_riesgo_favoritismo_REAL.csv", index=False)
    print(f"Pares proveedor-entidad con ≥2 contratos: {len(fav):,}")
    print(fav[[
        "id_proveedor", "id_entidad", "n_contratos", "monto_total",
        "pct_contratacion_directa", "pct_comparacion_precios",
        "concentracion_objeto", "score_riesgo",
    ]].head(15).to_string(index=False))

    frac = aplicar_regla_fraccionamiento(features_fraccionamiento_real(df))
    frac.sort_values("max_contratos_ventana_15d", ascending=False).to_csv(
        "outputs/ranking_riesgo_fraccionamiento_REAL.csv", index=False
    )
    print(f"\nGrupos proveedor-entidad-objeto con ≥2 contratos: {len(frac):,}")
    print(f"Grupos priorizados por señal: {int(frac['cumple_regla_fraccionamiento'].sum()):,}")

    vinculos = vinculos_organizacionales(df)
    vinculos.to_csv("outputs/ranking_vinculos_organizacionales_REAL.csv", index=False)
    print(f"Pares proveedor-entidad evaluados para vínculos: {len(vinculos):,}")
    print(f"Señales por teléfono/dirección compartidos: {int(vinculos['senal_organizacional'].sum()):,}")


if __name__ == "__main__":
    main()
