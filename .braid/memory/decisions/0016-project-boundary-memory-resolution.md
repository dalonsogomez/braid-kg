# ADR 0016 - Project Boundary Memory Resolution

- **Estado:** Accepted
- **Fecha:** 2026-06-05
- **Decisor:** Daniel Alonso Gomez
- **Tags:** memory, context-resolution, layout, migration

---

## Contexto

Braid ya adopto el layout canonico .braid/ por ADR 0015. Durante la migracion se
detectaron restos legacy en un directorio contenedor de proyectos
(/Users/dalonsogomez/Developer): .braid/, .kg/, .rag/, .memory/, .kgconfig y
wikiforge.files.

Ese estado raiz era legacy y debia archivarse, pero eso no significa que Developer
no pueda ser una frontera Braid valida. Cualquier directorio padre puede tener su
propia .braid/ si se trabaja directamente en el. La condicion critica es que, si
un agente trabaja dentro de un hijo como stock-pattern-classifier-orchestrator, el
contexto del padre no debe ganar por accidente sobre la frontera del hijo.

## Decision

Braid resuelve contexto por la frontera del proyecto real mas cercano.

Un proyecto real se reconoce por marcadores concretos como .git, pyproject.toml,
requirements.txt, package.json, Dockerfile, .sln, go.mod, Cargo.toml, README.md y
equivalentes. Una vez encontrada esa frontera, el estado Braid de un padre no
cruza hacia el proyecto hijo. Si el cwd esta en el padre, el padre puede ser su
propio contexto Braid; si el cwd esta en el hijo, gana el hijo.

La separacion queda asi:

```text
<proyecto>/.braid/       # memoria y runtime de proyecto
~/.braid/profile/        # memoria global/personal
~/.braid/cognee/         # backend compartido, siempre namespaced por dataset_id
```

braid init crea .braid/ en la frontera de proyecto real mas cercana. La lectura
legacy de .kg/, .rag/, .memory/ y .kgconfig se mantiene solo para migracion; las
escrituras nuevas no salen de .braid/.

Los restos legacy encontrados en el contenedor ~/Developer se archivan, no se
borran, bajo ~/.braid/migrations/developer-root-<timestamp>/.

El perfil global se ancla semanticamente en $HOME. Su almacenamiento fisico vive
en ~/.braid/profile/ y no convierte ~/.braid/ ni $HOME/.braid en proyecto activo.

## Consecuencias

- braid status desde un proyecto hijo sin .braid/ muestra ese proyecto como no
  inicializado en lugar de resolver el contenedor padre.
- braid status desde un padre inicializado muestra el padre como contexto activo.
- braid init dentro de un proyecto sin .git propio usa sus marcadores locales y
  crea <proyecto>/.braid/.
- braid init dentro de un subdirectorio de un repo real sigue usando la raiz del
  repo.
- braid init ejecutado directamente en un directorio padre puede crear la .braid/
  de ese padre; eso no afecta a hijos que tengan frontera propia.
- Las rutas internas nuevas siguen usando braid_ducklake y braid_fts.duckdb.
- Los artefactos legacy quedan recuperables desde la carpeta de migracion, pero
  dejan de aparecer como salida activa de Braid.
