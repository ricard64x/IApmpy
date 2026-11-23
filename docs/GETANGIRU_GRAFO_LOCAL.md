# Getangiru: motor de grafo local integrado en Tenonderã

Estado: piloto funcional; NO sustituye todas las API de Zep Cloud.

## Arquitectura operativa

- Qwen local, servido por llama.cpp en loopback, genera la ontología. Su inferencia no utiliza APIs de modelos externos.
- Getangiru Graph Engine, fuente: backend/app/services/getangiru_graph_engine.py, construye nodos y aristas deterministas con SQLite WAL, transacciones y aislamiento por (tenant,project_id). No usa modelos, embeddings ni APIs externas para construir grafos.
- Tenonderã usa ese motor directamente sobre backend/uploads/getangiru/graphs.sqlite3 en su propio Sprite. La API build/read y la interfaz de proyecto pueden consultar el grafo persistido.
- El Getangiru original, en un Sprite diferente, usa el mismo motor instalado mediante integrations/getangiru/install_graph_api.py. Expone rutas autenticadas /v1/graphs/{space}/rebuild, GET y DELETE, con base de datos propia.
- Los dos grafos son almacenes INDEPENDIENTES aunque comparten código. La replicación entre Sprites NO se encuentra verificada ni activada. El túnel temporal de la fase anterior no es transporte productivo. No afirmar una réplica centralizada o HA.

## Semántica y seguridad

Cada nodo se crea únicamente si una clase de actor de la ontología está mencionada literalmente en el documento. Las aristas CO_MENTIONED solo representan co-mención en una misma oración, nunca atribuyen causalidad o colaboración. Los tipos propuestos por Qwen permanecen separados en schema_relations y son templates, no hechos. Cada nodo/arista retiene fragmento textual y source_id. Fact claims = 0.

Se valida proyecto y tenant, se restringe longitud, se conservan transacciones idempotentes y se limita el máximo de elementos. Ruta de visualización requiere titularidad del proyecto; sin sesión devuelve 401 y otro analista 404. El grafo solo de co-menciones no constituye una reconstrucción factual validada de todas las operaciones del negocio.

## Activación y endpoints

Configurar en el archivo privado de Tenonderã con permisos 0600:

    GETANGIRU_GRAPH_LOCAL_ENABLED=true

Reiniciar únicamente el servicio tenondera-api.

- GET /api/graph/capabilities: graph_enabled=true, graph_backend=getangiru_local, simulation_enabled=false.
- POST /api/graph/build con project_id: crea grafo local y marca GRAPH_COMPLETED.
- GET /api/graph/data/{graph_id}: nodes, edges, schema_relations y fact_claims.
- GET /api/simulation/entities/{graph_id}: lectura local de actores/etiquetas.
- POST /api/simulation/create con grafo gtg_: HTTP 409. No se crean simulaciones OASIS/Zep por un backend incompatible.

El Getangiru independiente tiene endpoints para reconstruir grafos usando episodios del tenant correspondiente. Las sesiones son autenticadas por token Bearer y nunca aceptan una ID de organización suministrada para lectura transversal.

## Pruebas y reversión

Puntos de control: Getangiru v13, Tenonderã integrado v6 (previos a activación).

Caso sintético: 8 nodos, 15 co-menciones, 4 templates de relación, 0 relaciones causales afirmadas, 0 llamadas externas durante construcción. Pruebas de idempotencia, aislamiento, concurrencia y borrado, y pruebas HTTP con 401 anónimo, 200 propietario, 404 otro analista, 409 simulación incompatible.

Para desactivar, cambiar GETANGIRU_GRAPH_LOCAL_ENABLED=false y reiniciar la API. No borrar la base SQLite ni restaurar checkpoints sin comparar datos posteriores.

## Limitaciones y siguiente integración

Los agentes OASIS, los lectores Zep y el motor de reportes mantienen dependencias de Zep. Para simulaciones integrales se requiere adaptar sus consultas, perfilado y actualización de memoria al contrato Getangiru, y disponer de un canal privado estable entre los dos Sprites. No procesar datos regulados por Quick Tunnel efímero. La implementación actual habilita construcción, consulta y visualización de grafos, no equivalencia funcional absoluta con Zep Cloud.
