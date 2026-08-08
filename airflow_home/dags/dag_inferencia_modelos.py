"""DAG operacional de INFERENCE — Sprint 2.

No genera datos, no ejecuta tuning y no entrena. Consume una configuración
`mode: inference` y un registry champion ya promovido. En CGR las rutas reales
se suministrarían mediante variables de entorno/secret management institucional.
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
OUTPUT_DIR = os.environ.get("CGR_INFERENCE_OUTPUT_DIR", "outputs/runtime/inference/airflow")


def comando_inference():
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    return (
        f"test -x {python} || (echo 'Python de proyecto no encontrado: {PY}' >&2; exit 2); "
        f"cd {proyecto} && {python} src/score_inference.py "
        f"--config {shlex.quote(CONFIG)} "
        f"--registry {shlex.quote(REGISTRY)} "
        f"--output-dir {shlex.quote(OUTPUT_DIR)}"
    )


with DAG(
    dag_id="inferencia_modelos_1_8_2",
    description="Scoring con champion sin labels, tuning ni reentrenamiento",
    start_date=datetime(2026, 8, 8),
    schedule=None,
    catchup=False,
    default_args={"owner": "prototipo-independiente", "retries": 1},
    tags=["1.8.2", "inference", "serving", "poc"],
) as dag:
    score_champion = BashOperator(
        task_id="score_con_champion_sin_reentrenar",
        bash_command=comando_inference(),
    )
