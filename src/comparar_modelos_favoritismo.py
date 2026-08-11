"""Punto de entrada de compatibilidad para comparar modelos de favoritismo.

Delega en ``evaluar_favoritismo_operacional``, que aplica el split por
proveedor-entidad, ajusta el preprocesador únicamente sobre desarrollo y usa
``monto_capped``. Centralizar la comparación en el mismo evaluador evita que un
comando alternativo genere evidencia metodológica incompatible con TRAIN.
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
