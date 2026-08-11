# Módulo de Análisis de Datos para Priorización de Riesgos de Contratación

> **Prototipo público e independiente basado en el TDR del Proyecto Interno 1.8.2.**  
> No constituye una implementación oficial de la Contraloría General de la República (CGR), no utiliza accesos internos de la institución y no implica aprobación, certificación ni despliegue productivo.

Este repositorio implementa una herramienta reproducible para **integrar información de contratación, construir características analíticas, generar señales de riesgo y priorizar casos para revisión humana**. El alcance incluye posible favoritismo, posible fraccionamiento, vínculos proveedor–funcionario, análisis de pagos y modalidades, Apache Spark MLlib, GraphFrames, Airflow, capas Bronce/Plata/Oro, trazabilidad, model registry y contrato de reporting para SQL Server/SSRS.

Las salidas son **señales de priorización**. No constituyen hallazgos de control, imputaciones, decisiones jurídicas ni determinaciones automáticas de irregularidad.

---

## 1. Qué resuelve la herramienta

El módulo organiza el análisis alrededor de cuatro frentes:

| Frente | Unidad analítica | Resultado |
|---|---|---|
| Posible favoritismo | par proveedor–entidad | score/ranking de priorización |
| Posible fraccionamiento | proveedor–entidad–familia de objeto | score de anomalía + señal interpretable |
| Vínculos | red proveedor–funcionario | relaciones y señales de conectividad |
| Pagos y modalidades | contrato / modalidad / régimen | ratios, demoras, estados y contexto analítico |

La herramienta no intenta reemplazar el criterio auditor. Su función es **reducir el espacio de revisión**, hacer explícitos los factores que generan una señal y conservar evidencia suficiente para reproducir cada ejecución.

---

## 2. Arquitectura operacional

```text
Fuentes configuradas
(SQL Server / Spark SQL / CSV controlado)
              |
              v
      connector + mapping YAML
              |
              v
        esquema canónico
              |
        quality gates
              |
      +-------+--------+
      |                |
      | TRAIN          | INFERENCE
      v                v
FIT preprocesador   preprocesador congelado
      |                |
      v                v
features Spark      features Spark
      |                |
      v                v
modelos MLlib      champion MLlib
      |                |
      v                v
candidate --------> scores/rankings
      |
      | evaluación + aprobación explícita
      v
   champion
```

El **perfil operacional objetivo es `spark_mllib`**. Las implementaciones sklearn se conservan como benchmarks metodológicos, regresión reproducible y apoyo de explicabilidad; no definen el serving activo.

Para `source.type: spark_sql`, el DataFrame permanece en Spark desde `SparkSession.table(...)` hasta MLlib y la escritura distribuida. Para `local_csv` y `sqlserver` existe un adaptador pandas→Spark adecuado para demostración local y volúmenes acotados.

**INFERENCE no consume labels, no ejecuta `.fit()`, no hace tuning y no reentrena.** TRAIN genera un candidate; la promoción del candidate es una operación distinta.

Más detalle: [`docs/Train_Inference.md`](docs/Train_Inference.md) y [`docs/Arquitectura_MLOps.md`](docs/Arquitectura_MLOps.md).

---

## 3. Decisiones de diseño y fundamento

### 3.1 Esquema canónico en lugar de columnas físicas

Los modelos dependen de nombres canónicos y no de nombres físicos de SIAF, SEACE, Datamart u otra fuente.

```yaml
mapping:
  contracts:
    id_contrato: COLUMNA_FISICA_CONTRATO
    id_proveedor: COLUMNA_FISICA_PROVEEDOR
    monto: COLUMNA_FISICA_MONTO
```

**Por qué:** desacoplar el análisis de la estructura física permite cambiar tablas, vistas o nombres de columnas sin reescribir feature engineering, TRAIN o INFERENCE. La adaptación institucional se concentra en fuentes, mappings, permisos y gobierno.

Referencia: [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md).

### 3.2 Quality gates antes del modelado

La integración valida claves primarias, identificadores vacíos, integridad referencial cuando existe la dimensión padre, montos negativos y reglas estructurales del contrato.

**Por qué:** una duplicidad, una clave rota o un error de fuente puede crear artificialmente concentración, frecuencia o montos y terminar convertido en una señal de riesgo falsa.

Referencia: [`docs/Quality_Gates_Datos.md`](docs/Quality_Gates_Datos.md).

### 3.3 FIT del preprocesamiento solo durante TRAIN

El preprocesador aprende durante TRAIN:

- mediana de monto por objeto;
- mediana global;
- moda de modalidad;
- moda de objeto;
- percentil 99 de monto;
- versión del contrato.

INFERENCE reutiliza exactamente ese estado congelado.

**Por qué:** recalcular estadísticas con el lote que se está puntuando introduce *train-serving skew*, hace que el comportamiento del modelo dependa de cada lote y reduce la trazabilidad de la inferencia.

### 3.4 `monto_capped` para favoritismo, monto original para fraccionamiento

Favoritismo utiliza `monto_capped`, limitado por el P99 aprendido únicamente en TRAIN.

**Por qué:** reduce la influencia de contratos monetariamente extremos sobre características agregadas sin aprender información del lote de inferencia.

Fraccionamiento conserva el monto sin capar.

**Por qué:** sus características comparan cuantías contractuales con referencias normativas; alterar la escala monetaria cambiaría el significado de esa comparación.

### 3.5 Random Forest Spark para favoritismo

El modelo operacional de favoritismo es un `RandomForestClassificationModel` de Spark MLlib.

**Por qué:** permite representar relaciones no lineales, manejar múltiples variables agregadas, incorporar ponderación ante desbalance y producir Feature Importance directamente ligada al champion servido.

La selección y evaluación utilizan AUC-PR como métrica primaria porque la clase positiva es minoritaria; Accuracy, AUC-ROC, precision, recall, F1 y recall@K se conservan como métricas complementarias.

El benchmark sklearn compara Regresión Logística, Random Forest y Gradient Boosting y proporciona SHAP como evidencia explicativa complementaria.

### 3.6 KMeans Spark para fraccionamiento

El modelo operacional de fraccionamiento combina:

```text
features
   -> StandardScalerModel
   -> KMeansModel
   -> distancia al centroide
   -> score de anomalía
```

**Por qué:** Spark MLlib no incluye Isolation Forest nativo y el caso requiere una implementación distribuible que produzca un ranking aun cuando el ground truth operativo sea escaso. Las etiquetas se utilizan para evaluación y selección de configuración, no para ajustar KMeans.

Isolation Forest permanece como benchmark sklearn de compatibilidad, no como champion operativo.

### 3.7 `objeto_familia` en lugar de igualdad textual exacta

El fraccionamiento agrupa pequeñas variantes lexicales mediante una firma reproducible y auditable (`objeto_familia`).

**Por qué:** exigir igualdad exacta entre textos puede separar contratos conceptualmente similares solo por puntuación, flexión o variantes controladas. Se eligió una normalización lexical conservadora en lugar de embeddings opacos para mantener trazabilidad y comportamiento determinista.

### 3.8 Cantidad y monto de una misma ventana de 15 días

`max_contratos_ventana_15d` y `monto_total_ventana_15d` corresponden al **mismo intervalo seleccionado**.

**Por qué:** reportar el máximo número de contratos de una ventana y el máximo monto de otra produciría dos indicadores que aparentan describir un mismo episodio sin hacerlo realmente.

La ventana de 15 días es una **heurística analítica de priorización** y no constituye por sí sola una regla jurídica.

### 3.9 TRAIN, candidate, champion e INFERENCE separados

```text
TRAIN -> candidate -> evaluación/gate -> promoción explícita -> champion -> INFERENCE
```

**Por qué:** evita que entrenar habilite serving automáticamente, separa responsabilidades, permite revisar evidencia antes de promoción y hace posible rollback hacia un champion anterior.

### 3.10 Candidate y champion versionados por contenido

Los manifests registran hashes SHA-256, fingerprint del corpus, preprocesador, hiperparámetros y evidencia de evaluación. Las promociones nuevas se almacenan por `candidate_id` en un store inmutable y el registry cambia el puntero solo después de verificar el conjunto completo.

**Por qué:** una inferencia debe poder asociarse a los artefactos exactos con los que fue producida y una promoción parcial no debe dejar el registry apuntando a un conjunto inconsistente.

### 3.11 `spark_sql` permanece distribuido

```text
Spark SQL / Lakehouse
        -> Spark DataFrame
        -> mapping y validación Spark
        -> FIT/TRANSFORM Spark
        -> feature engineering Spark
        -> evaluación/TRAIN/INFERENCE MLlib
        -> Parquet distribuido
```

**Por qué:** materializar el corpus contractual en pandas o en el driver rompería la propiedad de escalabilidad que justifica Spark y podría convertirse en un cuello de botella de memoria.

La evaluación de modelos también dispone de ruta `spark_sql` distribuida y conserva el mismo fingerprint de corpus exigido por TRAIN.

### 3.12 No se implementa un Spark JDBC genérico con parámetros ficticios

El conector SQL Server actual es un adaptador pandas para volúmenes acotados. Para grandes volúmenes se prioriza `spark_sql`.

**Por qué:** un Spark JDBC robusto necesita driver, autenticación, estrategia de particionamiento, límites, aislamiento y estándares de infraestructura que deben ser definidos por la institución. Inventar esos valores en el PoC produciría una falsa sensación de cierre.

### 3.13 Shared Data Source en SSRS

Los RDL referencian `CGR_ModuloAnalisis` y no versionan hostname, catálogo o credenciales.

**Por qué:** cada ambiente puede vincular el mismo reporte a su datasource administrado sin modificar el RDL y sin incorporar información de conexión al repositorio.

Referencia: [`ssrs/README.md`](ssrs/README.md).

---

## 4. Contrato de datos

Dominios canónicos soportados:

- `contracts`
- `suppliers`
- `entities`
- `officials`
- `payments`

Campos obligatorios de `contracts` en INFERENCE:

```text
id_contrato
id_proveedor
id_entidad
monto
fecha_contrato
modalidad
objeto
categoria_principal
```

TRAIN añade:

```text
label_favoritismo
label_fraccionamiento
```

Los labels no forman parte del contrato de INFERENCE. En una implantación institucional deben provenir de un ground truth aprobado y no de los scores del propio modelo.

`categoria_principal` existe para resolver el contexto normativo del análisis de fraccionamiento. Puede contener nulos cuando el proveedor de umbrales dispone de fallback, pero la columna debe existir.

Referencia técnica completa: [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md).

---

## 5. Modelos y evaluación

### Favoritismo — serving Spark

- motor: Apache Spark MLlib;
- algoritmo: Random Forest;
- unidad analítica: proveedor–entidad;
- monto: `monto_capped`;
- holdout reservado antes del FIT del preprocesador;
- CV/tuning únicamente sobre desarrollo;
- métricas: AUC-PR, AUC-ROC, Accuracy, precision, recall, F1, recall@K;
- explicabilidad principal: Feature Importance del modelo servido;
- explicación complementaria: SHAP sobre benchmark sklearn.

### Fraccionamiento — serving Spark

- motor: Apache Spark MLlib;
- algoritmo: StandardScaler + KMeans + distancia al centroide;
- unidad analítica: proveedor–entidad–`objeto_familia`;
- monto original para contexto normativo;
- selección de `k` en desarrollo;
- holdout final independiente;
- labels no usados en el FIT de KMeans;
- señal complementaria interpretable basada en concentración temporal y cuantía.

### Interpretación de métricas

Las métricas generadas con el benchmark sintético validan **coherencia metodológica y funcionamiento reproducible del pipeline**. No estiman por sí solas desempeño productivo CGR.

La validación con datos públicos OCDS/OECE prueba portabilidad de transformaciones y reglas, pero no calibra el champion porque esa fuente no contiene ground truth institucional de favoritismo/fraccionamiento.

---

## 6. Datos públicos OCDS/OECE

El repositorio incluye una prueba adicional con datos abiertos reales para comprobar portabilidad de la metodología.

La relación utilizada es:

```text
Contract(main_ocid, awardID)
        -> Award(main_ocid, id)
        -> awards_suppliers(main_ocid, awards_id)
```

**Por qué:** el adjudicatario debe resolverse respecto de la adjudicación vinculada al contrato. Asociar proveedores únicamente a nivel general del OCID puede mezclar adjudicaciones distintas.

Los archivos crudos y rankings identificables no se versionan en este repositorio público.

Referencia: [`data_real/README.md`](data_real/README.md).

---

## 7. TRAIN, promoción e INFERENCE

### TRAIN Spark

```bash
python src/spark/entrenar_candidato_spark.py \
  --config config/local-training.yaml
```

TRAIN exige evidencia de evaluación correspondiente al **mismo fingerprint de corpus** y genera un candidate sin modificar el champion activo.

### Promoción técnica del PoC

```bash
python src/promover_candidato_spark.py \
  --manifest outputs/runtime/spark_model_candidates/candidate_manifest.json \
  --approved-by "operador técnico" \
  --acknowledge-poc-only
```

La promoción técnica del PoC no equivale a aprobación institucional. En un despliegue real debe integrarse con segregación de funciones, permisos y MLOps institucional.

### INFERENCE Spark

```bash
python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

El scorer:

1. integra al contrato canónico;
2. carga registry y champion;
3. verifica hashes;
4. carga el preprocesador congelado;
5. transforma sin FIT;
6. genera features;
7. carga los modelos MLlib;
8. produce rankings;
9. vuelve a verificar integridad antes de publicar.

Las salidas se generan primero en staging y solo se publican después del gate de integridad.

Referencia: [`docs/Train_Inference.md`](docs/Train_Inference.md).

---

## 8. Model registry, promoción y rollback

`outputs/model_registry.json` mantiene perfiles separados:

```text
serving_profiles
├── sklearn      # benchmark / compatibilidad
└── spark_mllib  # serving objetivo
```

Las promociones nuevas se almacenan bajo:

```text
outputs/champion_store/<profile>/<candidate_id>/
```

El registry conserva historial suficiente para rollback explícito. Los artefactos se verifican por SHA-256 y los candidates deben pertenecer a roots autorizados.

Referencia: [`docs/Arquitectura_MLOps.md`](docs/Arquitectura_MLOps.md).

---

## 9. Monitoreo y reentrenamiento

El monitor del champion activo controla:

- integridad del registry/champion;
- PSI de features de favoritismo;
- PSI de features y score de fraccionamiento;
- recall@K cuando existe ground truth válido;
- vínculo entre baseline y fingerprint de entrenamiento;
- generación de candidate cuando corresponde y existen labels adecuados.

Un trigger puede solicitar/generar un candidate, pero **no existe autopromoción**.

Un lote sin labels puede utilizarse para drift; no debe transformarse silenciosamente en ground truth de reentrenamiento.

El monitor batch público no colecta `spark_sql` al driver. La observabilidad distribuida institucional requiere definir fuente de lotes, persistencia de métricas, alertamiento y plataforma CGR.

---

## 10. Airflow

| DAG | Propósito |
|---|---|
| `reproducibilidad_poc_1_8_2` | reconstruir evidencia reproducible del PoC |
| `entrenamiento_candidato_1_8_2` | entrenar candidate Spark sin promoverlo |
| `inferencia_modelos_1_8_2` | puntuar con champion Spark sin reentrenar |
| `monitoreo_reentrenamiento_1_8_2` | ejecutar monitoreo sobre un lote externo configurado |

TRAIN, INFERENCE y monitoreo usan ejecuciones aisladas y `max_active_runs=1` para evitar solapamientos sobre artefactos compartidos.

Variables principales:

```text
PROYECTO_DIR
CGR_PROJECT_PYTHON
CGR_DATA_CONFIG
CGR_TRAIN_CONFIG
CGR_MODEL_REGISTRY
CGR_SPARK_MASTER
CGR_SPARK_SHUFFLE_PARTITIONS
CGR_SPARK_CANDIDATE_BASE
CGR_INFERENCE_OUTPUT_BASE
CGR_MONITOR_CONFIG
CGR_MONITOR_BATCH_PATH
CGR_MONITOR_OUTPUT_BASE
CGR_MONITOR_SCHEDULE
```

---

## 11. Spark operacional y escala

TRAIN e INFERENCE admiten:

```bash
export CGR_SPARK_MASTER='<master Spark aprobado>'
export CGR_SPARK_SHUFFLE_PARTITIONS='<n>'
```

Si `CGR_SPARK_MASTER` no está definido, el PoC usa `local[*]` como fallback de demostración.

La evaluación, TRAIN e INFERENCE tienen una frontera `spark_sql` que evita materializar observaciones en pandas. Las medianas por objeto aprendidas durante TRAIN se almacenan como Parquet Spark cuando la fuente es distribuida y vuelven a cargarse en INFERENCE.

El repositorio incluye un benchmark operacional parametrizable, pero sus resultados tienen `institutional_acceptance=false`: una prueba local no sustituye pruebas de volumen, concurrencia, skew, memoria y robustez sobre el clúster real.

Referencia: [`docs/Evaluacion_Spark_y_Performance.md`](docs/Evaluacion_Spark_y_Performance.md).

---

## 12. Reporting SQL Server / SSRS

El directorio `ssrs/` contiene:

- DDL T-SQL;
- vistas estables de reporting;
- plantilla de roles de mínimo privilegio;
- RDL de favoritismo;
- RDL de fraccionamiento.

Los RDL consumen un Shared Data Source llamado `CGR_ModuloAnalisis`. El binding real por DEV/QA/PROD se realiza fuera del archivo versionado.

`src/publicar_ssrs.py` valida localmente el contrato de datos; no despliega en un servidor institucional.

Referencia: [`ssrs/README.md`](ssrs/README.md).

---

## 13. Seguridad y gobernanza

Principios aplicados en el repositorio:

- secretos fuera de Git/YAML;
- `connection_env` referencia una variable de entorno, no una connection string;
- acciones CI con privilegio mínimo y separación del job con escritura;
- GitHub Actions externas fijadas a SHA;
- candidates restringidos a roots autorizados;
- artefactos de candidate verificados antes de promoción;
- champion store versionado;
- datos sintéticos identificados explícitamente con prefijos `SYN-*`;
- datos reales identificables excluidos del repositorio público;
- promoción separada de TRAIN;
- revisión humana obligatoria de señales;
- SQL/SSRS preparado para mínimo privilegio.

Los controles de identidad real, SSO/MFA, secret manager, redes, TLS/PKI, SIEM, backups, retención, roles efectivos y segregación DEV/QA/PROD dependen del entorno institucional.

Referencia: [`docs/Seguridad_y_Gobernanza.md`](docs/Seguridad_y_Gobernanza.md).

---

## 14. Capas de datos y trazabilidad

La ruta reproducible materializa capas Bronce/Plata/Oro y artefactos de evidencia. La ruta operacional no obliga a pasar por una Plata CSV para poder servir sobre `spark_sql`.

| Ruta | Contenido |
|---|---|
| `lakehouse/oro/` | salidas downstream reproducibles del PoC |
| `outputs/model_registry.json` | registry y perfil activo |
| `outputs/champion_store/` | promociones versionadas cuando corresponda |
| `outputs/runtime/` | candidates, staging e inferencias; no versionados |
| `outputs/linaje_datos.csv` | linaje fuente → transformación → feature → modelo/salida |
| `data/diccionario_datos.csv` | diccionario de datos |
| `outputs/run_manifest.json` | versiones, hashes, parámetros y artefactos |
| `outputs/evidencia_documental.json` | fuente machine-readable para documentación formal |
| `ssrs/` | contrato T-SQL/RDL de reporting |
| `reporte/` | generación de Productos 1–7 e Informe Final |

La identidad reproducible del experimento se calcula con entradas estables y se mantiene separada de metadata variable de ejecución como timestamps o duración.

---

## 15. Inicio rápido local

### Requisitos

- Python 3.12 recomendado;
- Java 17 para Spark;
- Graphviz para artefactos gráficos;
- Airflow solo para ejecutar/cargar DAGs;
- LibreOffice solo para materializar/QA de los DOCX formales;
- `pyodbc` + driver ODBC únicamente para SQL Server.

### Instalación

```bash
git clone https://github.com/NoeCalle/cgr-analisis-datos.git
cd cgr-analisis-datos

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

En Windows, usar los ejecutables equivalentes de `.venv\Scripts\`.

### Pruebas

```bash
.venv/bin/pytest -q
```

### Validar una configuración sin conectarse

```bash
.venv/bin/python src/ingestar_canonico.py \
  --config config/cgr.example.yaml \
  --validate-only
```

### Evaluar modelos Spark sobre el corpus configurado

```bash
.venv/bin/python src/spark/evaluar_favoritismo_spark.py \
  --config config/local-training.yaml

.venv/bin/python src/spark/evaluar_fraccionamiento_spark.py \
  --config config/local-training.yaml
```

### Entrenar candidate Spark

```bash
.venv/bin/python src/spark/entrenar_candidato_spark.py \
  --config config/local-training.yaml
```

### Ejecutar INFERENCE

```bash
.venv/bin/python src/spark/score_inference_spark.py \
  --config config/local.yaml \
  --registry outputs/model_registry.json
```

### Analizar pagos y modalidades

```bash
.venv/bin/python src/analisis_pagos_modalidades.py \
  --config config/local-tdr.yaml
```

---

## 16. Integración institucional

La adaptación prevista se concentra en **fuentes, mappings, infraestructura, seguridad, ground truth y gobierno**, no en reescribir los modelos por cambios de nombres físicos.

Secuencia recomendada:

1. migrar una revisión aprobada del código a un repositorio institucional privado;
2. registrar el commit de origen;
3. aprobar tablas/vistas y diccionario;
4. configurar mappings al esquema canónico;
5. inyectar secretos mediante el mecanismo institucional;
6. validar quality gates en DEV;
7. preparar ground truth histórico aprobado;
8. ejecutar evaluación sobre ese mismo corpus;
9. entrenar candidate Spark;
10. revisar métricas, hashes y artefactos;
11. promover mediante autoridad separada;
12. ejecutar INFERENCE;
13. publicar salidas aprobadas en almacenamiento/SQL Server/SSRS;
14. validar QA/PROD, rendimiento, observabilidad, rollback y operación.

Manual: [`docs/Manual_Aterrizaje_Institucional_CGR.md`](docs/Manual_Aterrizaje_Institucional_CGR.md).

La plantilla `config/cgr.example.yaml` contiene placeholders; no representa nombres reales de tablas, vistas o columnas CGR.

---

## 17. Qué está demostrado y qué sigue siendo institucional

La auditoría reproducible del TDR público mantiene:

| Estado | Criterios | Interpretación |
|---|---:|---|
| ✅ | 12 | cubiertos con evidencia reproducible del repositorio |
| 🟡 | 8 | software/contrato demostrable; cierre literal requiere entorno o validación CGR |
| 🔵 | 5 | actividades institucionales/contractuales |
| 🔴 | **0** | no quedan brechas cerrables desde el repositorio dentro de los criterios evaluados |

`0 🔴` **no equivale a producción certificada**.

Siguen dependiendo de CGR, entre otros:

- fuentes internas y ground truth institucional;
- clúster, almacenamiento y observabilidad reales;
- performance/robustez con volumen y concurrencia reales;
- identidad, permisos y segregación DEV/QA/PROD;
- umbrales numéricos de aceptación productiva;
- ejecución SQL Server/SSRS institucional;
- certificación, marcha blanca y transferencia formal.

Referencias:

- [`docs/Auditoria_TDR_Completo.md`](docs/Auditoria_TDR_Completo.md)
- [`docs/Checklist_Anexo_03.md`](docs/Checklist_Anexo_03.md)
- [`docs/Dependencias_Institucionales_CGR.md`](docs/Dependencias_Institucionales_CGR.md)

---

## 18. Documentación técnica

| Documento | Propósito |
|---|---|
| [`docs/Integracion_Datos.md`](docs/Integracion_Datos.md) | contrato canónico, conectores y frontera Spark |
| [`docs/Quality_Gates_Datos.md`](docs/Quality_Gates_Datos.md) | calidad estructural e integridad referencial |
| [`docs/Train_Inference.md`](docs/Train_Inference.md) | separación TRAIN/INFERENCE y serving |
| [`docs/Arquitectura_MLOps.md`](docs/Arquitectura_MLOps.md) | registry, candidate, promoción, rollback y monitor |
| [`docs/Seguridad_y_Gobernanza.md`](docs/Seguridad_y_Gobernanza.md) | seguridad del repositorio, artefactos y reporting |
| [`docs/Evaluacion_Spark_y_Performance.md`](docs/Evaluacion_Spark_y_Performance.md) | evaluación distribuida, fingerprints y benchmark operacional |
| [`docs/Manual_Aterrizaje_Institucional_CGR.md`](docs/Manual_Aterrizaje_Institucional_CGR.md) | guía de adopción institucional |
| [`ssrs/README.md`](ssrs/README.md) | contrato SQL Server / SSRS |
| [`data_real/README.md`](data_real/README.md) | prueba con datos abiertos OCDS/OECE |

Los documentos de auditoría y `RELEASE_NOTES.md` conservan evidencia de cumplimiento y snapshots de release. La descripción funcional vigente de la herramienta se mantiene en este README y en los documentos técnicos anteriores.

---

## 19. CI y reproducibilidad

GitHub Actions valida, entre otros:

- pruebas unitarias/regresión;
- contrato canónico pandas y Spark-native;
- quality gates;
- ausencia de `toPandas()` en la frontera distribuida protegida;
- evaluación Spark ligada al mismo fingerprint exigido por TRAIN;
- candidate aislado del champion;
- promoción explícita e integridad de artefactos;
- INFERENCE sin labels/FIT/tuning;
- publicación de rankings solo después del gate de integridad;
- KMeans/RandomForest MLlib;
- GraphFrames;
- Oro y trazabilidad;
- seguridad de rutas/secrets/CI;
- carga de DAGs Airflow;
- generación, render y QA de los ocho DOCX;
- checklist Anexo 3 y auditoría integral del TDR.

---

## 20. Principio de uso responsable

Un score alto significa **prioridad analítica para revisión**, no culpabilidad ni confirmación de irregularidad. La interpretación final requiere contexto contractual, normativa aplicable, documentación de sustento y juicio profesional del auditor o especialista responsable.
