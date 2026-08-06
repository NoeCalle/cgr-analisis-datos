"""
Análisis Exploratorio de Datos (EDA) — Segundo Producto (parte 1) del TDR.

Corresponde al numeral 4.1.1 del TDR: "Análisis Exploratorio de Datos (EDA):
Realizar un análisis exploratorio profundo de los datos para comprender su
estructura, distribuciones, relaciones iniciales y la identificación de
anomalías."

Genera gráficos (outputs/charts/) y un resumen impreso que alimenta el
documento técnico del Segundo Producto.
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CHARTS_DIR = "outputs/charts"


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
    print("\nValores faltantes por columna:")
    nulos = df.isnull().sum()
    print(nulos[nulos > 0])
    print(f"\n% de registros con al menos un nulo: {df.isnull().any(axis=1).mean()*100:.2f}%")


def grafico_distribucion_montos(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].hist(df["monto"].dropna(), bins=60, color="#2b6cb0", edgecolor="white")
    axes[0].set_title("Distribución de montos (escala normal)")
    axes[0].set_xlabel("Monto (S/.)")
    axes[0].set_ylabel("N° de contratos")

    axes[1].boxplot(df["monto"].dropna(), vert=True)
    axes[1].set_title("Boxplot de montos (detección de outliers)")
    axes[1].set_ylabel("Monto (S/.)")
    plt.tight_layout()
    plt.savefig(f"{CHARTS_DIR}/01_distribucion_montos.png", dpi=130)
    plt.close()

    q1, q3 = df["monto"].quantile([0.25, 0.75])
    iqr = q3 - q1
    limite_superior = q3 + 1.5 * iqr
    n_outliers = (df["monto"] > limite_superior).sum()
    print(f"\nOutliers por método IQR (monto > {limite_superior:,.0f}): {n_outliers} contratos "
          f"({n_outliers/len(df)*100:.2f}%)")


def grafico_modalidades(df):
    counts = df["modalidad"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    counts.plot(kind="barh", ax=ax, color="#2b6cb0")
    ax.set_title("N° de contratos por modalidad de contratación")
    ax.set_xlabel("N° de contratos")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(f"{CHARTS_DIR}/02_modalidades_contratacion.png", dpi=130)
    plt.close()
    print("\nDistribución por modalidad:")
    print(counts)


def grafico_concentracion_proveedores(df, top_n=15):
    top = df["id_proveedor"].value_counts().head(top_n)
    fig, ax = plt.subplots(figsize=(8, 5))
    top.plot(kind="barh", ax=ax, color="#c53030")
    ax.set_title(f"Top {top_n} proveedores por N° de contratos ganados")
    ax.set_xlabel("N° de contratos")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(f"{CHARTS_DIR}/03_concentracion_proveedores.png", dpi=130)
    plt.close()
    print(f"\nTop {top_n} proveedores por N° de contratos:")
    print(top)


def grafico_serie_temporal(df):
    serie = df.set_index("fecha_contrato").resample("ME")["monto"].agg(["count", "sum"])
    fig, ax1 = plt.subplots(figsize=(10, 4.5))
    ax1.bar(serie.index, serie["count"], width=20, color="#2b6cb0", alpha=0.7, label="N° contratos")
    ax1.set_ylabel("N° de contratos", color="#2b6cb0")
    ax2 = ax1.twinx()
    ax2.plot(serie.index, serie["sum"], color="#c53030", label="Monto total")
    ax2.set_ylabel("Monto total (S/.)", color="#c53030")
    ax1.set_title("Evolución mensual: N° de contratos y monto total")
    plt.tight_layout()
    plt.savefig(f"{CHARTS_DIR}/04_serie_temporal.png", dpi=130)
    plt.close()


def analisis_pares_sospechosos(df):
    """Combinaciones proveedor+entidad+objeto con múltiples contratos en
    ventanas cortas — señal preliminar de fraccionamiento (se modela a
    fondo en el paso 5)."""
    print("\n" + "=" * 60)
    print("2. SEÑALES PRELIMINARES (para modelado posterior)")
    print("=" * 60)
    grp = df.groupby(["id_proveedor", "id_entidad", "objeto"]).agg(
        n_contratos=("id_contrato", "count"),
        monto_total=("monto", "sum"),
        rango_dias=("fecha_contrato", lambda s: (s.max() - s.min()).days),
    ).reset_index()
    sospechosos = grp[(grp["n_contratos"] >= 3) & (grp["rango_dias"] <= 15)]
    print(f"Combinaciones proveedor+entidad+objeto con ≥3 contratos en ≤15 días: {len(sospechosos)}")
    print(sospechosos.sort_values("n_contratos", ascending=False).head(10).to_string(index=False))

    print("\nConcentración proveedor-entidad con modalidades poco competitivas:")
    poco_competitivas = df[df["modalidad"].isin(["Contratación Directa", "Comparación de Precios"])]
    concentracion = poco_competitivas.groupby(["id_proveedor", "id_entidad"]).size()
    concentracion = concentracion[concentracion >= 5].sort_values(ascending=False)
    print(f"Pares proveedor-entidad con ≥5 contratos poco competitivos: {len(concentracion)}")
    print(concentracion.head(10))


def main():
    contratos, proveedores, entidades = cargar_datos()
    resumen_calidad_datos(contratos)
    grafico_distribucion_montos(contratos)
    grafico_modalidades(contratos)
    grafico_concentracion_proveedores(contratos)
    grafico_serie_temporal(contratos)
    analisis_pares_sospechosos(contratos)
    print(f"\nGráficos guardados en {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
