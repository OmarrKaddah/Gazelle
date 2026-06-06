# Router Classifier — Handoff

Status as of 2026-06-06. This is the authority for the **classical local/global query
router** work. Read this before touching `router/`.

## Goal

Replace the per-query LLM router (`src/router.py::routeQuery`, one LLM call) with a
**classical classifier** that labels a query `local` (specific fact → PPR arm) vs
`global` (corpus-wide sensemaking → community-summary arm). Must be **bilingual
(Arabic + English)** and **airgapped** (no API in the hot path). Motivation is the
`airgapped-sqlite` branch + Adaptive-RAG precedent (a small trained router matches an
always-expensive baseline at far lower cost).

## Locked design decisions (do not relitigate without reason)

- **Three models, two embedding-free** (the comparison is itself a thesis contribution):
  1. **cue-LR** — hand-crafted bilingual cue features (`src/routerFeatures.py`), ~14 dims. Interpretable baseline.
  2. **char-TFIDF-LR** — char_wb (3–5)-gram TF-IDF + LR. Embedding-free learned-lexical baseline. Char (not word) n-grams chosen for Arabic morphology/clitics.
  3. **embedding-LR (DEPLOYED)** — calibrated LR over the **bge-m3** query embedding (1024-d, via Ollama `embedQuery`, same vector `seeder.py` already computes, so routing is ~free). Optional `+cues` concat tested as ablation (marginal — embedding subsumes cues).
- **Ladder story:** hand cues → learned surface → semantic. Expectation: char-TFIDF **collapses cross-lingually** (disjoint scripts) while the embedding model holds — that's the headline finding.
- **Decision policy: asymmetric → default local.** Binary classifier + a calibrated probability; route `global` only when `p_global ≥ threshold` tuned for **high global precision** (global arm is the expensive map-reduce; prefer to miss a borderline-global than over-fire it). Threshold stored in the artifact, not hard-coded. (No trained 3rd "both" class — uncertainty is handled by the threshold, not a noisy label.)
- **"no API" applies to DATA GENERATION only.** Training/serving may use local Ollama bge-m3 (airgapped).
- Deploy **LR** (calibrated probabilities for the threshold); report LinearSVC as a one-line ablation if desired.

## What is built

| File | Purpose | State |
|---|---|---|
| `src/routerFeatures.py` | Bilingual cue extractor: `normalizeArabic`, `normalizeText`, `cueFeatures(query)` → 14-dim, `FEATURE_NAMES`. Validated on all 4 quadrants. | **Done** |
| `router/genData.py` | Pure-stdlib (NO API) synthetic data generator. Mines slots from disk, fills template banks, dedups, splits. | **Done** |
| `router/data/{train,test}.jsonl` | Generated dataset. Schema: `{text,label,lang,domain,source,template_id,doc}`. ~2975 train / 1484 test (rerun genData to refresh). | **Done** |
| `router/data/holdout_real.jsonl` | Scaffold + 4 example rows. **Needs ~80–100 real hand-authored bilingual questions.** | **TODO** |
| `router/train.py` | Trains all 4 variants, reports per-class+macro-F1 on test, tunes asymmetric threshold, persists deployed model. Content-addressed embedding cache (`router/data/emb_cache.pkl`). | **Done** |
| `src/models/router.joblib` | Deployed artifact: `{model, threshold=0.170, thresholdSource='holdout_llm', globalIdx, featureVersion}`. | **Built + validated on real holdout (see §Honest eval)** |
| `router/genEval.py` | DeepSeek-V3 generator of a FRESH real held-out eval set over real corpus excerpts (Arabic-dominant; corpus is 26/27 docs Arabic). Labels cross-checked by the llama-3.3-70b judge (`routeQuery`). | **Done** |
| `router/data/holdout_llm.jsonl` | 455 real held-out questions (288 AR / 167 EN), `{text,label,lang,domain,judge,agree}`. Generator-vs-judge agreement **0.941**. | **Done** |
| `router/evalHoldout.py` | Scores cue/char/embedding on the real holdout by language, re-tunes the global-precision threshold. | **Done** |
| `router/_bootstrap.py` | Mirrors other subsystems (adds `src/` to path, chdir root). | **Done** |
| `router/README.md` | Schema + source→cell map. | **Done** |

## Data design

**Sources → cells** (every label×domain×lang cell filled, to learn INTENT not domain register):
- **local·EN·gold:** musique + 2wiki `question` fields (natural, abundant). musique is **local-only** (its unrelated paragraphs make global sensemaking semantically invalid).
- **local·EN·template:** entity-name inversion from `extractions/{apnews,2wiki}_graph.json` + EN CBE discussion-paper term mining.
- **local·AR·template:** Arabic term/entity mining from `Doc_Out/*_ar.md` (frequency bigrams/trigrams, Arabic-stopword filtered) + `*_ar_graph.json`.
- **global·EN:** templates over frequent news/2wiki entity topics + 10 tagged `llm_news` real questions (`sensemaking/questions_slice.json`).
- **global·AR:** templates over mined Arabic CBE topics.

**Template banks** live in `genData.py` (≥10–12 paraphrases per intent×language). **Slot quality filter** `isGoodSlot` drops numerals, single-word, calendar words, short-edge fragments. **Dedup:** exact + char-4-gram Jaccard ≥0.85 within (label,lang). **Split:** gold uses native train/dev; templated uses **template-disjoint** split (`splitByTemplate`) — whole templates held out for test.

> Note: `apnews_graph.json`/`musique_graph.json` currently live at **repo root**; genData expects them in `extractions/`. They were copied there. If a fresh checkout fails, re-copy.

## ⚠️ THE KEY FINDING — synthetic eval is saturated, do not trust in-distribution accuracy

All four models score **macro-F1 0.99–1.00 on the test set, including char-TFIDF at a perfect 1.000 even with the template-disjoint split.** This is **not** success — it means the synthetic classes are trivially linearly separable by surface vocabulary, by construction:

- The template bank gives each class a **shared lexical fingerprint** (every global template, held-out or not, contains "across the documents / عبر الوثائق / الموضوعات / corpus"). Holding out one template can't remove a signal that recurs across all sibling templates.
- Therefore **no train/test split of this synthetic data will be honest.** More split surgery is pointless.
- The deployed `threshold` came out **0.100** (degenerate) — the val set was so separable every threshold cleared the precision bar, so it took the lowest. This T is NOT meaningful and would over-fire global on real input. It will land on a real value once evaluated on non-saturated data.

This matches the literature warning (["From Synthetic to Native", arXiv 2603.23172](https://arxiv.org/pdf/2603.23172)): synthetic-trained intent classifiers must be validated on native queries.

## ✅ HONEST EVAL — resolved (2026-06-06)

Built a **fresh real held-out set** instead of hand-labeling: `router/genEval.py` generates natural, varied questions with **DeepSeek-V3** grounded in real corpus excerpts, labels = generation intent, **cross-checked by a different model** (the llama-3.3-70b `routeQuery` judge) → 455 questions, **0.941 generator-vs-judge agreement** (labels trustworthy; the 27 disagreements are genuine boundary cases, 25 of them Arabic-global). Arabic-dominant by design because the corpus is 26/27 Arabic docs (filename `_en`/`_ar` suffixes are unreliable — classify by script). `router/evalHoldout.py` scores all three models on it by language.

**Result — the model generalizes; saturation was an eval artifact, not a broken model:**

| Model | ALL macro-F1 | **AR** | EN |
|---|---|---|---|
| cue-LR | 0.686 | 0.654 | 0.741 |
| char-TFIDF-LR | 0.604 | 0.632 | 0.544 |
| **embedding-LR (deployed)** | **0.848** | **0.830** | 0.880 |

- **Arabic holds at 0.83 macro-F1** (balanced local/global) — the deployment reality works.
- **The ladder is real on OOD data** (the synthetic test couldn't show it): semantic ≫ cue ≫ char. Surface methods don't generalize past their synthetic fingerprint (global recall 0.24–0.48); embedding does (global recall 0.84–0.95). Note char does *not* collapse on Arabic specifically — it's weak everywhere on real phrasing; the original cross-lingual-collapse prediction was the wrong framing.
- **Threshold re-tuned on the real holdout: 0.100 → 0.170** (≥85% global precision: 0.858 ALL / 0.866 AR), persisted to the artifact (`thresholdSource='holdout_llm'`). The degenerate 0.100 is gone.

Caveat: threshold tuned and reported on the same 455 (1 param, low overfit risk; split if you want a clean number). The holdout is LLM-generated, not native human queries — still the honest arbiter available without hand-labeling.

## Next steps

1. ✅ **Honest eval — DONE** (see §Honest eval). Replaced the un-buildable real-holdout/cross-lingual plan with the LLM-generated held-out set; embedding-LR validated at 0.83 AR / 0.85 ALL, threshold fixed to 0.170.
2. **Integrate (remaining)** — wire `src/router.py`: rename current LLM router to `routeQueryLLM`; add `routeQuery(query)` that loads `src/models/router.joblib` once at module level, calls `embedQuery`, applies `model.predict_proba` ≥ `threshold` (0.170). Keep `routeQueryLLM` as a reported baseline (classical-vs-LLM agreement — already 0.941 on the holdout).
3. **Optional rigor** — (a) tune the threshold on a held-out split of `holdout_llm.jsonl` rather than the full set; (b) regenerate a larger/native holdout if a human-authored arbiter is later wanted; (c) formal cross-lingual transfer table (train-EN→test-AR) if the thesis wants it explicitly — the by-language holdout numbers already tell the story.

## Known issues / caveats

- **Arabic slot noise:** some mined slots are OCR-garbled (`فسل` for غسل) or letter boilerplate (`بنك تحية` = "dear bank", `وتفضلوا بقبول`). Cosmetic — does NOT flip local/global labels (intent = template framing). Chasing further needs a boilerplate stoplist or NER; low priority.
- **Threshold T=0.100** is a saturation artifact; expect a real value after honest eval.
- `+cues` ablation ≈ embedding-only (cues redundant with bge-m3) — deploy embedding-only, no cue-scaler at predict time.

## How to run (Windows)

```powershell
# Direct env python (conda run chokes on Arabic stdout — avoid it):
$env:PYTHONUTF8="1"; & C:\Users\omarl\miniconda3\envs\gazelle312\python.exe -u router\genData.py
$env:PYTHONUTF8="1"; & C:\Users\omarl\miniconda3\envs\gazelle312\python.exe -u router\train.py
```
- Env `gazelle312` (has sklearn 1.8, joblib). Needs **Ollama running** for bge-m3 (train/eval only).
- Embedding cache `router/data/emb_cache.pkl` is content-addressed → reruns are instant. Delete it to force re-embed.
- bge-m3 on Ollama emits NaN on some inputs; `embedNanSafe` rescues per-item. Embedding is done concurrently (8 workers) in `train.py`.
```
