# Piloto de inferencia local: Tenonderã + Qwen3 4B

## Alcance real

- **Inferencia documental local:** Qwen3-4B-Instruct-2507 GGUF, Q4_K_M (2.497.281.120 bytes), servido por llama.cpp b12633 en 127.0.0.1:18080. La aplicación usa un endpoint OpenAI-compatible **dentro del Sprite**, no OpenAI ni otro proveedor de inferencia externo.
- **Memoria local:** Getangiru permanece independiente y el espejo SQLite se consulta sin servicios externos.
- **Construcción del grafo:** el código principal aún depende de Zep Cloud. Sin `ZEP_API_KEY`, la ontología puede generarse localmente, **pero las simulaciones que requieren Zep no pueden completarse**. El estado de la interfaz indica “Ontología lista · Grafo pendiente”.
- **Limitaciones:** el modelo cuantizado de 4B requiere evaluación de precisión antes de usarlo con documentos sensibles; no se debe confundir JSON válido con hechos verificados. El procesamiento de documentos grandes utiliza muestreo representativo hasta 10.500 caracteres en el piloto local. El ensayo sintético no demuestra precisión en casos reales.

## Recursos y controles

- Infraestructura: Sprite separado `tenondera-integrado` (piloto). No modifica la máquina Fly original.
- Modelo: repositorio Unsloth en Hugging Face, archivo `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`. LFS SHA-256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.
- Servidor oficial: ggml-org/llama.cpp, versión `b12633`, binario Linux CPU `llama-b12633-bin-ubuntu-x64.tar.gz`, SHA-256 `9c4a2c1bd1437f22831e0b56cc75329b321bac87225ffb5c83cd8d13b1f44fa2`.
- 5 hilos CPU, contexto 8.192 tokens, 1 ejecución simultánea, lotes de 256/128, sin interfaz web.
- `--host 127.0.0.1` y `--api-key-file` dedicado con permisos 0600. Nunca exponer 18080 a Internet ni copiar credenciales desde otros servicios.
- Instalar binarios y modelo solo con hashes contrastados. Mantener logs libres de prompts y secretos.

## Configuración (privada)

En el archivo del servicio, fuera del repositorio y con permisos 0600:

```sh
LLM_LOCAL_INFERENCE=true
LLM_BASE_URL=http://127.0.0.1:18080/v1
LLM_MODEL_NAME=qwen3-4b-local
LLM_API_KEY=<clave-unica-protegida>
```

El servidor se inicia con `deploy/local-llm/start-llama.sh` desde el Sprite, con el modelo ya verificado. No se debe ejecutar el binario sin verificar la firma/hash del paquete. El frontend usa `GET /api/graph/capabilities`, que consulta salud local y devuelve solo indicadores (no secretos).

**Puertas de seguridad:** si el motor local se detiene, la API devuelve `503 LOCAL_ONTOLOGY_MODEL_UNAVAILABLE` **antes** de crear un proyecto. Si no hay configuración devuelve `503 ONTOLOGY_PROVIDER_NOT_CONFIGURED`. El servidor no intenta recurrir silenciosamente a un proveedor remoto. Resultados JSON incompletos se rechazan; no se inventan entidades para alcanzar una puntuación ficticia.

## Pruebas obligatorias

1. SHA-256 de ambos artefactos; `GET http://127.0.0.1:18080/health` = 200.
2. POST sin credencial al modelo = 401; POST autenticado JSON = 200 con JSON válido.
3. `GET /api/graph/capabilities` autenticado: `ontology_backend=local`, `ontology_enabled=true` y `graph_enabled=false` mientras no haya motor compatible.
4. Crear proyecto con **documento ficticio** y comprobar 10 tipos de entidades, al menos 4 relaciones con endpoints válidos, persistencia y acceso por propietario.
5. Desconectar temporalmente el motor y comprobar que el preflight devuelve 503 sin crear un proyecto.
6. Verificar p50/p95, uso máximo de memoria, CPU y latencia por documento; mantener métricas separadas de benchmarks sintéticos y resultados productivos.
7. Si se configura un motor de grafo distinto a Zep, realizar integración explícita y pruebas por separado; no declarar “simulación completa” solo por tener la ontología.
