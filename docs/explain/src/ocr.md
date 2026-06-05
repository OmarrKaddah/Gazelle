# src/ocr.py

OCR pipeline. Renders each PDF page to a PNG, sends it to a vision LLM with a carefully tuned Arabic-aware prompt, and writes both a joined markdown file and a per-page JSON sidecar.

## Line-by-line

**Lines 1-9 — imports**

- `base64` to encode page PNGs into the `data:image/jpeg;base64,…` URLs the vision API expects.
- `json` to write the sidecar.
- `os`, `tempfile` for file handling.
- `ThreadPoolExecutor, as_completed` to OCR multiple PDF pages in parallel.
- `pypdfium2` is the PDF renderer (a PDFium binding — faster and more accurate than PyPDF2's text extraction; importantly it can RENDER pages, not just extract text).
- `requests` for the HTTP calls to the vision endpoint.
- Constants pulled from `config.py`: which provider to use, how many pages in parallel, both endpoint URLs, and the Ollama vision model name.

**Lines 11-47 — `OCR_PROMPT`**

A multi-paragraph prompt string telling the vision model exactly what to output. Critical rules:

1. Extract characters exactly as they appear — do NOT normalize Arabic-Indic numerals `(٠١٢٣٤٥٦٧٨٩)` to Western digits or vice versa. Each digit system stays in its own form.
2. Anything not in a visible row/column grid → markdown headings or paragraphs.
3. Only true tables → GitHub-Flavored Markdown tables.
4. Never put titles, notes, or single-column text inside a table.
5. Tables must have a `|---|` separator row after the headers.
6. Signature blocks (multiple people's titles side-by-side with names underneath) get rendered as a ONE-COLUMN-PER-PERSON table to preserve which name belongs to which title. Flattening these to a vertical list would lose that pairing.

A worked example follows in Arabic, showing a document title, semester header, a daily schedule table, and a signature block — gives the model a concrete pattern to imitate.

**CLAUDE.md explicitly warns: do not casually edit this prompt; it's tuned for the Arabic legal/regulatory documents in `Documents/`.**

**Lines 50-67 — `callVision(url, model, b64)`**

One unified function that posts an OpenAI-compatible chat-completions request to either Ollama or llama-server. Body shape:

- `model` — the requested model id.
- `messages` — a single user message with two content blocks: the image (as a base64 data URL) and the text prompt.
- `temperature: 0` — deterministic output.
- `max_tokens: 2048` — caps output length per page.

`response.raise_for_status()` turns HTTP errors into exceptions. The returned content from `choices[0].message.content` is stripped of surrounding whitespace and returned.

**Lines 70-75 — `ocr(path)`**

Reads the image bytes once, base64-encodes them once, then dispatches to `callVision` with either the Ollama or local endpoint depending on `OCR_PROVIDER`. This is the single per-image entry point used by both PDF page rendering and direct image OCR.

**Lines 78-85 — `renderAndOcr(doc, scale, i)`**

Renders page `i` of the open PDF document to a temp PNG file, then calls `ocr` on that file. The `try/finally` ensures the temp file is deleted whether OCR succeeds or fails. Returns a `(page_index, text)` tuple so the caller can reassemble pages in order even though they complete out of order.

- `scale` controls render resolution. The caller passes ~`200/72 ≈ 2.78` for ~200 DPI.
- `rotation=0` keeps the page orientation as in the source PDF.

**Lines 88-99 — `processPdf(path)`**

Top-level PDF handler.

- Opens the PDF with `pypdfium2.PdfDocument`.
- `scale = int(round(200/72))` computes the render scale once.
- `nPages = len(doc)` is the page count.
- A `ThreadPoolExecutor` with at most `OCR_PARALLEL_PAGES` threads submits one `renderAndOcr` call per page.
- `as_completed` yields futures in completion order (not submission order); each result is stored in the `results` dict keyed by page index, and a progress line is printed.
- The final list comprehension walks pages 0…N-1 in order and emits `[{"page": 1, "markdown": "..."}, ...]` — reordering the dict back into page order.

**Lines 102-118 — `runOcrAndDump(imagePath)`**

Public entry point.

- If the path ends in `.pdf`, calls `processPdf`; otherwise treats the path as a single image and wraps the result in a one-element list.
- Creates `Doc_Out/` and `output/` if they don't exist.
- `stem` is the basename without extension — used as the output filename.
- Concatenates all page markdowns with `\n\n---\n\n` separators and writes to `Doc_Out/<stem>.md`. The horizontal-rule separator survives later parsing as a page boundary.
- Writes the per-page JSON sidecar to `output/<stem>.json` with `ensure_ascii=False` so Arabic characters appear as themselves rather than `\u…` escapes.
- Returns both output paths.
