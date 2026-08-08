"""Genera pagos sintéticos vinculados a los contratos del PoC.

Sprint 4 cierra una brecha del TDR completo: el TDR solicita un análisis
estadístico y exploratorio de patrones de pagos, montos contractuales y
modalidades. Este dataset es exclusivamente sintético y NO representa SIAF real.

La generación es aditiva: no modifica ``data/contratos_siaf_seace.csv`` ni la
semántica legacy usada para reconstruir ``v1.0.0-rc.1``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260808)
INPUT = Path("data/contratos_siaf_seace.csv")
OUTPUT = Path("data/pagos_siaf_sintetico.csv")
FECHA_CORTE = pd.Timestamp("2026-08-07")

ESCENARIOS = ["completo", "parcial", "demorado", "pendiente", "sobrepago_senal"]
PROB_ESCENARIOS = [0.70, 0.12, 0.10, 0.06, 0.02]


def _particionar(total: float, n: int) -> list[float]:
    if n <= 1:
        return [round(float(total), 2)]
    pesos = RNG.dirichlet(np.ones(n) * 2.0)
    valores = np.round(pesos * float(total), 2)
    valores[-1] = round(float(total) - float(valores[:-1].sum()), 2)
    return [max(0.0, float(x)) for x in valores]


def _fecha_limitada(fecha) -> pd.Timestamp:
    return min(pd.Timestamp(fecha), FECHA_CORTE)


def generar_pagos(contratos: pd.DataFrame) -> pd.DataFrame:
    base = contratos.copy()
    base["fecha_contrato"] = pd.to_datetime(base["fecha_contrato"], errors="raise")
    base["monto"] = pd.to_numeric(base["monto"], errors="coerce")
    mediana = float(base["monto"].median())

    filas: list[dict] = []
    secuencia = 1

    for row in base.itertuples(index=False):
        monto_contrato = float(row.monto) if pd.notna(row.monto) else mediana
        monto_contrato = max(monto_contrato, 1.0)
        escenario = str(RNG.choice(ESCENARIOS, p=PROB_ESCENARIOS))

        if escenario == "completo":
            ratio_objetivo = 1.0
            n_pagos = int(RNG.integers(1, 4))
            demora_extra = 0
        elif escenario == "parcial":
            ratio_objetivo = float(RNG.uniform(0.55, 0.90))
            n_pagos = int(RNG.integers(1, 3))
            demora_extra = 0
        elif escenario == "demorado":
            ratio_objetivo = 1.0
            n_pagos = int(RNG.integers(1, 3))
            demora_extra = int(RNG.integers(45, 91))
        elif escenario == "sobrepago_senal":
            ratio_objetivo = float(RNG.uniform(1.03, 1.08))
            n_pagos = int(RNG.integers(1, 3))
            demora_extra = 0
        else:  # pendiente
            ratio_objetivo = 0.0
            n_pagos = 1
            demora_extra = 0

        total_pagado = monto_contrato * ratio_objetivo
        total_devengado = (
            monto_contrato * float(RNG.uniform(0.35, 0.80))
            if escenario == "pendiente"
            else total_pagado
        )
        devengados = _particionar(total_devengado, n_pagos)
        pagados = _particionar(total_pagado, n_pagos) if total_pagado > 0 else [0.0] * n_pagos

        fecha_base = pd.Timestamp(row.fecha_contrato)
        for i, (monto_devengado, monto_pagado) in enumerate(zip(devengados, pagados)):
            fecha_dev = _fecha_limitada(
                fecha_base + pd.Timedelta(days=int(RNG.integers(5, 46)) + 20 * i)
            )
            fecha_gir = _fecha_limitada(fecha_dev + pd.Timedelta(days=int(RNG.integers(0, 11))))

            if escenario == "pendiente":
                fecha_pag = pd.NaT
                estado = "PENDIENTE"
            else:
                fecha_pag = _fecha_limitada(
                    fecha_gir
                    + pd.Timedelta(days=int(RNG.integers(0, 21)) + demora_extra)
                )
                estado = "PAGADO"

            filas.append(
                {
                    "id_pago": f"PG{secuencia:08d}",
                    "id_contrato": str(row.id_contrato),
                    "fecha_devengado": fecha_dev,
                    "fecha_girado": fecha_gir,
                    "fecha_pagado": fecha_pag,
                    "monto_devengado": round(float(monto_devengado), 2),
                    "monto_pagado": round(float(monto_pagado), 2),
                    "estado": estado,
                    "escenario_sintetico": escenario,
                }
            )
            secuencia += 1

    return pd.DataFrame(filas)


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Falta {INPUT}. Ejecuta primero: python src/generar_datos.py"
        )
    contratos = pd.read_csv(INPUT)
    pagos = generar_pagos(contratos)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pagos.to_csv(OUTPUT, index=False)

    conteos = pagos["escenario_sintetico"].value_counts().to_dict()
    print(f"Pagos sintéticos generados: {len(pagos)} para {contratos['id_contrato'].nunique()} contratos")
    for escenario in ESCENARIOS:
        print(f"  {escenario}: {int(conteos.get(escenario, 0))}")
    print("Naturaleza: dataset sintético de prueba; no contiene información SIAF real.")


if __name__ == "__main__":
    main()
