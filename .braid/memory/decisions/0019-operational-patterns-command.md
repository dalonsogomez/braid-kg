# ADR 0019 - Operational Patterns Command

- **Estado:** Accepted
- **Fecha:** 2026-06-05
- **Decisor:** Daniel Alonso Gomez
- **Tags:** cli, diagnostics, agents, docs, patterns

---

## Contexto

Braid ya expone `doctor --json` para diagnostico local y `status --json` para
estado consumible por agentes. Tambien documenta patrones operativos recurrentes
en el README: frontera de proyecto, diagnostico antes de cambiar estado,
activacion de agentes, aislamiento de fixtures y cambios de retrieval guiados
por evals.

Ese modelo mental es util para usuarios y agentes, pero no debe mezclarse con
la semantica de salud de `doctor`: `doctor` devuelve warnings/errors y puede
salir con codigo 1; un playbook de patrones debe poder mostrarse aunque existan
warnings locales.

## Decision

Anadir `braid patterns [--json]` como comando canonico read-only.

El comando:

- muestra los patrones operativos vigentes de Braid;
- conecta cada patron con comandos recomendados y evidencia local ligera;
- usa la informacion de `doctor` solo en modo lectura, sin `--fix`;
- no ejecuta `braid index`, no llama al LLM, no promueve memoria y no escribe
  estado.

`doctor` sigue siendo el diagnostico de salud. `patterns` es una guia
operativa y una interfaz estable para agentes que necesitan entender como usar
Braid sin parsear el README.

## Consecuencias

- Los usuarios ven en CLI el mismo modelo operativo que aparece en el README.
- Los agentes pueden consumir `patterns --json` sin confundir warnings de salud
  con fallo del playbook.
- Cualquier ampliacion futura de patrones debe mantener la salida read-only y
  evitar solapar reparaciones con `doctor --fix` o `agent-init --fix`.
