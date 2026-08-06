"""
Preprocesamiento y Feature Engineering — Segundo/Quinto Producto del TDR.

Cubre lo pedido en el numeral 4.1.4 (Limpieza y Transformación) y 4.1.5
(Enriquecimiento y Generación de Características), y el checklist del
Anexo 3 (ítem 2: "Justificación estadística de nulos y outliers").

Genera dos datasets listos para modelar:
  - data/dataset_favoritismo.csv      → nivel proveedor+entidad
  - data/dataset_fraccionamiento.csv  → nivel proveedor+entidad+objeto (ventanas)

NOTA: la columna `*_real` se conserva únicamente como ground truth para
validar los modelos del prototipo (sabemos qué sembramos). En un dataset
real de producción esta etiqueta no existe de antemano — los modelos de
favoritismo/fraccionamiento operan de forma no supervisada o con
retroalimentación de los auditores (ver 3.2.c del TDR: "estrategias de
sostenibilidad del modelo" / auto-entrenamiento).
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, OneHotEncoder

UMBRAL_ADJ_SIMPLIFICADA = 400_000
MODALIDADES_NO_COMPETITIVAS = {"Contratación Directa", "Comparación de Precios"}


def cargar():
    return pd.read_csv("data/contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])


def limpiar_e_imputar(df):
    """Imputación de nulos y tratamiento de outliers (checklist ítem 2)."""
    df = df.copy()
    n_antes = df.isnull().sum().sum()

    # Imputación: monto -> mediana por objeto (más robusto que la media global,
    # ya que las medias log-normales se distorsionan con la cola larga)
    df["monto"] = df.groupby("objeto")["monto"].transform(lambda s: s.fillna(s.median()))
    df["monto"] = df["monto"].fillna(df["monto"].median())  # residual si objeto también era nulo

    # Categóricas -> moda
    for col in ["modalidad", "objeto"]:
        df[col] = df[col].fillna(df[col].mode().iloc[0])

    # Tratamiento de outliers: winsorización al percentil 99 (no se eliminan,
    # se capan, porque un monto alto real es justamente lo que puede interesar
    # a un auditor — eliminarlo perdería la señal)
    p99 = df["monto"].quantile(0.99)
    df["monto_capped"] = df["monto"].clip(upper=p99)

    n_despues = df.isnull().sum().sum()
    print(f"Valores nulos: {n_antes} → {n_despues} (imputados)")
    print(f"Outliers capados al percentil 99 (S/. {p99:,.0f}): "
          f"{(df['monto'] > p99).sum()} registros")
    return df


def codificar_y_normalizar(df):
    """Codificación de categóricas + normalización de numéricas."""
    df = df.copy()
    scaler = StandardScaler()
    df["monto_norm"] = scaler.fit_transform(df[["monto_capped"]])

    ohe = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    modalidad_ohe = ohe.fit_transform(df[["modalidad"]])
    modalidad_cols = [f"modalidad_{c}" for c in ohe.categories_[0]]
    modalidad_df = pd.DataFrame(modalidad_ohe, columns=modalidad_cols, index=df.index)

    df = pd.concat([df, modalidad_df], axis=1)
    df["es_modalidad_no_competitiva"] = df["modalidad"].isin(MODALIDADES_NO_COMPETITIVAS)
    return df


def features_favoritismo(df):
    """Feature engineering a nivel proveedor+entidad (numeral 4.1.5)."""
    grp = df.groupby(["id_proveedor", "id_entidad"])
    feats = grp.agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        monto_promedio=("monto", "mean"),
        n_objetos_unicos=("objeto", "nunique"),
        pct_no_competitiva=("es_modalidad_no_competitiva", "mean"),
        n_funcionarios_distintos=("id_funcionario", "nunique"),
        fecha_min=("fecha_contrato", "min"),
        fecha_max=("fecha_contrato", "max"),
        label_favoritismo_real=("es_favoritismo_real", "max"),  # solo para validar
    ).reset_index()

    feats["dias_actividad"] = (feats["fecha_max"] - feats["fecha_min"]).dt.days.clip(lower=1)
    feats["concentracion_objeto"] = 1 - (feats["n_objetos_unicos"] / feats["n_contratos"])
    feats["contratos_por_mes"] = feats["n_contratos"] / (feats["dias_actividad"] / 30)
    feats["monto_por_funcionario"] = feats["monto_total"] / feats["n_funcionarios_distintos"]

    feats = feats.drop(columns=["fecha_min", "fecha_max"])
    return feats


def features_fraccionamiento(df):
    """Feature engineering a nivel proveedor+entidad+objeto, con ventanas
    temporales (numeral 4.1.5 y 4.2.3 del TDR)."""
    df = df.sort_values("fecha_contrato")
    grp = df.groupby(["id_proveedor", "id_entidad", "objeto"])

    filas = []
    for (prov, ent, obj), g in grp:
        if len(g) < 2:
            continue
        g = g.sort_values("fecha_contrato")
        fechas = g["fecha_contrato"].values
        montos = g["monto"].values

        # Ventana deslizante de 15 días: máximo n° de contratos y suma de montos
        max_n_ventana, max_monto_ventana = 1, montos[0]
        for i in range(len(g)):
            ventana = g[(g["fecha_contrato"] >= fechas[i]) &
                        (g["fecha_contrato"] <= fechas[i] + pd.Timedelta(days=15))]
            if len(ventana) > max_n_ventana:
                max_n_ventana = len(ventana)
                max_monto_ventana = ventana["monto"].sum()

        pct_bajo_umbral = (montos < UMBRAL_ADJ_SIMPLIFICADA * 0.95).mean()

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
    df = cargar()
    df = limpiar_e_imputar(df)
    df = codificar_y_normalizar(df)
    df.to_csv("data/contratos_procesados.csv", index=False)

    fav = features_favoritismo(df)
    fav.to_csv("data/dataset_favoritismo.csv", index=False)
    print(f"\nDataset de favoritismo: {len(fav)} pares proveedor-entidad, "
          f"{fav['label_favoritismo_real'].sum()} con favoritismo real sembrado")

    frac = features_fraccionamiento(df)
    frac.to_csv("data/dataset_fraccionamiento.csv", index=False)
    print(f"Dataset de fraccionamiento: {len(frac)} grupos proveedor-entidad-objeto (≥2 contratos), "
          f"{frac['label_fraccionamiento_real'].sum()} con fraccionamiento real sembrado")


if __name__ == "__main__":
    main()
