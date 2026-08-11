"""DAG explícito de TRAIN operacional.

Genera un candidate Spark MLlib con el mismo preprocesamiento que usa INFERENCE.
Deliberadamente NO contiene ninguna tarea de promoción. Cada run escribe en una
ruta propia para que dos ejecuciones no compartan el directorio candidate.
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
CONFIG = os.environ.get("CGR_TRAIN_CONFIG", "config/local-training.yaml")
CANDIDATE_BASE = os.environ.get(
    "CGR_SPARK_CANDIDATE_BASE",
    "outputs/runtime/spark_model_candidates/airflow",
)
RUN_TOKEN = "{{ ts_nodash }}"
MANIFEST = f"{CANDIDATE_BASE}/{RUN_TOKEN}/candidate_manifest.json"


def comando_train():
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    error_python = shlex.quote(f"Python de proyecto no encontrado: {PY}")
    return (
        f"test -x {python} || (echo {error_python} >&2; exit 2); "
        f"cd {proyecto} && {python} src/spark/entrenar_candidato_spark.py "
        f"--config {shlex.quote(CONFIG)} --manifest {shlex.quote(MANIFEST)}"
    )


with DAG(
    dag_id="entrenamiento_candidato_1_8_2",
    description="TRAIN Spark separado: genera candidate por run y nunca lo promueve automáticamente",
    start_date=datetime(2026, 8, 8),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "prototipo-independiente", "retries": 0},
    tags=["1.8.2", "training", "spark", "mllib", "candidate", "poc"],
) as dag:
    entrenar_candidate = BashOperator(
        task_id="entrenar_spark_y_persistir_candidate",
        bash_command=comando_train(),
    )
