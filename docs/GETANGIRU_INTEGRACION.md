# Tenonderã + Getangiru: arquitectura híbrida, seguridad y evidencia

**Estado:** adaptador de consulta integrado en código, **OFF por defecto**. No existe una URL ni credencial de Getangiru verificadas mediante los conectores actuales: ninguna prueba con un doble simulado equivale a integración real.

## Objetivo

- Mantener **Tenonderã** (simulación, UI, informes, proyectos) y **Getangiru** (memoria) en servidores y almacenamiento **independientes**.
- Las tareas deterministas (autenticación, validación, deduplicación, conteo, medición, control de costos y recuperación) no deben depender de modelos externos.
- El procesamiento generativo necesita un modelo. Podrá ser externo o **autohospedado** en un servicio diferente con capacidad suficiente; **los 2 GB del servidor de Tenonderã no son apropiados para alojar un LLM generalista**.
- La mejora de exactitud no se deduce de una respuesta convincente ni de un alto porcentaje de perfiles procesados.

## Flujo

~~~mermaid
flowchart TD
  U[Usuario autorizado] --> UI[Tenonderã: panel e informes]
  UI --> ACL[Backend Flask: permisos por proyecto]
  ACL --> RUN[Simulador liviano]
  RUN --> PROFILE[Perfiles y documentos guardados]
  RUN --> MEMORY[GetangiruBridge: off/shadow/enrich]
  MEMORY -- proyecto autenticado --> G[Getangiru: servidor independiente]
  MEMORY -- timeout/circuito abierto --> RUN
  RUN --> MODEL[Modelo generativo configurado]
  MODEL --> VALID[Validar IDs, respuestas y gasto]
  VALID --> EVENTS[Eventos sintéticos etiquetados]
  EVENTS --> KPI[Métricas y exportación]
  KPI --> UI
~~~

| Módulo | Archivo | Responsabilidad |
|---|---|---|
| Memoria | backend/scripts/getangiru_bridge.py | API autenticada, caché por proyecto, timeout, circuito y validación |
| Ejecución | backend/scripts/run_lightweight_simulation.py | Batches, presupuestos, métricas de tokens y tiempo |
| Indicadores | backend/app/services/efficiency_metrics.py | Cálculo reproducible sin datos de perfiles |
| API métricas | GET /api/simulation/sim_xxx/efficiency | Privada; ACL global de simulación |
| Interfaz | frontend/src/components/EfficiencyMetricsPanel.vue | Indicadores y exportación JSON |
| Benchmark | scripts/benchmark_getangiru.py | Precision@5, recall@5, MRR, p95 y tokens con referencia |
| Pruebas | tests/test_getangiru_bridge.py | Seguridad, aislamiento y resiliencia |

## Contrato de memoria (a homologar con el servicio REAL)

Getangiru debe implementar un endpoint de consulta compatible, o un adaptador de compatibilidad en su servidor. El cliente no presupone que ya existe. Se configura URL exacta, DNS permitido y **token exclusivo** en secretos Fly.

Solicitud POST JSON:

~~~json
{
  "project_id": "proj_ejemplo123",
  "namespace": "project:proj_ejemplo123",
  "simulation_id": "sim_ejemplo123",
  "query": "Controles de acceso del escenario ficticio",
  "top_k": 4
}
~~~

Respuesta JSON:

~~~json
{
  "project_id": "proj_ejemplo123",
  "namespace": "project:proj_ejemplo123",
  "results": [{
    "source_id": "doc:control-01",
    "project_id": "proj_ejemplo123",
    "namespace": "project:proj_ejemplo123",
    "score": 0.94,
    "text": "Referencia documental autorizada y limitada"
  }]
}
~~~

Ambos campos de ámbito deben coincidir **en todos los resultados**. Si aparece un resultado de otro proyecto, la respuesta completa se rechaza. El score **no es** la probabilidad de que el texto sea cierto. No se implementan escrituras automáticas hasta validar el contrato, conservación y borrado del lado Getangiru.

## Configuración segura

| Variable | Descripción |
|---|---|
| GETANGIRU_MODE | off (default), shadow (mide sin añadir contexto) o enrich (usa referencias válidas) |
| GETANGIRU_SEARCH_URL | Endpoint exacto de Getangiru; no una URL deducida |
| GETANGIRU_ALLOWED_HOST | Host DNS único permitido |
| GETANGIRU_API_TOKEN | Secreto propio, **nunca reutilizar clave de GPT** |
| GETANGIRU_ALLOW_PRIVATE_HTTP | 1 solamente para host .internal Fly explícitamente privado; preferir TLS |
| SIMULATION_LLM_CALL_BUDGET | Límite 1–80, default 40 llamadas |
| LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_NAME | Modelo existente, interno o externo |
| LLM_PRICE_INPUT_PER_1M_USD, LLM_PRICE_OUTPUT_PER_1M_USD | Tarifas voluntarias para calcular USD; sin ellas el costo aparece desconocido |

Activar por fases: (1) verificar y endurecer Getangiru real, (2) probar autorización y contrato, (3) establecer métricas baseline, (4) activar shadow, (5) ejecutar evaluación pareada, (6) activar enrich a un canario limitado, (7) medir y decidir. Rollback inmediato: GETANGIRU_MODE=off. **No introducir credenciales en README, consola compartida ni conversación.**

## Indicadores: métricas que matan relato

**Por ejecución y a partir de archivos reales**: llamadas al modelo, reintentos, p50/p95 de latencia, tokens de uso reportados, costo USD solo con tarifas configuradas, RSS pico del proceso hijo, consultas y fallos de Getangiru, hit de caché, fuentes válidas, perfiles con acciones, repetición de texto. La respuesta no expone prompts ni textos. No inventa ahorros ni exactitud factual.

**Benchmark pareado de recuperación:** usar más de 50 consultas representativas con fuentes de referencia anotadas por especialistas independientes; ejecutar el mismo conjunto contra el sistema actual y el híbrido:

~~~bash
python3 scripts/benchmark_getangiru.py evaluacion_gold.json --output resultados_ab.json
~~~

El programa exige al menos 12 casos para funcionar, pero **12 no son una base estadística robusta**. Reporta precision@5, recall@5, MRR, latencia p95 y tokens. Si no existen datos, muestra null. **Esto mide recuperación de documentos, no exactitud de predicciones de fraude ni de incidentes.**

**Gates propuestos (objetivos, NO resultados medidos):**
- 0 filtraciones entre proyectos y 0 secretos expuestos a servidores no autorizados;
- Recall@5 no inferior al sistema base por más de 3 puntos porcentuales;
- p95 total de extremo a extremo sin regresión superior al 10% en la misma carga;
- objetivo de reducción de tokens >=15% solo si se preserva o mejora la calidad;
- 0 fallos de memoria OOM bajo la carga objetivo;
- el nivel de acierto de conclusiones se evaluará **por separado** con resultados reales anonimizados y etiquetas independientes.

Comparación controlada: mismos perfiles, documentos, rondas, modelo, temperatura, presupuesto y carga. Repetir ejecuciones para observar variabilidad; publicar errores, muestras y condiciones.

## Matriz de riesgos

| Riesgo | Control |
|---|---|
| IDOR / aislamiento entre empresas | ACL Flask más scope project_id+namespace validado para cada respuesta de memoria |
| SSRF / fuga del token | Host fijo, HTTPS, prohibición de redirecciones y máximo 64 KiB por respuesta |
| Exposición de PII/secretos | Solo consulta breve con redacción preventiva; no se envían documentos completos |
| Prompt injection en memoria | Fuentes tratadas como DATOS no confiables, nunca instrucciones de sistema |
| Envenenamiento / falsos hechos | source_id y score obligatorios, revisión de resultados y casos gold-set independientes |
| Getangiru caído | timeout 2,5 s, caché TTL 90 s, 3 fallos -> circuito abierto por 60 s, continuar con contexto local |
| Costos GPT | presupuesto de lotes, telemetría de tokens, posibilidad de modelo local compatible |
| Métricas engañosas | nulos explícitos en precio, exactitud y ahorro si no hay evidencia A/B |
| Privacidad de indicadores | endpoint autenticado, datos agregados y exportación sin texto de perfiles |

**Riesgos residuales:** la redacción por patrones no sustituye DLP; la inyección de prompts no desaparece solo con un prompt; Getangiru todavía necesita verificación de retención, backups, borrado, secretos, cifrado, controles de roles, auditoría y pruebas de carga en su servidor. La calidad de Getangiru y la inferencia local todavía no están verificadas.

## Criterio de cierre en producción

No declarar “integrado y optimizado” hasta demostrar: endpoint real accesible, aislamiento multiempresa, ninguna fuga en pruebas adversariales, A/B con etiquetas independientes, smoke sin pérdida de simulaciones, costo/memoria/latencia medidos, backups y rollback. El código puede desplegarse en **off** mientras se obtiene acceso al servicio, pero eso **no significa que Getangiru ya esté conectado**.
