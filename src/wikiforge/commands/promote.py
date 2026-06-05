"""`fairlead promote-decision`, `promote-to-global`, `demote` — promoción manual de memoria.

Regla de oro AGENTS.md sec. 4.2: NO existe promoción automática.
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import sys
from pathlib import Path

from ..paths import PROFILE_DIR, resolve_context


ADR_TEMPLATE = """\
# ADR {num} — {title}

- **Estado:** Accepted
- **Fecha:** {date}
- **Decisor:** {decisor}
- **Tags:** {tags}
- **Origen:** promoción manual sesión → proyecto vía `fairlead promote-decision`

---

## Decisión

{text}

## Notas

(añade contexto, motivación, consecuencias y supersedence chain según evolucione)
"""


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "decision"


def _next_adr_number(decisions_dir: Path) -> str:
    existing = sorted(decisions_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
    if not existing:
        return "0001"
    last = existing[-1].name[:4]
    return f"{int(last) + 1:04d}"


def run_promote_decision(text: str, title: str | None = None, tags: str = "") -> int:
    ctx = resolve_context()
    decisions_dir = ctx.memory_dir / "decisions"
    if not decisions_dir.is_dir():
        print(f"[promote-decision] no existe {decisions_dir} — corre `fairlead init` primero.", file=sys.stderr)
        return 1

    title = title or text.split(".")[0][:80]
    num = _next_adr_number(decisions_dir)
    slug = _slugify(title)
    fname = f"{num}-{slug}.md"
    out = decisions_dir / fname

    body = ADR_TEMPLATE.format(
        num=num,
        title=title,
        date=dt.date.today().isoformat(),
        decisor="Daniel Alonso Gómez",
        tags=tags or "(ninguno)",
        text=text,
    )
    out.write_text(body)
    print(f"[promote-decision] creado {out.relative_to(ctx.root)}")

    # Also store in DuckLake catalog for SQL-queryable access
    try:
        from ..ducklake import WikiForgeCatalog
        with WikiForgeCatalog() as cat:
            cat.store_adr(num, title, "Active", text, text, project_slug=ctx.dataset_id)
        print(f"[promote-decision] ADR {num} también registrado en DuckLake catalog.")
    except Exception as e:
        print(f"[promote-decision] DuckLake no disponible (no es error crítico): {e}", file=sys.stderr)

    print(f"[promote-decision] recomendación: añade una línea en {ctx.memory_dir / 'MEMORY.md'} apuntando a este ADR.")
    return 0


def run_promote_to_global(decision_id: str) -> int:
    """Copia un ADR del proyecto al perfil global (`~/.fairlead/profile/decisions/`)."""
    ctx = resolve_context()
    decisions_dir = ctx.memory_dir / "decisions"
    matches = list(decisions_dir.glob(f"{decision_id}*.md")) or list(decisions_dir.glob(f"*{decision_id}*.md"))
    if not matches:
        print(f"[promote-to-global] no se encontró ADR con id '{decision_id}' en {decisions_dir}", file=sys.stderr)
        return 1
    src = matches[0]

    target_dir = PROFILE_DIR / "decisions"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / src.name
    shutil.copy2(src, target)
    print(f"[promote-to-global] copiado {src.name} → {target}")
    print("[promote-to-global] revisa que la decisión aplica cross-proyectos antes de ratificar.")
    return 0


def run_demote(decision_id: str) -> int:
    """Mueve un ADR a `.memory/decisions/_demoted/` para mantener trazabilidad sin que cuente como Active."""
    ctx = resolve_context()
    decisions_dir = ctx.memory_dir / "decisions"
    matches = list(decisions_dir.glob(f"{decision_id}*.md"))
    if not matches:
        print(f"[demote] no se encontró ADR con id '{decision_id}' en {decisions_dir}", file=sys.stderr)
        return 1
    demoted_dir = decisions_dir / "_demoted"
    demoted_dir.mkdir(exist_ok=True)
    src = matches[0]
    target = demoted_dir / src.name
    src.rename(target)
    print(f"[demote] movido {src.name} → {target.relative_to(ctx.root)}")
    return 0
