# Política de seguridad

## Alcance

Este es un prototipo público e independiente. No procesa datos institucionales reales de la CGR ni contiene credenciales. Aun así, se toman en serio los reportes sobre:

- vulnerabilidades en el código Python/Node.js versionado;
- debilidades en los workflows de GitHub Actions (escalación de privilegios, inyección en pasos privilegiados, manejo de artefactos);
- exposición accidental de datos identificables o de apariencia identificable;
- dependencias con vulnerabilidades conocidas no cubiertas por Dependabot/CodeQL.

## Cómo reportar

**No abras un issue público para vulnerabilidades.** Usa el reporte privado de GitHub:

1. Ve a la pestaña **Security** del repositorio.
2. Selecciona **Report a vulnerability** (Private vulnerability reporting).
3. Describe el problema, el impacto y, si es posible, pasos de reproducción.

Si el reporte privado no está disponible, contacta al mantenedor por los canales indicados en su perfil de GitHub antes de divulgar públicamente.

## Qué esperar

- Confirmación de recepción y evaluación inicial del reporte.
- Corrección priorizada según impacto; los cambios pasan por el CI con CodeQL (`security-extended`) y los tests de regresión de seguridad (`tests/test_security_hardening.py`).
- Crédito en las notas del cambio si el reportante lo desea.

## Controles existentes

- CI no privilegiado para PRs (token de solo lectura); persistencia y tagging solo desde `main` con verificación de SHA.
- Actions fijadas por SHA completo; CodeQL con `security-extended`; Dependabot activo.
- Rechazo de secrets inline en configuración (`connection_env` obliga a variables de entorno).
- Identificadores sintéticos con prefijos inequívocos y política de no versionar datos reales identificables (`data_real/README.md`).
