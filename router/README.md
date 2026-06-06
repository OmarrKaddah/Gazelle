# Router Training Data

Synthetic bilingual dataset for Gazelle's query router, which classifies a user query as
`local` (specific fact / entity lookup) or `global` (corpus-wide sensemaking: themes, trends, comparisons).

Regenerate: `conda run -n gazelle312 python router/genData.py` from the repo root.
Random seed: `13` (set at module top). Pure Python stdlib only — no network, no API, no LLM.

---

## Schema

One JSON object per line in every `.jsonl` file.

| Field | Type | Values / Notes |
|-------|------|----------------|
| `text` | str | The query text |
| `label` | str | `"local"` or `"global"` |
| `lang` | str | `"en"` or `"ar"` |
| `domain` | str | `"musique"`, `"2wiki"`, `"news"`, `"cbe"` |
| `source` | str | `"gold"`, `"template"`, `"llm_news"`, `"example"` |
| `template_id` | str or null | e.g. `"en_local_03"`, `"ar_global_07"`. Null for gold and llm_news rows. |
| `doc` | str | Source identifier (file stem or logical group). Metadata only — not a model feature. |

`lang`, `domain`, `source`, `template_id`, and `doc` are **metadata for eval slicing only**.
The router model should train on `text` → `label` and optionally `lang`.

---

## Source → Cell Map

| Source file(s) | label | lang | domain | source tag | split rule |
|----------------|-------|------|--------|------------|------------|
| `musique/data/musique_ans_v1.0_train.jsonl` | local | en | musique | gold | train |
| `musique/data/musique_ans_v1.0_dev.jsonl` | local | en | musique | gold | test |
| `twowiki/data/train.json` | local | en | 2wiki | gold | train |
| `twowiki/data/dev.json` | local | en | 2wiki | gold | test |
| `sensemaking/questions_slice.json` | global | en | news | llm_news | train (all 10) |
| `extractions/apnews_graph.json` entities | local | en | news | template | 85/15 row-split |
| `extractions/apnews_graph.json` entity names as topics | global | en | news | template | 85/15 row-split |
| `extractions/2wiki_graph.json` entities | local | en | 2wiki | template | 85/15 row-split |
| `extractions/2wiki_graph.json` entity names as topics | global | en | 2wiki | template | 85/15 row-split |
| `Doc_Out/*_en.md` + `*discussionpaper*.md` bigrams/trigrams | local + global | en | cbe | template | 85/15 row-split |
| `extractions/*_discussionpaper_graph.json` entities | local | en | cbe | template | 85/15 row-split |
| `Doc_Out/*_ar.md` bigrams/trigrams + `*_ar_graph.json` entities | local + global | ar | cbe | template | 85/15 row-split |

Gold rows follow the natural dataset split (train file → train, dev file → test) to prevent leakage.
Templated rows are split 85/15 by random row shuffle (not by doc, since most templated sources are
a single logical document group).

---

## Slot Mining

Arabic and English terms are mined from `Doc_Out/` markdown files by:

1. Strip markdown syntax (`#`, `*`, `|`, code blocks, links).
2. Tokenize on whitespace/punctuation (`re.findall(r'[؀-ۿ\w]+')`).
3. Build all bigrams and trigrams, excluding grams where every token is a stopword.
4. For Arabic: additionally filter out grams containing non-Arabic characters (OCR artifacts).
5. Keep the top 40–80 most frequent grams as slot values.

For news and 2wiki global topics, the top-40 most frequent entity names from the corresponding
`*_graph.json` file are used as `{t}` slots.

---

## Template Banks

Templates are keyed `en_local_NN`, `en_global_NN`, `ar_local_NN`, `ar_global_NN`.
`{e}` = entity/term slot (local), `{t}` = topic slot (global).

For entity-typed slots, the template is chosen by entity type (Person → "Who is {e}?",
Date → "When was {e} established?", Money/Number/Percent → "How much is {e}?" / "What is the value of {e}?",
Location → "Where is {e} located?", Org → "What is the role of {e}?", default → "What is {e}?").

Light surface noise (applied to ~15% of templated rows only, never gold): random lowercase (EN),
drop trailing `?`/`؟`, or strip trailing `.`.

---

## Eval Splits

| Split | File | Rows (approx) | Notes |
|-------|------|---------------|-------|
| Train | `train.jsonl` | ~2 600 | All gold train rows + 85% of templated rows |
| Test | `test.jsonl` | ~1 450 | All gold dev rows + 15% of templated rows |
| Holdout | `holdout_real.jsonl` | scaffold only | Hand-author 80-100 real bilingual queries here |

**Known caveat — test local/global imbalance:** the test split is local-heavy (~4.5:1) because
998 gold rows (MuSiQue dev + 2wiki dev) are all LOCAL and go to test by spec. The ~267 global
test rows are sufficient for per-cell accuracy slicing but the headline accuracy number should be
evaluated with class-weighted or per-label metrics, not raw accuracy.

**Known caveat — Arabic coverage:** only 2 Arabic graph files exist (`12-april-2_131_ar_graph.json`,
`16-august_125_ar_graph.json`), yielding ~51 unique Arabic entity names. Arabic slot diversity
comes primarily from bigram/trigram mining of the 12 `*_ar.md` CBE documents (~80 clean terms).
Total Arabic rows: ~520 train / ~133 test — adequate for domain-coverage checks but thin for
Arabic-only model training; augment `holdout_real.jsonl` with more hand-authored Arabic queries.

---

## holdout_real.jsonl

A scaffold file. The first line is a `_comment` JSON object explaining the format.
Four clearly-marked `source="example"` rows follow to show the schema.
**Hand-author ~80–100 real bilingual questions** (do not use templates; `source="real"`).
Mix domains, labels, and languages. These are for final holdout evaluation only —
do not train on them.
