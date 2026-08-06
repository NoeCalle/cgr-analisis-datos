"""
Genera un "nuevo lote" de contratos (trimestre siguiente) para probar el
mecanismo de autoevaluación — numeral 3.2.c del TDR: "Incorporar
mecanismos de autoevaluación y... autoentrenamiento para permitir la
actualización continua de los modelos mediante el análisis de nuevos
datos".

Se generan DOS escenarios para poder validar que el mecanismo distingue
correctamente entre ambos:
  - normal: mismas distribuciones que los datos de entrenamiento originales
    (el sistema NO debería disparar reentrenamiento).
  - con_drift: la proporción de modalidades no competitivas sube
    fuertemente (65% → 88%) y aparecen 2 casos de favoritismo con un
    perfil distinto al visto en entrenamiento (montos muy altos con pocos
    contratos, en vez de muchos contratos pequeños) — el sistema SÍ
    debería detectarlo y disparar reentrenamiento.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG = np.random.default_rng(99)

MODALIDADES = [
    "Licitación Pública", "Concurso Público", "Adjudicación Simplificada",
    "Contratación Directa", "Comparación de Precios",
]
OBJETOS = [
    "Adquisición de bienes de oficina", "Servicio de mantenimiento de infraestructura",
    "Consultoría en ingeniería", "Servicio de limpieza y vigilancia",
    "Adquisición de equipos informáticos", "Servicio de capacitación",
    "Obra de rehabilitación vial", "Adquisición de materiales de construcción",
    "Servicio de transporte", "Suministro de combustible",
]


def _cargar_maestros():
    proveedores = pd.read_csv("data/proveedores.csv")
    entidades = pd.read_csv("data/entidades.csv")
    funcionarios = pd.read_csv("data/funcionarios.csv")
    return proveedores, entidades, funcionarios


def generar_lote(escenario="normal", n_contratos=600):
    proveedores, entidades, funcionarios = _cargar_maestros()
    inicio, fin = datetime(2026, 7, 1), datetime(2026, 9, 30)

    if escenario == "normal":
        prob_modalidades = [0.15, 0.10, 0.35, 0.10, 0.30]  # igual que el dataset original
    elif escenario == "con_drift":
        prob_modalidades = [0.04, 0.03, 0.05, 0.53, 0.35]  # salto fuerte a no competitivas
    else:
        raise ValueError("escenario debe ser 'normal' o 'con_drift'")

    filas = []
    for i in range(n_contratos):
        entidad = RNG.choice(entidades["id_entidad"])
        funcs_entidad = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
        funcionario = RNG.choice(funcs_entidad) if len(funcs_entidad) else RNG.choice(funcionarios["id_funcionario"])
        proveedor = RNG.choice(proveedores["id_proveedor"])
        modalidad = RNG.choice(MODALIDADES, p=prob_modalidades)
        monto = round(min(float(RNG.lognormal(mean=11.0, sigma=1.0)), 3_000_000), 2)
        fecha = inicio + timedelta(days=int(RNG.integers(0, (fin - inicio).days)))
        filas.append({
            "id_contrato": f"CN{i:06d}", "id_proveedor": proveedor, "id_entidad": entidad,
            "id_funcionario": funcionario, "modalidad": modalidad, "objeto": RNG.choice(OBJETOS),
            "monto": monto, "fecha_contrato": fecha,
            "es_favoritismo_real": False, "es_fraccionamiento_real": False,
        })

    if escenario == "con_drift":
        # 2 casos de favoritismo con perfil DISTINTO al visto en entrenamiento:
        # pocos contratos pero de monto muy alto (en vez de muchos contratos
        # pequeños, el patrón que el modelo aprendió a reconocer)
        for caso in range(2):
            proveedor = RNG.choice(proveedores["id_proveedor"])
            entidad = RNG.choice(entidades["id_entidad"])
            funcs_entidad = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
            funcionario = RNG.choice(funcs_entidad) if len(funcs_entidad) else RNG.choice(funcionarios["id_funcionario"])
            objeto_fijo = RNG.choice(OBJETOS)
            for j in range(3):  # solo 3 contratos, no 8-15 como en el patrón original
                filas.append({
                    "id_contrato": f"CND{caso:02d}{j:02d}", "id_proveedor": proveedor, "id_entidad": entidad,
                    "id_funcionario": funcionario, "modalidad": "Contratación Directa", "objeto": objeto_fijo,
                    "monto": round(float(RNG.uniform(900_000, 1_500_000)), 2),
                    "fecha_contrato": inicio + timedelta(days=int(RNG.integers(0, 90))),
                    "es_favoritismo_real": True, "es_fraccionamiento_real": False,
                })

    df = pd.DataFrame(filas).sample(frac=1, random_state=99).reset_index(drop=True)
    path = f"data/lote_nuevo_{escenario}.csv"
    df.to_csv(path, index=False)
    print(f"Lote '{escenario}' generado: {len(df)} contratos → {path}")
    return df


if __name__ == "__main__":
    generar_lote("normal")
    generar_lote("con_drift")
