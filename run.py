import os
import sys
from pathlib import Path

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from ocr import runOcrAndDump
from parser import parseDoc, dumpParsed, loadParsed
from chunker import chunkDoc, dumpChunks
from embedding import embedDoc
from dotenv import load_dotenv
load_dotenv()
import os

from config import CHUNKER_TYPE

# Choose NER strategy (gliner | llm | hybrid). Mirrors runners/runAll.py
NER_STRATEGY = os.getenv('NER_STRATEGY', 'hybrid').lower()
if NER_STRATEGY == 'llm':
    from llmNER import extractEntities as extractEntitiesNER, dumpEntities as dumpEntitiesNER
else:
    from glinerExtract import extractEntities as extractEntitiesNER, dumpEntities as dumpEntitiesNER

if CHUNKER_TYPE == 'semantic':
    from semantic_chunker import chunkDoc, dumpChunks
else:
    from chunker import chunkDoc, dumpChunks

from llmExtract import extractDoc, dumpExtractions
from kgWriter import writeDoc, writeDocEntitiesOnly, clearDb
from entityEmbedding import embedEntities
from entityAlign import deduplicate

OCR_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def runOcr():
    print("\n=== OCR ===")
    sources = sorted(p for p in Path("Documents").iterdir() if p.suffix.lower() in OCR_EXTENSIONS)
    for source in sources:
        out = Path("Doc_Out") / (source.stem + ".md")
        if out.exists():
            print(f"[skip] {source.name}")
            continue
        print(f"[ocr ] {source.name}")
        mdPath, _ = runOcrAndDump(str(source))
        print(f"       -> {mdPath}")


def runParser():
    print("\n=== Parser ===")
    for source in sorted(Path("Doc_Out").glob("*.md")):
        docName = source.stem.lower()
        out = Path(f"parsed/{docName}.json")
        if out.exists():
            print(f"[skip] {source.name}")
            continue
        print(f"[parse] {source.name}")
        elements = parseDoc(str(source))
        dumpParsed(elements, docName)
        print(f"        -> parsed/{docName}.json")


def runChunker():
    print("\n=== Chunker ===")
    for parsed in sorted(Path("parsed").glob("*.json")):
        docName = parsed.stem
        out = Path(f"chunks/{docName}.json")
        if out.exists():
            print(f"[skip] {docName}")
            continue
        print(f"[chunk] {docName}")
        elements = loadParsed(docName)
        chunks = chunkDoc(elements)
        dumpChunks(chunks, docName)
        print(f"        -> chunks/{docName}.json  ({len(chunks)} chunks)")


def runEmbed():
    print("\n=== Embed ===")
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        print(f"[embed] {docName}")
        embedDoc(docName)


def runEntities():
    print("\n=== Entity Extraction ===")
    print(f"[NER_STRATEGY] {NER_STRATEGY}")
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        out = Path(f"extractions/{docName}_entities.json")
        if out.exists():
            print(f"[skip] {docName}")
            continue
        print(f"[ner  ] {docName}  ({NER_STRATEGY})")
        entities = extractEntitiesNER(docName)
        dumpEntitiesNER(entities, docName)
        print(f"         -> extractions/{docName}_entities.json  ({len(entities)} entities)")


def runLlm():
    print("\n=== LLM Extraction ===")
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        if not Path(f"extractions/{docName}_entities.json").exists():
            print(f"[wait ] {docName}  (no GLiNER output yet)")
            continue
        out = Path(f"extractions/{docName}.json")
        if out.exists():
            print(f"[skip] {docName}")
            continue
        print(f"[llm ] {docName}")
        results = extractDoc(docName)
        dumpExtractions(results, docName)
        totalEnts = sum(len(r['entities']) for r in results)
        totalRels = sum(len(r['relationships']) for r in results)
        print(f"        -> extractions/{docName}.json  ({totalEnts} ents, {totalRels} rels)")


def runKg():
    print("\n=== KG Writer ===")
    clearDb()
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        llmFile = Path(f"extractions/{docName}.json")
        glinerFile = Path(f"extractions/{docName}_entities.json")
        if llmFile.exists():
            print(f"[kg+rels ] {docName}")
            writeDoc(docName)
        elif glinerFile.exists():
            print(f"[kg+ents ] {docName}")
            writeDocEntitiesOnly(docName)
        else:
            print(f"[wait    ] {docName}  (no extractions yet)")


def runEntityEmbed():
    print("\n=== Entity Embed ===")
    embedEntities()


def runEntityAlign():
    print("\n=== Entity Align ===")
    deduplicate()


if __name__ == '__main__':
    runOcr()
    runParser()
    runChunker()
    runEmbed()
    runGliner()
    runLlm()
    runKg()
    runEntityEmbed()
    runEntityAlign()
