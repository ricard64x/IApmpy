# Getangiru ↔ Tenonderã: integración controlada (fase de lectura)

La integración **no está activada en producción**. Getangiru se ejecuta en un Sprite separado y su URL requiere autenticación de Sprite. No abrirlo públicamente ni copiar tokens desde Tenonderã.

## Implementado en este cambio
- Cliente Python opcional solo de lectura `GET /v1/memories/search`, exclusivamente `mode=text`.
- Sin llamadas a modelos, embeddings, reindexación, ni escritura a Getangiru.
- Token por organización, `space` validado, HTTPS, timeout de 2 s, sin reintentos ni redirecciones.
- Resultado limitado, validación de la respuesta, errores explícitos, pruebas sin red.
- El cliente **no está conectado todavía a los flujos funcionales**; su uso exige autorización por proyecto y un gateway privado aprobado.

## Activación posterior, NO ejecutar aún
1. Crear tenant y token específicos para Tenonderã en Getangiru; no compartir credenciales.
2. Aprobar red privada/gateway con TLS, autenticación extremo a extremo, allowlist y comprobación del origen; no usar la URL Sprite protegida como si fuese una API pública.
3. En Secrets (nunca Git): `GETANGIRU_READ_ENABLED=true`, `GETANGIRU_BASE_URL=https://<gateway-interno>`, `GETANGIRU_TENANT_TOKEN=<token-dedicado>`.
4. Asociar cada proyecto autorizado a un `space` estable y verificar que el backend impide acceso cruzado; testear 401/403 y rotación.
5. Ejecutar búsquedas sombra (sin modificar respuestas del usuario), comparar contra Zep y habilitar mediante feature flag progresivo.
6. No sustituir escrituras/Graphiti de Zep hasta implementar contrato funcional, idempotencia, migración, backup y rollback.

## Evidencias obligatorias
Guardar baseline de 7 días y después medir por proyecto, motor y etapa: p50/p95, RSS pico, CPU-segundos, tokens de entrada/salida, solicitudes externas, USD/caso completo, coste de infraestructura, tasa de errores, cobertura de fuentes, precisión/recall de recuperación y groundedness evaluado contra dataset etiquetado. Las simulaciones sintéticas jamás equivalen a encuestas reales.

## Umbrales iniciales para aprobar (objetivos, NO resultados)
- 0 fugas entre tenants en pruebas negativas; 100% de operaciones de lectura autenticadas.
- 0 cambios de resultados en modo sombra; rollback del feature flag probado.
- Exactitud de respuestas >= baseline con intervalo de confianza; errores críticos sin incremento.
- p95 y coste total por informe inferiores al baseline sin exceder RSS disponible.
- Backups externos restaurados satisfactoriamente.
