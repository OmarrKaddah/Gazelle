# Global-arm benchmark (BenchmarkQED on AP News)

End-to-end evaluation of Gazelle's **global arm** (GraphRAG-style community-summary
map-reduce) against a **naive vector-RAG baseline**, using Microsoft's
[BenchmarkQED](https://github.com/microsoft/benchmark-qed) (AutoQ query synthesis +
AutoE LLM-judge win-rates) on the open-licensed **AP News** corpus. This is the
global analogue of the MuSiQue/2Wiki harness in `musique/`.

Why this protocol: community-summary sensemaking has no gold answers, so the
canonical, comparable-to-published test is LLM-judge win-rate (comprehensiveness /
diversity / empowerment / relevance) vs naive RAG — reproducing the GraphRAG paper's
direction. See `docs/GLOBAL_PLAN.md` Stage 0 and the project TODO #2.

## Two environments

- **Main env** — our pipeline (Neo4j, Ollama, OpenRouter). Runs everything in `src/`,
  `runners/`, and this dir's `loadApNews.py` / `baseline.py` / `answerSystems.py`.
- **`.venv-qed`** — isolated venv with `benchmark-qed` (pulls `graphrag`, heavy/pinned;
  kept out of the main env). Runs only AutoQ + AutoE. Decoupled via answer files.

```
.venv-qed/Scripts/python.exe -m pip install benchmark-qed   # already done
```

## Prerequisites

Services up: **Neo4j**, **Ollama** (bge-m3 embed), and `OPENROUTER_API_KEY` set (Route 2
extraction + summaries + answers). A judge key for AutoE: `OPENAI_API_KEY` (faithful
default = `gpt-4.1`), or point the judge at OpenRouter (see step 7).

## Pipeline (run from repo root)

```bash
# 0. Corpus — same raw AP News articles feed both our loader and AutoQ.
.venv-qed/Scripts/benchmark-qed.exe data download AP_news sensemaking/data/ap_news

# 1. Chunks  (LIMIT=50 in loadApNews.py for the slice; set None for full 1,397)
python sensemaking/loadApNews.py

# 2. Route 2 graph  — graphBuild BEFORE embed: embed only SETs vectors on existing
#    Chunk nodes, and graphBuild is what creates them. (Differs from the MuSiQue
#    runbook, which is PPR-only and never needs chunk vectors.)
python runners/runGraphExtract.py apnews        # PAID (OpenRouter LLM extraction)
python runners/runGraphBuild.py apnews          # Document + Chunk + Entity + RELATED
python runners/runEmbed.py apnews               # chunk_embedding vectors (baseline needs these)
python runners/runEntityEmbed.py                # entity embeddings

# 3. Communities + summaries (the global arm's index)
python graphTraversal/runSynonyms.py apnews 0.85
python graphTraversal/runCommunities.py apnews  # Leiden -> (:Community) skeleton
python runners/runCommunitySummary.py apnews    # Stage 3 reports onto the nodes (PAID)

# 4. Questions  (AutoQ — global classes; writes questions JSON under the output dir)
.venv-qed/Scripts/benchmark-qed.exe autoq sensemaking/config/autoq <out> --generation-type data_global
.venv-qed/Scripts/benchmark-qed.exe autoq sensemaking/config/autoq <out> --generation-type activity_global

# 5. Answers — run both systems over the questions -> two answer files (PAID)
python sensemaking/answerSystems.py <out>/questions.json apnews

# 6. Judge — pairwise win-rates -> table
.venv-qed/Scripts/benchmark-qed.exe autoe pairwise-scores sensemaking/config/pairwise.json \
    sensemaking/eval_results/pairwise.json
```

## AutoQ config (step 4)

`benchmark-qed` scaffolds a correct config interactively — generate it once, then point
its `input.dataset_path` at `sensemaking/data/ap_news/raw_data` and its `llm_config` at
your model:

```bash
.venv-qed/Scripts/benchmark-qed.exe init      # writes a config scaffold + .env
```

Key fields: `input.dataset_path` = the downloaded `raw_data` dir, `input.input_type` =
`json`, `input.text_column` = `body_nitf`; `question.num_questions` small (e.g. 10) for
the slice.

## Judge backend (step 6)

`sensemaking/config/pairwise.json` defaults to OpenAI `gpt-4.1` (the paper's judge;
`api_key` is read from `OPENAI_API_KEY`). To judge via OpenRouter instead, set in
`llm_config`: `"init_args": {"base_url": "https://openrouter.ai/api/v1"}`,
`"api_key": "<OPENROUTER_API_KEY>"`, and `"model"` to an OpenRouter model id.

The comparison spec pits `global` (our arm) against the `vector` base; AutoE runs
`trials` counterbalanced LLM judgments per question per criterion and reports win-rates.
Success = the table is produced and `global` wins comprehensiveness/diversity (the
published direction); the absolute win-rate is the result.

## Slice first

Everything is gated on a small slice (`LIMIT=50` articles, ~10 questions) to validate
plumbing and cost before the full 1,397-article run. Paid stages: graph extraction,
community summaries, answer generation, and AutoE judging.
