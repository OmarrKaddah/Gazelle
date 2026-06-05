# Classical NER Pipeline — Implementation Plan

Arabic regulatory NER for the CBE knowledge graph.
Two-component system: CRF (closed-set, predefined types) + NP chunker/discovery (open-set, new types).

---

## Overview

```
chunks/*.json
      │
      ├─── GLiNER (threshold 0.75) ──────────────────────► gazetteer.json
      │                                                          │
      ├─── Manual annotation correction (Label Studio) ────► corrected BIO data
      │                                                          │
      │         ┌────────────────────────────────────────────────┘
      │         ▼
      │    Feature extraction (CAMeL POS + gazetteer + char features)
      │         │
      │    CRF training (sklearn-crfsuite)
      │         │
      │    CRF model ──────────────────────────────────────► Entity extractions
      │         │                                            (predefined types)
      │         │
      │    NP Chunker (POS rules on all chunks)
      │         │
      │    Subtract CRF entities → residual spans
      │         │
      │    fastText embed + frequency filter (≥3x)
      │         │
      │    K-means clustering
      │         │
      │    Human review → new entity types
      │         │
      │    Expand ontology.py → retrain CRF
      │         │
      └────────►▼
           Final extractions → kgWriter.py → Neo4j
```

---

## Stage 0 — Environment & downloads

Do this BEFORE going to the bank. Everything must be pre-downloaded.

### Python packages to install

```bash
pip install camel-tools          # Arabic POS tagging + morphological analysis
pip install sklearn-crfsuite     # CRF model
pip install scikit-learn         # k-means, evaluation metrics
pip install fasttext             # load Arabic fastText vectors
pip install label-studio         # annotation UI (run locally)
pip install seqeval              # proper NER F1 evaluation (span-level)
pip install matplotlib           # cluster visualization
pip install pandas               # data wrangling
pip install tqdm                 # progress bars
pip install tabulate             # pretty-print evaluation tables
```

Everything else (gliner, transformers, torch, neo4j, numpy, dotenv) is already in requirements.txt.

### CAMeL Tools model data

CAMeL Tools requires downloading morphological databases separately after pip install:

```bash
camel_data -i morphology-db-msa-r13      # MSA morphological DB ~200MB
camel_data -i named-entity-recognition   # optional, for reference
```

If the bank has no internet, run these on your machine first. The data lands in `~/.camel_tools/`. Copy that entire folder to the bank machine.

### Arabic fastText vectors

Download the pre-trained Arabic vectors from fastText official:

- File: `cc.ar.300.bin`
- Size: ~2.4 GB
- Source: https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.ar.300.bin

Put it somewhere accessible, e.g. `models/cc.ar.300.bin`. Add this path to `.env`:

```env
FASTTEXT_AR_PATH=models/cc.ar.300.bin
```

### GLiNER Arabic model

Already in use (`NAMAA-Space/gliner_arabic-v2.1`). If not already cached locally, it will download from HuggingFace on first run. To pre-cache it:

```bash
python -c "from gliner import GLiNER; GLiNER.from_pretrained('NAMAA-Space/gliner_arabic-v2.1')"
```

The model cache lives in `~/.cache/huggingface/`. Copy this folder to the bank machine if no internet there.

### Label Studio (annotation tool)

```bash
pip install label-studio
label-studio start     # opens at http://localhost:8080
```

No internet needed after install. Runs fully locally.

---

## Stage 1 — Build GLiNER high-confidence gazetteer

**What:** Run GLiNER at high threshold (0.75) on all existing chunks. Keep only high-confidence extractions. Deduplicate per entity type. This becomes a lookup feature for the CRF — if a token appears in the gazetteer, the CRF knows it's a known entity surface form.

**Why not circular:** GLiNER and CRF are separate models. GLiNER fires first, its output feeds the CRF as a feature. The CRF learns to combine gazetteer hits with morphological evidence.

**Input:**
- `chunks/*.json` — all chunked documents

**Output:**
- `gazetteer/gazetteer.json` — structure:
```json
{
  "BankingInstitution": ["البنك المركزي المصري", "بنك مصر", ...],
  "Law": ["قانون رقم 88 لسنة 2003", "قانون البنك المركزي", ...],
  "RegulatoryBody": ["هيئة الرقابة المالية", ...],
  ...
}
```

**Expected time:** 15–30 minutes to run, 1–2 hours to code.

---

## Stage 2 — Manual annotation with Label Studio

**What:** Import GLiNER extractions as pre-annotations. Human corrects them: fix wrong labels, delete false positives, add missed entities. Goal is ~100 documents fully corrected per entity type.

**Input:**
- `extractions/*_entities.json` — GLiNER output, loaded as pre-annotations
- Raw chunk text from `chunks/*.json`

**Output:**
- Corrected annotation files exported from Label Studio in CONLL/JSON format
- Target: ~100 documents, minimum 50 examples per entity type

**Label Studio setup:**
1. Create a NER project
2. Upload chunk texts
3. Import GLiNER JSON as pre-annotations (Label Studio has an importer for this)
4. Annotators correct each chunk
5. Export in CONLL 2003 format or JSON spans

**Expected time:** 2–4 hours per annotator per 100 documents. This is the bottleneck of the whole pipeline — start this in parallel with coding.

**Priority entity types to annotate carefully (most important for the graph):**
- `Law`, `Article` — most structurally regular, easy to annotate
- `RegulatoryBody` — appears frequently, high impact on graph
- `BankingInstitution` — core entity in all relationships
- `RegulatoryRequirement` — hardest, most important
- `Date`, `MonetaryAmount` — easiest, GLiNER already does these well

---

## Stage 3 — Feature extraction and BIO conversion

**What:** For each annotated chunk, run CAMeL Tools POS tagger on every token. Extract per-token features. Convert span annotations to BIO sequence labels. This produces the (X, y) pairs that train the CRF.

**Input:**
- Corrected annotations from Stage 2
- `gazetteer/gazetteer.json` from Stage 1

**Output:**
- `crf_data/train.pkl` — list of (feature_sequence, label_sequence) pairs
- `crf_data/test.pkl` — held-out 20% for evaluation

**Feature set per token:**

| Feature | Description | Arabic-specific reason |
|---|---|---|
| `pos` | CAMeL POS tag (NN, JJ, VBD...) | Main signal for NP boundaries |
| `prefix2`, `prefix3` | First 2–3 characters | Arabic prefixes: ب، ل، و، ال |
| `suffix2`, `suffix3` | Last 2–3 characters | Case endings, feminine markers |
| `has_def_art` | Starts with ال | Definite nouns are often entities |
| `has_prep_clitic` | First char in ب ل ك ف | Preposition clitics mark boundaries |
| `is_arabic_num` | All chars in ٠١٢٣٤٥٦٧٨٩ | Strong Date/MonetaryAmount signal |
| `char_len` | Token length | Short tokens rarely entities |
| `in_gazetteer` | Token in any gazetteer entry | Direct hit from Stage 1 |
| `gazetteer_type` | Which type matched | Disambiguates overlapping entries |
| `root` | CAMeL morphological root | Arabic root-and-pattern signal |
| `-1:pos`, `+1:pos` | POS of prev/next token | Context window |
| `-1:word`, `+1:word` | Surface of prev/next token | Local context |
| `BOS`, `EOS` | Beginning/end of sequence | Boundary markers |

**Expected time:** 3–5 hours to code, 1–2 hours to run on 100 docs.

---

## Stage 4 — CRF training and evaluation

**What:** Train a CRF on the feature sequences from Stage 3. Evaluate per entity type using span-level F1. Compare against GLiNER baseline.

**Input:**
- `crf_data/train.pkl`
- `crf_data/test.pkl`

**Output:**
- `models/crf_model.pkl` — serialized trained CRF
- Evaluation table: precision, recall, F1 per entity type vs GLiNER baseline

**Training config:**
```python
import sklearn_crfsuite
crf = sklearn_crfsuite.CRF(
    algorithm='lbfgs',
    c1=0.1,          # L1 regularization
    c2=0.1,          # L2 regularization
    max_iterations=200,
    all_possible_transitions=True
)
```

**Expected evaluation targets** (based on similar Arabic legal NER work):
- `Date`, `MonetaryAmount`: F1 ~0.88–0.92 (structurally regular)
- `Law`, `Article`: F1 ~0.82–0.88
- `RegulatoryBody`, `BankingInstitution`: F1 ~0.78–0.85
- `RegulatoryRequirement`: F1 ~0.60–0.72 (hardest — conceptual, not surface-regular)

**Expected time:** Training takes 2–10 minutes. Coding + evaluation: 3–4 hours.

---

## Stage 5 — NP chunker on full corpus (open-set discovery)

**What:** Run CAMeL POS on ALL chunks (not just annotated ones). Apply NP grammar rules to extract every noun-phrase-shaped span. Subtract spans already found by the CRF. What remains are candidate new entity types.

**Input:**
- All `chunks/*.json` (entire corpus)
- CRF model from Stage 4 (to know what's already extracted)

**Output:**
- `discovery/residuals.json` — all residual NP spans with frequency counts:
```json
[
  {"span": "إجراءات الترخيص",  "count": 43, "chunk_ids": ["Chapter_1-c0003", ...]},
  {"span": "ستة أشهر",          "count": 28, "chunk_ids": [...]},
  ...
]
```

**NP chunking rule (applied to POS sequence):**
```
NP → (PREP?) (DET?) (ADJ|NUM)* (NN|NNP)+ (ADJ)*
```

Implemented as a simple regex over the POS tag sequence per sentence.

**Expected time:** 2–3 hours to code, 30–60 minutes to run on all 8 chapters. On 2000 docs: ~4–6 hours runtime.

---

## Stage 6 — fastText embedding + frequency filtering

**What:** Embed each residual span as a vector (average of fastText subword vectors for each token in the span). Filter out spans that appear fewer than 3 times — those are noise. Keep a deduplicated set with their vectors.

**Input:**
- `discovery/residuals.json`
- `models/cc.ar.300.bin` — Arabic fastText model

**Output:**
- `discovery/residuals_embedded.pkl` — (span, count, vector[300]) triples

**Why fastText and not transformers:** fastText uses subword n-grams, which handles Arabic morphological variation well (ترخيص vs. الترخيص vs. بالترخيص → same root, similar vector). It's classical, fast, and runs on CPU.

**Expected time:** 1–2 hours to code, 20–40 minutes to run (fastText is fast).

---

## Stage 7 — Clustering and human review

**What:** K-means cluster the embedded spans. For each cluster, print the top-20 most frequent spans. Human reviewer decides: is this a real entity type? What should it be called?

**Input:**
- `discovery/residuals_embedded.pkl`

**Output:**
- `discovery/clusters.json` — clusters with ranked spans
- Human-confirmed new entity types (expected 3–6)
- Names and definitions for each new type → added to `src/ontology.py`

**Clustering config:**
- Start with k=15 clusters, inspect, adjust
- Use silhouette score to pick k if unsure
- Visualize with UMAP/t-SNE to spot garbage clusters early

**Expected output per cluster (what you'll see):**
```
Cluster 04  (n=127 unique spans)
  إجراءات الترخيص          43x
  إجراءات الحصول على        28x
  متطلبات التسجيل           22x
  خطوات تقديم الطلب         18x
  إجراءات فتح الحساب        12x
  → Decision: new type = Procedure
```

**Expected time:** 2–3 hours to code, 1–2 hours human review of clusters.

---

## Stage 8 — Ontology expansion and CRF retraining

**What:** Add confirmed new types to `src/ontology.py`. Annotate those spans in the training set (quick — you already know which chunks contain them from Stage 5). Retrain the CRF with the expanded label set.

**Input:**
- Confirmed new types from Stage 7
- Existing `crf_data/train.pkl`
- Span locations from `discovery/residuals.json`

**Output:**
- Updated `src/ontology.py`
- `models/crf_model_v2.pkl` — CRF trained on expanded ontology
- Final evaluation table: GLiNER vs CRF v1 (11 types) vs CRF v2 (11 + new types)

**Expected time:** 1–2 hours.

---

## Stage 9 — Run on full 2000-document corpus

**What:** Apply the final CRF + GLiNER hybrid to all 2000 documents. Feed output to existing `kgWriter.py` pipeline.

**Input:**
- 2000 document chunks
- `models/crf_model_v2.pkl`
- `gazetteer/gazetteer.json`

**Output:**
- Entity extractions in `extractions/` format (same schema as GLiNER output)
- Relationship extractions via `llmExtract.py` (unchanged)
- Neo4j graph populated via `kgWriter.py`

**Runtime estimate:**
- CRF inference: ~500 docs/hour on CPU
- So 2000 docs: ~4 hours
- GLiNER pass for gazetteer refresh: ~1 hour on GPU

---

## Total time estimate

| Stage | Code | Run | Human work |
|---|---|---|---|
| 0 — Install & downloads | — | 2–3 hrs (downloads) | — |
| 1 — GLiNER gazetteer | 1–2 hrs | 30 min | — |
| 2 — Annotation | — | — | 4–8 hrs (bottleneck) |
| 3 — Feature extraction | 3–5 hrs | 1–2 hrs | — |
| 4 — CRF train + eval | 3–4 hrs | 10 min | — |
| 5 — NP chunker | 2–3 hrs | 1 hr | — |
| 6 — fastText embed | 1–2 hrs | 30 min | — |
| 7 — Clustering + review | 2–3 hrs | 30 min | 1–2 hrs |
| 8 — Retrain | 1–2 hrs | 10 min | — |
| 9 — Full corpus run | — | 4–6 hrs | — |
| **Total** | **~18–26 hrs coding** | **~10 hrs runtime** | **~6–10 hrs human** |

Realistic calendar: 4–5 working days for code + annotation done in parallel.

---

## Complete install checklist (do before going to bank)

### Python packages
```bash
pip install camel-tools
pip install sklearn-crfsuite
pip install scikit-learn
pip install fasttext
pip install label-studio
pip install seqeval
pip install matplotlib
pip install pandas
pip install tqdm
pip install tabulate
pip install umap-learn        # for cluster visualization
```

### CAMeL Tools model data
```bash
camel_data -i morphology-db-msa-r13
```
Data saved to `~/.camel_tools/` — copy this folder to the bank machine.

### Files to carry to the bank (on drive)
```
models/
  cc.ar.300.bin                   ← 2.4 GB fastText Arabic vectors
~/.camel_tools/                   ← ~200 MB CAMeL morphological DB
~/.cache/huggingface/             ← GLiNER + BGE-M3 cached weights
conda env or venv with all packages installed
  (use: conda-pack or pip download -r requirements.txt -d wheelhouse/)
```

### Offline pip install at the bank
If no internet at the bank:
```bash
# On your machine — download all wheels
pip download -r requirements.txt -d wheelhouse/
pip download camel-tools sklearn-crfsuite seqeval fasttext label-studio \
    matplotlib tqdm tabulate umap-learn -d wheelhouse/

# At the bank — install from local wheels
pip install --no-index --find-links=wheelhouse/ -r requirements.txt
pip install --no-index --find-links=wheelhouse/ camel-tools sklearn-crfsuite \
    seqeval fasttext label-studio matplotlib tqdm tabulate umap-learn
```

### Hardware requirements at the bank
- GPU: needed for GLiNER + LLM relationship extraction (Qwen 2.5 72B)
- CPU: CRF runs fine on CPU — no GPU needed for that part
- RAM: 16 GB minimum, 32 GB recommended (fastText .bin model is ~5 GB in memory)
- Disk: ~15 GB free (fastText 2.4 GB + models + documents + outputs)

---

## File structure after full pipeline

```
Gazelle/
├── gazetteer/
│   └── gazetteer.json              ← Stage 1 output
├── crf_data/
│   ├── train.pkl                   ← Stage 3 output
│   └── test.pkl
├── models/
│   ├── cc.ar.300.bin               ← pre-downloaded
│   ├── crf_model.pkl               ← Stage 4 output
│   └── crf_model_v2.pkl            ← Stage 8 output
├── discovery/
│   ├── residuals.json              ← Stage 5 output
│   ├── residuals_embedded.pkl      ← Stage 6 output
│   └── clusters.json               ← Stage 7 output
├── src/
│   ├── ontology.py                 ← expanded in Stage 8
│   ├── crfExtract.py               ← new: CRF inference
│   ├── crfFeatures.py              ← new: feature extraction
│   ├── gazeteerBuilder.py          ← new: Stage 1
│   ├── npChunker.py                ← new: Stage 5
│   └── discoveryCluster.py         ← new: Stages 6–7
└── runners/
    ├── runGazetteer.py             ← new runner
    ├── runCrfTrain.py              ← new runner
    └── runDiscovery.py             ← new runner
```
