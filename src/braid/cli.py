"""CLI `braid` — punto de entrada con subcomandos.

Comandos canónicos AGENTS.md sec. 7:
- init, index, ask, promote-decision, promote-to-global, demote, sync, eval, wiki build
"""
from __future__ import annotations

import argparse
import re
import sys

from .commands import ask as ask_cmd
from .commands import agent as agent_cmd
from .commands import index as index_cmd
from .commands import init as init_cmd
from .commands import promote as promote_cmd
from .commands import review as review_cmd
from .commands import sync as sync_cmd


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="braid", description="Repo-scoped context guidance for coding agents.")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    p_init = sub.add_parser("init", help="crear .braid/ + config + memoria + symlinks")
    p_init.add_argument("--dataset", help="override dataset_id (default = nombre del directorio)")
    p_init.add_argument("--force", action="store_true", help="sobrescribir si ya existe")

    p_idx = sub.add_parser("index", help="ingestar código + docs (incremental por defecto)")
    p_idx.add_argument("--rebuild", action="store_true", help="prune previo + reindex full")
    p_idx.add_argument("--include", action="append", default=[], help="glob extra (repetible)")

    p_ask = sub.add_parser("ask", help="consultar el KG/RAG del proyecto activo")
    p_ask.add_argument("query", help="pregunta en lenguaje natural")
    p_ask.add_argument("--type", default="CHUNKS", choices=["CHUNKS", "SUMMARIES", "GRAPH_COMPLETION", "RAG_COMPLETION", "INSIGHTS"], help="search type de cognee")
    p_ask.add_argument("--top-k", type=int, default=5)
    p_ask.add_argument("--global", dest="use_global", action="store_true", help="forzar consulta al perfil global")

    p_pd = sub.add_parser("promote-decision", help="sesión → proyecto: genera ADR en .braid/memory/decisions/")
    p_pd.add_argument("text", help="texto canónico de la decisión (1-3 frases)")
    p_pd.add_argument("--title", help="título corto (default: derivado del texto)")
    p_pd.add_argument("--tags", default="", help="tags coma-separados")

    p_pg = sub.add_parser("promote-to-global", help="proyecto → global: copia decisión al perfil global")
    p_pg.add_argument("decision_id", help="NNNN o slug del ADR a promover")

    p_dm = sub.add_parser("demote", help="revertir una promoción indebida")
    p_dm.add_argument("--id", required=True, help="NNNN del ADR a degradar")

    p_sy = sub.add_parser("sync", help="reescanear `.braid/kg/` y reconciliar (alias de index incremental)")

    # ADR 0010 — suite eval real (ya no stub)
    p_ev = sub.add_parser("eval", help="ejecuta suite de preguntas y mide grounding/alucinación (ADR 0010)")
    p_ev.add_argument("--questions", default=None, help="path al questions.json (default .braid/memory/eval/questions.json)")
    p_ev.add_argument("--top-k", type=int, default=None, help="override top_k del scoring")
    p_ev.add_argument("--no-save", dest="save", action="store_false", help="no escribir run JSON al filesystem")
    p_ev.add_argument("--per-question-timeout", type=float, default=None, help="timeout en segundos por search; default 90s")
    p_ev.add_argument("--rerank", action="store_true", help="(ADR 0012) reordena top-K via Cohere Rerank 4 Fast en OpenRouter; requiere OPENROUTER_API_KEY en secrets.env")

    p_rev = sub.add_parser("review", help="revisar código con 3 modelos AI en paralelo vía ZenMux")
    p_rev.add_argument("prompt", help="código o diff a revisar")
    p_rev.add_argument("--system-prompt", help="rol del revisor (default: revisor experto)")
    p_rev.add_argument("--models", help="modelos separados por coma (default: los 3 canónicos)")
    p_rev.add_argument("--temperature", type=float, default=0.0, help="temperatura (default 0.0)")
    p_rev.add_argument("--max-tokens", type=int, default=4096, help="máximo tokens de salida (default 4096)")

    p_wiki = sub.add_parser("wiki", help="generar wiki publicable desde DuckLake")
    p_wiki.add_argument("subcmd", choices=["build"])
    p_wiki.add_argument("--output", default=None, help="directorio de salida (default: .braid/wiki/)")

    p_mcp = sub.add_parser("mcp-serve", help="lanzar MCP server (stdio transport)")

    p_status = sub.add_parser("status", help="resumen del proyecto activo + perfil global")
    p_status.add_argument("--json", dest="as_json", action="store_true", help="emitir JSON estructurado")

    p_doc = sub.add_parser("doctor", help="diagnosticar instalación, contexto, agentes y estado Braid")
    p_doc.add_argument("--json", dest="as_json", action="store_true", help="emitir JSON estructurado")
    p_doc.add_argument("--fix", action="store_true", help="aplicar solo reparaciones locales seguras")

    p_ai = sub.add_parser("agent-init", help="aplicar/verificar/reparar integración Braid para agentes IA")
    p_ai.add_argument(
        "--agent",
        default="all",
        choices=["claude", "codex", "cursor", "copilot", "all"],
        help="agente a configurar (default: all)",
    )
    mode = p_ai.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="solo verificar drift; no escribe")
    mode.add_argument("--fix", action="store_true", help="normalizar configuraciones legacy")
    mode.add_argument("--remove", action="store_true", help="retirar solo bloques gestionados por Braid")
    p_ai.add_argument("--json", dest="as_json", action="store_true", help="emitir JSON estructurado")

    # ADR 0009 — auto-bootstrap RAG vía SessionStart hook
    p_css = sub.add_parser(
        "claude-session-start",
        help="(hook) reporta estado memoria del repo activo en <500ms · sin LLM",
    )
    p_css.add_argument("--json", dest="as_json", action="store_true", help="emitir JSON estructurado")

    p_ci = sub.add_parser(
        "claude-init",
        help="cablea hook SessionStart en <git_root>/.claude/settings.json (idempotente)",
    )
    p_ci.add_argument("--remove", action="store_true", help="quitar el hook (preserva el resto del JSON)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.cmd

    if cmd == "init":
        return init_cmd.run(dataset=args.dataset, force=args.force)
    if cmd == "index":
        return index_cmd.run(rebuild=args.rebuild, extra_globs=args.include)
    if cmd == "ask":
        return ask_cmd.run(query=args.query, search_type=args.type, top_k=args.top_k, use_global=args.use_global)
    if cmd == "promote-decision":
        return promote_cmd.run_promote_decision(text=args.text, title=args.title, tags=args.tags)
    if cmd == "promote-to-global":
        return promote_cmd.run_promote_to_global(decision_id=args.decision_id)
    if cmd == "demote":
        return promote_cmd.run_demote(decision_id=args.id)
    if cmd == "sync":
        return sync_cmd.run()
    if cmd == "status":
        from .commands import status as status_cmd
        return status_cmd.run(as_json=args.as_json)
    if cmd == "doctor":
        from .commands import doctor as doctor_cmd
        return doctor_cmd.run(as_json=args.as_json, fix=args.fix)
    if cmd == "agent-init":
        return agent_cmd.run(
            agent=args.agent,
            check=args.check,
            fix=args.fix,
            remove=args.remove,
            as_json=args.as_json,
        )
    if cmd == "claude-session-start":
        from .commands import claude as claude_cmd
        return claude_cmd.run_session_start(as_json=args.as_json)
    if cmd == "claude-init":
        from .commands import claude as claude_cmd
        return claude_cmd.run_init(remove=args.remove)
    if cmd == "eval":
        from .commands import eval as eval_cmd
        return eval_cmd.run(
            questions_path=args.questions,
            top_k=args.top_k,
            save=args.save,
            per_question_timeout=args.per_question_timeout,
            rerank=args.rerank,
        )
    if cmd == "wiki":
        from .commands import wiki as wiki_cmd
        return wiki_cmd.run(output_dir=args.output)
    if cmd == "mcp-serve":
        import asyncio
        from .mcp_server import main as mcp_main
        asyncio.run(mcp_main())
        return 0
    if cmd == "review":
        models = args.models.split(",") if args.models else None
        return review_cmd.run(
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            models=models,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )

    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


def _legacy_main(old_name: str, argv: list[str] | None = None) -> int:
    """Entry point for deprecated command names retained during migration."""
    print(
        f"\033[33mWarning:\033[0m `{old_name}` is deprecated. Use `braid` instead.",
        file=sys.stderr,
    )
    return main(argv)


def legacy_fairlead_main(argv: list[str] | None = None) -> int:
    return _legacy_main("fairlead", argv)


def legacy_wikiforge_main(argv: list[str] | None = None) -> int:
    return _legacy_main("wikiforge", argv)


if __name__ == "__main__":
    sys.exit(main())
