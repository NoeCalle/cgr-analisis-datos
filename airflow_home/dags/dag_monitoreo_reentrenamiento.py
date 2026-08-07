"""
DAG de Monitoreo y Reentrenamiento — objetivo específico 3.2.c del TDR
("Estrategias de Sostenibilidad del Modelo"). Se ejecuta de forma
independiente del DAG de entrenamiento inicial (dag_modulo_analisis_datos.py):
este correría de forma periódica (@monthly) sobre la plataforma de la CGR,
evaluando si los nuevos contratos ingresados justifican un reentrenamiento.
"""

from datetime import datetime
import os
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Ver dag_modulo_analisis_datos.py para la explicación de este cálculo
# (corrección tras revisión externa: ya no está hardcodeada).
PROYECTO = os.environ.get(
    "PROYECTO_DIR",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)
PY = "python3"

with DAG(
    dag_id="monitoreo_reentrenamiento_1_8_2",
    description="Autoevaluación (PSI + degradación de recall) y reentrenamiento condicional — numeral 3.2.c del TDR",
    start_date=datetime(2026, 8, 1),
    schedule="@monthly",
    catchup=False,
    tags=["cgr", "1.8.2", "monitoreo"],
) as dag:

    generar_lote_nuevo = BashOperator(
        task_id="generar_lote_nuevo",
        bash_command=f"cd {PROYECTO} && {PY} src/generar_lote_nuevo.py",
    )

    autoevaluar_y_reentrenar = BashOperator(
        task_id="autoevaluar_y_reentrenar_si_corresponde",
        bash_command=f"cd {PROYECTO} && {PY} src/autoevaluacion.py",
    )

    generar_lote_nuevo >> autoevaluar_y_reentrenar
