"""`wikiforge eval`: ejecuta la suite de preguntas declarada en `.memory/eval/questions.json`.

ADR 0010. Scoring por substring + recall@1 / recall@K. Resultado JSON guardado en
`.memory/eval/runs/<ISO>.json`.

Robustez (post-review): validación temprana de questions.json, captura de OSError en
escritura de run, captura de JSONDecodeError, _extract_text defensivo ante listas/None,
timeout por pregunta opcional para evitar bloqueos por cognee colgado.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..paths import resolve_context
from ..runner import run_search


DEFAULT_QUESTIONS = ".memory/eval/questions.json"
RUNS_SUBDIR = ".memory/eval/runs"
DEFAULT_TOP_K = 10
DEFAULT_PER_QUESTION_TIMEOUT = 90.0
DEFAULT_TOP_1_BONUS = 0.5

# Header inyectado por annotate_file() en runner.py — lo extraemos para el run JSON
_FILE_HEADER_RE = re.compile(r"\[FILE\s+kind=\S+\s+path=\S+\]")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _extract_text(item: Any) -> str:
    """Cognee devuelve dicts con 'text' u objetos con .text. Defensivo ante None / list."""
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, list):
        return " \n ".join(_extract_text(x) for x in item)
    if isinstance(item, dict):
        for key in ("text", "content", "description", "summary"):
            v = item.get(key)
            if isinstance(v, str):
                return v
        try:
            return json.dumps(item, ensure_ascii=False)
        except (TypeError, ValueError):
            return repr(item)
    for attr in ("text", "content", "description", "summary"):
        v = getattr(item, attr, None)
        if isinstance(v, str):
            return v
    return str(item)


def _extract_top1_path(top_1_text: str) -> str | None:
    """Devuelve el header `[FILE kind=... path=...]` si está presente, None si no."""
    m = _FILE_HEADER_RE.search(top_1_text or "")
    return m.group(0) if m else None


def _validate_suite(suite: dict, qp: Path) -> list[dict]:
    """Valida formato del questions.json. Lanza ValueError con mensaje claro si rompe."""
    if not isinstance(suite, dict):
        raise ValueError(f"{qp}: el contenido raíz debe ser un objeto JSON")
    qs = suite.get("questions")
    if not isinstance(qs, list) or not qs:
        raise ValueError(f"{qp}: 'questions' debe ser un array no vacío")
    for i, q in enumerate(qs):
        if not isinstance(q, dict):
            raise ValueError(f"{qp}: questions[{i}] no es un objeto")
        qid = q.get("id")
        if not isinstance(qid, (str, int)) or qid == "":
            raise ValueError(f"{qp}: questions[{i}].id debe ser str/int no vacío")
        if not isinstance(q.get("query"), str) or not q["query"].strip():
            raise ValueError(f"{qp}: questions[{i}] (id={qid}) sin 'query' válido")
    return qs


def _score_question(
    q: dict,
    results_by_type: dict[str, list[Any]],
    primary_search_type: str,
    top_1_bonus: float,
) -> dict:
    """Aplica la regla de scoring 0/0.5/1.0 declarada en ADR 0010."""
    expected_any = q.get("expected_any_of") or []
    expected_top_1 = q.get("expected_top_1") or []

    primary = results_by_type.get(primary_search_type) or []
    top_1_text = _extract_text(primary[0]) if primary else ""
    top_1_path = _extract_top1_path(top_1_text)

    # Texto combinado de TODOS los search_types (top-K) → para expected_any_of
    combined_corpus = " \n ".join(
        _extract_text(item)
        for items in results_by_type.values()
        for item in items
    )

    score = 0.0
    rationale_parts: list[str] = []

    matched_any = [s for s in expected_any if s and s in combined_corpus]
    if matched_any:
        score += 0.5
        rationale_parts.append(f"any_of matched: {matched_any[:3]}")
    elif expected_any:
        rationale_parts.append("any_of: no match in top-K")

    matched_top1 = [s for s in expected_top_1 if s and s in top_1_text]
    if matched_top1:
        score += float(top_1_bonus)
        rationale_parts.append(f"top_1 matched: {matched_top1[:3]}")
    elif expected_top_1:
        rationale_parts.append("top_1: no match")

    return {
        "id": str(q.get("id", "?")),
        "kind": q.get("kind", "?"),
        "score": round(score, 3),
        "rationale": "; ".join(rationale_parts),
        "top_1_path": top_1_path,
        "search_results_count": {st: len(items) for st, items in results_by_type.items()},
    }


def _print_table(per_q: list[dict], totals: dict) -> None:
    print()
    print(f"{'ID':<6} {'KIND':<11} {'SCORE':<6} RATIONALE")
    print("-" * 80)
    for r in per_q:
        print(f"{str(r['id']):<6} {r['kind']:<11} {r['score']:<6} {r['rationale']}")
    print("-" * 80)
    print(
        f"TOTAL: {totals['total']:.1f}/{totals['max']:.1f}  "
        f"({totals['pct']:.1f}%)  "
        f"recall@1={totals['recall_at_1']:.2f}  "
        f"recall@K={totals['recall_at_k']:.2f}"
    )


def _save_run(root: Path, run: dict) -> Path | None:
    """Guarda el run; si el filesystem rechaza, devuelve None y se imprime fallback."""
    try:
        runs_dir = root / RUNS_SUBDIR
        runs_dir.mkdir(parents=True, exist_ok=True)
        out = runs_dir / f"{run['timestamp']}.json"
        out.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
        return out
    except OSError as e:
        print(f"[wikiforge eval] no se pudo guardar el run en disco: {e}", file=sys.stderr)
        print("[wikiforge eval] dump del run a stdout para no perder datos:", file=sys.stderr)
        sys.stdout.write(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
        return None


def _search_with_timeout(query: str, dataset_id: str, search_type: str, top_k: int, timeout_s: float) -> list[Any]:
    """Llama run_search con timeout; un cognee colgado no bloquea las otras preguntas."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(run_search, query, dataset_id, search_type=search_type, top_k=top_k)
        try:
            items = fut.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            print(f"    ! search {search_type} timeout tras {timeout_s:.0f}s", file=sys.stderr)
            return []
        except Exception as e:  # cognee internal exception → degraded silent fail
            print(f"    ! search {search_type} falló: {type(e).__name__}: {e}", file=sys.stderr)
            return []
    if items is None:
        return []
    if not isinstance(items, list):
        try:
            items = list(items)
        except TypeError:
            items = [items]
    return items[:top_k]


def run(
    questions_path: str | None = None,
    top_k: int | None = None,
    save: bool = True,
    per_question_timeout: float | None = None,
) -> int:
    ctx = resolve_context()
    qp = Path(questions_path) if questions_path else (ctx.root / DEFAULT_QUESTIONS)
    if not qp.is_file():
        print(
            f"[wikiforge eval] no encuentro questions en {qp}\n"
            "Crea `.memory/eval/questions.json` (ver ADR 0010 para formato).",
            file=sys.stderr,
        )
        return 1

    try:
        suite = json.loads(qp.read_text())
    except json.JSONDecodeError as e:
        print(f"[wikiforge eval] {qp} no es JSON válido: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"[wikiforge eval] no se pudo leer {qp}: {e}", file=sys.stderr)
        return 1

    try:
        questions = _validate_suite(suite, qp)
    except ValueError as e:
        print(f"[wikiforge eval] {e}", file=sys.stderr)
        return 1

    scoring = suite.get("scoring") if isinstance(suite.get("scoring"), dict) else {}
    search_types = scoring.get("search_types") or ["CHUNKS"]
    if not isinstance(search_types, list) or not search_types:
        search_types = ["CHUNKS"]
    effective_top_k = int(top_k or scoring.get("top_k") or DEFAULT_TOP_K)
    top_1_bonus = float(scoring.get("exact_top_1_bonus", DEFAULT_TOP_1_BONUS))
    timeout_s = float(per_question_timeout or DEFAULT_PER_QUESTION_TIMEOUT)
    dataset_id = suite.get("dataset_id") or ctx.dataset_id
    primary_st = search_types[0]

    print(
        f"[wikiforge eval] dataset={dataset_id} root={ctx.root} "
        f"questions={len(questions)} search_types={search_types} top_k={effective_top_k} "
        f"timeout={timeout_s:.0f}s"
    )

    per_q: list[dict] = []
    started = time.time()
    for q in questions:
        qid = str(q.get("id", "?"))
        print(f"  … {qid:<6} {q.get('kind','?'):<11} {q['query'][:80]}")
        results_by_type: dict[str, list[Any]] = {}
        for st in search_types:
            results_by_type[st] = _search_with_timeout(
                q["query"], dataset_id, st, effective_top_k, timeout_s
            )
        per_q.append(_score_question(q, results_by_type, primary_search_type=primary_st, top_1_bonus=top_1_bonus))

    elapsed = time.time() - started
    total = sum(r["score"] for r in per_q)
    max_score = float(len(per_q))
    n_top_1 = sum(1 for r in per_q if r["score"] >= 1.0)
    n_any = sum(1 for r in per_q if r["score"] >= 0.5)

    totals = {
        "total": round(total, 3),
        "max": max_score,
        "pct": round((total / max_score * 100.0) if max_score else 0.0, 2),
        "recall_at_1": round((n_top_1 / max_score) if max_score else 0.0, 4),
        "recall_at_k": round((n_any / max_score) if max_score else 0.0, 4),
    }

    _print_table(per_q, totals)

    run_doc = {
        "timestamp": _now_iso(),
        "dataset_id": dataset_id,
        "stack": {
            "llm": (ctx.kgconfig.get("llm") if ctx.kgconfig else None),
            "embedder": (ctx.kgconfig.get("embedder") if ctx.kgconfig else None),
            "graph_backend": (ctx.kgconfig.get("graph_backend") if ctx.kgconfig else None),
            "vector_backend": (ctx.kgconfig.get("vector_backend") if ctx.kgconfig else None),
        },
        "questions": per_q,
        **totals,
        "meta": {
            "root": str(ctx.root),
            "questions_path": str(qp),
            "search_types": search_types,
            "top_k": effective_top_k,
            "elapsed_seconds": round(elapsed, 1),
            "questions_suite_version": suite.get("version", 1),
        },
    }

    if save:
        out = _save_run(ctx.root, run_doc)
        if out is not None:
            print(f"\n[wikiforge eval] run guardado en {out}")
    else:
        print("\n[wikiforge eval] --no-save: run NO guardado")

    return 0
