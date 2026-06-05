# ADR 0020 - Obsidian Vault Export

- **Estado:** Accepted
- **Fecha:** 2026-06-05
- **Decisor:** Daniel Alonso Gomez
- **Tags:** cli, wiki, obsidian, export, memory

---

## Contexto

Braid ya genera Markdown bajo `.braid/wiki/` y mantiene la memoria humana
auditable bajo `.braid/memory/`. El usuario tambien trabaja con Obsidian como
superficie local de conocimiento, por lo que conviene poder exportar esa memoria
a una boveda sin convertir Obsidian en fuente canonica ni mezclar niveles de
memoria.

Crear un comando top-level adicional duplicaria la responsabilidad de
`braid wiki build`. La opcion mas coherente es anadir un modo de exportacion al
generador existente.

## Decision

Anadir `braid wiki build --obsidian` como modo canonico de exportacion
Obsidian.

El comando:

- crea una boveda generada en `.braid/wiki/obsidian/` cuando no se pasa destino;
- crea una boveda nueva en `--output <dir>` e incluye `.obsidian/` minimo;
- escribe solo en `<vault>/Braid/<dataset_id>/` cuando se usa
  `--vault <existing-vault>`;
- exporta memoria humana (`MEMORY.md`, ADRs y planes) aunque DuckLake no este
  disponible;
- puede anadir paginas KG/RAG generadas si el catalogo DuckLake esta accesible;
- no indexa, no llama al LLM, no promueve memoria y no toca KG/RAG.

`--output` y `--vault` son mutuamente excluyentes. En una boveda existente,
Braid no modifica notas ajenas ni la carpeta `.obsidian/`.

## Consecuencias

- Obsidian se convierte en una superficie de lectura local, no en fuente de
  verdad.
- La fuente canonica sigue siendo `<project>/.braid/memory/` y el perfil global
  sigue viviendo en `$HOME/.braid/profile/`.
- Futuras mejoras de navegacion o plantillas Obsidian deben mantener la regla de
  subcarpeta gestionada para vaults existentes.
