# Piloto de inferencia local: Tenonderã + Qwen (1.5B rápido / 4B opcional)

## Alcance real

- **Inferencia documental local operativa:** perfil rápido **Qwen2.5-1.5B-Instruct Q4_K_M** (1.117.320.736 bytes), servido por llama.cpp b12633 en 127.0.0.1:18080. El perfil **Qwen3-4B-Instruct-2507 Q4_K_M** (2.497.281.120 bytes) está disponible como alternativa de calidad, pero **no se ejecuta simultáneamente**. El endpoint OpenAI-compatible funciona dentro del Sprite, sin OpenAI ni otro proveedor de inferencia externo.
- **Memoria local:** Getangiru permanece independiente y el espejo SQLite se consulta sin servicios externos.
- **Construcción del grafo:** el código principal aún depende de Zep Cloud. Sin `ZEP_API_KEY`, la ontología puede generarse localmente, **pero las simulaciones que requieren Zep no pueden completarse**. El estado de la interfaz indica “Ontología lista · Grafo pendiente”.
- **Limitaciones:** un modelo pequeño puede generar actores que no aparecen en el texto. El perfil rápido aplica un filtro independiente de evidencia léxica y rechaza documentos con menos de ocho clases verificables; prefiere no generar antes que inventar datos. Esta verificación no equivale a validación semántica ni garantiza exactitud. El contexto del perfil rápido está limitado a 6.500 caracteres con muestreo de documentos largos, frente a 10.500 en perfil de calidad. Las pruebas sintéticas no prueban precisión con información real.

## Recursos y controles

- Infraestructura: Sprite separado `tenondera-integrado` (piloto). No modifica la máquina Fly original.
- Modelo rápido activo: `qwen2.5-1.5b-instruct-q4_k_m.gguf` (1.117.320.736 bytes), SHA-256 verificado `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`.
- Modelo alternativo: repositorio Unsloth en Hugging Face, `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, SHA-256 verificado `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.
- Servidor oficial: ggml-org/llama.cpp, versión `b12633`, binario Linux CPU `llama-b12633-bin-ubuntu-x64.tar.gz`, SHA-256 `9c4a2c1bd1437f22831e0b56cc75329b321bac87225ffb5c83cd8d13b1f44fa2`.
- Perfil rápido: 4 hilos CPU, contexto 8.192 tokens, una ejecución simultánea, lotes de 256/128, sin interfaz web. El perfil de calidad usa 5 hilos. Uso RSS del proceso rápido observado: aproximadamente 2 GiB.
- `--host 127.0.0.1` y `--api-key-file` dedicado con permisos 0600. Nunca exponer 18080 a Internet ni copiar credenciales desde otros servicios.
- Instalar binarios y modelo solo con hashes contrastados. Mantener logs libres de prompts y secretos.

## Configuración (privada)

En el archivo del servicio, fuera del repositorio y con permisos 0600:

```sh
LLM_LOCAL_INFERENCE=true
LLM_BASE_URL=http://127.0.0.1:18080/v1
LLM_MODEL_NAME=qwen25-1.5b-local
LLM_LOCAL_FAST_MODE=true
LLM_API_KEY=<clave-unica-protegida>
```

El servidor se inicia con `deploy/local-llm/start-llama.sh` desde el Sprite, con el modelo ya verificado. El archivo privado `local-llm/profile` selecciona `fast` o `quality`; cambiar de perfil requiere actualizar `LLM_MODEL_NAME` coherentemente y reiniciar el servicio para evitar publicidad incorrecta de disponibilidad. No se debe ejecutar el binario sin verificar la firma/hash del paquete. El frontend usa `GET /api/graph/capabilities`, que consulta salud local y devuelve solo indicadores (no secretos).

**Puertas de seguridad:** si el motor local se detiene, la API devuelve `503 LOCAL_ONTOLOGY_MODEL_UNAVAILABLE` **antes** de crear un proyecto. Si no hay configuración devuelve `503 ONTOLOGY_PROVIDER_NOT_CONFIGURED`. El servidor no intenta recurrir silenciosamente a un proveedor remoto. Resultados JSON incompletos se rechazan; no se inventan entidades para alcanzar una puntuación ficticia.

## Pruebas obligatorias

1. SHA-256 de ambos artefactos; `GET http://127.0.0.1:18080/health` = 200.
2. POST sin credencial al modelo = 401; POST autenticado JSON = 200 con JSON válido.
3. `GET /api/graph/capabilities` autenticado: `ontology_backend=local`, `ontology_enabled=true` y `graph_enabled=false` mientras no haya motor compatible.
4. Crear proyecto con **documento ficticio** y comprobar 10 tipos de entidades, al menos 4 relaciones con endpoints válidos, persistencia y acceso por propietario.
5. Desconectar temporalmente el motor y comprobar que el preflight devuelve 503 sin crear un proyecto.
6. Verificar p50/p95, uso máximo de memoria, CPU y latencia por documento; mantener métricas separadas de benchmarks sintéticos y resultados productivos.
7. Si se configura un motor de grafo distinto a Zep, realizar integración explícita y pruebas por separado; no declarar “simulación completa” solo por tener la ontología.

## Resultados de pruebas ejecutadas con el perfil rápido

- Prueba directa con actores explícitos: 10 tipos, 4 relaciones, 8,30 segundos, cero llamadas a modelos externos.
- API autenticada de Tenonderã con TXT ficticio: HTTP 200, 10 entidades, 4 relaciones, 9,17 segundos; el proyecto queda persistido como `ontology_generated`.
- Prueba negativa adversarial: documento con solo dos participantes; las versiones iniciales inventaban ocho clases. Con el filtro de evidencia, ahora la generación se rechaza en 1,91 segundos en lugar de completar roles no respaldados.
- Modelo sin token HTTP 401; salud HTTP 200; 10 pruebas unitarias del motor y controles de seguridad aprobadas en el Sprite de piloto.
- **La etapa de grafo sigue pendiente**: `graph_enabled=false`. No está permitida la simulación integral hasta incorporar un backend de grafo y validar sus flujos.
