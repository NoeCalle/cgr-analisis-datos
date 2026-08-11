"""DAG de monitoreo del champion activo.

A diferencia del smoke/demo local, este DAG no genera datos sintéticos. Exige
un lote externo indicado por ``CGR_MONITOR_BATCH_PATH`` y deja la frecuencia en
``CGR_MONITOR_SCHEDULE``; sin esa variable no se agenda automáticamente.
El monitor puede generar candidate si existen labels y se supera un gate, pero
nunca contiene promoción automática.
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
CONFIG = os.environ.get("CGR_MONITOR_CONFIG", os.environ.get("CGR_TRAIN_CONFIG", "config/local-training.yaml"))
REGISTRY = os.environ.get("CGR_MODEL_REGISTRY", "outputs/model_registry.json")
BATCH_PATH = os.environ.get("CGR_MONITOR_BATCH_PATH", "")
BATCH_NAME = os.environ.get("CGR_MONITOR_BATCH_NAME", "current")
MONITOR_BASE = os.environ.get("CGR_MONITOR_OUTPUT_BASE", "outputs/runtime/monitoring/airflow")
SCHEDULE = os.environ.get("CGR_MONITOR_SCHEDULE") or None
RUN_TOKEN = "{{ ts_nodash }}"
OUTPUT = f"{MONITOR_BASE}/{RUN_TOKEN}/monitoreo_champion.json"
LOG = f"{MONITOR_BASE}/{RUN_TOKEN}/log_reentrenamiento_champion.csv"


def comando_monitor():
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    batch = shlex.quote(BATCH_PATH)
    batch_arg = shlex.quote(f"{BATCH_NAME}={BATCH_PATH}")
    return (
        f"test -x {python} || (echo 'Python de proyecto no encontrado: {PY}' >&2; exit 2); "
        f"test -n {batch} || (echo 'CGR_MONITOR_BATCH_PATH es obligatorio para el DAG operacional' >&2; exit 2); "
        f"cd {proyecto} && {python} src/autoevaluacion_champion.py "
        f"--registry {shlex.quote(REGISTRY)} "
        f"--config {shlex.quote(CONFIG)} "
        f"--output {shlex.quote(OUTPUT)} "
        f"--log {shlex.quote(LOG)} "
        f"--batch {batch_arg}"
    )


with DAG(
    dag_id="monitoreo_reentrenamiento_1_8_2",
    description="Monitor configurable del champion activo; candidate sin autopromoción",
    start_date=datetime(2026, 8, 1),
    schedule=SCHEDULE,
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "prototipo-independiente", "retries": 1},
    tags=["1.8.2", "monitoreo", "spark", "mllib", "poc"],
) as dag:
    evaluar_champion_y_generar_candidato = BashOperator(
        task_id="evaluar_champion_activo_y_generar_candidato_si_corresponde",
        bash_command=comando_monitor(),
    )
