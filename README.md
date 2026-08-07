# Módulo de Análisis de Datos — Prototipo independiente (CGR 1.8.2)

> **Prototipo independiente.** Este repositorio no constituye una
> implementación oficial ni cuenta con aprobación institucional de la
> Contraloría General de la República (CGR). Es un ejercicio técnico propio,
> construido a partir de un TDR público de mayo de 2026.

Prueba de concepto del “Módulo de análisis de datos para dar soporte a los
auditores durante la ejecución de los servicios de control”, con énfasis en:

- priorización de señales de posible favoritismo;
- priorización de señales de posible fraccionamiento;
- análisis de vínculos proveedor–funcionario en el escenario sintético;
- Spark MLlib, Airflow, Lakehouse Bronce/Plata/Oro, SSRS y MLOps como PoC.

Las salidas de riesgo son **señales para revisión de auditor**. No constituyen
hallazgos, imputaciones ni determinaciones automáticas de irregularidad.

## Estado del plan de cierre de brechas

### ✅ P0 — Integridad OCDS y normativa: cerrado

En agosto de 2026 se re-auditó el repositorio contra el TDR y se corrigió la
parte más crítica del pipeline real:

- relación OCDS correcta: `Contract -> Award -> Supplier`;
- clave analítica del contrato: `OCID::contract.id`;
- adjudicatarios tomados de `awards_suppliers.csv`, sin mezclar suppliers de
  distintas adjudicaciones del mismo proceso;
- consorcios preservados según la identidad adjudicataria publicada;
- `mainProcurementCategory` (`goods/services/works`) tiene prioridad para el
  contexto normativo;
- motor normativo parametrizado 2018–2026 y cambio de régimen desde
  22/04/2025 (Ley 32069);
- tests de regresión de integridad y normativa;
- artefactos reales identificables antiguos retirados del repositorio público.

La regeneración P0 sobre los crudos OCDS utilizados produjo:

| Métrica | Resultado |
|---|---:|
| Contratos crudos | 47,510 |
| Contratos analíticos con award + supplier resolubles | **47,254** |
| Contratos excluidos por vínculo no resoluble | 256 |
| Adjudicatarios distintos presentes en contratos | 25,861 |
| Entidades distintas | 2,732 |
| Categoría `goods` | 23,630 |
| Categoría `services` | 18,584 |
| Categoría `works` | 5,040 |

El detalle agregado, hashes SHA-256 de las fuentes y comparación con la
ejecución antigua están en `outputs/validacion_p0_datos_reales.json`.

La cifra anterior de 47,442 contratos **ya no es válida** y los rankings
`*_REAL.csv` derivados de esa ejecución fueron retirados.

### 🟡 P1 — Modelado, validación y reproducibilidad: en implementación

Correcciones ya integradas en `main`:

- Contratación Directa y Comparación de Precios son features separadas; no se
  etiquetan como una única categoría “no competitiva”.
- Favoritismo y fraccionamiento consumen preferentemente datasets de la capa
  **Plata** del PoC.
- Los rankings para reporting se publican en **Oro**.
- Tuning de favoritismo persiste la configuración seleccionada y el modelo
  final la consume.
- Tuning de fraccionamiento reserva un **holdout final antes del tuning**.
- Autoevaluación usa un recall mínimo explícito y separa un holdout del lote
  nuevo; un reentrenamiento produce un **modelo candidato**, sin promoción
  automática.
- Airflow usa un Python de proyecto separado del virtualenv de Airflow.
- `outputs/run_manifest.json` registra commit, versiones, hashes, tuning y
  artefactos de una ejecución.
- GitHub Actions ejecuta pruebas de regresión en cada push/PR.

Los artefactos sintéticos versionados que fueron generados antes de estas
correcciones deben regenerarse antes de volver a citar sus métricas en los
Productos 1–7. La documentación formal se actualizará al final de P1 para que
lea evidencia generada automáticamente y no números escritos a mano.

## Correspondencia resumida con el TDR

| Área TDR | Estado PoC |
|---|---|
| EDA y calidad de datos | Implementado |
| Feature engineering | Implementado / endurecido en P1 |
| Favoritismo supervisado | Random Forest + CV + SHAP |
| Fraccionamiento no supervisado | Isolation Forest + regla interpretable + holdout de evaluación |
| Spark MLlib | Implementado en modo local; clúster institucional pendiente |
| Grafos | networkx + GraphFrames en escenario sintético |
| Airflow DAGs | Implementados; entorno reproducible endurecido en P1 |
| Bronce / Plata / Oro | Simulación local funcional; Lakehouse CGR pendiente |
| Autoevaluación/reentrenamiento | Modelo candidato + revisión humana requerida |
| SSRS | Esquema T-SQL + RDL + SQLite stand-in; servidor institucional pendiente |
| Linaje/diccionario | Diccionario, diagrama y run manifest |
| DEV/QA/PROD, Git institucional, certificación | Dependencia institucional CGR |
| Transferencia formal / marcha blanca | Dependencia contractual/institucional |

## Estructura

```text
src/                         Python principal
src/spark/                   Spark MLlib, GraphFrames, Delta, SQL, streaming, HMS
airflow_home/dags/           DAG principal + monitoreo
lakehouse/bronce/             Simulación de ingesta cruda
lakehouse/plata/              Datos limpios/features consumidos por modelos
lakehouse/oro/                Salidas para reporting/integración
ssrs/                         DDL T-SQL + RDL PoC
reporte/                      Generadores y documentos formales
outputs/                      Evidencias, modelos, tuning, manifests
tests/                        Pruebas de regresión
.github/workflows/            CI
```

## Reproducir el entorno Python

Se recomienda separar el entorno del proyecto del entorno de Airflow:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

python3 -m venv .venv_airflow
.venv_airflow/bin/pip install "apache-airflow==3.3.0" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.3.0/constraints-3.12.txt"
```

Para Airflow:

```bash
export PROYECTO_DIR="$PWD"
export CGR_PROJECT_PYTHON="$PWD/.venv/bin/python"
export AIRFLOW_HOME="$PWD/airflow_home"
```

## Pruebas

```bash
.venv/bin/pytest -q
```

Cubren, entre otros:

- `Contract -> Award -> Supplier`;
- claves `OCID::contract.id`;
- consorcios/adjudicatarios por award;
- topes normativos 2018–2026;
- cambio de régimen 22/04/2025;
- prioridad de `mainProcurementCategory`;
- separación Contratación Directa vs. Comparación de Precios;
- holdout independiente para reentrenamiento.

## Pipeline sintético orquestado

```bash
.venv_airflow/bin/airflow dags test modulo_analisis_datos_1_8_2
```

Flujo conceptual:

```text
fuentes -> Bronce -> preprocesamiento/features -> Plata
                       |                     |
                       |-> tuning favoritismo -> modelo
                       |-> tuning fraccionamiento -> modelo
                       |-> grafos
                                      ↓
                                     Oro
                                      ↓
                              run_manifest.json
                                      ↓
                                 documentación
```

Los scripts también pueden ejecutarse individualmente. En ese caso las
funciones de `src/rutas_datos.py` permiten un fallback explícito a `data/` o
`outputs/`, mostrando una advertencia para distinguirlo del flujo del DAG.

## Datos reales OCDS/OECE

Los crudos y derivados identificables no se publican en este repo. Para
reproducir localmente la validación, seguir `data_real/README.md` con:

- `main.csv`
- `contracts.csv`
- `awards.csv`
- `awards_suppliers.csv`
- `parties.csv`

Los rankings reales se generan localmente, pero están ignorados por Git para
evitar publicar asociaciones entre proveedores reales y señales estadísticas
fuera de contexto.

## Documentación formal

Los `.docx` existentes en `reporte/` y `reporte/productos_formales/` fueron
generados antes de parte de las correcciones P0/P1. Se conservan como evidencia
histórica del desarrollo, pero **no deben considerarse todavía la versión final
actualizada**. Se regenerarán al cerrar P1 usando `run_manifest.json` y los
resultados nuevos.

## Licencia

El código está bajo licencia MIT. Los datos públicos de OECE/OCP conservan su
licencia de origen (CC BY 4.0 cuando corresponda). Si el prototipo evolucionara
a un encargo contractual, los activos generados bajo dicho encargo deberían
separarse y regirse por las cláusulas de propiedad/confidencialidad del TDR.
