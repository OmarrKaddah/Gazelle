# Classical NER — Technical Reference

## What This Is

The classical NER module extracts named entities from Arabic banking and regulatory text (Central Bank of Egypt documents). It is a **hybrid pipeline**: GLiNER bootstraps annotations, human annotators correct them in Label Studio, and a CRF model trained on those corrections does final inference. The CRF is domain-adapted via a feature set built specifically for Arabic morphology and Egyptian regulatory language.

---

## Entity Ontology

Eleven entity types, defined in the Label Studio schema:

| Type | Arabic target | Examples |
|---|---|---|
| `Person` | individuals | رئيس مجلس الإدارة, أحمد عبد العال |
| `BankingInstitution` | licensed banks | البنك الأهلي المصري, بنك مصر |
| `RegulatoryBody` | supervisory orgs | البنك المركزي المصري, هيئة الرقابة المالية |
| `Law` | statutes | قانون رقم 88 لسنة 2003 |
| `Article` | law articles | المادة الثانية, المادة 27 |
| `License` | permits/authorizations | ترخيص تأسيس, ترخيص مزاولة النشاط |
| `Document` | regulatory instruments | قرار مجلس الإدارة, تعميم رقم |
| `FinancialInstrument` | products | شهادات الإيداع, أذون الخزانة |
| `RegulatoryRequirement` | obligations | متطلبات كفاية رأس المال, نسبة السيولة |
| `MonetaryAmount` | money values | 500 مليون جنيه, مليار دولار |
| `Date` | temporal expressions | 15 يناير 2024, الربع الأول |

---

## Pipeline Architecture

```
chunks/*.json
      │
      ▼
 runGliner.py          — GLiNER (NAMAA-Space/gliner_arabic-v2.1) initial extraction
      │                  threshold = 0.5, output: extractions/*_entities.json
      ▼
 convertToLabelStudio.py — formats extractions as Label Studio pre-labeled tasks
      │                    output: annotations/ls_import.json
      ▼
  Label Studio          — human annotators accept/correct/add/delete spans
      │                  output: annotations/corrected.json
      ▼
 buildGazetteer.py      — collects high-confidence entities (score ≥ 0.75)
      │                  into a normalized lookup table
      │                  output: gazetteer/gazetteer.json
      ▼
 featureExtract.py      — tokenizes + POS-tags + BIO-aligns + extracts features
      │                  output: training/train_data.json
      ▼
 trainCrf.py            — trains CRF on 80% split, evaluates on 20%
      │                  output: models/crf.pkl
      ▼
 runCrf.py              — inference on new chunks
                         output: extractions/crf/*_crf_entities.json
```

---

## Feature Engineering

Each token is represented by a feature dictionary. There are five feature groups.

### 1. Surface + Context
```
word       — the token itself
w-1, w+1  — left and right neighbors
is_first   — boolean, sentence-initial position
```

### 2. POS Tags
Provided by **CAMeL Tools** `DefaultTagger` backed by `MLEDisambiguator` (CALIMA-MSA-r13, a Maximum Likelihood Estimator trained on Penn Arabic Dependency Treebank). Accuracy on formal MSA is ~95–97%.
```
pos         — POS of current token
p-2, p-1   — POS of 2 and 1 tokens left
p+1, p+2   — POS of 1 and 2 tokens right
```

### 3. Morphological Features
Arabic-specific prefix stripping:
```
has_def_art      — token carries definite article "ال" (e.g. البنك)
has_prep_clitic  — token carries prep prefix (بال, لل, كال, وال, فال, ب, ل, ك, و, ف)
stem             — surface form with prefix and article stripped
```
Stripping is necessary because "البنك" and "بنك" and "للبنك" are the same lexeme. Without this, gazetteer and n-gram features miss morphological variants.

### 4. Script Features
```
is_arabic_num    — all Arabic-Indic digits (٠–٩)
is_western_num   — all ASCII digits (0–9)
contains_latin   — token mixes Latin characters (e.g. CBE, SWIFT)
is_clause_ref    — matches pattern like 88-2003 or 1-2-5 (law clause references)
is_abbreviation  — all-caps Latin 2–6 chars
```

### 5. Character N-grams
All bigrams and trigrams over the token surface form:
```
c2_بن, c2_نك, c3_بنك, ...
```
These capture morphological patterns the POS tagger may not surface — for example, the suffix "ية" strongly signals institutional names.

### 6. Trigger Features
```
is_org_trigger      — token is in {بنك, شركة, هيئة, وزارة, مؤسسة, صندوق, اتحاد, لجنة, إدارة, مجلس}
in_money_trigger    — token is in {جنيه, دولار, يورو, مليار, مليون, ألف, جنيهاً, دولاراً}
in_month            — token is an Arabic month name
prev_is_org_trigger — left neighbor is an org trigger
```

**Note on the gazetteer:** `loadGazetteer()` loads `gazetteer/gazetteer.json` and returns `gazSets`, but both `featureExtract.py` and `runCrf.py` discard it with `_`:

```python
_, orgTriggers, moneyTriggers, monthNames = loadGazetteer()
```

`tokenFeatures()` does not receive `gazSets` and does not emit `in_org_gaz` or `in_any_gaz`. The gazetteer is not part of the current feature set used during training or inference. The `gazFeatures()` function that uses it exists only in a parallel version of the file (`classical.txt`) and is not yet wired in.

---

## Sequence Labeling Schema

BIO tagging over tokens:

```
B-BankingInstitution   — first token of a BankingInstitution span
I-BankingInstitution   — continuation token
O                      — non-entity
```

Alignment is character-offset based: a span from the annotation `[start, end)` maps to all tokens whose `[tok.start, tok.end)` falls inside it. The first such token gets `B-`, the rest get `I-`.

---

## CRF Model

**Library:** `sklearn-crfsuite`  
**Algorithm:** L-BFGS with L1 + L2 regularization  
**Hyperparameters:**

| Parameter | Value | Role |
|---|---|---|
| `c1` | 0.1 | L1 penalty — drives sparse feature weights, removes irrelevant n-grams |
| `c2` | 0.1 | L2 penalty — prevents large weights on rare features |
| `max_iterations` | 200 | convergence budget |
| `all_possible_transitions` | True | allows the model to learn zero-weight transitions rather than ignoring unseen tag pairs |

**Why CRF over a neural model here:** The training set is small (human-corrected annotations over a specialized corpus). CRF with hand-crafted features generalizes better than a neural sequence model in this low-resource regime. Neural models need hundreds of annotated documents; CRF can work with dozens.

---

## Training Procedure

**Script:** `trainCrf.py`

1. Load `training/train_data.json` (sequences of `[feature_dict, BIO_label]` pairs)
2. Shuffle with `seed=42` and split 80/20 into train and test
3. Fit CRF on train
4. Evaluate on held-out test
5. Serialize to `models/crf.pkl`

Split is sequence-level (whole chunks), not token-level, so there is no token-level leakage between train and test.

---

## Evaluation Methodology

Two metrics are computed at evaluation time (`trainCrf.py → evaluate()`):

### Token Accuracy
```
correct_tokens / total_tokens
```
Measures per-token label agreement. This number is always high (typically >90%) because most tokens are `O` — treat it as a sanity check, not the primary metric.

### Span-level F1 (primary metric)
Computed via `seqeval.metrics.classification_report`. Seqeval implements the **CoNLL evaluation scheme**: a predicted span is correct only if both its **boundaries** and its **type** exactly match the gold span. Partial overlaps count as false positives and false negatives simultaneously.

For each entity type:

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * P * R / (P + R)
```

The report breaks this down per type plus micro-averaged overall.

**Why span-level F1 and not token accuracy:** A model that labels every token `O` gets very high token accuracy on sparse annotations. F1 over spans punishes boundary errors and type errors independently and is the standard NER evaluation metric (CoNLL 2003 benchmark uses exactly this).

---

## Expected Accuracy

These are **realistic targets** for this domain and training regime, not guarantees. Actual numbers depend on annotation volume and consistency.

| Entity Type | Expected F1 | Notes |
|---|---|---|
| `MonetaryAmount` | 0.85 – 0.92 | Highly regular surface pattern (digit + currency word). Script features alone get most of these. |
| `Date` | 0.82 – 0.90 | Month names + digit patterns are reliable. Relative dates ("الربع الأول") harder. |
| `BankingInstitution` | 0.75 – 0.85 | Gazetteer covers known banks; novel names rely on org triggers + context. |
| `RegulatoryBody` | 0.72 – 0.82 | Similar to BankingInstitution. هيئة / وزارة triggers help. |
| `Law` | 0.70 – 0.80 | "قانون رقم \d+" is regular; old law references without رقم are harder. |
| `Article` | 0.68 – 0.78 | "المادة" trigger is reliable; article number format varies. |
| `Document` | 0.60 – 0.72 | Diverse surface forms (قرار, تعميم, منشور) — context matters more than surface. |
| `Person` | 0.55 – 0.70 | Arabic person names have no capitalization signal. Context (titles, positions) is the main cue. |
| `RegulatoryRequirement` | 0.50 – 0.65 | Multi-word, semantically defined. Most likely the weakest class. |
| `FinancialInstrument` | 0.55 – 0.70 | Domain vocabulary; gazetteer coverage is key. |
| `License` | 0.58 – 0.70 | Sparse in corpus; few training examples expected. |
| **Micro average** | **~0.70 – 0.80** | Weighted by entity frequency; MonetaryAmount and Date dominate. |

Comparable Arabic NER systems on formal MSA (legal/financial domain) report F1 in the 0.68–0.82 range with similar training sizes. These targets are calibrated to that baseline.

---

## Limitations and Known Gaps

**No multi-word gazetteer lookup.** Current gazetteer matching is single-token. "البنك المركزي المصري" as a full phrase is not matched; only individual tokens like "البنك" trigger the `in_org_gaz` feature.

**No co-reference resolution.** "البنك" in sentence 3 that refers to "البنك الأهلي المصري" from sentence 1 is extracted as a separate, unlinked mention. This fragments entity coverage in the knowledge graph.

**No entity disambiguation.** "البنك المركزي", "البنك المركزي المصري", and "CBE" produce three separate nodes in Neo4j. Normalization is only applied inside the gazetteer, not across extracted spans.

**CRF score is always 1.0.** The `bioToSpans()` function in `runCrf.py` assigns `score=1.0` to all CRF spans unconditionally. CRF marginal probabilities are not currently extracted. This matters for the planned CRF + GLiNER fusion step where scores determine which prediction wins on conflict.

---

## Fusion with GLiNER (Planned)

The `extra.txt` design note describes a confidence-weighted merge:
- Both agree → high confidence span retained
- Only GLiNER fires → lower confidence, use as fallback
- Only CRF fires → lower confidence, prefer for domain-specific patterns
- Conflict on type → prefer GLiNER for unseen entity names, CRF for pattern-regular types (Date, MonetaryAmount, Law)

This requires CRF marginal probabilities — the `crf.predict_marginals()` method in sklearn-crfsuite returns per-token tag distributions, which can replace the hardcoded `score=1.0`.

---

## File Map

```
src/classical_NER/
  buildGazetteer.py     — builds gazetteer/gazetteer.json from extractions
  convertToLabelStudio.py — formats GLiNER output for Label Studio import
  featureExtract.py     — tokenization, POS tagging, BIO alignment, feature extraction
  trainCrf.py           — CRF training, 80/20 split, evaluation, serialization
  runCrf.py             — CRF inference on new chunks
  runGliner.py          — GLiNER batch inference (bootstrapping step)

artifacts/
  gazetteer/gazetteer.json     — normalized entity lookup table
  training/train_data.json     — feature sequences for CRF training
  models/crf.pkl               — serialized trained CRF
  annotations/corrected.json   — human-corrected Label Studio export
  extractions/crf/             — CRF entity output per document
  chunks/                      — chunked document input
```
