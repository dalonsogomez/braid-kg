# Plan 0001 — Fase 0 Bootstrap (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** cumplir el criterio de salida de Fase 0 del `AGENTS.md` sec. 10 — *"≥ 4 de 5 preguntas concretas sobre símbolos del repo respondidas correctamente sin abrir archivos"* — para el repositorio de prueba `~/Developer/ai/uml-class_diagram`, vía MCP server `cognee` consumido por Claude Code.

**Architecture:** Cognee 1.x (Direct Mode) corre en un venv dedicado bajo `~/.wikiforge/cognee-mcp/`, configurado para usar Gemini 3 Flash + `gemini-embedding-001` (ADR 0001). El servidor MCP se registra en Claude Code vía `claude mcp add` con transporte stdio. El repo de prueba se inicializa con `git init` + `.kgconfig` + symlinks AGENTS.md según sec. 6 del AGENTS.md canónico. La indexación inicial pasa por `cognee.run_code_graph_pipeline` (codify, tree-sitter Python) + `cognee.cognify` (docs Markdown). Las cinco preguntas de validación se ejecutan invocando las herramientas MCP `cognee_search` desde Claude Code y se comparan contra ground truth conocido del repo.

**Tech Stack:** Python 3.13.13 (pyenv-managed), `uv` 0.11.7, Cognee 1.x (LiteLLM debajo), Gemini 3 Flash Preview, `gemini-embedding-001` (3072 dims), networkx (graph backend in-process), LanceDB embebida (vector store), git, Claude Code MCP.

---

## File Structure

| Path | Acción | Responsabilidad |
|---|---|---|
| `~/.wikiforge/cognee-mcp/` | Crear | Workdir dedicado del MCP server. Clon de `topoteretes/cognee` rama estable. |
| `~/.wikiforge/cognee-mcp/cognee-mcp/.env` | Crear | Config de cognee-mcp (sin secretos; carga vía `~/.config/wikiforge/secrets.env`). |
| `~/.config/wikiforge/secrets.env` | Ya existe (commit anterior) | Keys (chmod 600), fuera del repo. |
| `~/Developer/ai/uml-class_diagram/.gitignore` | Crear | Excluye backups, output, build, `__pycache__`, `*.env`, `.kg/`, `.rag/`. |
| `~/Developer/ai/uml-class_diagram/.kgconfig` | Crear | TOML según AGENTS.md sec. 13.1 con valores Gemini del ADR 0001. |
| `~/Developer/ai/uml-class_diagram/AGENTS.md` | Crear | Plantilla AGENTS.md específica del repo de prueba (sec. 13.3 del canónico). |
| `~/Developer/ai/uml-class_diagram/CLAUDE.md` | Crear | Symlink → `AGENTS.md`. |
| `~/Developer/ai/uml-class_diagram/.github/copilot-instructions.md` | Crear | Symlink → `../AGENTS.md`. |
| `~/Developer/ai/uml-class_diagram/.cursor/rules/main.mdc` | Crear | Symlink → `../../AGENTS.md`. |
| `~/Developer/ai/uml-class_diagram/.memory/MEMORY.md` | Crear | Índice del repo de prueba. |
| `~/Developer/ai/uml-class_diagram/.memory/decisions/.gitkeep` | Crear | Carpeta vacía para futuros ADRs del repo de prueba. |
| `~/Developer/ai/uml-class_diagram/.memory/plans/.gitkeep` | Crear | Carpeta vacía para futuros planes. |
| `WikiForge/.memory/plans/0001-fase-0-bootstrap.md` | Este archivo | Plan de Fase 0. |
| `WikiForge/.memory/plans/0001-fase-0-bootstrap-results.md` | Crear (Task 9) | Registro de resultados de las 5 preguntas + decisión pass/fail. |

**Convención de commits:**
- Cada Task que termine con un cambio en disco hace commit en el repo correspondiente (WikiForge o uml-class_diagram).
- Mensajes en inglés (AGENTS.md sec. 8.4).
- No firmar como Co-Authored-By en el repo de prueba (es código del usuario, no de WikiForge); sí firmar en WikiForge.

---

## Task 1: Verify prerequisites

**Files:** ninguno.

**Goal:** confirmar que el entorno tiene Python ≥ 3.10, uv, git, claude CLI, y que la red llega a Gemini API.

- [ ] **Step 1.1: Verificar versión Python**

```bash
python3 --version
```

Expected: `Python 3.10.x` o superior. (Sabemos que es 3.13.13.) Si no, `pyenv install 3.13.13 && pyenv global 3.13.13`.

- [ ] **Step 1.2: Verificar uv**

```bash
uv --version
```

Expected: `uv 0.11.x` o superior. Si no, `brew install uv`.

- [ ] **Step 1.3: Verificar git**

```bash
git --version
```

Expected: cualquier `git version 2.x`.

- [ ] **Step 1.4: Verificar Claude Code CLI**

```bash
claude --version
```

Expected: imprime versión sin error. Si falla, abortar y avisar al usuario.

- [ ] **Step 1.5: Verificar conectividad Gemini API con la key**

```bash
source ~/.config/wikiforge/secrets.env
curl -sS -o /tmp/gemini_smoke.json -w "HTTP %{http_code}\n" \
  "https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}" | head -1
```

Expected: `HTTP 200`. Si `401`/`403`, la key no es válida → abortar y pedir rotación al usuario. Si `429`, la cuota free tier ya está agotada → considerar billing o reintentar tras la ventana.

- [ ] **Step 1.6: Confirmar que `gemini-3-flash-preview` está en el listado del proyecto**

```bash
jq -r '.models[].name' /tmp/gemini_smoke.json | grep -E "gemini-3-flash-preview|gemini-3-flash$"
```

Expected: imprime `models/gemini-3-flash-preview` (al menos una línea). Si no aparece, ese ID no está disponible para este proyecto/región: documentar en `bootstrap-results.md` y elegir el ID concreto disponible (`gemini-2.5-flash` como fallback inmediato; el cambio se registra como addendum al ADR 0001).

- [ ] **Step 1.7: Limpiar archivo temporal**

```bash
rm /tmp/gemini_smoke.json
```

- [ ] **Step 1.8: Sin commit (Task de verificación, no produce archivos).**

---

## Task 2: Install cognee-mcp from source under ~/.wikiforge/

**Files:**
- Create: `~/.wikiforge/cognee-mcp/` (clone target)

**Goal:** instalar Cognee + MCP server en un workdir dedicado, separado del repo WikiForge.

- [ ] **Step 2.1: Crear directorio raíz `~/.wikiforge/`**

```bash
mkdir -p ~/.wikiforge && cd ~/.wikiforge && pwd
```

Expected: imprime `/Users/dalonsogomez/.wikiforge`.

- [ ] **Step 2.2: Clonar el repo oficial topoteretes/cognee**

```bash
cd ~/.wikiforge && git clone --depth 1 https://github.com/topoteretes/cognee.git cognee-mcp
```

Expected: clon exitoso, `cd cognee-mcp` lleva al repo. Si la rama default ha cambiado el path del MCP server, ajustar steps siguientes.

- [ ] **Step 2.3: Verificar que existe el subdirectorio `cognee-mcp/`**

```bash
ls ~/.wikiforge/cognee-mcp/cognee-mcp/pyproject.toml
```

Expected: el archivo existe. Si no existe, el repo upstream cambió la estructura: leer `~/.wikiforge/cognee-mcp/README.md` y ajustar.

- [ ] **Step 2.4: Crear venv e instalar dependencias con uv**

```bash
cd ~/.wikiforge/cognee-mcp/cognee-mcp && uv sync --dev --all-extras --reinstall
```

Expected: termina sin error. Crea `~/.wikiforge/cognee-mcp/cognee-mcp/.venv/`.

- [ ] **Step 2.5: Verificar que el binario del server arranca con `--help`**

```bash
cd ~/.wikiforge/cognee-mcp/cognee-mcp && uv run python src/server.py --help 2>&1 | head -20
```

Expected: imprime ayuda con flags `--transport`, `--host`, `--port`. Si crashea, leer error y abortar para diagnosticar.

- [ ] **Step 2.6: Sin commit (instalación local, no toca repos).**

---

## Task 3: Configure cognee-mcp .env (no secrets in repo)

**Files:**
- Create: `~/.wikiforge/cognee-mcp/cognee-mcp/.env`

**Goal:** configurar Cognee con Gemini sin escribir la API key en disco fuera del secrets file.

- [ ] **Step 3.1: Crear `.env` apuntando a Gemini sin la key**

```bash
cat > ~/.wikiforge/cognee-mcp/cognee-mcp/.env <<'EOF'
# Generado por WikiForge Plan 0001 (Fase 0). Ver ADR 0001 sec. 2.3.
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-3-flash-preview
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini/gemini-embedding-001
EMBEDDING_DIMENSIONS=3072
GRAPH_DATABASE_PROVIDER=networkx
VECTOR_DB_PROVIDER=lancedb
# LLM_API_KEY se lee desde ~/.config/wikiforge/secrets.env vía exportación previa.
EOF
```

- [ ] **Step 3.2: Verificar permisos del secrets.env y que la key está**

```bash
ls -la ~/.config/wikiforge/secrets.env && grep -q "^GEMINI_API_KEY=" ~/.config/wikiforge/secrets.env && echo "key present"
```

Expected: archivo `-rw-------` (600), output incluye `key present`. Si no, el ADR 0001 sec. 2.4 fue violado: corregir antes de seguir.

- [ ] **Step 3.3: Crear shim `~/.wikiforge/bin/cognee-mcp-stdio.sh`**

Necesario porque cognee-mcp espera `LLM_API_KEY` como variable de entorno; el shim mapea `GEMINI_API_KEY` → `LLM_API_KEY` y arranca el server.

```bash
mkdir -p ~/.wikiforge/bin
cat > ~/.wikiforge/bin/cognee-mcp-stdio.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
# WikiForge cognee-mcp launcher. ADR 0001 sec. 2.4: API key vive en secrets.env (chmod 600).
SECRETS="${HOME}/.config/wikiforge/secrets.env"
if [[ ! -r "${SECRETS}" ]]; then
  echo "FATAL: ${SECRETS} not readable" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "${SECRETS}"
export LLM_API_KEY="${GEMINI_API_KEY:?GEMINI_API_KEY missing in secrets.env}"
export EMBEDDING_API_KEY="${GEMINI_API_KEY}"
cd "${HOME}/.wikiforge/cognee-mcp/cognee-mcp"
exec uv run python src/server.py --transport stdio "$@"
EOF
chmod +x ~/.wikiforge/bin/cognee-mcp-stdio.sh
```

- [ ] **Step 3.4: Smoke-run del shim (debe quedarse en stdio, esperando input)**

```bash
timeout 3 ~/.wikiforge/bin/cognee-mcp-stdio.sh 2>&1 | head -10 || true
```

Expected: el server imprime un banner JSON-RPC o se queda silencioso esperando stdin (timeout lo mata limpio). No debe imprimir errores fatales tipo `ImportError`, `KeyError`, `Authentication failed`. Si hay error de auth, revisar Step 3.3 o que la key esté correcta.

- [ ] **Step 3.5: Sin commit (instalación local, no toca repos).**

---

## Task 4: Smoke-test Gemini via Cognee end-to-end

**Files:**
- Create: `~/.wikiforge/cognee-mcp/smoke_test.py`

**Goal:** verificar que cognee puede invocar Gemini exitosamente con un prompt minúsculo, antes de gastar quota indexando un repo.

- [ ] **Step 4.1: Escribir el script de smoke test**

```bash
cat > ~/.wikiforge/cognee-mcp/smoke_test.py <<'EOF'
"""Phase 0 smoke test: verify Cognee can talk to Gemini and return a result."""
import asyncio
import os
import sys
from pathlib import Path

# Load secrets
secrets = Path.home() / ".config/wikiforge/secrets.env"
if not secrets.is_file():
    sys.exit(f"FATAL: {secrets} missing")
for line in secrets.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)
os.environ["LLM_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ["EMBEDDING_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["LLM_MODEL"] = "gemini/gemini-3-flash-preview"
os.environ["EMBEDDING_PROVIDER"] = "gemini"
os.environ["EMBEDDING_MODEL"] = "gemini/gemini-embedding-001"
os.environ["EMBEDDING_DIMENSIONS"] = "3072"

import cognee  # noqa: E402

async def main() -> int:
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    await cognee.add("Phase 0 of WikiForge swaps Ollama for Gemini per ADR 0001.")
    await cognee.cognify()
    results = await cognee.search(
        query_type=cognee.SearchType.SUMMARIES,
        query_text="What does Phase 0 of WikiForge do?",
    )
    print("RESULTS:", results)
    if not results:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
EOF
```

- [ ] **Step 4.2: Ejecutar smoke test**

```bash
cd ~/.wikiforge/cognee-mcp/cognee-mcp && uv run python ../smoke_test.py
```

Expected: termina con exit code 0 y la línea `RESULTS:` contiene una respuesta no vacía sobre Phase 0 / WikiForge / ADR 0001. Si falla con `Authentication failed`, revisar key. Si falla con `model not found`, ese ID no está disponible: caer al fallback `gemini-2.5-flash`, registrar en `bootstrap-results.md` como addendum al ADR 0001.

- [ ] **Step 4.3: Limpieza**

```bash
rm ~/.wikiforge/cognee-mcp/smoke_test.py
```

- [ ] **Step 4.4: Sin commit (verificación local).**

---

## Task 5: Initialize uml-class_diagram as Phase 0 test repo

**Files:**
- Create: `~/Developer/ai/uml-class_diagram/.git/` (via `git init`)
- Create: `~/Developer/ai/uml-class_diagram/.gitignore`
- Create: `~/Developer/ai/uml-class_diagram/.kgconfig`
- Create: `~/Developer/ai/uml-class_diagram/AGENTS.md`
- Create: `~/Developer/ai/uml-class_diagram/CLAUDE.md` → symlink AGENTS.md
- Create: `~/Developer/ai/uml-class_diagram/.github/copilot-instructions.md` → symlink ../AGENTS.md
- Create: `~/Developer/ai/uml-class_diagram/.cursor/rules/main.mdc` → symlink ../../AGENTS.md
- Create: `~/Developer/ai/uml-class_diagram/.memory/MEMORY.md`
- Create: `~/Developer/ai/uml-class_diagram/.memory/decisions/.gitkeep`
- Create: `~/Developer/ai/uml-class_diagram/.memory/plans/.gitkeep`

**Goal:** alinear el repo de prueba con la estructura de directorios canónica del AGENTS.md sec. 6.

- [ ] **Step 5.1: Confirmar que el repo NO es git todavía**

```bash
cd ~/Developer/ai/uml-class_diagram && (git rev-parse --is-inside-work-tree 2>/dev/null && echo "ALREADY GIT — abort" || echo "not git, OK to init")
```

Expected: `not git, OK to init`. Si ya es git (improbable), abortar y revisar con el usuario.

- [ ] **Step 5.2: `git init` con branch `main`**

```bash
cd ~/Developer/ai/uml-class_diagram && git init -b main
```

Expected: imprime `Initialized empty Git repository in .../uml-class_diagram/.git/`.

- [ ] **Step 5.3: Crear `.gitignore` excluyendo backups, output, build, secrets, KG**

```bash
cat > ~/Developer/ai/uml-class_diagram/.gitignore <<'EOF'
# Backups y outputs (no van a git ni a la indexación de Cognee)
_backup_pre_8bugs_*/
_backups_claude_code/
output/
build/

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.pytest_cache/

# Secretos
*.env
!.env.example
secrets.env
*.secret
*.key

# Cognee runtime data (Nivel 1)
.kg/
.rag/

# Sesiones volátiles (Nivel 0)
.memory/sessions/

# IDE / OS
.DS_Store
.idea/
.vscode/
*.swp
EOF
```

- [ ] **Step 5.4: Crear `.kgconfig` (TOML según AGENTS.md sec. 13.1, ajustado a Gemini)**

```bash
cat > ~/Developer/ai/uml-class_diagram/.kgconfig <<'EOF'
# WikiForge .kgconfig (AGENTS.md sec. 13.1 + ADR 0001 stack Gemini)
dataset_id = "vp-class-diagram-agent"
graph_backend = "networkx"
vector_backend = "lancedb"
embedder = "gemini/gemini-embedding-001"
llm = "gemini/gemini-3-flash-preview"
fallback_threshold = 0.55
priority = ["active_file", "project_graph", "project_vector", "global_profile"]

[memory]
temporal_store = ".memory/sessions"
persistent_store = ".memory/persistent"
promotion_policy = "explicit_only"
EOF
```

- [ ] **Step 5.5: Crear `AGENTS.md` específico del repo (sec. 13.3 plantilla canónica)**

```bash
cat > ~/Developer/ai/uml-class_diagram/AGENTS.md <<'EOF'
# Proyecto: VP Class Diagram Agent

Local MCP server and Visual Paradigm plugin for generating editable UML Class
Diagrams from local course PDFs, solved examples, and a structured
`ClassDiagramSpec.json` contract. Default workflow is private/local.

## Stack
- Python 3.13, MCP server (stdio).
- Visual Paradigm Open API plugin (Java) bajo `plugin/`.
- Tests: pytest bajo `tests/`.

## Comandos
- `uv sync` — instalar dependencias.
- `uv run python -m vp_class_diagram_agent` — arrancar MCP server.
- `uv run pytest` — correr tests.

## Convenciones críticas
- Salida principal: `.vpp` editable nativo de Visual Paradigm. PlantUML/XMI no son la ruta primaria.
- Estilo del profesor "afermosoga" (UPSA): material académico — no salir a APIs cloud sin autorización explícita.

## Memoria del proyecto
- Contexto extendido en `.memory/MEMORY.md` y `.memory/decisions/`.
- Knowledge graph disponible vía MCP server `cognee` con `dataset_id=vp-class-diagram-agent`.
- Para promover una decisión: `wikiforge promote-decision "..."` (CLI Fase 1, aún no instalado).
- El sistema sigue las reglas del `AGENTS.md` canónico de WikiForge (`~/Developer/claude/code-projects/WikiForge/AGENTS.md`).
EOF
```

- [ ] **Step 5.6: Crear symlinks AGENTS.md → CLAUDE.md, copilot-instructions.md, cursor**

```bash
cd ~/Developer/ai/uml-class_diagram
ln -sf AGENTS.md CLAUDE.md
mkdir -p .github && ln -sf ../AGENTS.md .github/copilot-instructions.md
mkdir -p .cursor/rules && ln -sf ../../AGENTS.md .cursor/rules/main.mdc
ls -la CLAUDE.md .github/copilot-instructions.md .cursor/rules/main.mdc
```

Expected: las tres entradas son symlinks (`l` al inicio de los permisos).

- [ ] **Step 5.7: Crear esqueleto `.memory/`**

```bash
cd ~/Developer/ai/uml-class_diagram
mkdir -p .memory/decisions .memory/plans
touch .memory/decisions/.gitkeep .memory/plans/.gitkeep
cat > .memory/MEMORY.md <<'EOF'
# MEMORY.md — VP Class Diagram Agent

> Índice operacional del repo. Apunta a decisiones y planes propios.

## Decisiones (ADRs)

(vacío — añadir con `wikiforge promote-decision` cuando exista CLI)

## Planes activos

(vacío)

## Convenciones

- AGENTS.md canónico de WikiForge gobierna; este `AGENTS.md` solo lista convenciones de este repo.
- Indexado en knowledge graph Cognee vía `dataset_id=vp-class-diagram-agent`.
EOF
```

- [ ] **Step 5.8: Primer commit del repo de prueba**

```bash
cd ~/Developer/ai/uml-class_diagram
git add .gitignore .kgconfig AGENTS.md CLAUDE.md .github/ .cursor/ .memory/
git commit -m "chore: bootstrap WikiForge governance for Phase 0 test repo

- AGENTS.md per-project (sec. 13.3 of canonical AGENTS.md)
- CLAUDE.md / copilot / cursor symlinks to AGENTS.md
- .kgconfig pointing to dataset 'vp-class-diagram-agent' with Gemini stack (ADR 0001)
- .memory/ skeleton (decisions/, plans/, MEMORY.md)
- .gitignore excluding backups, output, build, secrets, .kg/, .rag/"
```

- [ ] **Step 5.9: Segundo commit con el código existente del repo (snapshot baseline)**

```bash
cd ~/Developer/ai/uml-class_diagram
git add .
git status --short | head -20
```

Si `git status` muestra archivos pendientes (todo el código actual), continuar:

```bash
git add -A
git commit -m "chore: import existing project tree as baseline (pre-WikiForge work)"
```

Expected: commit incluye `src/`, `tests/`, `plugin/`, `docs/`, `README.md`, `pyproject.toml`, etc. Los `_backup_*` y `output/` quedan fuera por `.gitignore`.

---

## Task 6: Index uml-class_diagram with cognee

**Files:**
- Create: `~/.wikiforge/cognee-mcp/index_phase0.py` (script de indexación one-shot)
- Create: `~/Developer/ai/uml-class_diagram/.kg/`, `.rag/` (artefactos de cognee)

**Goal:** ejecutar `cognee.run_code_graph_pipeline` (codify) sobre `src/` + `tests/`, y `cognee.cognify` sobre los Markdown del repo.

- [ ] **Step 6.1: Escribir el script de indexación**

```bash
cat > ~/.wikiforge/cognee-mcp/index_phase0.py <<'EOF'
"""Phase 0 indexer: build code graph + doc embeddings for vp-class-diagram-agent."""
import asyncio
import os
import sys
from pathlib import Path

# Load secrets and config (same shim as smoke test)
secrets = Path.home() / ".config/wikiforge/secrets.env"
for line in secrets.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)
os.environ["LLM_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ["EMBEDDING_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["LLM_MODEL"] = "gemini/gemini-3-flash-preview"
os.environ["EMBEDDING_PROVIDER"] = "gemini"
os.environ["EMBEDDING_MODEL"] = "gemini/gemini-embedding-001"
os.environ["EMBEDDING_DIMENSIONS"] = "3072"

import cognee  # noqa: E402

REPO = Path("/Users/dalonsogomez/Developer/ai/uml-class_diagram").resolve()
DATASET = "vp-class-diagram-agent"
DOC_GLOBS = ["README.md", "MEMORY.md", "docs/**/*.md"]

async def main() -> int:
    print(f"[phase0] dataset={DATASET} repo={REPO}")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    # Code graph
    print("[phase0] running run_code_graph_pipeline (tree-sitter Python)...")
    async for status in cognee.run_code_graph_pipeline(
        repo_path=str(REPO / "src"),
        include_docs=False,
    ):
        print(f"  code-pipeline: {status}")

    # Docs (Markdown)
    docs: list[str] = []
    for glob in DOC_GLOBS:
        for p in REPO.glob(glob):
            if "_backup" in str(p) or "output" in str(p):
                continue
            docs.append(p.read_text(errors="ignore"))
    print(f"[phase0] adding {len(docs)} doc files for cognify...")
    if docs:
        await cognee.add(docs, dataset_name=DATASET)
        await cognee.cognify(datasets=[DATASET])

    # Sanity ping
    res = await cognee.search(
        query_type=cognee.SearchType.SUMMARIES,
        query_text="What does this repository do?",
        datasets=[DATASET],
    )
    print(f"[phase0] sanity result count: {len(res)}")
    return 0 if res else 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
EOF
```

- [ ] **Step 6.2: Ejecutar indexación**

```bash
cd ~/.wikiforge/cognee-mcp/cognee-mcp && time uv run python ../index_phase0.py 2>&1 | tee /tmp/phase0_index.log
```

Expected: termina con exit 0, tiempo total < 10 minutos para 27 archivos py + ~35 docs Markdown. La salida incluye `sanity result count: N` con `N ≥ 1`. Si falla con `429`/quota, esperar la ventana e intentar de nuevo. Si falla con `model not found`, aplicar fallback `gemini-2.5-flash` en `.env` y `index_phase0.py` y reintentar.

- [ ] **Step 6.3: Inspección rápida del grafo generado**

```bash
ls -la ~/.cognee/ 2>/dev/null | head -10
ls -la ~/.cognee/data/ 2>/dev/null | head -10
```

Expected: existen `~/.cognee/data/` con artefactos. Si Cognee escribió en otro path, ajustar `DATA_ROOT_DIRECTORY` env var en futuros pasos.

- [ ] **Step 6.4: Verificar que el grafo tiene los tipos de nodos esperados (AGENTS.md sec. 5.2)**

```bash
cat > /tmp/phase0_graph_check.py <<'EOF'
"""Cuenta nodos por tipo en el grafo NetworkX que cognee acaba de construir."""
import os
import pickle
from collections import Counter
from pathlib import Path

# Localizar el archivo de grafo
candidates = list(Path.home().glob(".cognee/**/networkx_graph.pkl"))
if not candidates:
    raise SystemExit("FATAL: networkx_graph.pkl no encontrado bajo ~/.cognee/")
graph_path = candidates[0]
print(f"[graph-check] graph={graph_path}")

with graph_path.open("rb") as f:
    g = pickle.load(f)

types = Counter(data.get("type", data.get("node_type", "?")) for _, data in g.nodes(data=True))
print(f"[graph-check] total nodes: {g.number_of_nodes()}")
for t, n in types.most_common(20):
    print(f"  {t}: {n}")
EOF
uv run --project ~/.wikiforge/cognee-mcp/cognee-mcp python /tmp/phase0_graph_check.py
rm /tmp/phase0_graph_check.py
```

Expected: imprime `total nodes: N` con `N ≥ 50` y al menos los tipos `File`, `Symbol` (o variantes que cognee use como `CodeFile`, `CodeFunction`, `CodeClass`). Si el grafo tiene < 20 nodos, la indexación falló silenciosamente: revisar `/tmp/phase0_index.log`. Si los tipos no encajan ni remotamente con AGENTS.md sec. 5.2, registrar la divergencia en `bootstrap-results.md` (puede ser que cognee 1.x use nombres distintos: `Repository`/`SourceCodeChunk`/etc.).

- [ ] **Step 6.5: Sin commit (los datos generados están bajo `~/.cognee/`, no en el repo).**

---

## Task 7: Register cognee MCP server in Claude Code

**Files:** ninguno (config en `~/.claude.json` gestionada por `claude` CLI).

**Goal:** que Claude Code pueda invocar las herramientas `cognee_*` vía MCP en futuras sesiones.

- [ ] **Step 7.1: Listar MCP servers actuales para no duplicar**

```bash
claude mcp list 2>&1 | grep -i cognee || echo "cognee not registered yet"
```

Expected: `cognee not registered yet`. Si ya estuviera, hacer `claude mcp remove cognee` antes.

- [ ] **Step 7.2: Registrar cognee como MCP server stdio**

```bash
claude mcp add --scope user --transport stdio cognee /Users/dalonsogomez/.wikiforge/bin/cognee-mcp-stdio.sh
```

Expected: imprime confirmación de registro. Sin error.

- [ ] **Step 7.3: Verificar conexión**

```bash
claude mcp list 2>&1 | grep cognee
```

Expected: línea con `cognee: ... ✓ Connected`. Si dice `✗`, ejecutar `claude mcp get cognee` para ver el error y diagnosticar (causa típica: shim sin permisos exec, secrets.env faltando, o dependencia Python no instalada).

- [ ] **Step 7.4: Sin commit.**

---

## Task 8: Define the 5 validation questions

**Files:**
- Create: `~/Developer/claude/code-projects/WikiForge/.memory/plans/0001-fase-0-bootstrap-questions.md`

**Goal:** fijar las 5 preguntas con su ground truth ANTES de invocar el MCP, para evitar mover el poste de la portería.

- [ ] **Step 8.1: Escribir el archivo de preguntas con ground truth**

```bash
cat > ~/Developer/claude/code-projects/WikiForge/.memory/plans/0001-fase-0-bootstrap-questions.md <<'EOF'
# Fase 0 — 5 preguntas de validación

> Plan 0001, criterio de salida AGENTS.md sec. 10: ≥ 4 / 5 correctas sin abrir archivos.

Cada pregunta cubre uno de los tipos de la sec. 5.3 del AGENTS.md (CALLS, IMPORTS, CONTAINS, DOCUMENTS, MENTIONS).

## Q1 — Comportamiento de un símbolo (CONTAINS + descripción)

**Pregunta:** "¿Qué hace la función `generate_from_statement` en el repo `vp-class-diagram-agent`? ¿Qué argumentos toma y qué retorna?"

**Ground truth:** vive en `src/vp_class_diagram_agent/generator.py`. Firma:
`def generate_from_statement(statement_path: str | Path, style: dict[str, Any] | None = None) -> dict[str, Any]:`
Genera un draft `ClassDiagramSpec.json` a partir de un PDF de enunciado, opcionalmente sesgado por un perfil de estilo del profesor.

**Aceptable si la respuesta:** menciona el archivo correcto, identifica los dos parámetros (statement_path y style), y describe el propósito (generar spec/draft a partir de un statement/enunciado).

## Q2 — Llamadas (relación CALLS)

**Pregunta:** "¿Qué función o método llama a `audit_exam_associations`?"

**Ground truth:** verificar con `rg "audit_exam_associations\(" src/`. La invocación canónica está en `src/vp_class_diagram_agent/iweb_generator.py` (en el flujo `generate_iweb_class_diagrams` / `_generate_bdbol_specs`). Si rg muestra otro callsite, ese es el ground truth.

**Aceptable si la respuesta:** nombra al menos un archivo y un símbolo concreto que la llame, y NO inventa un callsite que no exista.

## Q3 — Estructura del repo (CONTAINS / IMPORTS)

**Pregunta:** "¿Qué archivos componen el plugin de Visual Paradigm en este repo?"

**Ground truth:** `plugin/plugin.xml` + `plugin/src/**/*.java` (16 archivos Java según conteo previo).

**Aceptable si la respuesta:** identifica el directorio `plugin/` como raíz, menciona `plugin.xml` y reconoce que el código es Java bajo `plugin/src/`.

## Q4 — Documentación (DOCUMENTS)

**Pregunta:** "¿En qué sección del README se describe el flujo `Direct .vpp Solution Output` para WEB MYSPORT?"

**Ground truth:** sección `## Direct \`.vpp\` Solution Output` del README, segundo heading. Describe el pipeline `generate_iweb_exam_solution_vpp` → review bundles → copia plantilla `resources/vp-uml/templates/empty_project.vpp` → plugin VP aplica spec.

**Aceptable si la respuesta:** cita el heading correcto del README y resume los pasos clave.

## Q5 — Privacidad / convención del repo (MENTIONS / DOC chunks)

**Pregunta:** "¿Cuál es el flujo por defecto de privacidad de este repo: local o cloud?"

**Ground truth:** la sección `## Privacy Notes` del README explica que el flujo default es privado/local (PDFs ingeridos localmente, plugin Java aplica spec en `.vpp`, sin envío a APIs cloud salvo autorización explícita).

**Aceptable si la respuesta:** dice "local/privado por defecto" y cita la sección Privacy Notes o equivalente.

---

## Reglas de scoring

- **Correcta (1 pt):** la respuesta cubre el ground truth sin inventar nombres, archivos o comportamientos. Citas a `file:line` aproximadas (±5 líneas) cuentan como correctas.
- **Parcial (0.5 pt):** menciona el archivo correcto pero el comportamiento es vago, o el comportamiento correcto pero atribuido al archivo equivocado.
- **Incorrecta (0 pt):** alucina un símbolo, archivo o comportamiento que no existe en el repo.
- **Criterio de salida:** suma ≥ 4.0 / 5.0.
EOF
```

- [ ] **Step 8.2: Verificar ground truth de Q2 con `rg`**

```bash
cd ~/Developer/ai/uml-class_diagram && grep -rE "audit_exam_associations\(" src/ | head -5
```

Si el callsite real difiere de lo que dice `0001-fase-0-bootstrap-questions.md` Q2, **editar el archivo de preguntas para reflejar la realidad** antes de Task 9. No mover el poste de la portería tras ver respuestas.

- [ ] **Step 8.3: Commit en WikiForge**

```bash
cd ~/Developer/claude/code-projects/WikiForge
git add .memory/plans/0001-fase-0-bootstrap-questions.md
git commit -m "docs: define Phase 0 validation questions with ground truth

5 questions covering CALLS, IMPORTS, CONTAINS, DOCUMENTS, MENTIONS relations.
Ground truth recorded BEFORE invoking the MCP to avoid moving the goalposts.
Pass criterion: >= 4.0 / 5.0 (AGENTS.md sec. 10).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Run validation questions and score

**Files:**
- Create: `~/Developer/claude/code-projects/WikiForge/.memory/plans/0001-fase-0-bootstrap-results.md`

**Goal:** ejecutar las 5 preguntas vía Claude Code → MCP `cognee` → grafo, y registrar puntuación.

- [ ] **Step 9.1: Iniciar una sesión de Claude Code DENTRO del repo de prueba**

Manualmente, desde otra terminal:
```bash
cd ~/Developer/ai/uml-class_diagram && claude
```

Esto asegura que `cwd → git root → .kgconfig` resuelva al dataset `vp-class-diagram-agent`. (Tarea de validación humana / agente, no automatizable en este script.)

- [ ] **Step 9.2: En esa sesión, hacer las 5 preguntas una a una**

Pegar cada pregunta literal del archivo `0001-fase-0-bootstrap-questions.md`. **No abrir archivos del repo** durante la sesión: la métrica exige que la respuesta venga del MCP. Si Claude Code intenta usar `Read`, declinarlo.

Para cada pregunta, recoger:
- Texto íntegro de la respuesta del agente.
- ¿Citó archivo:línea? ¿Se ajusta al ground truth?
- Puntuación (1.0 / 0.5 / 0.0).

- [ ] **Step 9.3: Crear el archivo de resultados**

```bash
cat > ~/Developer/claude/code-projects/WikiForge/.memory/plans/0001-fase-0-bootstrap-results.md <<'EOF'
# Fase 0 — Resultados de validación

**Fecha de ejecución:** YYYY-MM-DD
**Repo de prueba:** vp-class-diagram-agent
**Dataset Cognee:** vp-class-diagram-agent
**Modelo extracción:** gemini-3-flash-preview (o fallback registrado)

## Resultados por pregunta

### Q1
- Respuesta del agente: <pegar literal>
- Ground truth: ver `0001-fase-0-bootstrap-questions.md` Q1
- Puntuación: <1.0 / 0.5 / 0.0>
- Notas: <observaciones, alucinaciones detectadas, archivos citados>

### Q2
- Respuesta: <...>
- Puntuación: <...>
- Notas: <...>

### Q3
- Respuesta: <...>
- Puntuación: <...>
- Notas: <...>

### Q4
- Respuesta: <...>
- Puntuación: <...>
- Notas: <...>

### Q5
- Respuesta: <...>
- Puntuación: <...>
- Notas: <...>

## Total

- **Puntuación total:** <X.Y / 5.0>
- **Criterio (AGENTS.md sec. 10):** ≥ 4.0
- **Resultado:** PASS / FAIL

## Próximas decisiones

- Si PASS: cerrar Fase 0, abrir Fase 1 (CLI `wikiforge`, wrapper de tres niveles, perfil global).
- Si FAIL: análisis de modo de fallo, posible reindex con `gemini-3.1-pro-preview` en lugar de Flash, o addendum al ADR 0001.
EOF
```

- [ ] **Step 9.4: Rellenar manualmente el archivo de resultados con los datos del Step 9.2**

Editar `0001-fase-0-bootstrap-results.md` sustituyendo cada `<...>` con el contenido real.

- [ ] **Step 9.5: Calcular total y registrar PASS/FAIL**

Sumar las 5 puntuaciones, escribir el total, y marcar PASS o FAIL.

- [ ] **Step 9.6: Commit**

```bash
cd ~/Developer/claude/code-projects/WikiForge
git add .memory/plans/0001-fase-0-bootstrap-results.md
git commit -m "docs: record Phase 0 validation results

<PASS|FAIL> with score <X.Y/5.0>. Details inline. Next phase decision noted.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Update MEMORY.md and commit Phase 0 closure

**Files:**
- Modify: `~/Developer/claude/code-projects/WikiForge/.memory/MEMORY.md`

**Goal:** dejar trazabilidad y enlaces correctos del cierre de Fase 0.

- [ ] **Step 10.1: Actualizar `.memory/MEMORY.md` con enlaces al plan, preguntas y resultados**

Editar `MEMORY.md` para que la sección "Planes activos" apunte al estado real:

```markdown
## Planes activos

- [Plan 0001 — Bootstrap Fase 0](plans/0001-fase-0-bootstrap.md) — Status: <Completed|Failed> (YYYY-MM-DD)
- [Plan 0001 — Preguntas de validación](plans/0001-fase-0-bootstrap-questions.md)
- [Plan 0001 — Resultados](plans/0001-fase-0-bootstrap-results.md)
```

- [ ] **Step 10.2: Si PASS, dejar nota sobre próxima fase**

Añadir bajo "Estado del repositorio":

```markdown
- Fase 0 cerrada con score <X.Y/5.0>. Próxima fase: Fase 1 (CLI `wikiforge`, wrapper MCP de tres niveles, perfil global).
```

- [ ] **Step 10.3: Commit**

```bash
cd ~/Developer/claude/code-projects/WikiForge
git add .memory/MEMORY.md
git commit -m "docs: close Phase 0 in MEMORY.md, link plan + questions + results

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-review

### 1. Spec coverage

- AGENTS.md sec. 10 (Fase 0 entregable y criterio): cubierto en Tasks 6-9.
- AGENTS.md sec. 13.1 (`.kgconfig` template): Task 5 Step 5.4.
- AGENTS.md sec. 13.2 (`.env` cognee-mcp): Task 3 Step 3.1, alineado con ADR 0001.
- AGENTS.md sec. 13.3 (AGENTS.md per-project template): Task 5 Step 5.5.
- AGENTS.md sec. 6 (estructura de directorios): Task 5 Steps 5.6-5.7 (CLAUDE.md / copilot / cursor symlinks; `.memory/`).
- ADR 0001 sec. 2.4 (gestión de secretos): Task 3 Steps 3.1-3.3 (shim que carga desde secrets.env).
- ADR 0001 sec. 2.5 (autorización privacidad por repo): contemplada en Task 5 (solo `uml-class_diagram` indexado).
- AGENTS.md sec. 8.4 (idioma): commits en inglés, contenido funcional en español, OK.

**Fuera de scope explícito (Fase 1+):** wrapper MCP de tres niveles (sec. 4.3), CLI `wikiforge`, perfil global `~/.wikiforge/profile/AGENTS.md`, suite `wikiforge eval`.

### 2. Placeholder scan

- Comprobado: no hay `TBD`, `TODO`, "implementar después", ni "similar a Task N".
- Step 8.2 lleva una verificación condicional ("editar si difiere") explicada con razón.
- Step 9.4 indica "rellenar `<...>` con datos reales" — esto es esperado en un task de medición humana, no un placeholder de código.

### 3. Type/name consistency

- `dataset_id = "vp-class-diagram-agent"` aparece consistentemente en .kgconfig, AGENTS.md per-project, index_phase0.py, MEMORY.md.
- Modelo `gemini-3-flash-preview` consistente en `.env`, shim, smoke test, index_phase0.py, kgconfig, ADR 0001.
- Path `~/.wikiforge/cognee-mcp/cognee-mcp/` (doble `cognee-mcp` por el subdirectorio del repo upstream) consistente en Tasks 2, 3, 4, 6.

### 4. Riesgos no cubiertos por el plan

- **Si Cognee 1.x cambió el nombre de `run_code_graph_pipeline`** (firmas internas evolucionan), Step 6.1 falla. Mitigación: el smoke test (Task 4) detecta API breakage antes de Task 6.
- **Si el shim no exporta `EMBEDDING_API_KEY` correctamente** y cognee espera otra var, embedding falla. Mitigación: smoke test (Task 4) embebe documentos → si falla allí, ajustar el shim.
- **Quota Gemini agotada en medio de Task 6** → reanudable: Cognee mantiene checkpoints, o se ejecuta Task 6 de nuevo tras la ventana de 1 minuto / 1 día.

---

## Approval gate

**Este plan está pendiente de aprobación del usuario antes de ejecutarse.** Tras aprobación, el usuario decide entre dos modos de ejecución:

1. **Subagent-Driven (recomendado)** — un subagente fresco por Task con review entre tareas.
2. **Inline Execution** — todas las Tasks en esta sesión con checkpoints.

No se invocará ninguna otra skill ni se ejecutará ningún Task hasta que el usuario apruebe explícitamente.
