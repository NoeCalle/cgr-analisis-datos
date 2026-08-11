"""Punto de entrada de compatibilidad para tuning de favoritismo.

Delega en ``evaluar_favoritismo_operacional``, que centraliza la selección de
hiperparámetros con holdout reservado antes del FIT del preprocesador y usa
``monto_capped`` igual que el contrato operacional. Mantener un único evaluador
evita divergencias entre comparación, tuning, TRAIN e INFERENCE.
"""

from evaluar_favoritismo_operacional import evaluar


def main():
    resultado = evaluar()
    resumen = resultado["tuning"]
    best = resumen["mejor_configuracion"]
    score = resumen["mejor_auc_pr_cv"]
    print(f"Mejores hiperparámetros operacionales: {best}")
    print(f"Mejor AUC-PR desarrollo (CV): {score:.4f}")
    return best, score


if __name__ == "__main__":
    main()
