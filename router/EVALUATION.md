# Router — Honest Evaluation

How the Gazelle query router (`local` vs `global`) was validated on **real, held-out,
Arabic-dominant** questions after the synthetic test set turned out to be saturated, and
the metrics that came out of it.

Companion docs: `router/HANDOFF.md` (full state), `router/README.md` (training-data schema).

---

## 1. Why a new evaluation was needed

The router is three models — `cue-LR`, `char-TFIDF-LR`, and the **deployed `embedding-LR`**
(calibrated logistic regression over bge-m3 query embeddings) — trained on a synthetic,
template-generated dataset (`router/genData.py`).

That synthetic test set was **useless for measuring real quality**:

- **Saturation.** All three models scored macro-F1 **0.99–1.00** on the synthetic test split —
  even char-TFIDF hit a perfect 1.000 with a template-disjoint split. The template bank gives
  each class a shared lexical fingerprint (every `global` template contains "across the documents /
  عبر الوثائق"), so the classes are trivially separable by surface vocabulary. No train/test split
  of that data can be honest.
- **The threshold was degenerate.** Tuned on the saturated val set, the global-precision threshold
  collapsed to **T = 0.100** — it would over-fire the expensive global arm on real input.
- **No real data existed to test against.** The only ~10 real `global` questions on disk
  (`sensemaking/questions_slice.json`) had **already leaked into training**. There were **zero**
  held-out real global questions and **zero** real Arabic questions of either class.

Hand-authoring a holdout was ruled out (no manual labeling). So we generated one.

---

## 2. Approach — an LLM-generated, dual-model-agreed holdout

`router/genEval.py` builds a fresh held-out set that the training data cannot have memorized:

1. **Real grounding.** Sample real corpus excerpts from `chunks/` — classified **by Arabic script
   ratio, not filename** (the `_en`/`_ar` suffixes are unreliable; the corpus is **26 / 27 docs
   Arabic**, so the set is Arabic-dominant by design, matching deployment reality).
2. **Natural generation.** **DeepSeek-V3** (via OpenRouter) writes 6 distinct questions per excerpt
   per intent, temperature 0.95, with explicit anti-template diversity constraints (vary structure,
   opening, length, register). The label is the generation intent.
3. **Independent label check.** Every question is re-classified by a **different** model — the
   llama-3.3-70b LLM router (`src/router.py::routeQuery`, `backend='openrouter'`). Agreement between
   the DeepSeek generator and the llama judge is the label-trust signal (no human in the loop).

`router/evalHoldout.py` then trains the three models on the synthetic train set and scores them on
this real holdout, **sliced by language**, and re-tunes the threshold on honest data.

Cost: ~$0.05 of OpenRouter usage. Reproduce:

```powershell
$env:PYTHONUTF8="1"
& C:\Users\omarl\miniconda3\envs\gazelle312\python.exe -u router\genEval.py      # needs OPENROUTER_API_KEY
& C:\Users\omarl\miniconda3\envs\gazelle312\python.exe -u router\evalHoldout.py   # needs Ollama (bge-m3)
```

---

## 3. The holdout — `router/data/holdout_llm.jsonl`

455 questions. Schema: `{text, label, lang, domain, judge, agree}`.

| Cell | local | global |
|------|------:|-------:|
| **Arabic** (central-bank regulatory) | 144 | 144 |
| **English** (news + 1 EN CBE doc) | 83 | 84 |

- **Arabic-dominant:** 288 AR / 167 EN (63% Arabic), reflecting the real corpus.
- **Generator-vs-judge agreement: 0.941** (428 / 455). The 27 disagreements are genuine boundary
  cases — 25 of them Arabic, 16 of those Arabic-global (the subtlest intent boundary).

---

## 4. Results

Models trained on the synthetic train set, scored on the real holdout (`macro-F1`, per language):

| Model | ALL | **Arabic** | English |
|-------|----:|----:|----:|
| cue-LR (hand cues) | 0.686 | 0.654 | 0.741 |
| char-TFIDF-LR (surface) | 0.604 | 0.632 | 0.544 |
| **embedding-LR (deployed)** | **0.848** | **0.830** | **0.880** |

Per-class detail for the deployed model (at the deployed threshold T = 0.170):

| Slice | global precision | global recall | local precision | local recall |
|-------|----:|----:|----:|----:|
| ALL | 0.858 | 0.798 | 0.811 | 0.868 |
| **Arabic** | 0.866 | 0.715 | 0.757 | 0.889 |
| English | 0.849 | 0.940 | 0.932 | 0.831 |

---

## 5. Threshold

The decision policy is **asymmetric → default local**: route `global` only when
`p_global ≥ threshold`, with the threshold tuned for **high global precision** (≥ 0.85), because the
global arm is the expensive map-reduce and over-firing is costly.

Re-tuned on the real holdout: **T = 0.100 (degenerate synthetic) → T = 0.170**, which delivers
global precision **0.858 ALL / 0.866 AR**. Persisted to the deployed artifact
(`src/models/router.joblib`, `thresholdSource='holdout_llm'`).

---

## 6. What the numbers mean

1. **The model generalizes.** The deployed embedding-LR reaches **0.83 macro-F1 on real Arabic**
   questions (balanced local/global) and 0.85 overall. The 0.99-everywhere synthetic score was an
   eval artifact; the model itself is sound on out-of-distribution, native-style queries.
2. **The model ladder is real on OOD data** — what the saturated synthetic test could never show:
   **semantic (0.85) ≫ hand cues (0.69) ≫ surface char (0.60)**. The surface methods do not
   generalize past their synthetic fingerprint (global recall craters to 0.24–0.48); the embedding
   model holds (global recall 0.72–0.94).
3. **Framing correction.** The original hypothesis was that char-TFIDF would *collapse cross-lingually
   on Arabic specifically* (disjoint script). It doesn't — char is weak **everywhere** on real
   phrasing (EN 0.544 is actually its worst slice). The honest thesis claim is **"surface methods
   don't generalize to native queries,"** not "char collapses on Arabic."

---

## 7. Caveats

- **Threshold tuned and reported on the same 455 rows.** One parameter, low overfit risk; split the
  holdout if a perfectly clean number is wanted.
- **LLM-generated, not native-human.** This is the honest arbiter available without hand-labeling;
  DeepSeek generates and llama judges, so generator/judge blind spots are decorrelated, but a
  human-authored native holdout would be stronger still.
- **English regulatory grounding is thin** — only one EN CBE doc exists (`antimoneylaunderinglaw.json`);
  the EN side leans on news. This matches the corpus, which is overwhelmingly Arabic.
