# Auditoría final de release — v1.0.0-rc.1

> Release candidate del PoC independiente. `release_ready=true` significa coherencia técnica del repositorio, **no conformidad ni aprobación institucional de la CGR**.

- Commit auditado: `1c58058ccaf16941bfdf473c846cb84604eead2e`
- Checks: **19/19 OK**
- Resultado: **READY**

| Estado | Verificación | Detalle |
|:---:|---|---|
| ✅ | versión semántica release candidate | 1.0.0-rc.1 |
| ✅ | disclaimer público explícito | README distingue el PoC de una implementación oficial |
| ✅ | release no se presenta como oficial | RELEASE_NOTES mantiene el alcance independiente |
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
| ✅ | Oro sin datasets intermedios | artefactos Oro=7 |
| ✅ | sin derivados reales identificables versionados | raw/derivados reales identificables permanecen fuera del repositorio |
| ✅ | documentación formal completa | 8 DOCX (7 productos + informe final) |
| ✅ | manifiesto reproducible Spark/GraphFrames | commit evidencia=73a023eb977bdedb1391ea6c60098d040735bb8f |
| ✅ | sin residuos de nomenclatura obsoleta en artefactos canónicos | nomenclatura y conteos vigentes |
| ✅ | licencia presente | MIT para el código del PoC |

## Pendientes después del release

No se trasladan aquí como brechas técnicas. La única fuente canónica es `docs/Dependencias_Institucionales_CGR.md` (`CGR-DEP-01..08`).
