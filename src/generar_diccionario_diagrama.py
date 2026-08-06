"""
Diccionario de datos y Diagrama del Modelo de Datos — numeral 3.2.g del TDR:
"Proveer Documentación Técnica Completa y Validada: Elaborar y mantener
actualizado el diccionario y diagrama del modelo de datos..."

Genera:
  - data/diccionario_datos.csv   → una fila por columna, en todas las tablas
  - outputs/charts/09_diagrama_modelo_datos.png → diagrama entidad-relación
"""

import pandas as pd
from graphviz import Digraph

# ---------------------------------------------------------------------------
# 1. DICCIONARIO DE DATOS
# ---------------------------------------------------------------------------
DICCIONARIO = [
    # tabla, columna, tipo, descripción, fuente/origen
    ("contratos_siaf_seace", "id_contrato", "string", "Identificador único del contrato (simula clave de proceso SEACE).", "SEACE (simulado)"),
    ("contratos_siaf_seace", "id_proveedor", "string (FK)", "Referencia al proveedor adjudicado. Llave foránea a proveedores.id_proveedor.", "SEACE (simulado)"),
    ("contratos_siaf_seace", "id_entidad", "string (FK)", "Entidad pública contratante. Llave foránea a entidades.id_entidad.", "SEACE (simulado)"),
    ("contratos_siaf_seace", "id_funcionario", "string (FK)", "Funcionario responsable del proceso. Llave foránea a funcionarios.id_funcionario.", "SIAF (simulado)"),
    ("contratos_siaf_seace", "modalidad", "categórica", "Modalidad de contratación según la Ley de Contrataciones del Estado (Licitación Pública, Adjudicación Simplificada, Contratación Directa, etc.).", "SEACE (simulado)"),
    ("contratos_siaf_seace", "objeto", "categórica", "Tipo de bien, servicio u obra contratado.", "SEACE (simulado)"),
    ("contratos_siaf_seace", "monto", "numérico (S/.)", "Monto contractual en soles.", "SIAF (simulado)"),
    ("contratos_siaf_seace", "fecha_contrato", "fecha", "Fecha de suscripción del contrato.", "SEACE (simulado)"),
    ("contratos_siaf_seace", "es_favoritismo_real", "booleano", "Etiqueta de validación interna del prototipo (ground truth sintético). No existe en un dataset de producción.", "Generado para el prototipo"),
    ("contratos_siaf_seace", "es_fraccionamiento_real", "booleano", "Etiqueta de validación interna del prototipo (ground truth sintético). No existe en un dataset de producción.", "Generado para el prototipo"),

    ("proveedores", "id_proveedor", "string (PK)", "Identificador único del proveedor.", "RNP / SEACE (simulado)"),
    ("proveedores", "ruc", "string", "Registro Único de Contribuyente del proveedor.", "SUNAT (simulado)"),
    ("proveedores", "razon_social", "string", "Razón social del proveedor.", "RNP / SUNAT (simulado)"),

    ("entidades", "id_entidad", "string (PK)", "Identificador único de la entidad pública.", "SEACE (simulado)"),
    ("entidades", "nombre_entidad", "string", "Nombre de la entidad pública contratante.", "SEACE (simulado)"),

    ("funcionarios", "id_funcionario", "string (PK)", "Identificador único del funcionario.", "SIAF / legajo institucional (simulado)"),
    ("funcionarios", "dni_funcionario", "string", "Documento Nacional de Identidad del funcionario (para futuro cruce de vínculos, numeral 4.2.4).", "RENIEC (simulado)"),
    ("funcionarios", "id_entidad", "string (FK)", "Entidad a la que pertenece el funcionario. Llave foránea a entidades.id_entidad.", "Legajo institucional (simulado)"),

    ("dataset_favoritismo", "id_proveedor / id_entidad", "string (FK compuesta)", "Clave del par proveedor-entidad agregado.", "Derivado (feature engineering)"),
    ("dataset_favoritismo", "n_contratos", "numérico", "N° de contratos ganados por el proveedor en la entidad.", "Derivado"),
    ("dataset_favoritismo", "monto_total / monto_promedio", "numérico (S/.)", "Monto acumulado y promedio de los contratos del par.", "Derivado"),
    ("dataset_favoritismo", "pct_no_competitiva", "numérico [0-1]", "Proporción de contratos bajo modalidades poco competitivas (Contratación Directa, Comparación de Precios).", "Derivado"),
    ("dataset_favoritismo", "concentracion_objeto", "numérico [0-1]", "1 − (objetos distintos / n° contratos). Cercano a 1 = siempre el mismo tipo de objeto.", "Derivado"),
    ("dataset_favoritismo", "score_riesgo_favoritismo", "numérico [0-1]", "Salida del modelo Random Forest — probabilidad estimada de favoritismo.", "Modelo (salida)"),

    ("dataset_fraccionamiento", "id_proveedor / id_entidad / objeto", "string (FK compuesta)", "Clave del grupo proveedor-entidad-objeto.", "Derivado"),
    ("dataset_fraccionamiento", "max_contratos_ventana_15d", "numérico", "Máximo de contratos del grupo dentro de cualquier ventana móvil de 15 días.", "Derivado"),
    ("dataset_fraccionamiento", "pct_montos_bajo_umbral", "numérico [0-1]", "Proporción de contratos con monto < 95% del umbral de Adjudicación Simplificada (S/. 400,000).", "Derivado + regla normativa"),
    ("dataset_fraccionamiento", "score_anomalia", "numérico", "Salida del modelo Isolation Forest — score de anomalía (mayor = más atípico).", "Modelo (salida)"),
    ("dataset_fraccionamiento", "cumple_regla_fraccionamiento", "booleano", "Regla interpretable: ≥3 contratos en ventana de 15 días Y ≥70% de montos bajo el umbral.", "Modelo (salida, regla de negocio)"),
]


def generar_diccionario():
    df = pd.DataFrame(DICCIONARIO, columns=["tabla", "columna", "tipo", "descripcion", "fuente"])
    df.to_csv("data/diccionario_datos.csv", index=False)
    print(f"Diccionario de datos generado: {len(df)} columnas documentadas en {df['tabla'].nunique()} tablas.")
    return df


# ---------------------------------------------------------------------------
# 2. DIAGRAMA DEL MODELO DE DATOS (entidad-relación)
# ---------------------------------------------------------------------------
def generar_diagrama():
    g = Digraph("modelo_datos", format="png")
    g.attr(rankdir="LR", fontname="Arial", fontsize="11", bgcolor="white")
    g.attr("node", shape="plaintext", fontname="Arial")

    def tabla_html(nombre, columnas, color_header="#2b6cb0"):
        filas = "".join(
            f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{c}</FONT></TD></TR>' for c in columnas
        )
        return (
            f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">'
            f'<TR><TD BGCOLOR="{color_header}"><FONT COLOR="white"><B>{nombre}</B></FONT></TD></TR>'
            f'{filas}</TABLE>>'
        )

    # Tablas fuente (simulan SIAF/SEACE integrados)
    g.node("proveedores", tabla_html("proveedores", ["id_proveedor (PK)", "ruc", "razon_social"]))
    g.node("entidades", tabla_html("entidades", ["id_entidad (PK)", "nombre_entidad"]))
    g.node("funcionarios", tabla_html("funcionarios", ["id_funcionario (PK)", "dni_funcionario", "id_entidad (FK)"]))
    g.node("contratos", tabla_html(
        "contratos_siaf_seace (tabla de hechos)",
        ["id_contrato (PK)", "id_proveedor (FK)", "id_entidad (FK)", "id_funcionario (FK)",
         "modalidad", "objeto", "monto", "fecha_contrato"],
        color_header="#c53030",
    ))

    # Tablas derivadas (feature engineering / salida de modelos)
    g.node("dataset_favoritismo", tabla_html(
        "dataset_favoritismo (derivada)",
        ["id_proveedor + id_entidad", "n_contratos", "concentracion_objeto",
         "pct_no_competitiva", "score_riesgo_favoritismo"],
        color_header="#6b46c1",
    ))
    g.node("dataset_fraccionamiento", tabla_html(
        "dataset_fraccionamiento (derivada)",
        ["id_proveedor + id_entidad + objeto", "max_contratos_ventana_15d",
         "pct_montos_bajo_umbral", "score_anomalia"],
        color_header="#6b46c1",
    ))

    # Relaciones (claves foráneas)
    g.edge("proveedores", "contratos", label="1 : N")
    g.edge("entidades", "contratos", label="1 : N")
    g.edge("funcionarios", "contratos", label="1 : N")
    g.edge("entidades", "funcionarios", label="1 : N")

    # Linaje: de la tabla de hechos a las tablas derivadas (feature engineering)
    g.edge("contratos", "dataset_favoritismo", label="agregación\n(proveedor+entidad)", style="dashed")
    g.edge("contratos", "dataset_fraccionamiento", label="agregación\n(proveedor+entidad+objeto)", style="dashed")

    g.render("outputs/charts/09_diagrama_modelo_datos", cleanup=True)
    print("Diagrama del modelo de datos generado en outputs/charts/09_diagrama_modelo_datos.png")


def main():
    generar_diccionario()
    generar_diagrama()


if __name__ == "__main__":
    main()
