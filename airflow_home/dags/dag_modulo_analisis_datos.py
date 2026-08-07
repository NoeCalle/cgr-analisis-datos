"""
DAG de orquestación — numeral 6 del TDR ("Orquestación de Procesos ETL
(DAGs): Diseñar, desarrollar y probar los Directed Acyclic Graphs (DAGs)
para orquestar los procesos ETL").

Orden real de dependencias (linaje de datos):
  generar_datos → capa Bronce
       → preprocesamiento (limpieza) → capa Plata
             → dataset_favoritismo / dataset_fraccionamiento → capa Oro
                   → [entrenar_favoritismo, entrenar_fraccionamiento, grafos] (en paralelo)
                         → diccionario_y_diagrama (documentación final)

Cada tarea invoca el script correspondiente del prototipo vía BashOperator.
En producción, las tareas de entrenamiento (Spark) se reemplazarían por
SparkSubmitOperator apuntando al clúster YARN de la CGR; aquí se ejecutan
como procesos Python locales para poder validar el DAG completo de punta
a punta dentro de este entorno de prueba de concepto.
"""

from datetime import datetime
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

PROYECTO = "/home/claude/proyecto_1.8.2"
PY = "python3"

default_args = {
    # Nota: "owner" es un campo administrativo de Airflow (no implica
    # autoría institucional). Este DAG es de un prototipo independiente,
    # no una implementación oficial de la CGR — ver README.md.
    "owner": "prototipo-independiente",
    "retries": 1,
}

with DAG(
    dag_id="modulo_analisis_datos_1_8_2",
    description="Pipeline de favoritismo, fraccionamiento y vínculos — Proyecto Interno 1.8.2 (CGR)",
    start_date=datetime(2026, 8, 1),
    schedule=None,  # disparo manual / bajo demanda, no periódico
    catchup=False,
    default_args=default_args,
    tags=["cgr", "1.8.2", "auditoria"],
) as dag:

    generar_datos = BashOperator(
        task_id="generar_datos",
        bash_command=f"cd {PROYECTO} && {PY} src/generar_datos.py",
    )

    cargar_bronce = BashOperator(
        task_id="cargar_capa_bronce",
        bash_command=f"cd {PROYECTO} && {PY} src/lakehouse_capas.py bronce",
    )

    preprocesar = BashOperator(
        task_id="preprocesamiento_y_features",
        bash_command=f"cd {PROYECTO} && {PY} src/preprocesamiento.py",
    )

    mover_plata = BashOperator(
        task_id="publicar_capa_plata",
        bash_command=f"cd {PROYECTO} && {PY} src/lakehouse_capas.py plata",
    )

    entrenar_favoritismo = BashOperator(
        task_id="entrenar_modelo_favoritismo",
        bash_command=f"cd {PROYECTO} && {PY} src/modelo_favoritismo.py",
    )

    entrenar_fraccionamiento = BashOperator(
        task_id="entrenar_modelo_fraccionamiento",
        bash_command=f"cd {PROYECTO} && {PY} src/modelo_fraccionamiento.py",
    )

    analizar_vinculos = BashOperator(
        task_id="analizar_vinculos_proveedor_funcionario",
        bash_command=f"cd {PROYECTO} && {PY} src/modelo_grafos.py",
    )

    mover_oro = BashOperator(
        task_id="publicar_capa_oro",
        bash_command=f"cd {PROYECTO} && {PY} src/lakehouse_capas.py oro",
    )

    documentar = BashOperator(
        task_id="generar_diccionario_y_diagrama",
        bash_command=f"cd {PROYECTO} && {PY} src/generar_diccionario_diagrama.py",
    )

    # Linaje de dependencias — refleja el flujo real de datos, no solo un orden arbitrario
    generar_datos >> cargar_bronce >> preprocesar >> mover_plata
    mover_plata >> [entrenar_favoritismo, entrenar_fraccionamiento, analizar_vinculos]
    [entrenar_favoritismo, entrenar_fraccionamiento, analizar_vinculos] >> mover_oro >> documentar
