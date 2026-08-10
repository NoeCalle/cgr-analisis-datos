"""Compatibilidad CLI para comparar candidatos de favoritismo.

La comparación vigente se ejecuta en ``evaluar_favoritismo_operacional`` con
split proveedor-entidad, preprocesador ajustado solo en desarrollo y
``monto_capped``. Este wrapper conserva el comando histórico sin permitir que
la ruta Plata/legacy sobrescriba la evidencia operacional.
"""

from evaluar_favoritismo_operacional import evaluar


def main():
    resultado = evaluar()
    comparacion = resultado["comparacion"]
    print(
        "Candidato con mayor AUC-PR OOF en desarrollo: "
        f"{comparacion['mejor_candidato']}"
    )
    return comparacion


if __name__ == "__main__":
    main()
