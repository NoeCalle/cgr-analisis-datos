# Prueba con datos abiertos SEACE / OCDS

Esta ruta permite ejecutar una prueba adicional del PoC sobre **datos abiertos reales** para observar la portabilidad de la metodología fuera del benchmark sintético. No sustituye la integración institucional prevista por el TDR y no valida el champion operativo porque la publicación abierta no contiene ground truth aprobado de favoritismo/fraccionamiento.

Los resultados deben interpretarse como **señales estadísticas para priorización de revisión**. No constituyen hallazgos ni determinaciones de irregularidad.

## 1. Contrato relacional OCDS utilizado

La asociación contrato–adjudicación–proveedor se resuelve mediante:

```text
Contract(main_ocid, awardID)
        |
        v
Award(main_ocid, id)
        |
        v
awards_suppliers(main_ocid, awards_id)
```

La clave analítica del contrato es:

```text
OCID::contract.id
```

### Por qué se usa esta relación

El proveedor debe asociarse a la **adjudicación específica vinculada al contrato**. Vincular suppliers únicamente a nivel general del OCID puede mezclar adjudicatarios pertenecientes a awards distintos del mismo proceso.

Los contratos cuyo award/supplier no puede resolverse se excluyen de análisis que dependan de proveedor y se contabilizan explícitamente.

## 2. Integridad de la corrida publicada

La evidencia agregada versionada registra:

- contratos crudos: **47,510**;
- contratos con adjudicación y supplier resolubles: **47,254**;
- contratos excluidos por no poder resolver adjudicación/supplier: **256**;
- adjudicatarios distintos presentes en contratos: **25,861**;
- entidades distintas: **2,732**;
- categorías OCDS: 23,630 `goods`, 18,584 `services`, 5,040 `works`;
- rango de fecha de firma: 2018-09-18 a 2024-11-08.

El resumen completo, hashes de fuentes y validaciones se conserva en:

```text
outputs/validacion_p0_datos_reales.json
```

## 3. Política de publicación

Los archivos crudos y derivados identificables **no se versionan** en este repositorio público.

Se excluyen, entre otros:

```text
main.csv
contracts.csv
awards.csv
awards_suppliers.csv
parties.csv
sources.csv
contratos_reales.csv
proveedores_reales.csv
entidades_reales.csv
*_REAL.csv
```

### Por qué

Aunque la fuente sea pública, publicar un ranking que asocie un proveedor real con una señal de riesgo generada por un prototipo sin ground truth puede inducir a una interpretación incorrecta fuera de su contexto metodológico. El repositorio conserva evidencia agregada y reproducible, no rankings identificables.

## 4. Fuente

Portal de Datos Abiertos de la OECE (Perú), publicación OCDS utilizada por el proyecto.

Licencia de datos de la publicación: Creative Commons Attribution 4.0 International (CC BY 4.0).

La referencia de descarga está documentada en los artefactos de validación del proyecto.

## 5. Cómo reproducir localmente

1. descargar y descomprimir la publicación OCDS;
2. colocar en `data_real/` como mínimo:
   - `main.csv`;
   - `contracts.csv`;
   - `awards.csv`;
   - `awards_suppliers.csv`;
   - `parties.csv`;
3. ejecutar:

```bash
python src/cargar_datos_reales_seace.py
```

4. verificar la evidencia de integridad;
5. ejecutar las pruebas de regresión:

```bash
pytest -q
```

6. ejecutar el análisis exploratorio sobre datos reales:

```bash
python src/modelo_real.py
```

Los rankings resultantes deben permanecer fuera del repositorio público.

## 6. Adjudicatarios y consorcios

La identidad del proveedor se toma de `awards_suppliers` respecto del award correspondiente.

Muchos consorcios aparecen como una **entidad adjudicataria propia** (`CONSORCIO ...`). No deben reconstruirse agrupando indiscriminadamente todas las parties supplier del OCID.

Si una publicación OCDS contiene realmente más de un supplier para una misma adjudicación, el loader genera una identidad compuesta determinística para ese award sin mezclar proveedores de adjudicaciones distintas.

### Por qué

El nivel correcto de asociación es la adjudicación. El proceso puede contener varios awards y cada uno puede tener proveedores diferentes.

## 7. Categoría contractual y motor normativo

Se conserva `tender_mainProcurementCategory` como `categoria_principal`.

Cuando existe, esta categoría estructurada (`goods`, `services`, `works`) tiene prioridad para resolver el contexto normativo. El texto libre del objeto se utiliza únicamente como fallback conservador.

### Por qué

Distinguir bienes/servicios/obras mediante una variable estructurada es más reproducible y menos ambiguo que inferir siempre la categoría desde descripciones libres.

El corpus contiene contratos con fechas de firma entre 2018 y 2024; por ello el motor normativo incorpora las vigencias necesarias dentro de ese intervalo y falla explícitamente para años no parametrizados en vez de aproximar una cuantía.

## 8. Portabilidad del feature engineering

Fraccionamiento reutiliza el mismo contrato de features canónico que el pipeline principal:

- `objeto_familia`;
- semántica de ventana de 15 días;
- cuantías normativas por fecha/categoría;
- agregación proveedor–entidad–familia.

### Por qué

La prueba con datos públicos debe comprobar si **las mismas transformaciones** pueden aplicarse sobre otra distribución, no crear una metodología distinta solo para producir resultados visualmente favorables.

## 9. Favoritismo sobre datos abiertos

La ruta de datos reales utiliza una señal no supervisada independiente para explorar concentración proveedor–entidad.

Esta señal **no es el champion Spark del model registry** y no lo recalibra.

### Por qué

La publicación abierta no contiene labels institucionales de favoritismo. Sin ground truth no es posible estimar precision/recall del champion ni justificar una nueva versión supervisada.

## 10. Vínculos

OCDS abierto no contiene funcionarios públicos individuales con el contrato requerido por el modelo de vínculos. La prueba real se limita a relaciones organizacionales proveedor–entidad y coincidencias de información publicada cuando existen.

No debe interpretarse esa adaptación como equivalente al análisis institucional proveedor–funcionario previsto por el módulo completo.

## 11. Limitaciones

- no existe ground truth real de favoritismo/fraccionamiento;
- los rankings no permiten estimar precisión productiva;
- la señal de favoritismo de esta ruta es exploratoria/no supervisada;
- no se valida ni recalibra el champion servido;
- la disponibilidad de contactos depende de la completitud de la publicación;
- el texto libre utilizado para EDA no sustituye `categoria_principal` para contexto normativo;
- el corpus abierto no representa necesariamente la distribución, variables o calidad de las fuentes internas CGR.

La validación productiva requiere datos institucionales, definición de ground truth, revisión funcional y criterios de aceptación aprobados.
