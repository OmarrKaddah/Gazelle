import base64
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pypdfium2
import requests

# Switch between "local" (llama-server) and "ollama"
PROVIDER = "ollama"
PARALLEL_PAGES = 1

LLAMA_SERVER_URL = "http://localhost:8080/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
OLLAMA_MODEL = "qwen3-vl:8b-instruct-q4_K_M"

OCR_PROMPT = (
    "Extract every visible character from this image exactly as it appears. "
    "Preserve every digit — Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩) stay Arabic-Indic, "
    "Western numerals (0123456789) stay Western. Do not omit any cell, number, or word. "
    "Do not translate. Do not summarize. Do not add commentary.\n\n"
    "Structure rules — follow exactly:\n"
    "1. Document titles, page headers, captions, footnotes, and any text "
    "that is NOT inside a visible row-and-column grid → output as Markdown headings "
    "(## for main titles) or plain paragraphs.\n"
    "2. ONLY content that appears in a visible row-and-column grid → output as a "
    "GitHub Flavored Markdown table.\n"
    "3. NEVER place title text, notes, or single-column text inside the table. "
    "Title and header lines always go ABOVE the table as separate paragraphs.\n"
    "4. The first table row must be the column headers, followed by a separator row "
    "of |---|---|---| with one --- per column.\n"
    "5. Signature/authority blocks where multiple people's titles appear horizontally "
    "side-by-side with their names directly underneath → output as a Markdown table "
    "with ONE COLUMN PER PERSON. Preserve the title-above-name pairing within each "
    "column. Do NOT flatten these into a vertical list — that destroys which name "
    "belongs to which title.\n\n"
    "Example of a schedule with title and signature block:\n"
    "## عنوان الوثيقة\n\n"
    "الفصل الدراسي الأول ٢٠٢٤/٢٠٢٥\n\n"
    "### الصف الثاني الإعدادي\n\n"
    "| اليوم والتاريخ | المادة |\n"
    "| --- | --- |\n"
    "| السبت ٢٠٢٥/١/١١ | اللغة العربية |\n"
    "| الأحد ٢٠٢٥/١/١٢ | اللغة الأجنبية |\n\n"
    "ملاحظة: جميع الامتحانات تبدأ الساعة التاسعة صباحاً.\n\n"
    "| مدير الإدارة | رئيس الإدارة المركزية لشئون المديريات | المشرف على الإدارة العامة للامتحانات |\n"
    "| --- | --- | --- |\n"
    "| إلهام فتحي | خالد عبد الحكيم أحمد | د/ هالة عبد السلام خفاجي |\n\n"
    "يعتمد،،\n"
    "وزير التربية والتعليم والتعليم الفني\n"
    "محمد أحمد عبد اللطيف\n\n"
    "Output only the extracted content."
)


def parse_local(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    response = requests.post(
        LLAMA_SERVER_URL,
        json={
            "model": "local",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 2048,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def parse_ollama(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 2048,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def ocr(path: str) -> str:
    if PROVIDER == "ollama":
        return parse_ollama(path)
    return parse_local(path)


def render_and_ocr(doc: pypdfium2.PdfDocument, render_scale: int, i: int) -> tuple[int, str]:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    try:
        doc[i].render(scale=render_scale, rotation=0).to_pil().save(tmp.name, "PNG")
        return i, ocr(tmp.name)
    finally:
        os.unlink(tmp.name)


def process_pdf(path: str) -> list[dict]:
    doc = pypdfium2.PdfDocument(path)
    render_scale = int(round(200 / 72))
    n_pages = len(doc)
    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=PARALLEL_PAGES) as pool:
        futures = {pool.submit(render_and_ocr, doc, render_scale, i): i for i in range(n_pages)}
        for future in as_completed(futures):
            idx, text = future.result()
            results[idx] = text
            print(f"[page {idx + 1}/{n_pages}] done", flush=True)
    return [{"page": i + 1, "markdown": results[i]} for i in range(n_pages)]


def runOcrAndDump(imagePath: str) -> tuple[str, str]:
    if imagePath.lower().endswith(".pdf"):
        pages = process_pdf(imagePath)
    else:
        pages = [{"page": 1, "markdown": ocr(imagePath)}]

    os.makedirs("Doc_Out", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    stem = os.path.splitext(os.path.basename(imagePath))[0]

    joined = "\n\n---\n\n".join(p["markdown"] for p in pages)
    md_path = os.path.join("Doc_Out", f"{stem}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(joined)

    sidecar_path = os.path.join("output", f"{stem}.json")
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    return md_path, sidecar_path
