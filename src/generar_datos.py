"""
Generador de datos sintéticos de contrataciones públicas.

Simula la estructura de datos que resultaría de integrar SIAF (pagos) y
SEACE (procesos de contratación), tal como describe el TDR (numeral 4.1.2
y 4.1.3: Identificación/Adquisición e Integración/Consolidación de fuentes).

IMPORTANTE: estos datos son 100% sintéticos, generados para demostrar el
pipeline. En producción, esta etapa se reemplaza por la ingesta real desde
el Lakehouse (capa Bronce) descrito en el Anexo 2 del TDR.

Se "siembran" deliberadamente patrones de:
  - Favoritismo: proveedores que ganan de forma desproporcionada en una
    entidad, con modalidades poco competitivas.
  - Fraccionamiento: compras del mismo proveedor/entidad/objeto partidas
    en montos pequeños dentro de ventanas cortas de tiempo.
Esto permite validar que los modelos de los pasos siguientes SÍ detectan
lo que se sabe que está ahí (ground truth conocido), algo que no se puede
hacer con datos reales sin etiquetas.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG = np.random.default_rng(42)

N_CONTRATOS_NORMALES = 3500
N_PROVEEDORES = 220
N_ENTIDADES = 18
N_FUNCIONARIOS = 60

MODALIDADES = [
    "Licitación Pública",
    "Concurso Público",
    "Adjudicación Simplificada",
    "Contratación Directa",
    "Comparación de Precios",
]
# Probabilidad de cada modalidad en contrataciones "normales"
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

UMBRAL_ADJ_SIMPLIFICADA = 400_000  # S/. umbral usado SOLO para sembrar casos de
# prueba (no para detectarlos): se siembra siempre con el umbral de
# bienes/servicios 2022, como un patrón representativo conocido. El umbral
# real usado por los modelos de DETECCIÓN sí está parametrizado por año y
# categoría — ver src/umbrales_normativos.py.


def _fecha_aleatoria(inicio, fin):
    delta = (fin - inicio).days
    return inicio + timedelta(days=int(RNG.integers(0, delta)))


def generar_proveedores(n=N_PROVEEDORES):
    return pd.DataFrame({
        "id_proveedor": [f"P{str(i).zfill(4)}" for i in range(n)],
        "ruc": [f"20{RNG.integers(100000000, 999999999)}" for _ in range(n)],
        "razon_social": [f"Proveedor {i:04d} SAC" for i in range(n)],
    })


def generar_entidades(n=N_ENTIDADES):
    return pd.DataFrame({
        "id_entidad": [f"E{str(i).zfill(2)}" for i in range(n)],
        "nombre_entidad": [f"Entidad Pública {i:02d}" for i in range(n)],
    })


def generar_funcionarios(n=N_FUNCIONARIOS, entidades=None):
    entidad_asignada = RNG.choice(entidades["id_entidad"], size=n)
    return pd.DataFrame({
        "id_funcionario": [f"F{str(i).zfill(3)}" for i in range(n)],
        "dni_funcionario": [f"{RNG.integers(10000000, 79999999)}" for _ in range(n)],
        "id_entidad": entidad_asignada,
    })


def generar_contratos_normales(proveedores, entidades, funcionarios, n=N_CONTRATOS_NORMALES):
    inicio, fin = datetime(2023, 1, 1), datetime(2026, 6, 30)
    filas = []
    for i in range(n):
        entidad = RNG.choice(entidades["id_entidad"])
        funcs_entidad = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
        funcionario = RNG.choice(funcs_entidad) if len(funcs_entidad) else RNG.choice(funcionarios["id_funcionario"])
        proveedor = RNG.choice(proveedores["id_proveedor"])
        modalidad = RNG.choice(MODALIDADES, p=PROB_MODALIDADES_NORMAL)
        monto = float(RNG.lognormal(mean=11.0, sigma=1.0))  # distribución realista de montos
        monto = round(min(monto, 3_000_000), 2)
        filas.append({
            "id_contrato": f"C{str(i).zfill(6)}",
            "id_proveedor": proveedor,
            "id_entidad": entidad,
            "id_funcionario": funcionario,
            "modalidad": modalidad,
            "objeto": RNG.choice(OBJETOS),
            "monto": monto,
            "fecha_contrato": _fecha_aleatoria(inicio, fin),
            "es_favoritismo_real": False,
            "es_fraccionamiento_real": False,
        })
    return pd.DataFrame(filas)


def sembrar_favoritismo(proveedores, entidades, funcionarios, n_casos=6, contratos_por_caso=(8, 15)):
    """Simula proveedores que concentran contratos en una entidad con modalidades
    poco competitivas (Contratación Directa / Comparación de Precios)."""
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 6, 30)
    filas = []
    idx_base = 900000
    for caso in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        funcs_entidad = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
        funcionario = RNG.choice(funcs_entidad) if len(funcs_entidad) else RNG.choice(funcionarios["id_funcionario"])
        n_contratos = int(RNG.integers(*contratos_por_caso))
        objeto_fijo = RNG.choice(OBJETOS)
        for j in range(n_contratos):
            monto = round(float(RNG.uniform(50_000, 380_000)), 2)
            filas.append({
                "id_contrato": f"C{str(idx_base).zfill(6)}",
                "id_proveedor": proveedor,
                "id_entidad": entidad,
                "id_funcionario": funcionario,
                "modalidad": RNG.choice(
                    ["Contratación Directa", "Comparación de Precios"], p=[0.7, 0.3]
                ),
                "objeto": objeto_fijo,
                "monto": monto,
                "fecha_contrato": _fecha_aleatoria(inicio, fin),
                "es_favoritismo_real": True,
                "es_fraccionamiento_real": False,
            })
            idx_base += 1
    return pd.DataFrame(filas)


def sembrar_fraccionamiento(proveedores, entidades, funcionarios, n_casos=8, partes_por_caso=(3, 6)):
    """Simula compras divididas: mismo proveedor+entidad+objeto, montos justo
    debajo del umbral de Adjudicación Simplificada, en ventana de pocos días."""
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 5, 1)
    filas = []
    idx_base = 800000
    for caso in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        funcs_entidad = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
        funcionario = RNG.choice(funcs_entidad) if len(funcs_entidad) else RNG.choice(funcionarios["id_funcionario"])
        objeto_fijo = RNG.choice(OBJETOS)
        n_partes = int(RNG.integers(*partes_por_caso))
        fecha_base = _fecha_aleatoria(inicio, fin)
        monto_total = float(RNG.uniform(500_000, 1_200_000))
        montos_partes = np.abs(RNG.normal(monto_total / n_partes, monto_total * 0.05, n_partes))
        for j, monto in enumerate(montos_partes):
            monto = round(min(float(monto), UMBRAL_ADJ_SIMPLIFICADA * 0.95), 2)
            filas.append({
                "id_contrato": f"C{str(idx_base).zfill(6)}",
                "id_proveedor": proveedor,
                "id_entidad": entidad,
                "id_funcionario": funcionario,
                "modalidad": "Adjudicación Simplificada",
                "objeto": objeto_fijo,
                "monto": monto,
                "fecha_contrato": fecha_base + timedelta(days=int(RNG.integers(0, 10))),
                "es_favoritismo_real": False,
                "es_fraccionamiento_real": True,
            })
            idx_base += 1
    return pd.DataFrame(filas)


def introducir_valores_faltantes(df, columnas=("modalidad", "objeto", "monto"), frac=0.02):
    """Introduce nulos aleatorios para que el paso de preprocesamiento tenga
    algo real que limpiar (como pide el Segundo/Quinto Producto del TDR)."""
    df = df.copy()
    for col in columnas:
        mask = RNG.random(len(df)) < frac
        df.loc[mask, col] = np.nan
    return df


def main():
    proveedores = generar_proveedores()
    entidades = generar_entidades()
    funcionarios = generar_funcionarios(entidades=entidades)

    normales = generar_contratos_normales(proveedores, entidades, funcionarios)
    favoritismo = sembrar_favoritismo(proveedores, entidades, funcionarios)
    fraccionamiento = sembrar_fraccionamiento(proveedores, entidades, funcionarios)

    contratos = pd.concat([normales, favoritismo, fraccionamiento], ignore_index=True)
    contratos = contratos.sample(frac=1, random_state=42).reset_index(drop=True)
    contratos = introducir_valores_faltantes(contratos)

    contratos.to_csv("data/contratos_siaf_seace.csv", index=False)
    proveedores.to_csv("data/proveedores.csv", index=False)
    entidades.to_csv("data/entidades.csv", index=False)
    funcionarios.to_csv("data/funcionarios.csv", index=False)

    print(f"Contratos generados: {len(contratos)}")
    print(f"  - Normales: {len(normales)}")
    print(f"  - Con favoritismo sembrado: {len(favoritismo)}")
    print(f"  - Con fraccionamiento sembrado: {len(fraccionamiento)}")
    print(f"Proveedores: {len(proveedores)} | Entidades: {len(entidades)} | Funcionarios: {len(funcionarios)}")


if __name__ == "__main__":
    main()
