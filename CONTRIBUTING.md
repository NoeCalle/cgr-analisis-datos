# Contribuciones y feedback

Este repositorio es un **prototipo público e independiente** basado en el TDR del Proyecto Interno 1.8.2 de la CGR. No es una implementación oficial de la Contraloría General de la República. Las contribuciones de investigadores, entidades públicas, universidades y desarrolladores son bienvenidas dentro de ese marco.

## Cómo reportar problemas

Usa **GitHub Issues** para:

- errores de ejecución en el quickstart, los tests o los scripts;
- inconsistencias entre el código, la documentación y la evidencia versionada;
- problemas de reproducibilidad (resultados que difieren entre corridas o entornos);
- observaciones metodológicas sobre features, modelos, umbrales normativos o evaluación.

Un buen reporte incluye: sistema operativo, versión de Python y Java, el comando exacto ejecutado y la salida completa del error.

Para vulnerabilidades de seguridad, **no abras un issue público**: sigue el procedimiento de [`SECURITY.md`](SECURITY.md).

## Cómo proponer cambios

1. Abre primero un issue describiendo el problema o la mejora, para discutir el enfoque antes de invertir trabajo.
2. Haz fork del repositorio y crea una rama descriptiva.
3. Verifica localmente antes de abrir el pull request:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

4. Los pull requests corren el CI no privilegiado (tests, DagBag de Airflow, CodeQL) con token de solo lectura. La persistencia de artefactos y el etiquetado de releases ocurren únicamente desde `main`.

## Principios que toda contribución debe respetar

- **Uso responsable**: las salidas de los modelos son señales de priorización para revisión humana; ninguna contribución debe presentarlas como hallazgos, imputaciones o determinaciones automáticas de irregularidad.
- **Sin datos identificables**: no se versionan datasets institucionales, rankings derivados de datos reales identificables, credenciales ni connection strings. Los identificadores sintéticos usan prefijos inequívocos (`SYN-DNI-`, `SYN-RUC-`, `SYN-TEL-`, `SYN-DIR-`).
- **Separación TRAIN/INFERENCE**: INFERENCE no consume labels, no ejecuta `.fit()` y no reentrena; los tests de regresión lo verifican con hashes.
- **Reproducibilidad**: dependencias fijadas, artefactos regenerables y evidencia machine-readable. Un cambio que rompa la regeneración determinista de la evidencia necesita justificación explícita.
- **Honestidad de alcance**: las limitaciones se documentan como tales; no se presenta como resuelto lo que depende de infraestructura, fuentes o aprobaciones institucionales (`CGR-DEP-01..08`).

## Licencia

Al contribuir aceptas que tu aporte se publique bajo la licencia MIT del repositorio. Los datos abiertos de SEACE/OECE conservan su licencia CC BY 4.0 y no se versionan en forma identificable.
