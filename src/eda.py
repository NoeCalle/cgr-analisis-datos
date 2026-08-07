"""
Análisis Exploratorio de Datos (EDA) — numeral 4.1.1 del TDR.

Genera evidencia descriptiva previa al modelado. No convierte patrones
estadísticos en hallazgos. P1 evita agrupar Contratación Directa y Comparación
de Precios bajo la misma etiqueta de "poco competitivas"; se reportan por
separado para que la interpretación normativa quede en manos del análisis
correspondiente.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

CHARTS_DIR = Path("outputs/charts")


def cargar_datos():
    contratos = pd.read_csv("data/contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])
    proveedores = pd.read_csv("data/proveedores.csv")
    entidades = pd.read_csv("data/entidades.csv")
    return contratos, proveedores, entidades


def resumen_calidad_datos(df):
    print("=" * 60)
    print("1. ESTRUCTURA Y CALIDAD DE DATOS")
    print("=" * 60)
    print(f"Registros totales: {len(df):,}")
    print(f"Rango de fechas: {df['fecha_contrato'].min().date()} a {df['fecha_contrato'].max().date()}")
    nulos = df.isnull().sum()
    print("\nValores faltantes por columna:")
    print(nulos[nulos > 0])
    print(f"% con al menos un nulo: {df.isnull().any(axis=1).mean()*100:.2f}%")


def grafico_distribucion_montos(df):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(df["monto"].dropna(), bins=60)
    ax.set_title("Distribución de montos")
    ax.set_xlabel("Monto (S/.)")
    ax.set_ylabel("N° de contratos")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "01_distribucion_montos.png", dpi=130)
    plt.close()

    q1, q3 = df["monto"].quantile([0.25, 0.75])
    limite = q3 + 1.5 * (q3 - q1)
    n = int((df["monto"] > limite).sum())
    print(f"Outliers descriptivos por IQR (monto > {limite:,.0f}): {n} ({n/len(df)*100:.2f}%)")


def grafico_modalidades(df):
    counts = df["modalidad"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    counts.plot(kind="barh", ax=ax)
    ax.set_title("N° de contratos por modalidad/procedimiento")
    ax.set_xlabel("N° de contratos")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "02_modalidades_contratacion.png", dpi=130)
    plt.close()
    print("\nDistribución por modalidad:")
    print(counts)


def grafico_concentracion_proveedores(df, top_n=15):
    top = df["id_proveedor"].value_counts().head(top_n)
    fig, ax = plt.subplots(figsize=(8, 5))
    top.plot(kind="barh", ax=ax)
    ax.set_title(f"Top {top_n} proveedores por número de contratos")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "03_concentracion_proveedores.png", dpi=130)
    plt.close()


def grafico_serie_temporal(df):
    serie = df.set_index("fecha_contrato").resample("ME")["monto"].agg(["count", "sum"])
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(serie.index, serie["count"])
    ax.set_title("Evolución mensual del número de contratos")
    ax.set_ylabel("N° de contratos")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "04_serie_temporal.png", dpi=130)
    plt.close()


def analisis_senales_preliminares(df):
    print("\n" + "=" * 60)
    print("2. SEÑALES PRELIMINARES PARA MODELADO")
    print("=" * 60)

    grp = df.groupby(["id_proveedor", "id_entidad", "objeto"]).agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        rango_dias=("fecha_contrato", lambda s: (s.max() - s.min()).days),
    ).reset_index()
    ventana = grp[(grp["n_contratos"] >= 3) & (grp["rango_dias"] <= 15)]
    print(f"Proveedor-entidad-objeto con ≥3 contratos en ≤15 días: {len(ventana)}")

    for modalidad in ["Contratación Directa", "Comparación de Precios"]:
        subset = df[df["modalidad"].eq(modalidad)]
        concentracion = subset.groupby(["id_proveedor", "id_entidad"]).size()
        concentracion = concentracion[concentracion >= 5].sort_values(ascending=False)
        print(f"Pares proveedor-entidad con ≥5 contratos en {modalidad}: {len(concentracion)}")

    hard_negatives = df[df.get("escenario_sintetico", pd.Series(index=df.index, dtype="string")).eq(
        "hard_negative_concentracion_legitima"
    )]
    if len(hard_negatives):
        print(f"Hard negatives legítimos incluidos para desafiar el modelo: {len(hard_negatives)} contratos")


def main():
    contratos, _, _ = cargar_datos()
    resumen_calidad_datos(contratos)
    grafico_distribucion_montos(contratos)
    grafico_modalidades(contratos)
    grafico_concentracion_proveedores(contratos)
    grafico_serie_temporal(contratos)
    analisis_senales_preliminares(contratos)
    print(f"\nGráficos guardados en {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
