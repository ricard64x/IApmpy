# OASIS en Fly.io: modo de baja memoria (2 GiB)

## Causa del incidente

En camel-oasis 0.2.5, oasis.make(platform=DefaultPlatformType.TWITTER) selecciona recsys_type=twhin-bert.
OasisEnv.step() invoca Platform.update_rec_table() antes de las acciones, y al encontrar publicaciones,
TwHIN-BERT carga un Transformer local con PyTorch. Esto ocurre incluso con un solo agente,
explicando el SIGKILL/-9 de las pruebas y el aumento del contador oom_kill.

## Solución

El helper backend/scripts/oasis_runtime.py crea una plataforma Twitter explícita con
recomendador random (nativo de OASIS): no necesita cargar ningún modelo local de recomendaciones.
Las acciones de los agentes siguen siendo generadas por la API LLM remota.
Reddit conserva su recomendador nativo, sin modelos locales.

Configuración Fly (2 GiB): OASIS_TWITTER_RECSYS=random;
OASIS_MAX_CONCURRENT_LLM_ACTIONS=2; OMP_NUM_THREADS=1; OPENBLAS_NUM_THREADS=1;
MKL_NUM_THREADS=1; TOKENIZERS_PARALLELISM=false; MALLOC_ARENA_MAX=2.

## Fidelidad y otros modos

El feed random cambia la exposición de publicaciones frente a TwHIN-BERT.
Por tanto, no se deben comparar directamente experimentos con recomendadores distintos.
Para comparar variantes A/B/C, mantener fijo el algoritmo y documentarlo.

Modos opcionales: twitter usa MiniLM y twhin-bert reproduce el original.
Ambos pueden requerir más RAM y deben probarse explícitamente antes de activarlos.

## Verificación

1. Esperar la validación automática de GitHub (frontend, Python, Docker y fábrica OASIS real).
2. Hacer un despliegue controlado con la máquina de 2 GiB y volumen persistente.
3. Probar un agente y una ronda; verificar acciones LLM reales, no solo posts iniciales.
4. Medir el pico de RAM y comprobar que el contador oom_kill no crezca.
5. Ampliar gradualmente a 10 y 45 agentes, en pruebas separadas, monitoreando CPU, RAM y costos LLM.
6. Usar un ID de simulación nuevo. Los incidentes pasados deben conservar su estado failed.

## Limitación

Evitar TwHIN-BERT elimina un factor grande de consumo de memoria, pero no garantiza
que dos plataformas con 45 agentes funcionen en 2 GiB. Esa capacidad se debe medir.
No reiniciar la máquina mientras una simulación esté en ejecución.
