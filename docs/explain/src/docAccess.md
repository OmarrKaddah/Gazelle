# src/docAccess.py

Per-document access control. Maps each source document to a clearance level; users only retrieve chunks from documents at or below their own clearance.

## Line-by-line

**Lines 1-2 — comment**

Notes that this file is the edit point for marking documents confidential or restricted, and that unlisted documents default to `internal`.

**Line 4 — `LEVELS`**

An ordered list of the four clearance levels, lowest to highest: `public`, `internal`, `confidential`, `restricted`. Order matters because `levelRank` later uses the list index as a numeric rank.

**Line 6 — `DEFAULT_LEVEL`**

`'internal'` is the fallback for any document missing from `DOC_ACCESS`. Chosen as the middle-of-the-road default so unlabeled documents are neither openly leaked nor accidentally locked behind a high clearance.

**Line 8 — `DOC_ACCESS`**

A dict-comprehension generating `{'Chapter_1': 'internal', …, 'Chapter_8': 'internal'}`. The eight chapters of the CBE handbook are mock-labeled as `internal` for now — placeholders to be replaced with real per-doc classifications.

**Lines 11-12 — `levelRank(level)`**

Returns the integer position of `level` in the `LEVELS` list. So `levelRank('public') == 0` and `levelRank('restricted') == 3`. Used to compare clearance levels numerically.

**Lines 15-16 — `docLevel(docName)`**

Looks up the clearance of a specific document. `DOC_ACCESS.get(docName, DEFAULT_LEVEL)` returns the mapped level if the document is listed, otherwise the default. Avoids `KeyError` for unlisted documents.

**Lines 19-24 — `allowedDocs(userClearance)`**

Returns a list of document names the user is allowed to see.

- `threshold = levelRank(userClearance)` converts the user's textual clearance to its numeric rank once.
- The list comprehension iterates over every (doc, level) pair in `DOC_ACCESS` and keeps only those where the document's rank is `<=` the user's. So an `internal` user (rank 1) sees `public` (0) and `internal` (1) docs but not `confidential` (2) or above.

**Lines 27-28 — `canSeeDoc(docName, userClearance)`**

The single-document version of `allowedDocs`. Returns `True` if the user's rank is `>=` the document's rank. Used as a per-row filter in retrieval.
