"""Generador de datos sintéticos de contrataciones públicas.

El ground truth es exclusivamente sintético y sirve para validación funcional y
metodológica. El benchmark incluye positivos variados, hard negatives de alta
concentración y repeticiones legítimas, además de variantes lexicales del mismo
objeto para probar la agrupación de objetos similares.
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
N_CASOS_LIMITE_LEGITIMOS = 30
N_CASOS_REPETICION_LEGITIMA = 24
N_CASOS_FAVORITISMO = 30
N_CASOS_FRACCIONAMIENTO = 24

MODALIDADES = [
    "Licitación Pública", "Concurso Público", "Adjudicación Simplificada",
    "Contratación Directa", "Comparación de Precios",
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

VARIANTES_OBJETO = {
    "Servicio de mantenimiento de infraestructura": [
        "Mantenimiento preventivo de infraestructura",
        "Servicio de conservación preventiva de infraestructura",
    ],
    "Obra de rehabilitación vial": [
        "Rehabilitación de vía pública",
        "Obra de rehabilitación de carretera",
    ],
    "Adquisición de equipos informáticos": [
        "Adquisición de equipo informático",
        "Compra de equipos informáticos",
    ],
    "Adquisición de materiales de construcción": [
        "Adquisición de material de construcción",
        "Compra de materiales de construcción",
    ],
    "Servicio de transporte": [
        "Servicios de transporte",
        "Contratación de servicio de transporte",
    ],
}

CATEGORIA_POR_OBJETO = {
    "Adquisición de bienes de oficina": "goods",
    "Servicio de mantenimiento de infraestructura": "services",
    "Consultoría en ingeniería": "services",
    "Servicio de limpieza y vigilancia": "services",
    "Adquisición de equipos informáticos": "goods",
    "Servicio de capacitación": "services",
    "Obra de rehabilitación vial": "works",
    "Adquisición de materiales de construcción": "goods",
    "Servicio de transporte": "services",
    "Suministro de combustible": "goods",
}
for _base, _variantes in VARIANTES_OBJETO.items():
    for _variante in _variantes:
        CATEGORIA_POR_OBJETO[_variante] = CATEGORIA_POR_OBJETO[_base]


def categoria_principal(objeto):
    return CATEGORIA_POR_OBJETO.get(objeto, "services")


def _variante_objeto(base, prob=0.45):
    variantes = VARIANTES_OBJETO.get(base, [])
    if variantes and RNG.random() < prob:
        return RNG.choice(variantes)
    return base


def _fecha_aleatoria(inicio, fin):
    return inicio + timedelta(days=int(RNG.integers(0, (fin - inicio).days)))


def generar_proveedores(n=N_PROVEEDORES):
    return pd.DataFrame({
        "id_proveedor": [f"P{i:04d}" for i in range(n)],
        # Conserva una llamada RNG por fila para no alterar la semilla del benchmark,
        # pero antepone SYN para que nunca se confunda con un RUC real publicable.
        "ruc": [f"SYN-RUC-{RNG.integers(100000000, 999999999)}" for _ in range(n)],
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
        # El prefijo evita colisiones/confusión con DNI reales manteniendo la
        # misma secuencia RNG utilizada por el benchmark histórico.
        "dni_funcionario": [f"SYN-DNI-{RNG.integers(10000000, 79999999)}" for _ in range(n)],
        "id_entidad": entidad_asignada,
    })


def _funcionario_de_entidad(funcionarios, entidad):
    candidatos = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"]
    return RNG.choice(candidatos) if len(candidatos) else RNG.choice(funcionarios["id_funcionario"])


def fila_contrato(idx, proveedor, entidad, funcionario, modalidad, objeto, monto, fecha, fav, frac, escenario):
    return {
        "id_contrato": f"C{idx:06d}",
        "id_proveedor": proveedor,
        "id_entidad": entidad,
        "id_funcionario": funcionario,
        "modalidad": modalidad,
        "objeto": objeto,
        "categoria_principal": categoria_principal(objeto),
        "monto": round(float(monto), 2),
        "fecha_contrato": fecha,
        "es_favoritismo_real": fav,
        "es_fraccionamiento_real": frac,
        "escenario_sintetico": escenario,
    }


def generar_contratos_normales(proveedores, entidades, funcionarios, n=N_CONTRATOS_NORMALES):
    inicio, fin = datetime(2023, 1, 1), datetime(2026, 6, 30)
    filas = []
    for i in range(n):
        entidad = RNG.choice(entidades["id_entidad"])
        objeto = RNG.choice(OBJETOS)
        filas.append(fila_contrato(
            i,
            RNG.choice(proveedores["id_proveedor"]),
            entidad,
            _funcionario_de_entidad(funcionarios, entidad),
            RNG.choice(MODALIDADES, p=PROB_MODALIDADES_NORMAL),
            objeto,
            min(float(RNG.lognormal(mean=11.0, sigma=1.0)), 3_000_000),
            _fecha_aleatoria(inicio, fin),
            False, False, "normal",
        ))
    return pd.DataFrame(filas)


def generar_casos_limite_legitimos(proveedores, entidades, funcionarios, n_casos=N_CASOS_LIMITE_LEGITIMOS):
    """Hard negatives de favoritismo: alta concentración sin etiqueta positiva."""
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 6, 30)
    filas, idx = [], 700000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        objeto_fijo = RNG.choice(OBJETOS)
        for _ in range(int(RNG.integers(6, 13))):
            objeto = _variante_objeto(objeto_fijo, prob=0.20) if RNG.random() < 0.90 else RNG.choice(OBJETOS)
            filas.append(fila_contrato(
                idx, proveedor, entidad, _funcionario_de_entidad(funcionarios, entidad),
                RNG.choice(
                    ["Licitación Pública", "Concurso Público", "Adjudicación Simplificada"],
                    p=[0.50, 0.20, 0.30],
                ),
                objeto, RNG.uniform(80_000, 900_000), _fecha_aleatoria(inicio, fin),
                False, False, "hard_negative_concentracion_legitima",
            ))
            idx += 1
    return pd.DataFrame(filas)


def generar_repeticiones_legitimas(proveedores, entidades, funcionarios, n_casos=N_CASOS_REPETICION_LEGITIMA):
    """Hard negatives de fraccionamiento: compras repetidas cercanas pero legítimas.

    Fuerzan a que la regla temporal por sí sola tenga falsos positivos y, por
    tanto, no pueda confundirse con ground truth.
    """
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 5, 1)
    filas, idx = [], 750000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        base_objeto = RNG.choice(OBJETOS)
        categoria = categoria_principal(base_objeto)
        fecha_base = _fecha_aleatoria(inicio, fin)
        umbral = obtener_umbral(fecha_base, objeto=base_objeto, categoria_principal=categoria)
        n = int(RNG.integers(3, 6))
        # Casos deliberadamente bajo el umbral y próximos en el tiempo, pero
        # etiquetados como legítimos para desafiar la regla heurística.
        for _ in range(n):
            objeto = _variante_objeto(base_objeto, prob=0.65)
            filas.append(fila_contrato(
                idx,
                proveedor,
                entidad,
                _funcionario_de_entidad(funcionarios, entidad),
                RNG.choice(["Licitación Pública", "Concurso Público", "Adjudicación Simplificada"]),
                objeto,
                RNG.uniform(0.10 * umbral, 0.45 * umbral),
                fecha_base + timedelta(days=int(RNG.integers(0, 10))),
                False,
                False,
                "hard_negative_repeticion_legitima",
            ))
            idx += 1
    return pd.DataFrame(filas)


def sembrar_favoritismo(proveedores, entidades, funcionarios, n_casos=N_CASOS_FAVORITISMO, contratos_por_caso=(7, 14)):
    """Siembra señales combinadas con ruido; no una modalidad aislada."""
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 6, 30)
    filas, idx = [], 900000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        candidatos = funcionarios.loc[funcionarios["id_entidad"] == entidad, "id_funcionario"].tolist()
        if not candidatos:
            candidatos = funcionarios["id_funcionario"].tolist()
        funcionarios_caso = RNG.choice(candidatos, size=min(2, len(candidatos)), replace=False)
        objeto_fijo = RNG.choice(OBJETOS)
        for _ in range(int(RNG.integers(*contratos_por_caso))):
            objeto = _variante_objeto(objeto_fijo, prob=0.25) if RNG.random() < 0.82 else RNG.choice(OBJETOS)
            filas.append(fila_contrato(
                idx, proveedor, entidad, RNG.choice(funcionarios_caso),
                RNG.choice(
                    ["Contratación Directa", "Comparación de Precios", "Adjudicación Simplificada"],
                    p=[0.58, 0.17, 0.25],
                ),
                objeto, RNG.uniform(50_000, 650_000), _fecha_aleatoria(inicio, fin),
                True, False, "favoritismo_sembrado",
            ))
            idx += 1
    return pd.DataFrame(filas)


def sembrar_fraccionamiento(proveedores, entidades, funcionarios, n_casos=N_CASOS_FRACCIONAMIENTO, partes_por_caso=(3, 7)):
    """Siembra compras divididas con variantes lexicales del mismo objeto."""
    inicio, fin = datetime(2024, 1, 1), datetime(2026, 5, 1)
    filas, idx = [], 800000
    for _ in range(n_casos):
        proveedor = RNG.choice(proveedores["id_proveedor"])
        entidad = RNG.choice(entidades["id_entidad"])
        base_objeto = RNG.choice(OBJETOS)
        categoria = categoria_principal(base_objeto)
        n_partes = int(RNG.integers(*partes_por_caso))
        fecha_base = _fecha_aleatoria(inicio, fin)
        umbral = obtener_umbral(fecha_base, objeto=base_objeto, categoria_principal=categoria)
        monto_total = float(RNG.uniform(1.10 * umbral, 2.20 * umbral))
        montos = np.abs(RNG.normal(monto_total / n_partes, monto_total * 0.04, n_partes))

        for monto in montos:
            objeto = _variante_objeto(base_objeto, prob=0.70)
            modalidad = (
                "Adjudicación Simplificada"
                if fecha_base < datetime(2025, 4, 22)
                else ("Licitación Pública Abreviada" if categoria in {"goods", "works"} else "Concurso Público Abreviado")
            )
            filas.append(fila_contrato(
                idx, proveedor, entidad, _funcionario_de_entidad(funcionarios, entidad),
                modalidad, objeto, min(float(monto), umbral * 0.94),
                fecha_base + timedelta(days=int(RNG.integers(0, 10))),
                False, True, "fraccionamiento_sembrado",
            ))
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
    hard_fav = generar_casos_limite_legitimos(proveedores, entidades, funcionarios)
    hard_frac = generar_repeticiones_legitimas(proveedores, entidades, funcionarios)
    favoritismo = sembrar_favoritismo(proveedores, entidades, funcionarios)
    fraccionamiento = sembrar_fraccionamiento(proveedores, entidades, funcionarios)

    contratos = pd.concat(
        [normales, hard_fav, hard_frac, favoritismo, fraccionamiento], ignore_index=True
    ).sample(frac=1, random_state=42).reset_index(drop=True)
    contratos = introducir_valores_faltantes(contratos)

    contratos.to_csv("data/contratos_siaf_seace.csv", index=False)
    proveedores.to_csv("data/proveedores.csv", index=False)
    entidades.to_csv("data/entidades.csv", index=False)
    funcionarios.to_csv("data/funcionarios.csv", index=False)

    print(f"Contratos generados: {len(contratos)}")
    print(f"  normales: {len(normales)}")
    print(f"  hard negatives concentración: {len(hard_fav)}")
    print(f"  hard negatives repetición: {len(hard_frac)}")
    print(f"  favoritismo sembrado: {len(favoritismo)}")
    print(f"  fraccionamiento sembrado: {len(fraccionamiento)}")


if __name__ == "__main__":
    main()