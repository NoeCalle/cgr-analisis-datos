# TRAIN / INFERENCE — Sprint 2

Este documento describe la separación operacional incorporada después del release candidate `v1.0.0-rc.1` del PoC público independiente.

> Nada de lo aquí descrito constituye aprobación, despliegue ni arquitectura oficial de la Contraloría General de la República. El objetivo es reducir el trabajo de adaptación futura y dejar explícitas las dependencias institucionales.

## Objetivo

Evitar que una ejecución destinada a puntuar contratos actuales pueda:

- requerir ground truth;
- recalcular estadísticas de preprocesamiento;
- ejecutar tuning;
- reentrenar modelos;
- sobrescribir el modelo que se usa para scoring.

El contrato queda dividido en tres acciones distintas:

```text
TRAIN -> candidate -> promoción explícita -> champion
                                      |
                                      +-> INFERENCE usa únicamente champion
```

La promoción del PoC **no equivale a aprobación institucional CGR**. El registry persiste `institutional_approval=false` de forma explícita.

## 1. TRAIN

Configuración de demostración: `config/local-training.yaml`.

TRAIN requiere ground truth canónico:

- `label_favoritismo`
- `label_fraccionamiento`

La fuente física puede usar otros nombres; Sprint 1 los adapta mediante YAML. En el PoC local se mapean desde las etiquetas sintéticas únicamente para reproducibilidad.

Ejecución:

```bash
python src/entrenar_candidatos.py --config config/local-training.yaml
```

TRAIN realiza:

```text
fuente histórica con labels
    -> integración canónica
    -> FIT del preprocesador
    -> TRANSFORM de TRAIN
    -> feature engineering
    -> entrenamiento
    -> candidate manifest + artefactos candidate
```

Los candidatos se guardan en `outputs/runtime/model_candidates/`, ruta ignorada por Git. Generar un candidato **no modifica** `outputs/model_registry.json` ni los binarios champion.

El manifest registra, entre otros:

- fingerprint SHA-256 del contenido canónico usado para entrenamiento;
- número de filas y positivos;
- lista exacta de features;
- hiperparámetros;
- hashes SHA-256 de los artefactos candidate;
- rutas de evidencia de validación/tuning del PoC.

## 2. Preprocesamiento: FIT solo en TRAIN

`src/preprocesamiento.py` separa ahora:

- `ajustar_estado_preprocesamiento(...)`: aprende estadísticas;
- `aplicar_estado_preprocesamiento(...)`: aplica estadísticas ya aprendidas;
- `preparar_para_features_entrenamiento(...)`: FIT + TRANSFORM;
- `preparar_para_features_inferencia(...)`: solo TRANSFORM.

El estado persistido contiene actualmente:

- mediana de monto por objeto;
- mediana global de monto;
- moda de modalidad;
- moda de objeto;
- P99 de monto;
- versión del esquema de preprocesamiento.

Esto evita *train-serving skew*: un lote de contratos actuales no puede redefinir sus propias medianas, modas ni P99 antes de ser puntuado.

### Corrección de un comportamiento legacy

Durante las pruebas de Sprint 2 se detectó un efecto del pipeline histórico: la expresión

```python
df.groupby("objeto")["monto"].transform(...)
```

excluía por defecto las filas con `objeto` nulo. Al reasignar el resultado del `transform`, un monto originalmente válido podía convertirse en `NaN` y luego ser reemplazado por la mediana global.

Ejemplo sintético versionado detectado por la regresión:

- contrato `C002938`;
- `objeto` nulo;
- monto observado: `117888.71`.

La ruta nueva TRAIN/INFERENCE conserva el monto observado. La función legacy `limpiar_e_imputar(...)` mantiene deliberadamente la semántica anterior **solo para reconstruir las métricas históricas de `v1.0.0-rc.1`**. De esta forma no se reescribe retrospectivamente la evidencia del RC1 y, al mismo tiempo, el serving nuevo no hereda el defecto.

## 3. Candidate no es Champion

`src/registro_modelos.py` mantiene un registry mínimo para demostrar el control de promoción.

Un candidate debe pasar validación de:

- `schema_version`;
- estado `candidate`;
- presencia de todos los artefactos requeridos;
- integridad SHA-256 de cada archivo.

La promoción se realiza con un comando separado:

```bash
python src/promover_candidato.py \
  --manifest outputs/runtime/model_candidates/candidate_manifest.json \
  --approved-by "operador técnico del PoC" \
  --acknowledge-poc-only
```

Sin `--acknowledge-poc-only`, la promoción se bloquea.

El champion se materializa en:

```text
outputs/model_registry.json
outputs/champions/preprocesador_contratos.joblib
outputs/champions/modelo_favoritismo_rf.joblib
outputs/champions/modelo_fraccionamiento_isoforest.joblib
outputs/champions/scaler_fraccionamiento.joblib
```

El registry registra los SHA-256 y vuelve a verificarlos cuando INFERENCE carga el champion.

## 4. INFERENCE

Configuración local: `config/local.yaml`.

No incluye labels.

Ejecución:

```bash
python src/score_inference.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

Flujo:

```text
contratos actuales SIN labels
    -> integración canónica
    -> carga registry champion + verificación SHA-256
    -> carga preprocesador champion
    -> TRANSFORM sin FIT
    -> feature engineering sin labels
    -> predict / decision_function
    -> rankings de priorización
    -> segunda verificación SHA-256 de champion
```

El código de `src/score_inference.py` no contiene llamadas a `.fit()`, constructores de los algoritmos de entrenamiento ni tuning.

Las salidas detalladas se escriben por defecto bajo `outputs/runtime/inference/`, porque una futura fuente institucional podría contener identificadores que no deben versionarse.

La evidencia agregada del smoke reproducible se conserva en `outputs/inference_smoke_summary.json`.

## 5. Airflow: tres responsabilidades diferentes

### Reproducibilidad integral del PoC

`airflow_home/dags/dag_modulo_analisis_datos.py`

DAG ID:

```text
reproducibilidad_poc_1_8_2
```

Reconstruye datos sintéticos, benchmarks, Spark MLlib, GraphFrames, Oro y evidencia documental. Deliberadamente puede entrenar porque su finalidad es reproducir la evidencia, **no servir predicciones operacionales**.

### TRAIN

`airflow_home/dags/dag_entrenamiento_modelos.py`

DAG ID:

```text
entrenamiento_candidato_1_8_2
```

Genera candidate. No contiene una tarea de promoción.

### INFERENCE

`airflow_home/dags/dag_inferencia_modelos.py`

DAG ID:

```text
inferencia_modelos_1_8_2
```

Solo llama `src/score_inference.py`. No genera datos sintéticos, no ejecuta tuning y no entrena.

## 6. Evidencia CI de cierre

GitHub Actions valida automáticamente que:

1. las regresiones legacy siguen reproduciendo los artefactos del RC1;
2. el nuevo preprocesamiento no sustituye un monto válido por tener `objeto` nulo;
3. TRAIN genera un candidate y no cambia registry/champion;
4. la promoción requiere reconocimiento explícito de alcance PoC;
5. INFERENCE recibe la configuración sin labels;
6. INFERENCE no ejecuta training ni tuning;
7. los hashes champion son idénticos antes y después del scoring;
8. se producen 2,328 scores de favoritismo y 180 scores de fraccionamiento para los 3,709 contratos sintéticos actuales;
9. después de ese smoke continúan pasando Spark MLlib, GraphFrames, Oro y los ocho DOCX formales.

El champion actual de demostración queda identificado por `champion_id` dentro de `outputs/model_registry.json`; ese identificador es técnico y reproducible, no institucional.

## 7. Qué sigue dependiendo de CGR

Sprint 2 resuelve el **contrato de software** entre entrenamiento y scoring. No puede resolver desde este repositorio:

- quién tiene autoridad institucional para aprobar/promover un modelo;
- el registry/MLOps corporativo que CGR decida utilizar;
- credenciales, roles y segregación DEV/QA/PROD;
- fuentes históricas con ground truth institucional;
- clúster Spark/Lakehouse institucional;
- criterios numéricos de aceptación productiva no consignados en el TDR público;
- despliegue, marcha blanca, certificación y transferencia formal.

Esas responsabilidades deben integrarse mediante los controles y plataformas que defina la CGR.