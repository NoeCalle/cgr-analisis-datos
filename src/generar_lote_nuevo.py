"""Genera lotes sintéticos futuros para probar monitoreo del champion activo.

- ``normal`` conserva aproximadamente las distribuciones de entrenamiento.
- ``con_drift`` aumenta Contratación Directa/Comparación de Precios y añade
  positivos de favoritismo con un perfil distinto al patrón histórico.

Los lotes incluyen ``categoria_principal`` para cumplir el mismo contrato de
TRAIN que el resto del pipeline.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from generar_datos import categoria_principal

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


def _fila(id_contrato, proveedor, entidad, funcionario, modalidad, objeto, monto, fecha, fav):
    return {
        "id_contrato": id_contrato,
        "id_proveedor": proveedor,
        "id_entidad": entidad,
        "id_funcionario": funcionario,
        "modalidad": modalidad,
        "objeto": objeto,
        "categoria_principal": categoria_principal(objeto),
        "monto": monto,
        "fecha_contrato": fecha,
        "es_favoritismo_real": fav,
        "es_fraccionamiento_real": False,
    }


def generar_lote(escenario="normal", n_contratos=700):
    proveedores, entidades, funcionarios = _cargar_maestros()
    inicio, fin = datetime(2026, 7, 1), datetime(2026, 9, 30)

    if escenario == "normal":
        prob_modalidades = [0.15, 0.10, 0.35, 0.10, 0.30]
    elif escenario == "con_drift":
        prob_modalidades = [0.04, 0.03, 0.05, 0.53, 0.35]
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
        objeto = RNG.choice(OBJETOS)
        filas.append(_fila(
            f"CN{i:06d}", proveedor, entidad, funcionario, modalidad,
            objeto, monto, fecha, False,
        ))

    if escenario == "con_drift":
        # Positivos futuros con perfil distinto: pocos contratos y montos altos.
        for caso in range(6):
            proveedor = RNG.choice(proveedores["id_proveedor"])
            entidad = RNG.choice(entidades["id_entidad"])
            funcs_entidad = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
            funcionario = RNG.choice(funcs_entidad) if len(funcs_entidad) else RNG.choice(funcionarios["id_funcionario"])
            objeto_fijo = RNG.choice(OBJETOS)
            for j in range(3):
                filas.append(_fila(
                    f"CND{caso:02d}{j:02d}", proveedor, entidad, funcionario,
                    "Contratación Directa", objeto_fijo,
                    round(float(RNG.uniform(900_000, 1_500_000)), 2),
                    inicio + timedelta(days=int(RNG.integers(0, 90))), True,
                ))

    df = pd.DataFrame(filas).sample(frac=1, random_state=99).reset_index(drop=True)
    path = f"data/lote_nuevo_{escenario}.csv"
    df.to_csv(path, index=False)
    print(f"Lote '{escenario}' generado: {len(df)} contratos → {path}")
    return df


if __name__ == "__main__":
    generar_lote("normal")
    generar_lote("con_drift")
