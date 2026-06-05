# ADR 0010 — Suite `braid eval` (entregable formal Fase 2)

- **Estado:** Active
- **Fecha:** 2026-05-09
- **Decisor:** Daniel Alonso Gómez
- **Tags:** eval,fase-2,quality-gate,baseline
- **Origen:** sec. 10 Fase 2 AGENTS.md exige *"suite `braid eval` con 10-20 preguntas por repo activo, baseline de calidad medido y registrado"*. Esta entrega convierte el stub `braid eval` en un comando operativo.

---

## Contexto

Fase 0 cerró con `validate_phase0.py` ad-hoc (PASS 4/5). Esa pieza es local al repo de prueba y no es portable a cualquier repo gobernado por Braid. La sec. 7 de AGENTS.md prevé un `braid eval` canónico para que cualquier repo pueda medir grounding y alucinación con un único comando.

Sin un eval estandarizado:

1. No hay forma objetiva de detectar regresiones en cambios al stack.
2. Los síntomas de migración (sec. 11) requieren métricas — sin eval, son observación informal.
3. La promesa A del proyecto (*"% de respuestas correctas sin abrir archivos"*) no es medible.

## Decisión

Se introduce el comando `braid eval` con la siguiente arquitectura, gobernada por *"el corpus de preguntas vive en el repo, las respuestas vivien en el grafo, el scoring es declarativo en JSON"*:

### 1. Layout

```
<repo>/.memory/eval/
├── questions.json         # corpus de preguntas con ground truth (versionado)
└── runs/
    └── <ISO-timestamp>.json   # output de cada ejecución (no versionado salvo baseline)
```

### 2. Formato de `questions.json`

```json
{
  "version": 1,
  "dataset_id": "Braid",
  "scoring": {
    "match": "substring",
    "search_types": ["CHUNKS", "SUMMARIES"],
    "top_k": 10,
    "exact_top_1_bonus": 0.0
  },
  "questions": [
    {
      "id": "Q01",
      "kind": "CONTAINS",
      "query": "¿Qué hace el comando 'braid claude-session-start'?",
      "expected_any_of": [
        "claude.py",
        "claude-session-start",
        "ADR 0009"
      ],
      "expected_top_1": ["src/braid/commands/claude.py"],
      "notes": "Q sobre símbolo nuevo del CLI."
    }
  ]
}
```

**Reglas de campo:**

- `expected_any_of`: lista de substrings; **al menos uno** debe aparecer en el top-K combinado de los `search_types` para sumar 0.5.
- `expected_top_1`: lista de substrings; **al menos uno** debe aparecer en el top-1 (el primer chunk devuelto) para sumar 0.5 adicional.
- Score por pregunta = 0.0 / 0.5 / 1.0 (igual que Fase 0).
- Score total normalizado a 10 si hay 10 preguntas (5 → 5, 20 → 20, etc.).

### 3. Ejecución

```bash
braid eval [--questions FILE] [--top-k N] [--no-save]
```

- Lee `questions.json` (default `.memory/eval/questions.json`).
- Por cada pregunta:
  - Llama `cognee.search(query_type=CHUNKS, query_text=Q.query, datasets=[ds])`.
  - Llama `cognee.search(query_type=SUMMARIES, ...)` si está en `search_types`.
  - Concatena los textos del top-K, scoring por substring contra `expected_any_of` / `expected_top_1`.
- Imprime tabla por pregunta + total + recall@1 + recall@K.
- Guarda run en `.memory/eval/runs/<ISO-timestamp>.json` (a menos que `--no-save`).

### 4. Tipo de salida JSON del run

```json
{
  "timestamp": "2026-05-09T...",
  "dataset_id": "Braid",
  "stack": { "llm": "kimi-k2.6:cloud", "embedder": "bge-m3", ... },
  "questions": [
    {
      "id": "Q01",
      "score": 1.0,
      "rationale": "expected_any_of matched: claude.py (top-1)",
      "top_1_path": "[FILE kind=code path=src/braid/commands/claude.py]",
      "search_results_count": { "CHUNKS": 5, "SUMMARIES": 5 }
    }
  ],
  "total": 9.5,
  "max": 10.0,
  "pct": 95.0,
  "recall_at_1": 0.7,
  "recall_at_k": 0.95
}
```

### 5. Criterio de salida AGENTS.md sec. 10 Fase 2

> *"baseline de calidad medido y registrado"*

Se cumple ejecutando `braid eval` una vez tras la implementación, comprometiendo el primer run en `.memory/eval/runs/baseline.json` (o tag relacionado).

## Alternativas consideradas

| Alternativa | Por qué descartada |
|---|---|
| Reusar `validate_phase0.py` | Ad-hoc, dependiente del repo de prueba, no portable, scoring inline en Python. |
| Usar `RAGAS` o `DeepEval` | Sobre-ingeniería para 10 preguntas; introduce nueva dep + LLM judge (coste y privacidad). Se reconsidera en sec. 11.6 (Langfuse) si llegan ≥5 flujos. |
| Scoring vía LLM judge | Requiere LLM extra → coste + latencia. Sustring matching es objetivo y reproducible. |
| Preguntas en Markdown | JSON parseable es más estricto y permite versionar el formato. Markdown + frontmatter sería viable pero más fragil. |

## Consecuencias

### Positivas

- Cualquier repo gobernado por Braid puede medir su calidad RAG con un comando.
- Cada commit puede correr `braid eval` como CI gate (futuro — esta ADR no lo activa).
- Los síntomas sec. 11.4 (reranker) y sec. 11.10 (calidad insuficiente) ahora son verificables con `braid eval`, no estimación.

### Negativas

- Las preguntas requieren mantenimiento — si el repo evoluciona y cambian paths, hay que actualizar `expected_*`.
- Substring matching es laxo (puede pasar por casualidad). Mitigación: combinaciones de substrings específicas (p.ej. `"src/braid/commands/claude.py"` es más estricto que `"claude"`).

### Neutras

- El comando `braid eval` deja de ser stub; el contrato de sec. 7 AGENTS.md se cumple.
- `~/.braid/profile/` no requiere cambios.

## Verificación

1. `braid eval --help` muestra opciones.
2. Ejecución con `questions.json` válido: imprime tabla por pregunta + JSON con `total/max/pct/recall_at_1/recall_at_k`.
3. Run guardado en `.memory/eval/runs/` con timestamp ISO.
4. Run con `--no-save` no escribe filesystem.
5. Run con `questions.json` ausente: error mensaje útil indicando `braid init` o ruta esperada.

## Migración / rollback

- Trivial: si `braid eval` regresa, sustituir el archivo `commands/eval.py` por el stub original.
- Las preguntas son data, no código — versionables como cualquier ADR.

## Referencias

- AGENTS.md sec. 7 (CLI canónico — esta ADR convierte stub en comando real).
- AGENTS.md sec. 10 Fase 2 (criterio de salida).
- AGENTS.md sec. 11.4 (síntoma reranker — `braid eval` lo verifica numéricamente).
- AGENTS.md sec. 11.10 (síntoma calidad LLM insuficiente — idem).
- ADR 0009 (auto-bootstrap RAG — `eval` se ejecuta sobre el dataset poblado por `index/sync`).
- Plan 0001-fase-0-bootstrap-questions.md (5 preguntas Fase 0; `eval` generaliza ese patrón).
