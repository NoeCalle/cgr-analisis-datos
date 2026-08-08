"""DAG explícito de TRAIN operacional — Sprint 3.

Genera un candidate Spark MLlib con el mismo preprocesamiento corregido que usa
INFERENCE. Deliberadamente NO contiene ninguna tarea de promoción: pasar un
candidate a champion es una operación separada y, en un entorno institucional,
debe quedar detrás del gate de aprobación definido por la CGR.
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
MANIFEST = os.environ.get(
    "CGR_SPARK_CANDIDATE_MANIFEST",
    "outputs/runtime/spark_model_candidates/candidate_manifest.json",
)


def comando_train():
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    return (
        f"test -x {python} || (echo 'Python de proyecto no encontrado: {PY}' >&2; exit 2); "
        f"cd {proyecto} && {python} src/spark/entrenar_candidato_spark.py "
        f"--config {shlex.quote(CONFIG)} --manifest {shlex.quote(MANIFEST)}"
    )


with DAG(
    dag_id="entrenamiento_candidato_1_8_2",
    description="TRAIN Spark separado: genera candidate y nunca lo promueve automáticamente",
    start_date=datetime(2026, 8, 8),
    schedule=None,
    catchup=False,
    default_args={"owner": "prototipo-independiente", "retries": 0},
    tags=["1.8.2", "training", "spark", "mllib", "candidate", "poc"],
) as dag:
    entrenar_candidate = BashOperator(
        task_id="entrenar_spark_y_persistir_candidate",
        bash_command=comando_train(),
    )
