# Auditoría de coherencia del estado actual de `main`

> Versión declarada en `VERSION`: **v1.0.0-rc.1**. Si ese tag ya existe, permanece como snapshot histórico e inmutable; este documento audita el commit actual de `main` y no afirma que el tag contenga cambios posteriores.

`release_ready=true` significa que los gates técnicos del repositorio están coherentes; **no significa conformidad, aprobación ni despliegue institucional de la CGR**.

- Commit auditado: `9c7c494c929f21a6ccd4969f915c270fe1c2ea38`
- Checks: **19/19 OK**
- Resultado del gate: **READY**

| Estado | Verificación | Detalle |
|:---:|---|---|
| ✅ | versión semántica release candidate declarada | 1.0.0-rc.1 |
| ✅ | disclaimer público explícito | README distingue el PoC de una implementación oficial sin depender de una frase literal |
| ✅ | release histórico no se presenta como oficial | RELEASE_NOTES mantiene el alcance independiente |
| ✅ | Anexo 3 sin brechas rojas | ✅=6, 🟡=4, 🔵=1, 🔴=0 |
| ✅ | distribución esperada del checklist | 6 ✅ / 4 🟡 / 1 🔵 |
| ✅ | checklist enlazado al catálogo CGR | referencias=['CGR-DEP-01', 'CGR-DEP-02', 'CGR-DEP-03', 'CGR-DEP-04', 'CGR-DEP-05', 'CGR-DEP-06'] |
| ✅ | catálogo institucional único | 8 dependencias canónicas CGR-DEP-01..08 |
| ✅ | contrato SSRS local verificado | {'PrediccionesFavoritismo': 2328, 'PrediccionesFraccionamiento': 180, 'VinculosProveedorFuncionario': 2995} |
| ✅ | dos RDL de riesgo presentes | favoritismo + fraccionamiento + DDL T-SQL |
| ✅ | Accuracy/F1/AUC-ROC reportados en favoritismo | Accuracy se reporta sin desplazar AUC-PR como criterio primario |
| ✅ | Accuracy/F1/AUC-ROC reportados en fraccionamiento | holdout final independiente |
| ✅ | nomenclatura canónica de fraccionamiento | senal_priorizacion_fraccionamiento |
| ✅ | modalidades de favoritismo separadas | Contratación Directa != Comparación de Precios |
| ✅ | Oro sin datasets intermedios | artefactos Oro=9 |
| ✅ | sin derivados reales identificables versionados | raw/derivados reales identificables permanecen fuera del repositorio |
| ✅ | documentación formal completa | 8 DOCX (7 productos + informe final) |
| ✅ | manifiesto reproducible Spark/GraphFrames | commit evidencia=9c7c494c929f21a6ccd4969f915c270fe1c2ea38 |
| ✅ | sin residuos de nomenclatura obsoleta en artefactos canónicos | nomenclatura y conteos vigentes |
| ✅ | licencia presente | MIT para el código del PoC |

## Dependencias institucionales abiertas

No se trasladan aquí como defectos del repositorio. La fuente canónica es `docs/Dependencias_Institucionales_CGR.md` (`CGR-DEP-01..08`).
