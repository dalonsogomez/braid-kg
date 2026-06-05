# ADR 0018 - Doctor, Status JSON, and Config Hardening

- **Estado:** Accepted
- **Fecha:** 2026-06-05
- **Decisor:** Daniel Alonso Gomez
- **Tags:** cli, diagnostics, agents, ci, hardening

---

## Contexto

Braid ya puede inicializar proyectos, activar agentes con `agent-init`, exponer
MCP y mantener memoria separada por frontera de proyecto. En uso real todavia
faltan dos piezas operativas: diagnosticar una instalacion sin ejecutar indexado
ni LLM, y ofrecer una salida estable que otros agentes puedan leer sin parsear
texto humano.

Tambien se detecto un riesgo en `agent-init`: los archivos JSON de configuracion
malformados no deben tratarse como configuracion vacia, porque eso podria
sobrescribir configuracion del usuario.

## Decision

Anadir:

- `braid doctor [--json] [--fix]` como diagnostico local de instalacion,
  contexto, `.braid/`, legacy drift, agentes, secretos, GitHub y catalogo.
- `braid status --json` como interfaz CLI estable para agentes.
- Politica estricta de JSON invalido en `agent-init`: reportar error y no
  escribir.
- CI en GitHub Actions para validar tests, CLI basica y assets del README.

`doctor` no ejecuta `braid index`, no llama al LLM y no promueve memoria.
`doctor --fix` solo aplica reparaciones locales seguras y gestionadas por Braid.

## Consecuencias

- Los agentes pueden consumir estado de Braid sin depender de salida localizada.
- Las instalaciones rotas se diagnostican antes de mezclar memoria o tocar KG/RAG.
- Los hooks legacy siguen migrandose con `agent-init`, pero los JSON corruptos se
  preservan intactos hasta que el usuario los repare manualmente.
- Cambios futuros en retrieval siguen requiriendo evidencia de `braid eval`.
