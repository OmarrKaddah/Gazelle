# NER Evaluation Notes

Notes and observations for use when writing the final report.

---

## Datasets Used

### ANERcorp
- Standard Arabic NER benchmark in CoNLL format
- Labels: PER, ORG, LOC, MISC
- Source: news text (Al-Hayat newspaper)
- **Problem with this dataset for our pipeline:** ORG covers sports teams, political parties, media organizations — our LABEL_MAP forces all ORG → RegulatoryBody, which is wrong for general news. This makes CRF look artificially inflated and GLiNER look artificially bad. Results on ANERcorp are not a valid comparison between CRF and GLiNER.

### WikiANN Arabic
- HuggingFace dataset: `wikiann`, `ar`
- Size: 20k train / 10k validation / 10k test
- Labels: PER, ORG, LOC
- Source: Wikipedia articles (more formal text, closer to banking domain than news)
- Split used: full train → full test (no internal split; `--all` flag used for training)
- **Why better:** Wikipedia ORGs are mostly real institutions (governments, universities, companies), so ORG → RegulatoryBody mapping is less noisy. Comparison between CRF and GLiNER is more meaningful.

---

## Results

### CRF on WikiANN Test Set

Trained on: WikiANN train (20k sentences, ~10 sentences/chunk)
Tested on: WikiANN test (10k sentences)
Model: sklearn-crfsuite, lbfgs, c1=0.1, c2=0.1, max_iter=200

| Type           |   P    |   R    |   F1   | Support |
|----------------|--------|--------|--------|---------|
| Person         | 0.8029 | 0.7745 | 0.7885 |   3850  |
| RegulatoryBody | 0.8474 | 0.8004 | 0.8232 |   7409  |
| **micro avg**  | **0.8320** | **0.7915** | **0.8113** | **11259** |

### CRF on ANERcorp Test Set (for reference only — see caveats above)

| Type           |   P    |   R    |   F1   | Support |
|----------------|--------|--------|--------|---------|
| Person         | —      | —      | —      |    —    |
| RegulatoryBody | —      | —      | —      |    —    |
| Document       | —      | —      | —      |    —    |
| **micro avg**  | —      | —      | ~0.71  |    —    |

*Exact per-type numbers not recorded — overall micro F1 was ~0.71.*

### GLiNER on ANERcorp Test Set

| Type           |   F1   | Notes |
|----------------|--------|-------|
| micro avg      | 0.0432 | Not a real failure — GLiNER correctly refuses to label sports teams / media orgs as RegulatoryBody. The mapping is the problem, not the model. |

---

## Key Observations

### 1. CRF F1=0.81 on WikiANN Arabic is competitive
Published BERT-based transformer models on WikiANN Arabic typically achieve F1 ≈ 0.83–0.87.
Our classical CRF is within ~5 points of transformer models using only hand-crafted features + CAMeL Tools POS. This is a meaningful result for a classical model.

### 2. Precision > Recall on both entity types
The model is conservative: when it predicts an entity it is usually right, but it misses some.
For a banking compliance KG, this is the correct tradeoff — false positives in the knowledge graph are more harmful than missing a few entities. A spurious regulatory body cited in a compliance answer is worse than a missing one.

### 3. RegulatoryBody (F1=0.82) > Person (F1=0.79)
Expected behavior: ORG/LOC entities in Arabic are frequently preceded by strong trigger words (بنك, هيئة, جمهورية, مدينة) that the feature set captures directly. Person names in Arabic are morphologically ambiguous and rarely have a consistent preceding signal, making them harder to learn.

### 4. Distribution shift is the main remaining risk
WikiANN is Wikipedia text; the target domain is Central Bank of Egypt regulatory documents. Regulatory text has a distinct vocabulary: قرار, تعميم, مادة, بند, لائحة, ضوابط. The model may miss domain-specific entities that never appear in Wikipedia. This is addressed in the pipeline by the GLiNER-teacher → manual correction → CRF retraining loop on actual bank documents.

### 5. Why CRF + GLiNER rather than GLiNER alone
- GLiNER requires a Python environment with transformers >= 4.51
- CAMeL Tools (used by CRF) requires transformers == 4.43.4
- These are a hard pip conflict — they cannot coexist in one environment
- CRF is CPU-only, fast, and deployable offline (bank machine has no internet)
- GLiNER is used as a teacher model (knowledge distillation), not at inference time

### 6. The ANERcorp CRF vs GLiNER comparison is not valid
The inflated CRF score and near-zero GLiNER score on ANERcorp are both artifacts of the LABEL_MAP (all ORG → RegulatoryBody for news text). Do not cite these numbers in the paper without explaining the mapping issue.

---

## Feature Engineering Summary

Features used by the CRF (defined in `src/classical_NER/featureExtract.py`):

| Feature group       | Features |
|---------------------|----------|
| Word identity       | `word`, `w-1`, `w+1` |
| POS tags            | `pos`, `p-2`, `p-1`, `p+1`, `p+2` (CAMeL Tools calima-msa-r13) |
| Morphology          | `has_def_art`, `has_prep_clitic`, `stem` |
| Script              | `is_arabic_num`, `is_western_num`, `contains_latin`, `is_clause_ref`, `is_abbreviation` |
| Character n-grams   | all bigrams and trigrams (`c2_*`, `c3_*`) |
| Context triggers    | `is_org_trigger`, `in_money_trigger`, `in_month`, `prev_is_org_trigger` |
| Position            | `is_first` |

**Gazetteer lookup features were deliberately removed from training.** Direct entity name lookup in training features causes memorization — the model learns "if this word is in the entity list, label it" rather than learning linguistic context. Gazetteer is reserved for post-processing (override layer after CRF prediction), not as a training signal. Trigger features (بنك, هيئة, etc.) are kept because they are linguistic context clues, not entity names.

---

## Architecture Decision: Two-Environment Pipeline

```
classical_env (offline, CPU)         gliner_env (online, GPU optional)
├── CAMeL Tools                       ├── GLiNER (NAMAA gliner_arabic-v2.1)
├── sklearn-crfsuite                  └── transformers >= 4.51
└── transformers == 4.43.4
```

The two environments are the direct result of a hard pip conflict between transformers versions. This is not a design choice but a practical constraint. In production the CRF runs entirely in `classical_env`; GLiNER is only needed for the labeling/annotation phase when expanding training data.

---

## Pending Evaluations

- [ ] CRF on actual bank documents (Central Bank of Egypt corpus) — blocked until bank machine access
- [ ] GLiNER vs CRF on WikiANN (need to run GLiNER on wikiann_test chunks and compare)
- [ ] CRF retrained on GLiNER-corrected bank document annotations
- [ ] Relationship extraction evaluation (not yet implemented)

---

## Files Reference

| File | Role |
|------|------|
| `src/classical_NER/featureExtract.py` | Feature extraction + BIO alignment |
| `src/classical_NER/trainCrf.py` | CRF training (use `--all` for final model) |
| `src/classical_NER/runCrf.py` | CRF inference on new chunks |
| `src/classical_NER/evalNer.py` | Span-level evaluation (exact match, per-type F1) |
| `src/classical_NER/convertWikiann.py` | WikiANN → pipeline format converter |
| `src/classical_NER/convertAnercorp.py` | ANERcorp CoNLL → pipeline format converter |
| `runners/runGliner.py` | GLiNER extraction (use this, not `src/classical_NER/runGliner.py`) |
| `models/crf.pkl` | Trained CRF model |
| `annotations/gold_{docName}.json` | Gold spans for evaluation |
