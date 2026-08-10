"""
Preprocesamiento y Feature Engineering — Segundo/Quinto Producto del TDR.

La ruta operacional separa explícitamente FIT (solo TRAIN) de TRANSFORM
(TRAIN/INFERENCE), congela estadísticas aprendidas y mantiene Contratación
Directa y Comparación de Precios como variables distintas.

Favoritismo operacional usa ``monto_capped`` (P99 aprendido únicamente en
TRAIN). Fraccionamiento conserva el monto sin capar porque compara cuantías con
umbrales normativos.

La ruta ``limpiar_e_imputar`` se conserva exclusivamente para reproducibilidad
histórica. Los flujos TRAIN/INFERENCE nuevos usan el contrato corregido.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from core.objeto_similarity import firma_objeto
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
    """Reconstrucción legacy exacta del benchmark anterior al TRAIN explícito."""
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


def _seleccionar_ventana_15d_pandas(g: pd.DataFrame) -> tuple[int, float]:
    """Elige una sola ventana: máximo número de contratos, empate por inicio más temprano."""
    g = g.sort_values(["fecha_contrato", "id_contrato"], kind="mergesort")
    mejor_n = 1
    mejor_monto = float(g.iloc[0]["monto"])
    for fecha_i in g["fecha_contrato"]:
        ventana = g[
            (g["fecha_contrato"] >= fecha_i)
            & (g["fecha_contrato"] <= fecha_i + pd.Timedelta(days=15))
        ]
        n = int(len(ventana))
        if n > mejor_n:
            mejor_n = n
            mejor_monto = float(ventana["monto"].sum())
    return mejor_n, mejor_monto


def features_fraccionamiento(
    df: pd.DataFrame,
    label_col: str | None = "es_fraccionamiento_real",
    output_label: str | None = None,
) -> pd.DataFrame:
    """Construye grupos proveedor-entidad-familia de objeto y ventanas coherentes.

    ``objeto_familia`` es una firma lexical conservadora. Permite que variantes
    menores/sinónimos controlados se analicen juntas sin ocultar el texto
    representativo original. La ventana reporta monto y cantidad del MISMO
    intervalo de 15 días.
    """
    base = df.copy()
    if "categoria_principal" in base.columns:
        categorias = base["categoria_principal"]
    else:
        categorias = pd.Series([None] * len(base), index=base.index)
    base["objeto_familia"] = [
        firma_objeto(obj, cat) for obj, cat in zip(base["objeto"], categorias)
    ]
    base = base.sort_values(["fecha_contrato", "id_contrato"], kind="mergesort")

    filas = []
    for (prov, ent, familia), g in base.groupby(
        ["id_proveedor", "id_entidad", "objeto_familia"], dropna=False
    ):
        if len(g) < 2:
            continue
        g = g.sort_values(["fecha_contrato", "id_contrato"], kind="mergesort")
        max_n_ventana, max_monto_ventana = _seleccionar_ventana_15d_pandas(g)
        fechas = g["fecha_contrato"].tolist()
        montos = g["monto"].to_numpy()
        categorias_g = (
            g["categoria_principal"].tolist()
            if "categoria_principal" in g.columns
            else [None] * len(g)
        )
        objeto_representativo = str(g["objeto"].mode().iloc[0]) if not g["objeto"].mode().empty else str(g.iloc[0]["objeto"])
        umbrales = np.array([
            obtener_umbral(f, objeto=o, categoria_principal=c)
            for f, o, c in zip(fechas, g["objeto"].tolist(), categorias_g)
        ])
        pct_bajo_umbral = float((montos < umbrales * 0.95).mean())

        fila = {
            "id_proveedor": prov,
            "id_entidad": ent,
            "objeto": objeto_representativo,
            "objeto_familia": familia,
            "n_contratos_grupo": int(len(g)),
            "max_contratos_ventana_15d": int(max_n_ventana),
            "monto_total_ventana_15d": float(max_monto_ventana),
            "pct_montos_bajo_umbral": pct_bajo_umbral,
            "monto_total_grupo": float(montos.sum()),
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
    # Reproduce artefactos legacy para trazabilidad histórica; TRAIN/INFERENCE
    # modernos usan las funciones FIT/TRANSFORM anteriores.
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
