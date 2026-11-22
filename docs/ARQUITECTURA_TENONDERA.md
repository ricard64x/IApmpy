# Tenonderã — Arquitectura técnica y catálogo de módulos

**Versión:** noviembre de 2026 · Repositorio ricard64x/IApmpy  
**Objetivo:** documentar responsabilidades, componentes, flujos, controles de seguridad y consumo de recursos.

> Tenonderã genera escenarios mediante participantes virtuales. Sus respuestas NO representan una encuesta real, una muestra representativa ni predicciones verificadas.

## 1. Vista general

Tenonderã es una aplicación web modular: Vue 3/Vite sirve la interfaz desde Flask/Gunicorn bajo un mismo origen HTTPS. Los proyectos, usuarios, simulaciones e informes se guardan en un volumen persistente. La memoria de relaciones utiliza el proveedor de grafos Zep y los textos se generan mediante una API de lenguaje compatible con OpenAI. El motor de simulación social se ejecuta como subproceso de Python, limitado por ronda y plataforma. El chat posterior NO vuelve a iniciar el motor social.

### Diagrama de contenedores (Mermaid)

~~~mermaid
flowchart TD
    U["Navegador del usuario"] -->|"HTTPS"| N["Tenonderã · Fly.io (2 GB, 1 vCPU)"]
    subgraph APP["Servidor de aplicación"]
      WEB["Vue 3 + Vite · interfaz"]
      API["Flask + Gunicorn · API"]
      AUTH["Autenticación y permisos"]
      GRAPH["Construcción de conocimiento"]
      SIM["Simulación social + monitor"]
      REPORT["Informes + exportación"]
      CHAT["Consultas y encuestas posteriores"]
      DISK[("Volumen persistente /uploads")]
      WEB --> API
      API --> AUTH
      API --> GRAPH
      API --> SIM
      API --> REPORT
      API --> CHAT
      AUTH --> DISK
      SIM --> DISK
      REPORT --> DISK
      CHAT --> DISK
    end
    GRAPH -->|"Red externa"| Z["Zep · servicio de relaciones"]
    SIM -->|"Batch de eventos"| Z
    SIM -->|"LLM"| L["Proveedor de modelos IA remoto"]
    REPORT -->|"LLM"| L
    CHAT -->|"Una solicitud acotada"| L
~~~

Zep y el modelo externo son dependencias fuera de la VM. No se debe describir esta versión como completamente independiente del proveedor.

## 2. Módulos del sistema

| Módulo visible | Código principal | Responsabilidad |
|---|---|---|
| Identidad y cuentas | backend/app/auth.py; frontend/src/views/Login.vue | Login, cambios de clave, sesiones, roles, propiedad de proyectos |
| Panel de escenarios | frontend/src/views/Home.vue; components/HistoryDatabase.vue | Nuevos escenarios, fuentes, ámbito geográfico, historial |
| Red de conocimiento | backend/app/api/graph.py; services/graph_builder.py; frontend/src/components/Step1GraphBuild.vue | Extraer entidades/relaciones de documentos y construir grafo |
| Preparación | services/simulation_manager.py; services/oasis_profile_generator.py; frontend/src/components/Step2EnvSetup.vue | Perfiles virtuales y reglas del escenario |
| Preferencias de interacción | services/simulation_execution.py; api/simulation.py | Info Plaza, Topic Community o ambas; rondas; cierre automático/manual |
| Ejecución | services/simulation_runner.py; scripts/run_parallel_simulation.py; components/Step3Simulation.vue | Ejecutar rondas, monitorear eventos, cerrar entorno con IPC |
| Memoria de relaciones | services/zep_graph_memory_updater.py; services/zep_tools.py | Sincronización de acciones y consulta del grafo externo |
| Informe de análisis | services/report_agent.py; services/report_prompts_es.py; api/report.py; components/Step4Report.vue | Planificar, redactar, guardar y restaurar capítulos |
| Consultas y encuestas | services/report_interactions.py; components/Step5Interaction.vue | Chat y preguntas grupales SIN volver a iniciar la simulación |
| Traducciones | locales/*.json; frontend/src/i18n/index.js; backend/app/utils/locale.py | Idioma del usuario y del contenido generado |
| Capacidad | backend/app/capacity.py; fly.toml | Restricciones de VM, perfiles, rondas y concurrencia |
| Exportación | api/report.py; frontend/src/api/report.js | Descargar el informe ya almacenado, sin invocar el modelo |
| Entrega | Dockerfile; .github/workflows/verify-fly.yml; deploy-fly.yml | CI, verificación y despliegue de la revisión exacta |

## 3. Flujo funcional completo

~~~mermaid
sequenceDiagram
    actor U as Usuario
    participant V as Vue
    participant A as Flask
    participant D as Volumen persistente
    participant G as Zep
    participant O as Simulación social
    participant I as Modelo remoto
    U->>V: Carga documentos y define escenario
    V->>A: Crea proyecto y prepara conocimiento
    A->>D: Guarda fuentes y propietario
    A->>G: Construye red de relaciones
    G-->>A: Referencias de entidades
    U->>V: Elige plataformas, rondas y cierre
    V->>A: Guarda configuración
    A->>I: Genera perfiles y reglas
    A->>D: Persiste perfiles y configuración
    V->>A: Inicia simulación
    A->>O: Subproceso temporal con límites
    loop Rondas
      O->>I: Decisiones de participantes
      O->>D: Acciones y estado
      O->>G: Actualización de memoria
    end
    alt Cierre automático
      O-->>A: Proceso finalizado
    else Manual
      U->>V: Cerrar y finalizar
      V->>A: Solicita cierre IPC
      A->>O: Cierre controlado
    end
    A->>G: Consolida escrituras pendientes
    A->>D: Estado terminal del proceso
    U->>V: Solicita informe
    A->>I: Índice y redacción en español
    A->>D: Guarda capítulos y contenido final
    U->>V: Envía consulta o encuesta
    V->>A: Interacción posterior al informe
    A->>D: Recupera perfiles e informe
    A->>I: Una consulta de tamaño acotado
    A->>D: Registra respuesta sintética
    V-->>U: Respuesta y opciones de exportación
~~~

## 4. Estados de ejecución

- idle: ejecución no iniciada.
- running_rounds: participantes ejecutando rondas.
- awaiting_close: todas las plataformas seleccionadas terminaron sus eventos, pero el entorno IPC sigue abierto.
- finalizing: cierre solicitado o automático; esperando fin del proceso y consolidación de memoria.
- completed: simulación terminada correctamente, sin escritura pendiente.
- stopped: ejecución detenida; si faltan rondas el resultado es parcial.
- failed: error; NO habilitar informe de opinión pública.

**Una ronda 10/10 no es suficiente para liberar el informe.** El backend verifica los eventos de finalización por plataforma y el estado terminal del proceso, más la barrera de ingesta.

## 5. Interfaces API

| Método y endpoint | Uso |
|---|---|
| POST /api/auth/login | Login y cookie de sesión |
| GET/POST /api/simulation/<id>/execution-settings | Configuración previa por simulación |
| POST /api/simulation/start | Iniciar rondas |
| GET /api/simulation/<id>/run-status | Fase y progreso |
| POST /api/simulation/close-env | Solicitar cierre manual |
| POST /api/report/generate | Preparar el informe |
| GET /api/report/<id> | Informe persistente y metadatos |
| GET /api/report/<id>/sections | Capítulos guardados |
| GET /api/report/<id>/export?format=md | Exportación MD/HTML/JSON/TXT |
| POST /api/report/interactions | Consulta y encuesta sintética posterior |
| GET /api/report/interactions | Historial privado de respuestas |
| GET /api/capacity/status | Límites de ejecución |

Todas las rutas con objetos pertenecientes al usuario deben validar la propiedad del recurso en backend; nunca asumir que un botón deshabilitado es un control de autorización.

## 6. Almacenamiento persistente

~~~text
/app/backend/uploads/
  auth/users.sqlite3                  Cuenta, roles, propietarios
  projects/                           Archivos y proyectos
  simulations/sim_*/
    simulation_config.json            Escenario
    execution_settings.json           Plataforma / rondas / cierre
    run_state.json                    Estado de ejecución
    twitter_profiles.csv              Personas virtuales para Plaza
    reddit_profiles.json              Personas virtuales para Comunidad
    twitter/actions.jsonl             Acciones históricas
    reddit/actions.jsonl              Acciones históricas
    ipc_commands/                     Control de proceso
    ipc_responses/                    Respuestas de control
  reports/report_*/
    meta.json                         Estado / metadatos
    outline.json                      Estructura del informe
    section_01.md                     Capítulos independientes
    full_report.md                    Informe completo
    interacciones.jsonl               Chat y encuestas posteriores
~~~

El almacenamiento persistente en disco no sustituye un respaldo externo verificado. Deben existir snapshots, pruebas de restauración y retención definida.

## 7. Seguridad

1. Sesión HTTPOnly y SameSite, HTTPS obligatorio, protección CSRF en operaciones de escritura.
2. Cuentas administradas exclusivamente por el administrador; hashing de contraseñas e invalidación de cookies al restablecer clave.
3. Control de propietario en servidor para cada proyecto, simulación, informe, tarea y grafo.
4. Claves API y contraseñas en Fly.io Secrets; token de despliegue en los secretos privados de GitHub Actions. Nunca en el código o la interfaz.
5. Datos provenientes de documentos, perfiles y resultados LLM son contenido no confiable. Las instrucciones encontradas allí NO deben considerarse órdenes del sistema.
6. El HTML de exportación se escapa para no ejecutar etiquetas/scripts provenientes del informe.
7. Las respuestas posteriores se conservan separadas de los eventos originales, con etiqueta de procedencia sintética.

Pendientes de fortalecimiento: cuotas por usuario, auditoría de exportaciones, límites de almacenamiento, clasificación de documentos, respaldos probados y pruebas de aislamiento continuo.

## 8. Arquitectura de recursos, costo y escalado

Configuración de referencia: Fly.io, 2 GB RAM, 1 CPU compartida, una máquina con un proceso Gunicorn y un volumen. El simulador limita 45 perfiles, 2 participantes activos por ronda/plataforma, 10 rondas y una ejecución simultánea. Info Plaza usa recomendación aleatoria para evitar cargar un modelo local adicional.

**Optimizaciones aplicadas:**

- El motor social no permanece activo después del cierre automático.
- Chat y encuestas post-informe usan los datos persistidos; una solicitud LLM, sin proceso OASIS; máximo ocho participantes por encuesta.
- Una consulta post-informe a la vez para evitar saturar 2 GB; mensajes, historial y contextos acotados; salidas en tokens limitados.
- Informes españoles con máximo dos consultas de evidencia por sección, reduciendo iteraciones y gasto del modelo.
- Menor frecuencia de consultas de progreso en navegador; registros visibles acotados en memoria.
- Exportación desde archivos almacenados, sin regeneración.

**Alternativas de menor costo a evaluar:** medición de RSS y perfiles de OOM por etapa; caducidad controlada para sesiones de simulación abiertas; paginación de logs; resumir evidencia contextual; caché con separación por usuario/escenario; colas durables para trabajos pesados; evaluar grafos autogestionados solo cuando sus costos y requisitos operativos estén medidos. No reducir memoria ni aumentar límites de perfiles sin pruebas de carga.

## 9. CI/CD y restauración

- Docker multietapa: Node 22 compila Vue y Python 3.11 ejecuta Flask con Gunicorn.
- CI de GitHub valida sintaxis Python, traducciones, frontend, autenticación, preferencias de simulación, controles de memoria, consultas/encuestas y contenedor real.
- El workflow de despliegue se ejecuta únicamente tras CI exitoso de main y utiliza el commit exacto probado.
- Health-check de Fly.io en /health.
- Restauración: volver a imagen anterior sin borrar el volumen. Conservar evidencias del estado, carpetas de informe y usuarios.

## 10. Diccionario de lenguaje funcional

| Término técnico (solo documentación interna) | Presentar al usuario como |
|---|---|
| Agent | Participante virtual |
| GraphRAG | Red de conocimiento |
| OASIS | Motor de simulación |
| Zep | Memoria de relaciones |
| Fly.io | Servidor de Tenonderã |
| Report Agent | Asistente de análisis |
| Twitter simulado | Info Plaza |
| Reddit simulado | Topic Community |
| IPC | Cierre controlado |
| Ingestion barrier | Consolidación de resultados |

## 11. Riesgos y decisiones futuras

- **Dependencia del proveedor remoto:** el servicio de grafos y el modelo se consumen externamente; una arquitectura totalmente local requiere otro plan.
- **Estado monomáquina:** la memoria del proceso y el volumen local impiden horizontalización transparente. Se requiere coordinación distribuida antes de ampliar a varias instancias.
- **Contenido de informes anteriores:** informes ya guardados en otros idiomas no se traducen automáticamente; la generación nueva en español aplica al crear informes nuevos.
- **Evidencia de opinión:** nunca convertir respuestas de personas virtuales en cifras estadísticas de la población paraguaya.
- **Rendimiento:** no existe garantía técnica de “optimización al 100 %”; establecer línea base y comparar RAM pico, tiempo, costo LLM, fallos y número de perfiles.

Última actualización: documentación del rediseño de localización, consultas post-simulación, exportación y consumo acotado.
