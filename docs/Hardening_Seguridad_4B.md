# Hardening de seguridad — Etapa 4B

## Alcance

Esta etapa endurece el **PoC público independiente** sin cambiar la metodología de los modelos ni declarar despliegue, conformidad o certificación institucional CGR. Los controles aquí cerrados son reproducibles desde el repositorio; los controles que dependen de identidad, red, infraestructura y políticas CGR permanecen abiertos para el aterrizaje institucional.

## Controles cerrados en el repositorio

### CI/CD y cadena de suministro

- `tests` ejecuta PR y push con `contents: read`; ya no dispone de token de escritura.
- la persistencia de artefactos se realiza únicamente desde `audit-anexo3`, después de un `tests` exitoso originado por `push` a `main`;
- la auditoría privilegiada hace checkout del `workflow_run.head_sha`, comprueba que siga siendo `origin/main`, descarga la evidencia del **mismo run** y vuelve a verificar el SHA antes del commit;
- eventos `tests` exitosos que no provengan de `push/main` son rechazados por un job no privilegiado;
- el permiso `contents: write` existe solamente en el job trusted de auditoría y en el job gated de release;
- las GitHub Actions externas están fijadas a SHA completos de 40 caracteres;
- CodeQL queda versionado para Python y JavaScript/TypeScript;
- Dependabot queda versionado para pip, npm y GitHub Actions.

### Secretos y conexiones

`source.connection_env` debe ser el **nombre** de una variable de entorno (`^[A-Za-z_][A-Za-z0-9_]*$`). Una cadena ODBC/credencial escrita directamente en esa propiedad es rechazada antes de conectarse.

La cadena real continúa fuera de Git. En CGR, su contenido/DSN debe ser aprobado por Seguridad/DBA e incluir la política de cifrado, validación de certificado, driver y timeout correspondiente. El PoC no fuerza una sintaxis ODBC única porque el entorno institucional puede utilizar DSN o configuración administrada.

### Candidate/champion

TRAIN solo puede limpiar directorios candidate situados **estrictamente debajo** de roots autorizados. Por defecto:

```text
outputs/runtime
```

En un runtime institucional adicional puede definirse:

```text
CGR_ALLOWED_CANDIDATE_ROOTS=/ruta/segura/runtime
```

Si se requieren varios roots se separan con `os.pathsep` del sistema operativo.

La promoción verifica que todos los artefactos del manifest candidate, incluidos symlinks resueltos, estén dentro del directorio del propio candidate. Luego se mantienen los controles existentes de SHA-256, almacenamiento champion versionado, staging y rollback.

El perfil sklearn continúa utilizando artefactos `joblib`; por ello solo debe cargar champions producidos y gobernados por esta cadena de confianza. En un despliegue institucional se recomienda complementar SHA-256 con registry corporativo, identidad de servicio, auditoría y, si la plataforma lo soporta, firma/attestation de artefactos.

### Privacidad del benchmark

Los identificadores y contactos sintéticos publicados se marcan inequívocamente:

```text
SYN-RUC-...
SYN-DNI-...
SYN-TEL-...
SYN-DIR-...
```

El generador conserva la cantidad/orden de llamadas al RNG para no alterar innecesariamente el benchmark metodológico. Esta medida evita presentar números aleatorios de apariencia real como posibles RUC, DNI o teléfonos.

Los datos reales OCDS/SEACE y rankings identificables continúan excluidos del repositorio público mediante `.gitignore` y la política descrita en `data_real/README.md`.

### Previews de integración

La CLI de `src/ingestar_canonico.py` ya no escribe un preview de datos por defecto. Para materializarlo debe indicarse deliberadamente:

```bash
python src/ingestar_canonico.py \
  --config config/cgr.yaml \
  --output-dir /almacenamiento/autorizado/integracion
```

La ruta de salida y su retención siguen sujetas a la política del ambiente.

### SQL Server / SSRS

Los RDL dejaron de versionar hostname/catálogo y referencian el Shared Data Source:

```text
CGR_ModuloAnalisis
```

El binding DEV/QA/PROD se realiza en SSRS fuera del RDL. `schema_sql_server.sql` expone tres vistas estables de reporting y `security_roles_template.sql` documenta dos roles mínimos de referencia:

- `CGR_Analisis_ReportReader`: SELECT solo sobre vistas;
- `CGR_Analisis_Publisher`: DML solo sobre tablas destino.

La plantilla no crea logins ni se despliega automáticamente. La identidad de lectura de SIAF/SEACE debe mantenerse separada y en modo consulta sobre objetos autorizados, de acuerdo con el TDR.

## Controles que siguen siendo institucionales

La Etapa 4B **no cierra** por sí sola: repositorio privado CGR, branch/ruleset corporativo, MFA/SSO e identidades, secret manager, permisos efectivos de bases reales, TLS/PKI institucional, cifrado y retención de almacenamiento, redes/firewalls, instalación y permisos SSRS reales, DEV/QA/PROD, logs/SIEM, backups, respuesta a incidentes, aprobación de roles, certificación funcional ni marcha blanca.

Estos elementos deben mantenerse como dependencias 🟡/🔵 hasta existir evidencia del ambiente CGR.

## Gate de regresión

`tests/test_security_hardening.py` protege, entre otros, los siguientes contratos:

- `connection_env` no puede contener una connection string;
- TRAIN no puede limpiar fuera de roots autorizados;
- candidates no pueden referenciar artefactos externos ni escapar mediante symlink;
- los identificadores/contactos sintéticos conservan prefijos `SYN-*`;
- la CLI no escribe preview por defecto;
- PR CI es read-only y la persistencia está segregada;
- todas las Actions externas están fijadas a SHA;
- SQL/SSRS conserva el contrato de mínimo privilegio de referencia.
