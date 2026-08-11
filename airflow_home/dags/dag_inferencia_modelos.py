"""DAG operacional de INFERENCE.

El serving carga el champion ``spark_mllib`` del registry unificado. No genera
datos, no ejecuta tuning, no ajusta preprocesamiento y no entrena. Cada run usa
un directorio de salida propio para evitar colisiones entre ejecuciones.
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
CONFIG = os.environ.get("CGR_DATA_CONFIG", "config/local.yaml")
REGISTRY = os.environ.get("CGR_MODEL_REGISTRY", "outputs/model_registry.json")
OUTPUT_BASE = os.environ.get(
    "CGR_INFERENCE_OUTPUT_BASE",
    "outputs/runtime/inference_spark/airflow",
)
RUN_TOKEN = "{{ ts_nodash }}"
OUTPUT_DIR = f"{OUTPUT_BASE}/{RUN_TOKEN}"


def comando_inference():
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    error_python = shlex.quote(f"Python de proyecto no encontrado: {PY}")
    return (
        f"test -x {python} || (echo {error_python} >&2; exit 2); "
        f"cd {proyecto} && {python} src/spark/score_inference_spark.py "
        f"--config {shlex.quote(CONFIG)} "
        f"--registry {shlex.quote(REGISTRY)} "
        f"--output-dir {shlex.quote(OUTPUT_DIR)}"
    )


with DAG(
    dag_id="inferencia_modelos_1_8_2",
    description="Scoring Spark MLlib con champion, salida aislada por run y sin reentrenar",
    start_date=datetime(2026, 8, 8),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "prototipo-independiente", "retries": 1},
    tags=["1.8.2", "inference", "spark", "mllib", "serving", "poc"],
) as dag:
    score_champion = BashOperator(
        task_id="score_spark_champion_sin_reentrenar",
        bash_command=comando_inference(),
    )
