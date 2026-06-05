# ADR 0007 — TODO: centralizar cognee_system en ~/.braid/cognee/

- **Estado:** Resolved
- **Fecha:** 2026-05-03 (promovido) → 2026-05-04 (resuelto)
- **Decisor:** Daniel Alonso Gómez
- **Tags:** infra,cognee,fase-2-todo
- **Origen:** promoción manual sesión → proyecto vía `braid promote-decision`

---

## Decisión

Cognee 1.0 escribe el storage en site-packages/cognee/.cognee_system, no en $HOME. Como TODO Fase 2: configurar cognee.config.system_root_directory(~/.braid/cognee/) desde braid.runner para centralizar storage cross-venv y evitar islas por proyecto.

## Resolución (2026-05-04)

Cognee 1.0 usa Pydantic `BaseSettings` para `BaseConfig`. Por convención de pydantic-settings, los campos del settings object se auto-bind a env vars con el nombre del campo en mayúsculas (sin prefijo, dado que `BaseConfig` no declara `env_prefix`). Por tanto:

- `system_root_directory` ↔ env var `SYSTEM_ROOT_DIRECTORY`
- `data_root_directory` ↔ env var `DATA_ROOT_DIRECTORY`
- `cache_root_directory` ↔ env var `CACHE_ROOT_DIRECTORY`

Verificación previa al fix (2026-05-04):

```bash
$ SYSTEM_ROOT_DIRECTORY="/tmp/test_centralized" .venv/bin/python -c \
    "from cognee.base_config import get_base_config; print(get_base_config().system_root_directory)"
/private/tmp/test_centralized
```

### Implementación

1. **`src/braid/config.py::apply_stack_env()`** — añade tres env vars a los defaults, apuntando a `~/.braid/cognee/.cognee_system`, `.data_storage` y `.cognee_cache`. Crea los dirs antes de exportar (Cognee falla si no existen al boot).

2. **`~/.braid/bin/cognee-mcp-stdio.sh`** — el shim del MCP exporta las mismas tres env vars antes del `exec uv run python src/server.py`. Así el proceso del MCP server hereda el path centralizado.

3. **Verificación** — `from cognee.base_config import get_base_config; get_base_config().system_root_directory` devuelve `/Users/dalonsogomez/.braid/cognee/.cognee_system` desde **ambos venvs** (el de Braid y el de cognee-mcp), confirmando que las "islas por venv" desaparecen.

### Consecuencia

- El CLI `braid index/ask` y el MCP server `mcp__cognee__*` ven el mismo grafo + vector store.
- Datasets antiguos en los paths viejos (site-packages de cada venv) se descartan; se re-indexa en el path central.
- Para que el MCP server activo recoja las env vars nuevas, hay que reiniciarlo (`claude mcp remove cognee && claude mcp add --scope user --transport stdio cognee ~/.braid/bin/cognee-mcp-stdio.sh`). Las sesiones futuras lo recogen automáticamente.

### Limitaciones

- Cada repo proyecto sigue teniendo su propio `dataset_id` (vía `.kgconfig`); la centralización es del **storage físico**, no de los datasets lógicos. Esto es lo correcto.
- Si Cognee 2.x cambia el modelo de settings, este fix podría necesitar revisión. Mitigación: el campo `system_root_directory` está documentado en el upstream y el binding via env var es estándar de pydantic-settings.

## Notas

Este es el primer ADR del proyecto creado por **promoción explícita** vía `braid promote-decision` (no escrito a mano). Demuestra el ciclo de vida completo: TODO promovido en sesión N → resuelto en sesión N+1 con trazabilidad observable.
