"""DAG de monitoreo del champion activo — objetivo específico 3.2.c del TDR.

El flujo genera lotes de prueba, evalúa exactamente el perfil activo del
registry y, si se supera un gate, produce un MODELO CANDIDATO. Nunca existe
promoción automática; la eventual promoción requiere revisión explícita.
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


def comando(script):
    proyecto = shlex.quote(PROYECTO)
    python = shlex.quote(PY)
    return (
        f"test -x {python} || (echo 'Python de proyecto no encontrado: {PY}. "
        "Crear .venv o definir CGR_PROJECT_PYTHON.' >&2; exit 2); "
        f"cd {proyecto} && {python} {shlex.quote(script)}"
    )


with DAG(
    dag_id="monitoreo_reentrenamiento_1_8_2",
    description="PSI + recall@K del champion activo; genera candidate sin autopromoción",
    start_date=datetime(2026, 8, 1),
    schedule="@monthly",
    catchup=False,
    tags=["1.8.2", "monitoreo", "poc"],
) as dag:

    generar_lote_nuevo = BashOperator(
        task_id="generar_lote_nuevo",
        bash_command=comando("src/generar_lote_nuevo.py"),
    )

    evaluar_champion_y_generar_candidato = BashOperator(
        task_id="evaluar_champion_activo_y_generar_candidato_si_corresponde",
        bash_command=comando("src/autoevaluacion_champion.py"),
    )

    generar_lote_nuevo >> evaluar_champion_y_generar_candidato
