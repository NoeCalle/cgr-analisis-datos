"""
Preprocesamiento y Feature Engineering — Segundo/Quinto Producto del TDR.

Sprint 2:
- separa explícitamente FIT (solo TRAIN) de TRANSFORM (TRAIN/INFERENCE);
- el estado aprendido de imputación se puede persistir junto al modelo;
- las funciones de features aceptan labels opcionales, por lo que el scoring
  de contratos actuales no necesita ground truth;
- Contratación Directa y Comparación de Precios permanecen separadas;
- fraccionamiento mantiene montos reales/imputados para comparaciones normativas.

Sprint 4 hace consumible el tratamiento P99 en favoritismo: la función acepta
``monto_col``. La reconstrucción legacy mantiene ``monto`` para reproducir RC1;
TRAIN/INFERENCE modernos usan ``monto_capped``. Fraccionamiento continúa usando
monto sin capar porque compara cuantías contra umbrales normativos.

La función `limpiar_e_imputar` conserva deliberadamente la semántica histórica
usada para reconstruir las métricas del RC1. Esa ruta presentaba un efecto de
`groupby(..., dropna=True)`: cuando `objeto` era nulo, el `transform` reemplazaba
incluso montos válidos por NaN antes de la mediana global. El nuevo contrato
TRAIN/INFERENCE NO replica ese defecto; un monto válido siempre se conserva.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from umbrales_normativos import obtener_umbral

PREPROCESSOR_SCHEMA_VERSION = 1


def cargar():
    return pd.read_csv("data/contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])


def ajustar_estado_preprocesamiento(df: pd.DataFrame) -> dict:
    """Aprende estadísticas de limpieza. Debe ejecutarse únicamente en TRAIN."""
    base = df.copy()
    base["monto"] = pd.to_numeric(base["monto"], errors="coerce")

    medianas_objeto = (
        base.groupby("objeto", dropna=True)["monto"]
        .median()
        .dropna()
        .to_dict()
    )
    monto_parcial = base["monto"].fillna(base["objeto"].map(medianas_objeto))
    mediana_global = float(monto_parcial.median())
    monto_imputado = monto_parcial.fillna(mediana_global)

    modalidad_moda = _moda_o_error(base["modalidad"], "modalidad")
    objeto_moda = _moda_o_error(base["objeto"], "objeto")
    p99 = float(monto_imputado.quantile(0.99))

    return {
        "schema_version": PREPROCESSOR_SCHEMA_VERSION,
        "monto_mediana_por_objeto": {str(k): float(v) for k, v in medianas_objeto.items()},
        "monto_mediana_global": mediana_global,
        "modalidad_moda": str(modalidad_moda),
        "objeto_moda": str(objeto_moda),
        "monto_p99": p99,
    }


def aplicar_estado_preprocesamiento(df: pd.DataFrame, estado: dict) -> pd.DataFrame:
    """Aplica estadísticas ya aprendidas; no recalcula parámetros con el lote actual."""
    if estado.get("schema_version") != PREPROCESSOR_SCHEMA_VERSION:
        raise ValueError(
            "Estado de preprocesamiento incompatible: "
            f"schema_version={estado.get('schema_version')!r}."
        )

    out = df.copy()
    out["fecha_contrato"] = pd.to_datetime(out["fecha_contrato"], errors="raise")
    out["monto"] = pd.to_numeric(out["monto"], errors="coerce")

    medianas_objeto = estado["monto_mediana_por_objeto"]
    medianas_fila = out["objeto"].astype("string").map(medianas_objeto)
    out["monto"] = out["monto"].fillna(medianas_fila)
    out["monto"] = out["monto"].fillna(float(estado["monto_mediana_global"]))
    out["modalidad"] = out["modalidad"].fillna(estado["modalidad_moda"])
    out["objeto"] = out["objeto"].fillna(estado["objeto_moda"])
    out["monto_capped"] = out["monto"].clip(upper=float(estado["monto_p99"]))

    if "id_funcionario" not in out.columns:
        out["id_funcionario"] = "__NO_DISPONIBLE__"
    else:
        out["id_funcionario"] = out["id_funcionario"].fillna("__NO_DISPONIBLE__")

    out["es_contratacion_directa"] = out["modalidad"].eq("Contratación Directa")
    out["es_comparacion_precios"] = out["modalidad"].eq("Comparación de Precios")
    return out


def preparar_para_features_entrenamiento(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """FIT + TRANSFORM explícito para el flujo de entrenamiento."""
    estado = ajustar_estado_preprocesamiento(df)
    return aplicar_estado_preprocesamiento(df, estado), estado


def preparar_para_features_inferencia(df: pd.DataFrame, estado: dict) -> pd.DataFrame:
    """Solo TRANSFORM. Nunca aprende estadísticas del lote que se está puntuando."""
    return aplicar_estado_preprocesamiento(df, estado)


def limpiar_e_imputar(df):
    """Reconstrucción legacy exacta del benchmark anterior a Sprint 2.

    Se mantiene aislada para que `reproducibilidad_poc_1_8_2` pueda regenerar
    métricas históricas. No debe utilizarse en TRAIN ni en INFERENCE nuevos.
    """
    out = df.copy()
    n_antes = int(out.isnull().sum().sum())

    out["monto"] = out.groupby("objeto")["monto"].transform(
        lambda s: s.fillna(s.median())
    )
    out["monto"] = out["monto"].fillna(out["monto"].median())
    for col in ["modalidad", "objeto"]:
        out[col] = out[col].fillna(out[col].mode().iloc[0])

    p99 = float(out["monto"].quantile(0.99))
    out["monto_capped"] = out["monto"].clip(upper=p99)
    print(f"Valores nulos: {n_antes} → {out.isnull().sum().sum()}")
    print(f"Outliers capados al P99 (S/. {p99:,.0f}): {(out['monto'] > p99).sum()}")
    return out


def codificar_y_normalizar(df):
    """Transformaciones exploratorias históricas; no son requeridas por serving."""
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


def features_favoritismo(
    df: pd.DataFrame,
    label_col: str | None = "es_favoritismo_real",
    output_label: str | None = None,
    monto_col: str = "monto",
) -> pd.DataFrame:
    if monto_col not in df.columns:
        raise ValueError(f"Columna de monto para favoritismo no existe: {monto_col!r}")
    aggs = {
        "n_contratos": ("id_contrato", "count"),
        "monto_total": (monto_col, "sum"),
        "monto_promedio": (monto_col, "mean"),
        "n_objetos_unicos": ("objeto", "nunique"),
        "pct_contratacion_directa": ("es_contratacion_directa", "mean"),
        "pct_comparacion_precios": ("es_comparacion_precios", "mean"),
        "n_funcionarios_distintos": ("id_funcionario", "nunique"),
        "fecha_min": ("fecha_contrato", "min"),
        "fecha_max": ("fecha_contrato", "max"),
    }
    if label_col is not None:
        if label_col not in df.columns:
            raise ValueError(f"Label de favoritismo configurado no existe: {label_col}")
        aggs[output_label or label_col] = (label_col, "max")

    feats = df.groupby(["id_proveedor", "id_entidad"]).agg(**aggs).reset_index()
    feats["dias_actividad"] = (feats["fecha_max"] - feats["fecha_min"]).dt.days.clip(lower=1)
    feats["concentracion_objeto"] = 1 - (feats["n_objetos_unicos"] / feats["n_contratos"])
    feats["contratos_por_mes"] = feats["n_contratos"] / (feats["dias_actividad"] / 30)
    feats["monto_por_funcionario"] = feats["monto_total"] / feats["n_funcionarios_distintos"].clip(lower=1)
    return feats.drop(columns=["fecha_min", "fecha_max"])


def features_fraccionamiento(
    df: pd.DataFrame,
    label_col: str | None = "es_fraccionamiento_real",
    output_label: str | None = None,
) -> pd.DataFrame:
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

        fila = {
            "id_proveedor": prov,
            "id_entidad": ent,
            "objeto": obj,
            "n_contratos_grupo": len(g),
            "max_contratos_ventana_15d": max_n_ventana,
            "monto_total_ventana_15d": max_monto_ventana,
            "pct_montos_bajo_umbral": pct_bajo_umbral,
            "monto_total_grupo": montos.sum(),
        }
        if label_col is not None:
            if label_col not in g.columns:
                raise ValueError(f"Label de fraccionamiento configurado no existe: {label_col}")
            fila[output_label or label_col] = bool(g[label_col].max())
        filas.append(fila)
    return pd.DataFrame(filas)


def _moda_o_error(series: pd.Series, campo: str):
    moda = series.dropna().mode()
    if moda.empty:
        raise ValueError(f"No se puede ajustar preprocesamiento: {campo} no tiene valores válidos.")
    return moda.iloc[0]


def main():
    # Reproduce los artefactos y métricas legacy del PoC. Los flujos nuevos usan
    # `preparar_para_features_entrenamiento/inferencia` y no esta ruta.
    df = codificar_y_normalizar(limpiar_e_imputar(cargar()))
    df.to_csv("data/contratos_procesados.csv", index=False)
    fav = features_favoritismo(
        df,
        label_col="es_favoritismo_real",
        output_label="label_favoritismo_real",
    )
    fav.to_csv("data/dataset_favoritismo.csv", index=False)
    frac = features_fraccionamiento(
        df,
        label_col="es_fraccionamiento_real",
        output_label="label_fraccionamiento_real",
    )
    frac.to_csv("data/dataset_fraccionamiento.csv", index=False)
    print(
        f"Favoritismo: {len(fav)} pares / {int(fav['label_favoritismo_real'].sum())} positivos.\n"
        f"Fraccionamiento: {len(frac)} grupos / {int(frac['label_fraccionamiento_real'].sum())} positivos."
    )


if __name__ == "__main__":
    main()
