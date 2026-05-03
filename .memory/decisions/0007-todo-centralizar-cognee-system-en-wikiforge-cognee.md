# ADR 0007 — TODO: centralizar cognee_system en ~/.wikiforge/cognee/

- **Estado:** Accepted
- **Fecha:** 2026-05-03
- **Decisor:** Daniel Alonso Gómez
- **Tags:** infra,cognee,fase-2-todo
- **Origen:** promoción manual sesión → proyecto vía `wikiforge promote-decision`

---

## Decisión

Cognee 1.0 escribe el storage en site-packages/cognee/.cognee_system, no en $HOME. Como TODO Fase 2: configurar cognee.config.system_root_directory(~/.wikiforge/cognee/) desde wikiforge.runner para centralizar storage cross-venv y evitar islas por proyecto.

## Notas

(añade contexto, motivación, consecuencias y supersedence chain según evolucione)
