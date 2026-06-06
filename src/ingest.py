import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import CHUNKER_TYPE
from ocr import runOcrAndDump
from parser import parseDoc, dumpParsed, loadParsed
from graphExtract import extractDoc, dumpElements
from graphBuild import buildGraph
from embedding import embedDoc
from entityEmbedding import embedEntities

NER_STRATEGY = os.getenv('NER_STRATEGY', 'hybrid').lower()
if NER_STRATEGY == 'llm':
    from llmNER import extractEntities as extractEntitiesNER, dumpEntities as dumpEntitiesNER
else:
    from glinerExtract import extractEntities as extractEntitiesNER, dumpEntities as dumpEntitiesNER

from chunker import dumpChunks

if CHUNKER_TYPE == 'semantic':
    from semantic_chunker import chunkDoc

else:
    from chunker import chunkDoc


ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = ROOT / 'Documents'
DOC_OUT = ROOT / 'Doc_Out'
OUTPUT = ROOT / 'output'


IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
PDF_EXT = {'.pdf'}
DOCX_EXT = {'.docx'}
TEXT_EXT = {'.md', '.txt'}
SUPPORTED_EXT = IMAGE_EXT | PDF_EXT | DOCX_EXT | TEXT_EXT

log = logging.getLogger('gazelle.ingest')



def saveUpload(filename, data):
    DOCUMENTS.mkdir(exist_ok=True)

    dest = DOCUMENTS / Path(filename).name

    dest.write_bytes(data)

    log.info('saved upload: %s (%d bytes)', dest.name, len(data))
    return dest


def docNameFor(source):             

    return source.stem.lower()


def writeSidecar(stem, pages):           
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / f'{stem}.json').write_text(
        json.dumps(pages, ensure_ascii=False, indent=2), encoding='utf-8'
    )


def parseSource(source):

    ext = source.suffix.lower()

    if ext in IMAGE_EXT or ext in PDF_EXT:

        runOcrAndDump(str(source))
    elif ext in DOCX_EXT:

        return parseDoc(str(source))
    elif ext in TEXT_EXT:

        writeSidecar(source.stem, [{'page': 1, 'markdown': source.read_text(encoding='utf-8')}])
    else:
        
        raise ValueError(f'unsupported file type: {ext}')
    return parseDoc(str(DOC_OUT / f'{source.stem}.md'))

def ingestOne(source, emit=None):
    def tell(msg):
        log.info(msg)
        if emit:
            emit(msg)

    docName = docNameFor(source)
    tell(f'[{source.name}] parsing')
    dumpParsed(parseSource(source), docName)

    tell(f'[{source.name}] chunking')
    chunks = chunkDoc(loadParsed(docName))
    dumpChunks(chunks, docName)
    tell(f'[{source.name}] {len(chunks)} chunks')

    tell(f'[{source.name}] NER')
    dumpEntitiesNER(extractEntitiesNER(docName), docName)

    tell(f'[{source.name}] LLM extraction')
    extractions = extractDoc(docName)
    dumpElements(extractions, docName)
    relCount = sum(len(r['relationships']) for r in extractions)
    tell(f'[{source.name}] {relCount} relationships extracted')

    tell(f'[{source.name}] writing graph')
    buildGraph(docName)

    tell(f'[{source.name}] embedding chunks')
    embedDoc(docName)

    tell(f'[{source.name}] done — {len(chunks)} chunks, {relCount} rels')
    return {
        'file': source.name,
        'docName': docName,
        'chunks': len(chunks),
        'relationships': relCount,
        'status': 'published',
    }


def ingestUploads(payloads, emit=None):
    os.chdir(ROOT)
    results = []
    sources = []

    for filename, data in payloads:
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXT:
            log.warning('rejected unsupported upload: %s', filename)
            if emit:
                emit(f'[{filename}] rejected — unsupported type {ext}')
            results.append({'file': filename, 'status': 'rejected', 'error': f'unsupported type {ext}'})
            continue
        sources.append(saveUpload(filename, data))
        if emit:
            emit(f'[{filename}] saved')

    for source in sources:
        try:
            results.append(ingestOne(source, emit))
        except Exception as exc:
            log.exception('ingest failed: %s', source.name)
            if emit:
                emit(f'[{source.name}] FAILED — {exc}')
            results.append({'file': source.name, 'status': 'failed', 'error': str(exc)})

    if any(r['status'] == 'published' for r in results):
        if emit:
            emit('embedding entities')
        embedEntities()
        if emit:
            emit('entity embedding done')

    return {'results': results}
