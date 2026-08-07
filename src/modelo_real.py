"""
Pipeline de análisis sobre datos REALES de SEACE/OECE.

IMPORTANTE: los conteos históricos del repositorio (por ejemplo, 47,442
contratos) corresponden a una ejecución previa. Desde la corrección P0 de
integridad OCDS, el dataset debe regenerarse mediante
src/cargar_datos_reales_seace.py antes de considerar vigentes los rankings
*_REAL.csv. La nueva carga respeta Contract -> Award -> Supplier y usa
OCID::contract.id como clave analítica.

Diferencias metodológicas honestas frente al pipeline sintético:

  1. FAVORITISMO: no hay ground truth real. Se usa un score de riesgo NO
     SUPERVISADO como priorización para revisión por auditor, no como hallazgo.
  2. FRACCIONAMIENTO: se aplica una SEÑAL de compras repetitivas en ventana
     corta y montos cercanos al límite del procedimiento simplificado/abreviado.
     El motor normativo se parametriza por año, régimen y categoría contractual;
     la señal NO determina jurídicamente que exista fraccionamiento.
  3. VÍNCULOS: no hay funcionarios individuales en SEACE abierto. Se adapta a
     nivel organizacional proveedor-entidad con la información pública disponible.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from umbrales_normativos import obtener_umbral

MODALIDADES_NO_COMPETITIVAS = {
    "Contratación Directa", "Comparación de Precios", "Adjudicación Selectiva",
    "Procedimiento Especial de Contratación", "Régimen Especial",
}


def cargar():
    return pd.read_csv("data_real/contratos_reales.csv", parse_dates=["fecha_contrato"])


# ---------------------------------------------------------------------------
# FAVORITISMO (no supervisado)
# ---------------------------------------------------------------------------
def features_favoritismo_real(df):
    df = df.copy()
    df["no_competitiva"] = df["modalidad"].isin(MODALIDADES_NO_COMPETITIVAS)

    grp = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        monto_promedio=("monto", "mean"),
        n_objetos_unicos=("objeto", "nunique"),
        pct_no_competitiva=("no_competitiva", "mean"),
        fecha_min=("fecha_contrato", "min"),
        fecha_max=("fecha_contrato", "max"),
    ).reset_index()

    grp = grp[grp["n_contratos"] >= 2]
    grp["dias_actividad"] = (grp["fecha_max"] - grp["fecha_min"]).dt.days.clip(lower=1)
    grp["concentracion_objeto"] = 1 - (grp["n_objetos_unicos"] / grp["n_contratos"])
    grp["contratos_por_mes"] = grp["n_contratos"] / (grp["dias_actividad"] / 30)
    return grp.drop(columns=["fecha_min", "fecha_max"])


def score_favoritismo_real(feats):
    cols = ["n_contratos", "monto_total", "monto_promedio", "pct_no_competitiva",
            "concentracion_objeto", "contratos_por_mes"]
    X = StandardScaler().fit_transform(feats[cols])
    modelo = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
    modelo.fit(X)
    feats = feats.copy()
    feats["score_riesgo"] = -modelo.decision_function(X)

    # Heurística contextual: pagos de muy bajo monto pueden corresponder a
    # personas/evaluadores agrupados por la fuente y necesitan interpretación.
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

        # La categoría estructurada OCDS tiene prioridad sobre el texto libre.
        # Si el CSV fue generado con una versión antigua y no contiene
        # categoria_principal, el motor usa su fallback textual conservador.
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
            umbrales_fila = g["fecha_contrato"].apply(
                lambda f: obtener_umbral(f, objeto=obj)
            )

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
    """Marca una señal de priorización; no constituye hallazgo jurídico."""
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
    proveedores = pd.read_csv("data_real/proveedores_reales.csv")
    entidades = pd.read_csv("data_real/entidades_reales.csv")

    pares = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"), monto_total=("monto", "sum"),
    ).reset_index()

    tel_prov = proveedores.set_index("id_proveedor")["telefono"]
    dir_prov = proveedores.set_index("id_proveedor")["direccion"]
    tel_ent = entidades.set_index("id_entidad")["telefono"]
    dir_ent = entidades.set_index("id_entidad")["direccion"]

    pares["comparte_telefono"] = pares.apply(
        lambda r: pd.notna(tel_prov.get(r["id_proveedor"]))
        and tel_prov.get(r["id_proveedor"]) == tel_ent.get(r["id_entidad"]),
        axis=1,
    )
    pares["comparte_direccion"] = pares.apply(
        lambda r: pd.notna(dir_prov.get(r["id_proveedor"]))
        and dir_prov.get(r["id_proveedor"]) == dir_ent.get(r["id_entidad"]),
        axis=1,
    )
    pares["senal_organizacional"] = pares["comparte_telefono"] | pares["comparte_direccion"]
    return pares


def main():
    print("Cargando contratos reales regenerados...")
    df = cargar()
    print(
        f"{len(df):,} contratos analíticos, {df['id_proveedor'].nunique():,} proveedores/consorcios, "
        f"{df['id_entidad'].nunique():,} entidades\n"
    )

    print("=" * 60)
    print("FAVORITISMO (score de riesgo no supervisado)")
    print("=" * 60)
    feats_fav = features_favoritismo_real(df)
    print(f"Pares proveedor-entidad con ≥2 contratos: {len(feats_fav):,}")
    ranking_fav = score_favoritismo_real(feats_fav)
    ranking_fav.to_csv("outputs/ranking_riesgo_favoritismo_REAL.csv", index=False)
    print("\nTop 15 pares proveedor-entidad por score de riesgo (señal, no hallazgo):")
    print(
        ranking_fav[
            ["id_proveedor", "id_entidad", "n_contratos", "monto_total",
             "pct_no_competitiva", "concentracion_objeto", "score_riesgo"]
        ].head(15).to_string(index=False)
    )

    print("\n" + "=" * 60)
    print("POSIBLE FRACCIONAMIENTO (señal normativa para revisión)")
    print("=" * 60)
    feats_frac = aplicar_regla_fraccionamiento(features_fraccionamiento_real(df))
    print(f"Grupos proveedor-entidad-objeto con ≥2 contratos: {len(feats_frac):,}")
    marcados = feats_frac[feats_frac["cumple_regla_fraccionamiento"]]
    print(f"Grupos priorizados por la señal: {len(marcados):,}")
    feats_frac.sort_values("max_contratos_ventana_15d", ascending=False).to_csv(
        "outputs/ranking_riesgo_fraccionamiento_REAL.csv", index=False
    )
    print("\nTop 15 señales priorizadas:")
    print(
        marcados.sort_values("max_contratos_ventana_15d", ascending=False)[
            ["id_proveedor", "id_entidad", "objeto", "n_contratos_grupo",
             "max_contratos_ventana_15d", "pct_montos_bajo_umbral", "monto_total_grupo"]
        ].head(15).to_string(index=False)
    )

    print("\n" + "=" * 60)
    print("VÍNCULOS (adaptado a nivel organizacional, sin funcionarios)")
    print("=" * 60)
    vinculos = vinculos_organizacionales(df)
    vinculos.to_csv("outputs/ranking_vinculos_organizacionales_REAL.csv", index=False)
    marcados_v = vinculos[vinculos["senal_organizacional"]]
    print(
        f"Pares proveedor-entidad con teléfono/dirección compartidos: "
        f"{len(marcados_v)} de {len(vinculos):,}"
    )
    if len(marcados_v):
        print(marcados_v.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
