# Simulación multiactor nativa con Getangiru — piloto de producción controlada

## Estado comprobado

La vía LOCAL de simulación ya no utiliza Zep Cloud para crear o consultar el grafo, para construir decisiones ni para emitir el informe. Se mantiene la vía OASIS heredada sin cambios para proyectos antiguos, pero la interfaz la deshabilita cuando el grafo es Getangiru. No se declara compatibilidad con todas las funciones OASIS anteriores.

El piloto funciona en el Sprite separado tenondera-integrado. La máquina original iapmpy tiene 2.048 MiB de RAM y no es candidata segura para alojar simultáneamente Qwen CPU (~2 GiB RSS medido), Tenonderã, SQLite y agentes. No migrar ni sobrescribir el volumen original.

## Pipeline

1. El documento ingresado genera una ontología mediante Qwen cuantizado en localhost (modelo no externo).
2. Getangiru Graph Engine almacena exclusivamente actores respaldados y conexiones CO_MENTIONED, con procedencia de documentos/memorias HMAC y sin vínculos causales afirmados.
3. El motor nativo inicia un run lsim_ con propiedad de proyecto, huella SHA-256 del grafo, cuota de 100 ejecuciones por proyecto y un máximo de 12 actores. Solo hay una ejecución en curso por instancia.
4. Modo rules: acciones de 4 fases para cada actor, sin consultas LLM. Modo hybrid: una única consulta al Qwen local para priorización, seguida de acciones controladas; respuesta JSON inválida o timeout implica fallback explícito y medido.
5. Cuatro fases persistentes: detección, contención, recuperación y verificación. Se registran actor, acción, motivo, procedencia, hora y que es simulada, nunca acción real ejecutada.
6. Informe ejecutivo y archivo Markdown exportable, con métricas de acciones, referencias de evidencia, prioridad, tiempo, llamadas locales y llamadas externas. Se advierte que la cobertura de fuentes no equivale a precisión.
7. Un revisor puede aceptar o rechazar una acción. Rechazos anteriores añaden una obligación de validación reforzada a ese actor en ejecuciones posteriores. En modo híbrido, Qwen recibe **solo cantidades agregadas** de revisiones aceptadas/rechazadas del mismo proyecto como señal de prioridad; no recibe notas libres de revisores, minimizando inyección de instrucciones. No se autoentrenan los pesos ni se convierten hipótesis en evidencias originales.
8. La investigación pública opcional, activada separadamente por el administrador y el usuario, solo permite 1 a 5 IDs CVE explícitos. El servidor recupera un archivo fijo del repositorio oficial CISAgov KEV, sin redirecciones, con 8 s de timeout, 3 MB de límite y caché de 12 h. No se transmite el nombre del proyecto, texto extraído, identidad ni memoria. Nunca hace búsquedas privadas ni Internet general automáticamente.

## API

- POST /api/native-simulation/start: {project_id, mode: hybrid|rules}; 202 cuando se acepta.
- GET /api/native-simulation/project/{project_id}/latest: última ejecución visible al propietario.
- GET /api/native-simulation/{lsim_id}: progreso y acciones persistentes.
- POST /api/native-simulation/{lsim_id}/feedback: {actor_uuid,phase,verdict:accept|reject,note}; bajo revisión humana.
- GET /api/native-simulation/{lsim_id}/report.md: informe Markdown con autenticación.
- GET /api/native-simulation/capabilities: estado de motor local y política de investigación externa.
- POST /api/native-simulation/public-cve: {cves:[...]}; solo cuando está habilitado el control GETANGIRU_PUBLIC_RESEARCH_ENABLED=true.

El middleware de Tenonderã y los propios handlers validan sesión, CSRF para mutaciones y propiedad de proyecto / ejecución. Ningún usuario ve simulaciones ajenas. No existen endpoints para ejecutar scripts, escanear IPs o navegar URLs arbitrarias.

## Límites, rendimiento y seguridad

- Máximo 12 actores en 4 fases, 48 acciones hipotéticas por ejecución.
- Ensayos sintéticos en instantes distintos: modo reglas 32 acciones en ~0,02 s y ~0,206 s; híbrido Qwen local 32 acciones en 3,64 s y 18,92 s. La variabilidad depende de la carga; son ejecuciones puntuales, no percentiles ni validaciones de exactitud.
- Sin llamadas a modelos externos. El campo local_llm_requests registra intentos reales, incluidos fallbacks.
- SQLite/WAL con historia durable y transacciones. La falla del proceso se detecta como interrupted, no como éxito; nunca se reejecutan decisiones anteriores automáticamente.
- Sin borrado automático de auditoría: límite de 100 ejecuciones por proyecto. Se necesita exportación y retención definida antes de uso regulado.
- Una ejecución no equivale a simulación OASIS de interacciones sociales ni a evaluación real de intrusión. No confundir acciones hipotéticas con hallazgos, compromisos, pérdidas o mitigaciones comprobadas.
- Qwen es útil para elegir foco de simulación, no fuente de verdad. Todo resultado requiere revisión del dueño del proceso, Riesgos, Seguridad y Auditoría.
- El catálogo CISA KEV puede no incluir CVEs conocidas: ausencia no prueba que una vulnerabilidad sea segura. Fuentes públicas: https://github.com/CISAgov/kev-data

## Operación, activación y reversión

Feature flags en archivo privado con permiso 0600:

    GETANGIRU_GRAPH_LOCAL_ENABLED=true
    LLM_LOCAL_INFERENCE=true
    GETANGIRU_PUBLIC_RESEARCH_ENABLED=true

El tercer flag solo habilita el BOTÓN para búsquedas CVE explícitas. Nunca transmite información automáticamente.

La interfaz deja el flujo OASIS antiguo bloqueado en proyectos locales y muestra el panel Simulación multiactor local. Para revertir el nuevo motor, desplegar versión anterior y restaurar el checkpoint del Sprite; comparar previamente cambios posteriores de SQLite. No sobrescribir el volumen del Fly app original.

Validar en este orden: pruebas unitarias, auth 401/404, CSRF, creación 202, fases 1-4, informe 200, feedback, Qwen híbrido, fallback de modelo, CVE lookup con datos públicos, navegador, Docker CI y recuperación de errores.

La incorporación de feedback NO constituye entrenamiento automático en línea; los cambios de pesos se prohíben hasta establecer datos etiquetados, validación, privacidad y gestión de versiones.

## Endurecimiento de almacenamiento

Las carpetas del grafo y memoria Getangiru usan permisos 0700; bases de grafos, espejo de memoria y simulaciones usan 0600. La creación de nuevas bases aplica los mismos permisos automáticamente. El servicio de inferencia Qwen local no se publica como endpoint abierto; las rutas de simulación requieren sesión y CSRF. Se validó que las pruebas de seguridad, aislamiento y simulación continúan pasando tras el cambio.
