# src/ontology.py

Schema declaration for the knowledge graph. Single source of truth for entity types, allowed relationships between them, and the bilingual descriptions used to embed relationship semantics for retrieval scoring.

## Line-by-line

**Lines 1-3 — header comments**

Indicate this is v0 of a banking/finance regulatory ontology and that both extraction stages (GLiNER and the LLM) read from this file. Changes here cascade to extraction prompts, KG writer validation, and retriever scoring.

**Lines 5-17 — `ENTITIES` dict**

Maps a type name (string) to a one-line natural-language definition. Each definition is what gets shown to the LLM when it is asked to extract entities of that type, so the wording matters — `RegulatoryBody` for example explicitly names Egyptian regulators (البنك المركزي المصري, etc.) to anchor the model on the actual domain vocabulary.

- `Person` — humans like signatories or executives.
- `BankingInstitution` — banks, branches, subsidiaries.
- `RegulatoryBody` — central banks, ministries, tax/customs/social-insurance authorities, with example Arabic names embedded in the description.
- `Law` — laws identified by number and year.
- `Article` — sections inside a law.
- `License` — granted authorizations.
- `Document` — circulars, decrees, policy notes.
- `FinancialInstrument` — accounts, deposits, contracts.
- `RegulatoryRequirement` — capital ratios, reserve thresholds.
- `MonetaryAmount` — amounts with currency.
- `Date` — absolute dates and ranges.

**Lines 19-29 — `RELATIONSHIPS` dict**

Maps a relationship type name to a 2-tuple `(source_types, target_types)`. Each side is a list because most relationships can connect more than one source/target type. Used by `kgWriter.py` to validate extracted relations and by the retriever to enumerate valid traversals.

- `ISSUED_BY`: a License or Document is issued by a RegulatoryBody or Person.
- `GOVERNS`: a Law or Article governs a BankingInstitution.
- `AMENDS`, `SUPERSEDES`: Law-to-Law relationships for tracking legislative chains.
- `PART_OF`: an Article is part of a Law.
- `REQUIRES`: a Law or Article requires a RegulatoryRequirement.
- `SIGNED_BY`: a Document or License is signed by a Person.
- `EFFECTIVE_FROM`: a Law or License is effective from a Date.
- `APPLIES_TO`: a Law or Article applies to a BankingInstitution.

**Lines 31-34 — header for description map**

Notes that the descriptions are embedded with BGE-M3 to score query↔relation semantic similarity, and that bilingual phrasing is intentional because Arabic queries match Arabic strings more reliably even with a cross-lingual model.

**Lines 35-45 — `RELATIONSHIP_DESCRIPTIONS` dict**

Same keys as `RELATIONSHIPS`. Values are short Arabic-then-English descriptions separated by an em-dash. The format is consistent across all entries: 3 Arabic synonyms, em-dash, 3 English synonyms. Embedding this string produces a vector that captures the relation's meaning in both languages, which `retriever.py` then compares against the query embedding to weight which relation types matter for a given question.
