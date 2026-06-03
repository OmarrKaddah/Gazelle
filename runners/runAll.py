import _bootstrap  # noqa: F401
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from config import CHUNKER_TYPE, NER_STRATEGY
from parser import parseDoc, dumpParsed

if CHUNKER_TYPE == 'semantic':
    from semantic_chunker import chunkDoc, dumpChunks
else:
    from chunker import chunkDoc, dumpChunks

# Choose NER strategy ('gliner' | 'llm') from config
if NER_STRATEGY == 'llm':
    from llmNER import extractEntities, dumpEntities
else:
    from glinerExtract import extractEntities, dumpEntities

from llmExtract import extractDoc, dumpExtractions
from kgWriter import writeDoc
from embedding import embedDoc
from ocr import runOcrAndDump


def is_searchable_pdf(path: str) -> bool:
    try:
        from PyPDF2 import PdfReader
    except Exception:
        return False
    r = PdfReader(path)
    for p in r.pages:
        txt = p.extract_text() or ''
        if txt.strip():
            return True
    return False


def write_sidecar_and_md(pages, stem: str) -> str:
    os.makedirs('Doc_Out', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    joined = "\n\n---\n\n".join(p['markdown'] for p in pages)
    md_path = os.path.join('Doc_Out', f'{stem}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(joined)
    sidecar_path = os.path.join('output', f'{stem}.json')
    with open(sidecar_path, 'w', encoding='utf-8') as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)
    return md_path


def process_file(path: str, skip_kg: bool = False, skip_embed: bool = False):
    p = Path(path)
    stem = p.stem
    print(f"\n=== Processing {p.name} ===")
    if p.suffix.lower() == '.docx':
        elements = parseDoc(str(p))
        dumpParsed(elements, stem)
        print(f"Parsed {len(elements)} elements from {p.name}")
    elif p.suffix.lower() == '.pdf':
        if is_searchable_pdf(str(p)):
            print("Searchable PDF detected — extracting text pages")
            try:
                from PyPDF2 import PdfReader
                r = PdfReader(str(p))
                pages = []
                for i, pg in enumerate(r.pages):
                    pages.append({'page': i + 1, 'markdown': pg.extract_text() or ''})
                md_path = write_sidecar_and_md(pages, stem)
                elements = parseDoc(md_path)
                dumpParsed(elements, stem)
                print(f"Parsed {len(elements)} elements from {p.name}")
            except Exception:
                print("Failed to extract PDF text — falling back to OCR")
                md_path, _ = runOcrAndDump(str(p))
                elements = parseDoc(md_path)
                dumpParsed(elements, stem)
        else:
            print("Scanned PDF or image PDF — running OCR")
            md_path, _ = runOcrAndDump(str(p))
            elements = parseDoc(md_path)
            dumpParsed(elements, stem)
    elif p.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff']:
        md_path, _ = runOcrAndDump(str(p))
        elements = parseDoc(md_path)
        dumpParsed(elements, stem)
    else:
        print(f"Skipping unsupported file type: {p.name}")
        return

    chunks = chunkDoc(elements)
    dumpChunks(chunks, stem)
    print(f"Wrote {len(chunks)} chunks to chunks/{stem}.json")

    ner_label = 'LLM' if NER_STRATEGY == 'llm' else 'GLiNER'
    print(f"\n[NER Strategy: {NER_STRATEGY.upper()}] Using {ner_label} for entity extraction")
    
    ents = extractEntities(stem)
    dumpEntities(ents, stem)
    print(f"Wrote {len(ents)} entity spans to extractions/{stem}_entities.json")

    rels = extractDoc(stem)
    dumpExtractions(rels, stem)
    print(f"Wrote relationship extractions to extractions/{stem}.json")

    if not skip_kg:
        writeDoc(stem)
    else:
        print("Skipping KG write (disabled)")

    if not skip_embed:
        embedDoc(stem)
    else:
        print("Skipping embeddings (disabled)")


def main():
    ap = argparse.ArgumentParser(
        description='Run full pipeline for one or more source files',
        epilog=f"""
NER Strategy (from .env NER_STRATEGY) [current: {NER_STRATEGY}]:
  - gliner: Fast GLiNER-only entity extraction (baseline)
  - llm: LLM-based entity extraction (slower but more accurate, uses Ollama)

Configure in .env: NER_STRATEGY, GLINER_MODEL, GLINER_THRESHOLD, OLLAMA_TEXT_MODEL
        """
    )
    ap.add_argument('source', nargs='?', default='Documents', help='File or directory to process')
    ap.add_argument('--extensions', nargs='+', default=None, help='Limit to these file extensions (e.g. .pdf .docx)')
    ap.add_argument('--skip-kg', action='store_true', help='Skip writing to Neo4j')
    ap.add_argument('--skip-embed', action='store_true', help='Skip embedding step')
    args = ap.parse_args()

    from pathlib import Path

    src = Path(args.source) if args.source else Path.home() / "Documents"
    print(f"Source: {src}")
    if src.is_file():
        process_file(str(src), skip_kg=args.skip_kg, skip_embed=args.skip_embed)
        return

    files = []
    if src.is_dir():
        for f in src.iterdir():
            if not f.is_file():
                continue
            if args.extensions and f.suffix.lower() not in [e.lower() for e in args.extensions]:
                continue
            files.append(f)
    else:
        print(f"Source path not found: {src}")
        return

    for f in sorted(files):
        process_file(str(f), skip_kg=args.skip_kg, skip_embed=args.skip_embed)


if __name__ == '__main__':
    main()
