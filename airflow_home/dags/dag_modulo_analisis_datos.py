"""
DAG principal — orquestación ETL/ML del PoC según numeral 6 del TDR.

Flujo P1:
  generar fuentes -> Bronce -> preprocesar/features -> Plata
      -> tuning favoritismo -> entrenar favoritismo
      -> tuning fraccionamiento -> entrenar fraccionamiento
      -> análisis de vínculos
  -> Oro -> documentación

Airflow puede vivir en un virtualenv separado, pero las tareas de ciencia de
datos deben ejecutarse con el Python del proyecto (`.venv/bin/python`) o con
la ruta indicada por `CGR_PROJECT_PYTHON`. Esto evita que BashOperator use por
accidente el Python del entorno Airflow sin pandas/sklearn/SHAP.
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
    script_args = f" {args}" if args else ""
    return (
        f"test -x {python} || (echo 'Python de proyecto no encontrado: {PY}. "
        "Crear .venv o definir CGR_PROJECT_PYTHON.' >&2; exit 2); "
        f"cd {proyecto} && {python} {shlex.quote(script)}{script_args}"
    )


default_args = {"owner": "prototipo-independiente", "retries": 1}

with DAG(
    dag_id="modulo_analisis_datos_1_8_2",
    description="ETL y señales de riesgo — PoC independiente del Proyecto Interno 1.8.2",
    start_date=datetime(2026, 8, 1),
    schedule=None,
    catchup=False,
    default_args=default_args,
    tags=["1.8.2", "auditoria", "poc"],
) as dag:

    generar_datos = BashOperator(
        task_id="generar_datos",
        bash_command=comando("src/generar_datos.py"),
    )
    cargar_bronce = BashOperator(
        task_id="cargar_capa_bronce",
        bash_command=comando("src/lakehouse_capas.py", "bronce"),
    )
    preprocesar = BashOperator(
        task_id="preprocesamiento_y_features",
        bash_command=comando("src/preprocesamiento.py"),
    )
    mover_plata = BashOperator(
        task_id="publicar_capa_plata",
        bash_command=comando("src/lakehouse_capas.py", "plata"),
    )

    tuning_favoritismo = BashOperator(
        task_id="tuning_favoritismo",
        bash_command=comando("src/tuning_favoritismo.py"),
    )
    entrenar_favoritismo = BashOperator(
        task_id="entrenar_modelo_favoritismo",
        bash_command=comando("src/modelo_favoritismo.py"),
    )

    tuning_fraccionamiento = BashOperator(
        task_id="tuning_fraccionamiento_con_holdout",
        bash_command=comando("src/tuning_fraccionamiento.py"),
    )
    entrenar_fraccionamiento = BashOperator(
        task_id="entrenar_modelo_fraccionamiento",
        bash_command=comando("src/modelo_fraccionamiento.py"),
    )

    analizar_vinculos = BashOperator(
        task_id="analizar_vinculos_proveedor_funcionario",
        bash_command=comando("src/modelo_grafos.py"),
    )
    mover_oro = BashOperator(
        task_id="publicar_capa_oro",
        bash_command=comando("src/lakehouse_capas.py", "oro"),
    )
    documentar = BashOperator(
        task_id="generar_diccionario_y_diagrama",
        bash_command=comando("src/generar_diccionario_diagrama.py"),
    )

    generar_datos >> cargar_bronce >> preprocesar >> mover_plata
    mover_plata >> tuning_favoritismo >> entrenar_favoritismo
    mover_plata >> tuning_fraccionamiento >> entrenar_fraccionamiento
    mover_plata >> analizar_vinculos
    [entrenar_favoritismo, entrenar_fraccionamiento, analizar_vinculos] >> mover_oro >> documentar
