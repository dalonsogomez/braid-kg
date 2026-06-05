# ADR-0001 — Rename WikiForge to Fairlead

## Status
Accepted

## Date
2025-08-21

## Context
El proyecto fue inicialmente nombrado WikiForge. La metáfora "forge" enfatiza la generación de
artefactos (wikis, documentación) y desvía la atención de la funcionalidad central: una capa de
memoria persistente y contexto estructurado por repositorio para coding agents. Además, la
colisión de categoría con herramientas de background agents y la necesidad de un nombre más
orientado a la guía de contexto demandan un cambio.

## Decision
Renombrar el proyecto a **Fairlead**.

- Nombre del proyecto: Fairlead
- Comando CLI: `fairlead`
- Tagline: *Repo-scoped context guidance for coding agents.*
- Namespace (PyPI): `fairlead-mcp` (si se publica)
- Namespace (npm): `@dalonsogomez/fairlead` (si se publica)
- Directorio de memoria interno: `.memory/`
- Contrato cross-agent: `AGENTS.md`

## Rationale
Fairlead (fairlead en inglés) es una pieza náutica que guía un cabo, cuerda o cable con baja
fricción y sin engancharse. Esa metáfora captura la esencia: guiar el contexto del agente a
través del repositorio, evitando deriva, ruido y alucinación. `.memory/`, ADRs, decisiones
promocionadas manualmente y `AGENTS.md` son las fuentes confiables; MCP, KG y RAG son el
sistema de conducción.

Ventajas:
- Dos sílabas, ergonómico en CLI, no requiere alias artificial.
- Sin colisiones conocidas en el nicho MCP / memoria para agentes IA.
- Metáfora náutica clara: guía, baja fricción, sin enredos.
- Compatible con tagline descriptiva.

Verificación de namespaces (2025-08-21):
- PyPI `fairlead-mcp`: LIBRE
- npm `@dalonsogomez/fairlead`: LIBRE
- GitHub `fairlead/fairlead`: LIBRE
- GitHub handle `dalonsogomez`: activo (propietario)

## Alternatives considered
- **WikiForge** (status quo). Desalineado con la misión central; induce a error.
- **Astrolabe**. Ocupado en PyPI/npm y en grafos/dependencias (Astrolabe para Lean 4).
  Más largo y menos práctico.
- **Cairn**. Colisión con background agents y memoria/tareas para coding agents.
- **Fiducial**. Más exacto para puntos de referencia confiables, pero menos fluido en CLI.
- **Lodestone**. Correcto pero más abstracto; no refleja la acción de "guiar".
- **Torsor**, **Datum**, **Kernel**, **Tensor**, **Manifold**, **Cortex**, **Axiom**,
  **Lemma**, **Invar**, **Versor**, **Frenet**, **Basis**, **Frame**, **Gauge**, **Memex**,
  **Locus**, **Stratum**, **Weave**, **Knit**, **Interlace**, **Nexus**, **Threadline**,
  **Beacon**, **Tether**, **Hilo**, **Hebra**, **RepoGround**, **duckwiki**, **ducky**.
  Todos descartados por saturación, ruido o menor alineación.

## Consequences
- Reemplazo textual en `AGENTS.md` y `README.md` según lista de cambios.
- CLI principal: `fairlead`. Alias `wikiforge` mantenido con aviso de deprecación.
- Rutas de perfil global: `~/.wikiforge/` → `~/.fairlead/`.
- Rutas de secretos: `~/.config/wikiforge/` → `~/.config/fairlead/`.
- MCP tool names: `wikiforge_search` → `fairlead_search`, etc.
- Creación de ADR-0001 y actualización de `.memory/MEMORY.md`.
- No cambios en: `.memory/` (contenido), `.kg/wikiforge_ducklake` (datos existentes),
  `.vpp` reales, reglas de Visual Paradigm, configuración global, secretos.
- El directorio Python `src/wikiforge/` se mantiene sin renombrar en esta iteración;
  los imports internos `from wikiforge.` siguen siendo válidos.

## Verification
Tras aplicar el rename:

1. `grep -rni "wikiforge" AGENTS.md README.md` → vacío (salvo trazabilidad histórica).
2. `fairlead --help` responde.
3. `wikiforge --help` responde con aviso de deprecación.
4. Proyecto contiene `Repo-scoped context guidance for coding agents.` en descripción.
