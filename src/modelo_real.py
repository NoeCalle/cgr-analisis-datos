"""
Pipeline de análisis sobre datos REALES de SEACE (47,442 contratos reales
tras deduplicar consorcios — ver cargar_datos_reales_seace.py, función
construir_contratos), año de descarga 2022, con contratos de ejecución
que se extienden en el tiempo.

Diferencias metodológicas honestas frente al pipeline sintético
(src/modelo_favoritismo.py, src/modelo_fraccionamiento.py):

  1. FAVORITISMO: no hay ground truth real (no sabemos qué proveedores
     efectivamente incurrieron en favoritismo). No se puede entrenar ni
     validar un clasificador supervisado. Se reemplaza por un score de
     riesgo NO SUPERVISADO (Isolation Forest sobre las mismas variables
     de concentración/competitividad), presentado como lista de
     candidatos para revisión de auditor — exactamente el caso de uso
     real que describe el TDR ("dar soporte a los auditores"), no un
     clasificador con métricas de accuracy validadas.

  2. FRACCIONAMIENTO: el modelo original (ventana de 15 días + umbral
     legal S/. 400,000) NO depende de etiquetas — se aplica sin cambios
     sobre fechas y montos reales.

  3. VÍNCULOS: no hay funcionarios individuales en SEACE abierto. Se
     redefine a nivel organizacional: ¿un proveedor comparte teléfono o
     dirección con la ENTIDAD compradora misma? (una señal más débil que
     proveedor-funcionario individual, pero la única disponible con datos
     100% reales).
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

MODALIDADES_NO_COMPETITIVAS = {
    "Contratación Directa", "Comparación de Precios", "Adjudicación Selectiva",
    "Procedimiento Especial de Contratación", "Régimen Especial",
}
UMBRAL_ADJ_SIMPLIFICADA = 400_000


def cargar():
    df = pd.read_csv("data_real/contratos_reales.csv", parse_dates=["fecha_contrato"])
    return df


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

    grp = grp[grp["n_contratos"] >= 2]  # concentración solo tiene sentido con relación repetida
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

    # Anotación honesta: se verificó un caso real donde "consorcios" con
    # muchos integrantes resultaron ser evaluadores individuales pagados
    # por lotes (montos < S/. 5,000 c/u) en un programa de investigación,
    # NO empresas licitando juntas. Esto NO se filtra (sería ocultar el
    # dato) — se anota para que el auditor lo interprete correctamente.
    feats["posible_pago_individual_agrupado"] = (
        feats["monto_promedio"] < 5000
    )
    return feats.sort_values("score_riesgo", ascending=False)


# ---------------------------------------------------------------------------
# FRACCIONAMIENTO (reglas, sin cambios metodológicos)
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
            ventana = g[(g["fecha_contrato"] >= fecha_i) & (g["fecha_contrato"] <= fecha_i + pd.Timedelta(days=15))]
            if len(ventana) > max_n_ventana:
                max_n_ventana = len(ventana)
                max_monto_ventana = ventana["monto"].sum()
        pct_bajo_umbral = (g["monto"] < UMBRAL_ADJ_SIMPLIFICADA * 0.95).mean()
        filas.append({
            "id_proveedor": prov, "id_entidad": ent, "objeto": obj,
            "n_contratos_grupo": len(g), "max_contratos_ventana_15d": max_n_ventana,
            "monto_total_ventana_15d": max_monto_ventana, "pct_montos_bajo_umbral": pct_bajo_umbral,
            "monto_total_grupo": g["monto"].sum(),
        })
    return pd.DataFrame(filas)


def aplicar_regla_fraccionamiento(feats):
    feats = feats.copy()
    feats["cumple_regla_fraccionamiento"] = (
        (feats["max_contratos_ventana_15d"] >= 3) & (feats["pct_montos_bajo_umbral"] >= 0.7)
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
        lambda r: pd.notna(tel_prov.get(r["id_proveedor"])) and
                  tel_prov.get(r["id_proveedor"]) == tel_ent.get(r["id_entidad"]), axis=1)
    pares["comparte_direccion"] = pares.apply(
        lambda r: pd.notna(dir_prov.get(r["id_proveedor"])) and
                  dir_prov.get(r["id_proveedor"]) == dir_ent.get(r["id_entidad"]), axis=1)
    pares["senal_organizacional"] = pares["comparte_telefono"] | pares["comparte_direccion"]
    return pares


def main():
    print("Cargando contratos reales...")
    df = cargar()
    print(f"{len(df):,} contratos, {df['id_proveedor'].nunique():,} proveedores, "
          f"{df['id_entidad'].nunique():,} entidades\n")

    print("=" * 60)
    print("FAVORITISMO (score de riesgo no supervisado)")
    print("=" * 60)
    feats_fav = features_favoritismo_real(df)
    print(f"Pares proveedor-entidad con ≥2 contratos: {len(feats_fav):,}")
    ranking_fav = score_favoritismo_real(feats_fav)
    ranking_fav.to_csv("outputs/ranking_riesgo_favoritismo_REAL.csv", index=False)
    print("\nTop 15 pares proveedor-entidad por score de riesgo:")
    print(ranking_fav[["id_proveedor", "id_entidad", "n_contratos", "monto_total",
                        "pct_no_competitiva", "concentracion_objeto", "score_riesgo"]]
          .head(15).to_string(index=False))

    print("\n" + "=" * 60)
    print("FRACCIONAMIENTO (regla + umbral legal, sin cambios)")
    print("=" * 60)
    feats_frac = features_fraccionamiento_real(df)
    feats_frac = aplicar_regla_fraccionamiento(feats_frac)
    print(f"Grupos proveedor-entidad-objeto con ≥2 contratos: {len(feats_frac):,}")
    marcados = feats_frac[feats_frac["cumple_regla_fraccionamiento"]]
    print(f"Grupos que cumplen la regla de fraccionamiento: {len(marcados):,}")
    feats_frac.sort_values("max_contratos_ventana_15d", ascending=False).to_csv(
        "outputs/ranking_riesgo_fraccionamiento_REAL.csv", index=False)
    print("\nTop 15 casos marcados:")
    print(marcados.sort_values("max_contratos_ventana_15d", ascending=False)
          [["id_proveedor", "id_entidad", "objeto", "n_contratos_grupo",
            "max_contratos_ventana_15d", "pct_montos_bajo_umbral", "monto_total_grupo"]]
          .head(15).to_string(index=False))

    print("\n" + "=" * 60)
    print("VÍNCULOS (adaptado a nivel organizacional, sin funcionarios)")
    print("=" * 60)
    vinculos = vinculos_organizacionales(df)
    vinculos.to_csv("outputs/ranking_vinculos_organizacionales_REAL.csv", index=False)
    marcados_v = vinculos[vinculos["senal_organizacional"]]
    print(f"Pares proveedor-entidad con teléfono/dirección compartidos: {len(marcados_v)} de {len(vinculos):,}")
    if len(marcados_v):
        print(marcados_v.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
