"""
Diccionario de datos y diagrama del modelo — numeral 3.2.g del TDR.

La documentación se genera desde una definición única para reducir la deriva
entre código y entregables. Las señales de riesgo no se describen como
hallazgos jurídicos.
"""

import pandas as pd
from graphviz import Digraph

DICCIONARIO = [
    ("contratos_siaf_seace", "id_contrato", "string", "Identificador único del contrato en el dataset sintético; en OCDS real se usa OCID::contract.id.", "SEACE/OCDS (simulado o real)"),
    ("contratos_siaf_seace", "id_proveedor", "string (FK)", "Referencia al adjudicatario del contrato.", "SEACE/OCDS"),
    ("contratos_siaf_seace", "id_entidad", "string (FK)", "Entidad pública contratante.", "SEACE/OCDS"),
    ("contratos_siaf_seace", "id_funcionario", "string (FK)", "Funcionario responsable del proceso; solo existe en el escenario sintético/institucional, no en OCDS abierto.", "SIAF/legajo (simulado)"),
    ("contratos_siaf_seace", "modalidad", "categórica", "Modalidad/procedimiento de contratación publicado por la fuente.", "SEACE/OCDS"),
    ("contratos_siaf_seace", "objeto", "categórica", "Categoría temática derivada o simulada del objeto contractual.", "Derivado / simulado"),
    ("contratos_siaf_seace", "categoria_principal", "categórica", "Categoría estructurada OCDS: goods, services o works; tiene prioridad para seleccionar el contexto normativo cuando está disponible.", "OCDS mainProcurementCategory"),
    ("contratos_siaf_seace", "monto", "numérico (S/.)", "Monto contractual.", "SEACE/OCDS / SIAF"),
    ("contratos_siaf_seace", "fecha_contrato", "fecha", "Fecha de suscripción del contrato.", "SEACE/OCDS"),
    ("contratos_siaf_seace", "es_favoritismo_real", "booleano", "Ground truth sembrado solo para validación sintética; no existe en producción.", "Generado para el prototipo"),
    ("contratos_siaf_seace", "es_fraccionamiento_real", "booleano", "Ground truth sembrado solo para validación sintética; no existe en producción.", "Generado para el prototipo"),

    ("proveedores", "id_proveedor", "string (PK)", "Identificador canónico del proveedor/adjudicatario.", "RNP/SEACE/OCDS"),
    ("proveedores", "ruc", "string", "RUC cuando la fuente lo publica.", "RNP/SUNAT/OCDS"),
    ("proveedores", "razon_social", "string", "Razón social o nombre del adjudicatario.", "RNP/SEACE/OCDS"),

    ("entidades", "id_entidad", "string (PK)", "Identificador de la entidad pública contratante.", "SEACE/OCDS"),
    ("entidades", "nombre_entidad", "string", "Nombre de la entidad pública contratante.", "SEACE/OCDS"),

    ("funcionarios", "id_funcionario", "string (PK)", "Identificador interno/sintético del funcionario.", "Legajo institucional (simulado)"),
    ("funcionarios", "dni_funcionario", "string", "DNI para cruces autorizados en un entorno institucional; sintético en el PoC.", "RENIEC/legajo (simulado)"),
    ("funcionarios", "id_entidad", "string (FK)", "Entidad a la que pertenece el funcionario.", "Legajo institucional (simulado)"),

    ("dataset_favoritismo", "id_proveedor / id_entidad", "string (FK compuesta)", "Clave del par proveedor-entidad agregado.", "Derivado"),
    ("dataset_favoritismo", "n_contratos", "numérico", "Número de contratos del proveedor en la entidad.", "Derivado"),
    ("dataset_favoritismo", "monto_total / monto_promedio", "numérico (S/.)", "Monto acumulado y promedio del par.", "Derivado"),
    ("dataset_favoritismo", "pct_contratacion_directa", "numérico [0-1]", "Proporción de contratos del par bajo Contratación Directa.", "Derivado"),
    ("dataset_favoritismo", "pct_comparacion_precios", "numérico [0-1]", "Proporción de contratos del par bajo Comparación de Precios; se mantiene separada de Contratación Directa.", "Derivado"),
    ("dataset_favoritismo", "concentracion_objeto", "numérico [0-1]", "1 − objetos distintos / número de contratos; mayor valor indica mayor concentración temática.", "Derivado"),
    ("dataset_favoritismo", "score_riesgo_favoritismo", "numérico", "Score de priorización producido por el modelo; no constituye hallazgo.", "Modelo (salida)"),

    ("dataset_fraccionamiento", "id_proveedor / id_entidad / objeto", "string (FK compuesta)", "Clave del grupo proveedor-entidad-objeto.", "Derivado"),
    ("dataset_fraccionamiento", "max_contratos_ventana_15d", "numérico", "Máximo número de contratos dentro de una ventana móvil de 15 días.", "Derivado"),
    ("dataset_fraccionamiento", "pct_montos_bajo_umbral", "numérico [0-1]", "Proporción de contratos bajo el 95% de la cuantía parametrizada para el año/régimen/categoría aplicable.", "Derivado + motor normativo"),
    ("dataset_fraccionamiento", "score_anomalia", "numérico", "Score del detector estadístico de anomalías; mayor valor = mayor prioridad relativa según la implementación.", "Modelo (salida)"),
    ("dataset_fraccionamiento", "cumple_regla_fraccionamiento", "booleano", "Señal interpretable: ≥3 contratos en 15 días y ≥70% bajo el 95% de la cuantía parametrizada. Es una alerta para revisión, no una conclusión jurídica.", "Regla de priorización"),
]


def generar_diccionario():
    df = pd.DataFrame(DICCIONARIO, columns=["tabla", "columna", "tipo", "descripcion", "fuente"])
    df.to_csv("data/diccionario_datos.csv", index=False)
    print(f"Diccionario generado: {len(df)} elementos en {df['tabla'].nunique()} tablas.")
    return df


def generar_diagrama():
    g = Digraph("modelo_datos", format="png")
    g.attr(rankdir="LR", fontname="Arial", fontsize="11", bgcolor="white")
    g.attr("node", shape="plaintext", fontname="Arial")

    def tabla_html(nombre, columnas, color_header="#2b6cb0"):
        filas = "".join(f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{c}</FONT></TD></TR>' for c in columnas)
        return (
            f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">'
            f'<TR><TD BGCOLOR="{color_header}"><FONT COLOR="white"><B>{nombre}</B></FONT></TD></TR>'
            f'{filas}</TABLE>>'
        )

    g.node("proveedores", tabla_html("proveedores", ["id_proveedor (PK)", "ruc", "razon_social"]))
    g.node("entidades", tabla_html("entidades", ["id_entidad (PK)", "nombre_entidad"]))
    g.node("funcionarios", tabla_html("funcionarios", ["id_funcionario (PK)", "dni_funcionario", "id_entidad (FK)"]))
    g.node("contratos", tabla_html(
        "contratos (tabla de hechos)",
        ["id_contrato (PK)", "id_proveedor (FK)", "id_entidad (FK)", "id_funcionario (FK, si aplica)",
         "modalidad", "categoria_principal", "objeto", "monto", "fecha_contrato"],
        color_header="#c53030",
    ))
    g.node("dataset_favoritismo", tabla_html(
        "dataset_favoritismo (derivada)",
        ["id_proveedor + id_entidad", "n_contratos", "concentracion_objeto",
         "pct_contratacion_directa", "pct_comparacion_precios", "score_riesgo_favoritismo"],
        color_header="#6b46c1",
    ))
    g.node("dataset_fraccionamiento", tabla_html(
        "dataset_fraccionamiento (derivada)",
        ["id_proveedor + id_entidad + objeto", "max_contratos_ventana_15d",
         "pct_montos_bajo_umbral", "score_anomalia", "cumple_regla_fraccionamiento"],
        color_header="#6b46c1",
    ))

    g.edge("proveedores", "contratos", label="1 : N")
    g.edge("entidades", "contratos", label="1 : N")
    g.edge("funcionarios", "contratos", label="1 : N")
    g.edge("entidades", "funcionarios", label="1 : N")
    g.edge("contratos", "dataset_favoritismo", label="feature engineering", style="dashed")
    g.edge("contratos", "dataset_fraccionamiento", label="feature engineering", style="dashed")

    g.render("outputs/charts/09_diagrama_modelo_datos", cleanup=True)
    print("Diagrama generado en outputs/charts/09_diagrama_modelo_datos.png")


def main():
    generar_diccionario()
    generar_diagrama()


if __name__ == "__main__":
    main()
