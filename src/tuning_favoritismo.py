"""Compatibilidad CLI para el tuning de favoritismo.

Desde la Etapa 2B la única fuente válida de selección es
``evaluar_favoritismo_operacional``: separa holdout antes del FIT del
preprocesador y usa ``monto_capped``, igual que TRAIN/INFERENCE. Este wrapper se
mantiene para no romper comandos/documentación históricos sin permitir que la
ruta legacy vuelva a sobrescribir evidencia metodológica vigente.
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
