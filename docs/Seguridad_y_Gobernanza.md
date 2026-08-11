# Seguridad y gobernanza

## Objetivo

Este documento describe los controles de seguridad y gobierno que pueden demostrarse desde el repositorio y separa esos controles de los que requieren identidad, infraestructura, redes y políticas institucionales reales.

El principio general es: **el PoC puede reducir riesgos de software y dejar contratos verificables, pero no debe presentar como resueltos controles que solo existen cuando hay una plataforma CGR operativa**.

## 1. Modelo de confianza

El módulo procesa información potencialmente sensible y produce señales que pueden orientar revisión humana. Por ello el diseño separa:

```text
código versionado
    |
    +--> configuración no secreta
    |
    +--> referencias a secretos externos
    |
    +--> datos autorizados
    |
    +--> candidate / champion con hashes
    |
    +--> outputs controlados
```

No se considera seguro versionar credenciales, connection strings, datasets institucionales identificables ni rankings reales derivados de ellos.

## 2. Secretos y conexiones

La configuración SQL Server utiliza:

```yaml
source:
  type: sqlserver
  connection_env: CGR_SOURCE_DATABASE_URL
```

`connection_env` debe ser el **nombre de una variable de entorno**, no la cadena de conexión.

Se rechazan configuraciones que intenten incluir de forma directa propiedades sensibles como passwords, tokens, secrets, API keys o connection strings.

### Por qué

El repositorio debe poder compartirse, auditarse y ejecutar CI sin exponer secretos. El contenido real de la conexión debe ser administrado por el mecanismo de secretos del ambiente correspondiente.

El PoC no fuerza una única sintaxis ODBC porque el entorno institucional puede utilizar DSN, autenticación integrada u otros mecanismos administrados. Driver, cifrado, validación de certificado, timeouts y política de credenciales deben ser aprobados por DBA/Seguridad.

## 3. Proyección SQL controlada

El conector SQL Server construye una proyección de columnas configuradas y no acepta SQL libre desde YAML.

```text
SELECT columnas_configuradas
FROM tabla_o_vista_configurada
```

Para joins o filtros complejos se recomienda exponer vistas institucionales aprobadas.

### Por qué

Limitar la configuración a identificadores conocidos reduce la superficie de inyección y mantiene la lógica de integración bajo control de código/revisión. Las reglas de consolidación institucional pueden gobernarse mediante vistas con ownership y permisos definidos.

## 4. Datos sintéticos inequívocos

Los identificadores/contactos generados para el benchmark utilizan prefijos como:

```text
SYN-RUC-...
SYN-DNI-...
SYN-TEL-...
SYN-DIR-...
```

### Por qué

Un dato aleatorio con apariencia de RUC, DNI o teléfono real puede ser confundido con información personal o de una entidad existente. Los prefijos hacen explícita su naturaleza sintética y reducen esa ambigüedad.

## 5. Datos públicos reales

Los datasets OCDS/OECE se utilizan localmente como prueba adicional de portabilidad. Los archivos crudos, datasets derivados identificables y rankings `*_REAL.csv` permanecen fuera de Git mediante `.gitignore`.

### Por qué

Que una fuente sea pública no implica que sea apropiado publicar un ranking que asocie a una persona jurídica real con una señal de riesgo generada por un prototipo sin ground truth. La evidencia pública versionada se limita a resultados agregados, hashes y validaciones metodológicas.

## 6. Previews de integración

`src/ingestar_canonico.py` no materializa un preview de datos por defecto. Para escribirlo se debe proporcionar explícitamente `--output-dir`.

### Por qué

Una validación de configuración no necesita copiar datos. La materialización se trata como una decisión deliberada y la ubicación/retención del preview queda bajo responsabilidad del ambiente autorizado.

## 7. Candidate roots y borrado seguro

TRAIN solo puede preparar/limpiar directorios candidate situados estrictamente bajo roots autorizados. El root local por defecto está bajo `outputs/runtime` y pueden definirse roots adicionales mediante configuración de entorno.

La promoción también comprueba que los artefactos declarados en el manifest pertenezcan al propio directorio del candidate, incluyendo resolución de symlinks.

### Por qué

Los jobs de entrenamiento manipulan directorios de trabajo. Sin un límite de raíz, un error de configuración o una ruta manipulada podría provocar eliminación/copia fuera del espacio destinado a candidates.

## 8. Integridad de candidate y champion

Cada artefacto relevante se registra con SHA-256. La promoción:

1. valida manifest y rutas;
2. copia el conjunto completo a staging;
3. verifica hashes;
4. publica un directorio versionado;
5. actualiza el registry.

INFERENCE verifica el champion antes del scoring y de nuevo antes de publicar resultados.

### Por qué

La integridad de un modelo no depende solo de “que exista un archivo”. Debe ser exactamente el artefacto registrado y debe permanecer estable durante la ejecución que genera rankings.

## 9. Deserialización sklearn

El perfil sklearn utiliza artefactos `joblib`. Esos artefactos solo deben cargarse desde una cadena de confianza controlada por el proyecto/organización.

### Por qué

Los formatos de serialización Python no deben tratarse como documentos pasivos provenientes de terceros no confiables. En un despliegue institucional conviene complementar hashes con identidad de servicio, registry corporativo y, cuando la plataforma lo permita, firma/attestation de artefactos.

## 10. GitHub Actions y mínimo privilegio

La CI separa los jobs de validación de los jobs que necesitan persistir artefactos derivados.

Principios:

- PR/push de tests con permisos de lectura cuando no se necesita escribir;
- permiso `contents: write` únicamente en jobs explícitamente privilegiados/gated;
- persistencia asociada a una ejecución validada del mismo commit;
- verificación del SHA antes de persistir;
- Actions externas fijadas a SHA completo;
- CodeQL/Dependabot versionados.

### Por qué

Una prueba ejecutada sobre código no confiable no debería disponer automáticamente de credenciales capaces de modificar el repositorio. La separación reduce el impacto de una dependencia o cambio malicioso dentro del job de tests.

## 11. Champion de CI no es champion de `main`

Los smoke tests pueden ejercitar una promoción, pero antes de persistir evidencia CI restaura el serving versionado por el commit.

### Por qué

Probar el comando de promoción es distinto de decidir que ese candidate debe convertirse en el modelo servido por el repositorio.

## 12. SQL Server / SSRS

Los RDL no incluyen hostname, catálogo ni credenciales. Referencian el Shared Data Source:

```text
CGR_ModuloAnalisis
```

El repositorio incluye una plantilla de mínimo privilegio con roles de referencia:

- `CGR_Analisis_ReportReader`: SELECT sobre vistas de reporting;
- `CGR_Analisis_Publisher`: DML sobre tablas destino.

La identidad de lectura de las fuentes debe mantenerse separada de la identidad que publica resultados y de la que administra DDL.

### Por qué

Leer datos fuente, publicar predicciones y administrar esquema son capacidades distintas. Separarlas limita el alcance de una cuenta comprometida y facilita auditoría de responsabilidades.

## 13. Review humano y uso de scores

Una señal de riesgo no habilita una acción sancionadora automática. Los outputs deben ser interpretados con:

- contexto contractual;
- normativa aplicable;
- documentación de sustento;
- criterios funcionales;
- revisión del auditor/especialista responsable.

### Por qué

Los modelos priorizan patrones estadísticos. No observan por sí solos la totalidad del expediente, causales legales, excepciones, justificaciones o evidencia documental necesaria para una conclusión de control.

## 14. Segregación TRAIN / aprobación / PROD

El repositorio separa técnicamente TRAIN de promoción. En una implantación institucional, además deben existir identidades/roles distintos para:

- ejecutar TRAIN;
- aprobar candidate;
- promover a QA/PROD;
- operar INFERENCE;
- administrar datos/reporting.

El PoC no inventa esas identidades porque dependen de la política institucional.

## 15. Logging y observabilidad

El repositorio produce manifests y logs técnicos de ejecución, pero no afirma disponer de SIEM, telemetría, retención, alertamiento o SLA productivos.

Una implantación real debería definir:

- logs de acceso;
- logs de promoción/rollback;
- métricas de jobs;
- métricas de drift/modelo;
- retención;
- alertas;
- correlación de incidentes;
- responsables y escalamiento.

## 16. Dependencias institucionales de seguridad

Siguen fuera del alcance demostrable del repositorio público:

- repositorio privado CGR;
- SSO/MFA y grupos corporativos;
- branch/ruleset protection real;
- secret manager;
- cuentas de servicio;
- permisos efectivos sobre bases/tablas/vistas;
- TLS/PKI institucional;
- redes/firewalls;
- cifrado en reposo y política de retención;
- SIEM/SOC;
- backups/DR;
- respuesta a incidentes;
- segregación efectiva DEV/QA/PROD;
- aprobación formal de roles;
- certificación y marcha blanca.

Estos puntos deben permanecer como dependencias institucionales hasta existir evidencia verificable del ambiente.

## 17. Checklist operativo mínimo

Antes de utilizar datos institucionales:

1. repositorio privado y commit aprobado;
2. secretos fuera de Git;
3. identidad de mínimo privilegio;
4. vistas/tablas autorizadas;
5. output storage autorizado;
6. datos identificables excluidos del remoto público;
7. candidate/champion store con permisos separados;
8. promoción detrás de aprobación humana;
9. logging y rollback definidos;
10. reporting conectado mediante datasource administrado.

La guía completa de adopción se encuentra en [`Manual_Aterrizaje_Institucional_CGR.md`](Manual_Aterrizaje_Institucional_CGR.md).
