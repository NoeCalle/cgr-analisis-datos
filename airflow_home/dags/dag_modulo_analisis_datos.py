"""
DAG de reproducibilidad integral del PoC.

Este DAG reconstruye datos sintéticos, pagos sintéticos, análisis de montos y
modalidades, benchmarks, implementaciones Spark, grafos y evidencia documental.
Desde Sprint 2 NO se considera el flujo operacional de scoring porque
deliberadamente mezcla reconstrucción, tuning y entrenamiento para demostrar
reproducibilidad técnica.

Flujo de evidencia:
  sintético + pagos sintéticos -> Bronce -> preprocesar/features -> Plata
      |-> análisis pagos/montos/modalidades
      |-> benchmark sklearn: comparación/tuning/modelos
      |-> implementación objetivo TDR: Spark MLlib favoritismo/fraccionamiento
      |-> vínculos NetworkX -> GraphFrames
  -> Oro -> diccionario/diagrama -> linaje -> manifest -> evidencia

El scoring operacional sin reentrenamiento vive en `dag_inferencia_modelos.py`.
El TRAIN explícito que solo genera candidatos vive en `dag_entrenamiento_modelos.py`.
"""

from datetime import datetime
import os
import shlex

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

PROYECTO = os.environ.get(
    "PROYECTO_DIR",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)
PY = os.environ.get("CGR_PROJECT_PYTHON", os.path.join(PROYECTO, ".venv", "bin", "python"))


def comando(script, args=""):
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    error_python = shlex.quote(
        f"Python de proyecto no encontrado: {PY}. Crear .venv o definir CGR_PROJECT_PYTHON."
    )
    script_args = f" {args}" if args else ""
    return (
        f"test -x {python} || (echo {error_python} >&2; exit 2); "
        f"cd {proyecto} && {python} {shlex.quote(script)}{script_args}"
    )


default_args = {"owner": "prototipo-independiente", "retries": 1}

with DAG(
    dag_id="reproducibilidad_poc_1_8_2",
    description="Reconstrucción integral de evidencia del PoC; no es DAG de serving",
    start_date=datetime(2026, 8, 1),
    schedule=None,
    catchup=False,
    default_args=default_args,
    tags=["1.8.2", "reproducibilidad", "poc"],
) as dag:
    generar_datos = BashOperator(
        task_id="generar_datos", bash_command=comando("src/generar_datos.py")
    )
    generar_pagos = BashOperator(
        task_id="generar_pagos_sinteticos",
        bash_command=comando("src/generar_pagos_sinteticos.py"),
    )
    cargar_bronce = BashOperator(
        task_id="cargar_capa_bronce", bash_command=comando("src/lakehouse_capas.py", "bronce")
    )
    preprocesar = BashOperator(
        task_id="preprocesamiento_y_features", bash_command=comando("src/preprocesamiento.py")
    )
    mover_plata = BashOperator(
        task_id="publicar_capa_plata", bash_command=comando("src/lakehouse_capas.py", "plata")
    )
    analizar_pagos_modalidades = BashOperator(
        task_id="analizar_pagos_montos_modalidades",
        bash_command=comando("src/analisis_pagos_modalidades.py", "--config config/local-tdr.yaml"),
    )

    # Benchmark/referencia metodológica sklearn.
    comparar_favoritismo = BashOperator(
        task_id="comparar_algoritmos_favoritismo",
        bash_command=comando("src/comparar_modelos_favoritismo.py"),
    )
    tuning_favoritismo = BashOperator(
        task_id="tuning_favoritismo", bash_command=comando("src/tuning_favoritismo.py")
    )
    entrenar_favoritismo = BashOperator(
        task_id="entrenar_modelo_favoritismo_sklearn", bash_command=comando("src/modelo_favoritismo.py")
    )
    tuning_fraccionamiento = BashOperator(
        task_id="tuning_fraccionamiento_con_holdout",
        bash_command=comando("src/tuning_fraccionamiento.py"),
    )
    entrenar_fraccionamiento = BashOperator(
        task_id="entrenar_modelo_fraccionamiento_sklearn",
        bash_command=comando("src/modelo_fraccionamiento.py"),
    )

    # Implementación objetivo del TDR con Spark MLlib.
    spark_favoritismo = BashOperator(
        task_id="spark_mllib_favoritismo",
        bash_command=comando("src/spark/modelo_favoritismo_spark.py"),
    )
    spark_fraccionamiento = BashOperator(
        task_id="spark_mllib_fraccionamiento",
        bash_command=comando("src/spark/modelo_fraccionamiento_spark.py"),
    )

    analizar_vinculos = BashOperator(
        task_id="analizar_vinculos_networkx",
        bash_command=comando("src/modelo_grafos.py"),
    )
    graphframes = BashOperator(
        task_id="analizar_vinculos_graphframes",
        bash_command=comando("src/spark/vinculos_graphframes.py"),
    )

    mover_oro = BashOperator(
        task_id="publicar_capa_oro", bash_command=comando("src/lakehouse_capas.py", "oro")
    )
    documentar = BashOperator(
        task_id="generar_diccionario_y_diagrama",
        bash_command=comando("src/generar_diccionario_diagrama.py"),
    )
    generar_linaje = BashOperator(
        task_id="generar_linaje_datos", bash_command=comando("src/generar_linaje.py")
    )
    generar_manifest = BashOperator(
        task_id="generar_run_manifest", bash_command=comando("src/generar_run_manifest.py")
    )
    generar_evidencia = BashOperator(
        task_id="generar_evidencia_documental",
        bash_command=comando("src/generar_evidencia_documental.py"),
    )

    generar_datos >> generar_pagos >> cargar_bronce >> preprocesar >> mover_plata
    generar_pagos >> analizar_pagos_modalidades

    mover_plata >> comparar_favoritismo >> tuning_favoritismo >> entrenar_favoritismo
    mover_plata >> tuning_fraccionamiento >> entrenar_fraccionamiento
    mover_plata >> spark_favoritismo
    mover_plata >> spark_fraccionamiento
    mover_plata >> analizar_vinculos >> graphframes

    [
        analizar_pagos_modalidades,
        entrenar_favoritismo,
        entrenar_fraccionamiento,
        spark_favoritismo,
        spark_fraccionamiento,
        graphframes,
    ] >> mover_oro

    mover_oro >> documentar >> generar_linaje >> generar_manifest >> generar_evidencia
