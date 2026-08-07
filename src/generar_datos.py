"""
Generador de datos sintéticos de contrataciones públicas.

Simula una integración SIAF/SEACE para probar el pipeline sin usar datos
internos. El ground truth es deliberadamente sintético y solo sirve para
validación funcional/metodológica.

Corrección P1:
- los casos de favoritismo ya no dependen de tratar Comparación de Precios como
  equivalente a Contratación Directa;
- se agregan hard negatives legítimos: alta concentración proveedor-entidad y
  objeto repetido, pero procedimientos predominantemente abiertos;
- los casos de fraccionamiento se siembran con la cuantía parametrizada para
  su fecha/objeto, no con un umbral fijo de S/400 mil.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from umbrales_normativos import obtener_umbral

RNG = np.random.default_rng(42)

N_CONTRATOS_NORMALES = 3500
N_PROVEEDORES = 220
N_ENTIDADES = 18
N_FUNCIONARIOS = 60
N_CASOS_LIMITE_LEGITIMOS = 12

MODALIDADES = [
    "Licitación Pública",
    "Concurso Público",
    "Adjudicación Simplificada",
    "Contratación Directa",
    "Comparación de Precios",
]
PROB_MODALIDADES_NORMAL = [0.15, 0.10, 0.35, 0.10, 0.30]

OBJETOS = [
    "Adquisición de bienes de oficina",
    "Servicio de mantenimiento de infraestructura",
    "Consultoría en ingeniería",
    "Servicio de limpieza y vigilancia",
    "Adquisición de equipos informáticos",
    "Servicio de capacitación",
    "Obra de rehabilitación vial",
    "Adquisición de materiales de construcción",
    "Servicio de transporte",
    "Suministro de combustible",
]


def _fecha_aleatoria(inicio, fin):
    delta = (fin - inicio).days
    return inicio + timedelta(days=int(RNG.integers(0, delta)))


def generar_proveedores(n=N_PROVEEDORES):
    return pd.DataFrame({
        "id_proveedor": [f"P{i:04d}" for i in range(n)],
        "ruc": [f"20{RNG.integers(100000000, 999999999)}" for _ in range(n)],
        "razon_social": [f"Proveedor {i:04d} SAC" for i in range(n)],
    })


def generar_entidades(n=N_ENTIDADES):
    return pd.DataFrame({
        "id_entidad": [f"E{i:02d}" for i in range(n)],
        "nombre_entidad": [f"Entidad Pública {i:02d}" for i in range(n)],
    })


def generar_funcionarios(n=N_FUNCIONARIOS, entidades=None):
    entidad_asignada = RNG.choice(entidades["id_entidad"], size=n)
    return pd.DataFrame({
        "id_funcionario": [f"F{i:03d}" for i in range(n)],
        "dni_funcionario": [f"{RNG.integers(10000000, 79999999)}" for _ in range(n)],
        "id_entidad": entidad_asignada,
    })


def _funcionario_de_entidad(funcionarios, entidad):
    candidatos = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
    return RNG.choice(candidatos) if len(candidatos) else RNG.choice(funcionarios["id_funcionario"])


def generar_contratos_normales(proveedores, entidades, funcionarios, n=N_CONTRATOS_NORMALES):
    inicio, fin = datetime(2023, 1, 1), datetime(2026, 6, 30)
    filas = []
    for i in range(n):
        entidad = RNG.choice(entidades["id_entidad"])
        filas.append({
            "id_contrato": f"C{i:06d}",
            "id_proveedor": RNG.choice(proveedores["id_proveedor"]),
            "id_entidad": entidad,
            "id_funcionario": _funcionario_de_entidad(funcionarios, entidad),
            "modalidad": RNG.choice(MODALIDADES, p=PROB_MODALIDADES_NORMAL),
            "objeto": RNG.choice(OBJETOS),
            "monto": round(min(float(RNG.lognormal(mean=11.0, sigma=1.0)), 3_000_000), 2),
            "fecha_contrato": _fecha_aleatoria(inicio, fin),
            "es_favoritismo_real": False,
            "es_fraccionamiento_real": False,
            "escenario_sintetico": "normal",
        })
    return pd.DataFrame(filas)


def generar_casos_limite_legitimos(proveedores, entidades, funcionarios, n_casos=N_CASOS_LIMITE_LEGITIMOS):
    """Hard negatives: concentración alta sin etiqueta de favoritismo.

    Simulan, por ejemplo, proveedores especializados que ganan repetidamente un
    mismo objeto mediante procesos predominantemente abiertos. Obligan al
    modelo a no confundir concentración por sí sola con favoritismo.
    """
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 6, 30)
    filas = []
    idx = 700000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        objeto = RNG.choice(OBJETOS)
        n_contratos = int(RNG.integers(6, 13))
        for _ in range(n_contratos):
            filas.append({
                "id_contrato": f"C{idx:06d}",
                "id_proveedor": proveedor,
                "id_entidad": entidad,
                "id_funcionario": _funcionario_de_entidad(funcionarios, entidad),
                "modalidad": RNG.choice(
                    ["Licitación Pública", "Concurso Público", "Adjudicación Simplificada"],
                    p=[0.50, 0.20, 0.30],
                ),
                "objeto": objeto if RNG.random() < 0.90 else RNG.choice(OBJETOS),
                "monto": round(float(RNG.uniform(80_000, 900_000)), 2),
                "fecha_contrato": _fecha_aleatoria(inicio, fin),
                "es_favoritismo_real": False,
                "es_fraccionamiento_real": False,
                "escenario_sintetico": "hard_negative_concentracion_legitima",
            })
            idx += 1
    return pd.DataFrame(filas)


def sembrar_favoritismo(proveedores, entidades, funcionarios, n_casos=6, contratos_por_caso=(8, 15)):
    """Siembra señales combinadas, no una modalidad aislada.

    Alta recurrencia + concentración de objeto + predominio de Contratación
    Directa, con algo de ruido en objeto/procedimiento para evitar separación
    artificial perfecta por una sola variable.
    """
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 6, 30)
    filas = []
    idx = 900000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        funcionarios_entidad = funcionarios.loc[
            funcionarios["id_entidad"] == entidad, "id_funcionario"
        ].tolist()
        if not funcionarios_entidad:
            funcionarios_entidad = funcionarios["id_funcionario"].tolist()
        funcionarios_caso = RNG.choice(
            funcionarios_entidad,
            size=min(2, len(funcionarios_entidad)),
            replace=False,
        )
        objeto_fijo = RNG.choice(OBJETOS)
        n_contratos = int(RNG.integers(*contratos_por_caso))
        for _ in range(n_contratos):
            filas.append({
                "id_contrato": f"C{idx:06d}",
                "id_proveedor": proveedor,
                "id_entidad": entidad,
                "id_funcionario": RNG.choice(funcionarios_caso),
                "modalidad": RNG.choice(
                    ["Contratación Directa", "Comparación de Precios", "Adjudicación Simplificada"],
                    p=[0.65, 0.15, 0.20],
                ),
                "objeto": objeto_fijo if RNG.random() < 0.85 else RNG.choice(OBJETOS),
                "monto": round(float(RNG.uniform(50_000, 500_000)), 2),
                "fecha_contrato": _fecha_aleatoria(inicio, fin),
                "es_favoritismo_real": True,
                "es_fraccionamiento_real": False,
                "escenario_sintetico": "favoritismo_sembrado",
            })
            idx += 1
    return pd.DataFrame(filas)


def sembrar_fraccionamiento(proveedores, entidades, funcionarios, n_casos=8, partes_por_caso=(3, 6)):
    """Siembra compras divididas usando la cuantía aplicable a cada caso."""
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 5, 1)
    filas = []
    idx = 800000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        objeto = RNG.choice(OBJETOS)
        n_partes = int(RNG.integers(*partes_por_caso))
        fecha_base = _fecha_aleatoria(inicio, fin)
        umbral = obtener_umbral(fecha_base, objeto=objeto)
        monto_total = float(RNG.uniform(1.10 * umbral, 2.20 * umbral))
        montos = np.abs(RNG.normal(monto_total / n_partes, monto_total * 0.04, n_partes))

        for monto in montos:
            filas.append({
                "id_contrato": f"C{idx:06d}",
                "id_proveedor": proveedor,
                "id_entidad": entidad,
                "id_funcionario": _funcionario_de_entidad(funcionarios, entidad),
                "modalidad": "Adjudicación Simplificada" if fecha_base < datetime(2025, 4, 22) else "Procedimiento abreviado",
                "objeto": objeto,
                "monto": round(min(float(monto), umbral * 0.94), 2),
                "fecha_contrato": fecha_base + timedelta(days=int(RNG.integers(0, 10))),
                "es_favoritismo_real": False,
                "es_fraccionamiento_real": True,
                "escenario_sintetico": "fraccionamiento_sembrado",
            })
            idx += 1
    return pd.DataFrame(filas)


def introducir_valores_faltantes(df, columnas=("modalidad", "objeto", "monto"), frac=0.02):
    df = df.copy()
    for col in columnas:
        df.loc[RNG.random(len(df)) < frac, col] = np.nan
    return df


def main():
    proveedores = generar_proveedores()
    entidades = generar_entidades()
    funcionarios = generar_funcionarios(entidades=entidades)

    normales = generar_contratos_normales(proveedores, entidades, funcionarios)
    hard_negatives = generar_casos_limite_legitimos(proveedores, entidades, funcionarios)
    favoritismo = sembrar_favoritismo(proveedores, entidades, funcionarios)
    fraccionamiento = sembrar_fraccionamiento(proveedores, entidades, funcionarios)

    contratos = pd.concat(
        [normales, hard_negatives, favoritismo, fraccionamiento], ignore_index=True
    ).sample(frac=1, random_state=42).reset_index(drop=True)
    contratos = introducir_valores_faltantes(contratos)

    contratos.to_csv("data/contratos_siaf_seace.csv", index=False)
    proveedores.to_csv("data/proveedores.csv", index=False)
    entidades.to_csv("data/entidades.csv", index=False)
    funcionarios.to_csv("data/funcionarios.csv", index=False)

    print(f"Contratos generados: {len(contratos)}")
    print(f"  normales: {len(normales)}")
    print(f"  hard negatives legítimos: {len(hard_negatives)}")
    print(f"  favoritismo sembrado: {len(favoritismo)}")
    print(f"  fraccionamiento sembrado: {len(fraccionamiento)}")


if __name__ == "__main__":
    main()
