import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import CHUNKER_TYPE
from ocr import runOcrAndDump
from parser import parseDoc, dumpParsed, loadParsed
from llmExtract import extractDoc, dumpExtractions
from kgWriter import writeDoc
from embedding import embedDoc
from entityEmbedding import embedEntities
from entityAlign import deduplicate
from docConvert import docxToMarkdown, pdfPages

NER_STRATEGY = os.getenv('NER_STRATEGY', 'hybrid').lower()
if NER_STRATEGY == 'llm':
    from llmNER import extractEntities as extractEntitiesNER, dumpEntities as dumpEntitiesNER
else:
    from glinerExtract import extractEntities as extractEntitiesNER, dumpEntities as dumpEntitiesNER

if CHUNKER_TYPE == 'semantic':
    from semantic_chunker import chunkDoc, dumpChunks
else:
    from chunker import chunkDoc, dumpChunks

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = ROOT / 'Documents'
DOC_OUT = ROOT / 'Doc_Out'
OUTPUT = ROOT / 'output'

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
PDF_EXT = {'.pdf'}
DOCX_EXT = {'.docx'}
TEXT_EXT = {'.md', '.txt'}
SUPPORTED_EXT = IMAGE_EXT | PDF_EXT | DOCX_EXT | TEXT_EXT

# Above this many extractable chars we treat the PDF as digital and skip OCR.
PDF_TEXT_MIN_CHARS = 200

log = logging.getLogger('gazelle.ingest')


def saveUpload(filename, data):
    DOCUMENTS.mkdir(exist_ok=True)
    dest = DOCUMENTS / Path(filename).name
    dest.write_bytes(data)
    log.info('saved upload: %s (%d bytes)', dest.name, len(data))
    return dest


def docNameFor(source):
    return source.stem.lower()


# output/<stem>.json, same [{'page', 'markdown'}] shape OCR produces
def writeSidecar(stem, pages):
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / f'{stem}.json').write_text(
        json.dumps(pages, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# OCR only for images and scanned PDFs; digital PDFs, docx and text read directly.
def parseSource(source):
    ext = source.suffix.lower()
    if ext in IMAGE_EXT:
        runOcrAndDump(str(source))
    elif ext in PDF_EXT:
        pages = pdfPages(str(source))
        if sum(len(p['markdown']) for p in pages) >= PDF_TEXT_MIN_CHARS:
            log.info('pdf has text layer (%d pages): reading directly, no OCR', len(pages))
            writeSidecar(source.stem, pages)
        else:
            log.info('pdf has no usable text layer, falling back to OCR')
            runOcrAndDump(str(source))
    elif ext in DOCX_EXT:
        writeSidecar(source.stem, [{'page': 1, 'markdown': docxToMarkdown(str(source))}])
    elif ext in TEXT_EXT:
        writeSidecar(source.stem, [{'page': 1, 'markdown': source.read_text(encoding='utf-8')}])
    else:
        raise ValueError(f'unsupported file type: {ext}')
    return parseDoc(str(DOC_OUT / f'{source.stem}.md'))


# Full pipeline for one doc. writeDoc merges into Neo4j (no clearDb), and
# embedDoc runs after it so the Chunk nodes exist before we set their vectors.
def ingestOne(source):
    docName = docNameFor(source)
    log.info('ingest start: %s -> doc=%s', source.name, docName)

    dumpParsed(parseSource(source), docName)
    chunks = chunkDoc(loadParsed(docName))
    dumpChunks(chunks, docName)

    dumpEntitiesNER(extractEntitiesNER(docName), docName)
    extractions = extractDoc(docName)
    dumpExtractions(extractions, docName)

    writeDoc(docName)
    embedDoc(docName)

    relCount = sum(len(r['relationships']) for r in extractions)
    log.info('ingest done: doc=%s chunks=%d rels=%d', docName, len(chunks), relCount)
    return {
        'file': source.name,
        'docName': docName,
        'chunks': len(chunks),
        'relationships': relCount,
        'status': 'published',
    }


# API entry point. payloads is a list of (filename, bytes). One bad file
# doesn't abort the batch; embed + dedup run once at the end so new entities
# link against the existing graph.
def ingestUploads(payloads):
    os.chdir(ROOT)
    results = []
    sources = []
    for filename, data in payloads:
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXT:
            log.warning('rejected unsupported upload: %s', filename)
            results.append({'file': filename, 'status': 'rejected', 'error': f'unsupported type {ext}'})
            continue
        sources.append(saveUpload(filename, data))

    for source in sources:
        try:
            results.append(ingestOne(source))
        except Exception as exc:
            log.exception('ingest failed: %s', source.name)
            results.append({'file': source.name, 'status': 'failed', 'error': str(exc)})

    if any(r['status'] == 'published' for r in results):
        log.info('post-processing: entity embed + dedup')
        embedEntities()
        deduplicate()

    return {'results': results}
