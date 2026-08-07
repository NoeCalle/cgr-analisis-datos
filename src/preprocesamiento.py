"""
Preprocesamiento y Feature Engineering — Segundo/Quinto Producto del TDR.

P1:
- Contratación Directa y Comparación de Precios son features separadas.
- La cuantía de fraccionamiento usa `categoria_principal` cuando existe;
  el texto `objeto` queda solo como fallback.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from umbrales_normativos import obtener_umbral


def cargar():
    return pd.read_csv("data/contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])


def limpiar_e_imputar(df):
    df = df.copy()
    n_antes = df.isnull().sum().sum()
    df["monto"] = df.groupby("objeto")["monto"].transform(lambda s: s.fillna(s.median()))
    df["monto"] = df["monto"].fillna(df["monto"].median())
    for col in ["modalidad", "objeto"]:
        df[col] = df[col].fillna(df[col].mode().iloc[0])
    p99 = df["monto"].quantile(0.99)
    df["monto_capped"] = df["monto"].clip(upper=p99)
    print(f"Valores nulos: {n_antes} → {df.isnull().sum().sum()}")
    print(f"Outliers capados al P99 (S/. {p99:,.0f}): {(df['monto'] > p99).sum()}")
    return df


def codificar_y_normalizar(df):
    df = df.copy()
    df["monto_norm"] = StandardScaler().fit_transform(df[["monto_capped"]])
    ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    modalidad_ohe = ohe.fit_transform(df[["modalidad"]])
    modalidad_cols = [f"modalidad_{c}" for c in ohe.categories_[0]]
    df = pd.concat(
        [df, pd.DataFrame(modalidad_ohe, columns=modalidad_cols, index=df.index)], axis=1
    )
    df["es_contratacion_directa"] = df["modalidad"].eq("Contratación Directa")
    df["es_comparacion_precios"] = df["modalidad"].eq("Comparación de Precios")
    return df


def features_favoritismo(df):
    feats = df.groupby(["id_proveedor", "id_entidad"]).agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        monto_promedio=("monto", "mean"),
        n_objetos_unicos=("objeto", "nunique"),
        pct_contratacion_directa=("es_contratacion_directa", "mean"),
        pct_comparacion_precios=("es_comparacion_precios", "mean"),
        n_funcionarios_distintos=("id_funcionario", "nunique"),
        fecha_min=("fecha_contrato", "min"),
        fecha_max=("fecha_contrato", "max"),
        label_favoritismo_real=("es_favoritismo_real", "max"),
    ).reset_index()
    feats["dias_actividad"] = (feats["fecha_max"] - feats["fecha_min"]).dt.days.clip(lower=1)
    feats["concentracion_objeto"] = 1 - (feats["n_objetos_unicos"] / feats["n_contratos"])
    feats["contratos_por_mes"] = feats["n_contratos"] / (feats["dias_actividad"] / 30)
    feats["monto_por_funcionario"] = feats["monto_total"] / feats["n_funcionarios_distintos"].clip(lower=1)
    return feats.drop(columns=["fecha_min", "fecha_max"])


def features_fraccionamiento(df):
    df = df.sort_values("fecha_contrato")
    filas = []
    for (prov, ent, obj), g in df.groupby(["id_proveedor", "id_entidad", "objeto"]):
        if len(g) < 2:
            continue
        g = g.sort_values("fecha_contrato")
        fechas = g["fecha_contrato"].tolist()
        montos = g["monto"].to_numpy()
        max_n_ventana, max_monto_ventana = 1, montos[0]
        for fecha_i in fechas:
            ventana = g[
                (g["fecha_contrato"] >= fecha_i)
                & (g["fecha_contrato"] <= fecha_i + pd.Timedelta(days=15))
            ]
            if len(ventana) > max_n_ventana:
                max_n_ventana = len(ventana)
                max_monto_ventana = ventana["monto"].sum()

        categorias = (
            g["categoria_principal"].tolist()
            if "categoria_principal" in g.columns
            else [None] * len(g)
        )
        umbrales = np.array([
            obtener_umbral(f, objeto=obj, categoria_principal=c)
            for f, c in zip(fechas, categorias)
        ])
        pct_bajo_umbral = (montos < umbrales * 0.95).mean()

        filas.append({
            "id_proveedor": prov,
            "id_entidad": ent,
            "objeto": obj,
            "n_contratos_grupo": len(g),
            "max_contratos_ventana_15d": max_n_ventana,
            "monto_total_ventana_15d": max_monto_ventana,
            "pct_montos_bajo_umbral": pct_bajo_umbral,
            "monto_total_grupo": montos.sum(),
            "label_fraccionamiento_real": bool(g["es_fraccionamiento_real"].max()),
        })
    return pd.DataFrame(filas)


def main():
    df = codificar_y_normalizar(limpiar_e_imputar(cargar()))
    df.to_csv("data/contratos_procesados.csv", index=False)
    fav = features_favoritismo(df)
    fav.to_csv("data/dataset_favoritismo.csv", index=False)
    frac = features_fraccionamiento(df)
    frac.to_csv("data/dataset_fraccionamiento.csv", index=False)
    print(
        f"Favoritismo: {len(fav)} pares / {int(fav['label_favoritismo_real'].sum())} positivos.\n"
        f"Fraccionamiento: {len(frac)} grupos / {int(frac['label_fraccionamiento_real'].sum())} positivos."
    )


if __name__ == "__main__":
    main()
