import _bootstrap  # noqa: F401
from pathlib import Path

from config import CHUNKER_TYPE, NER_STRATEGY, GRAPH_ROUTE, GRAPH_EXTRACT_BACKEND
from ocr import runOcrAndDump
from parser import parseDoc, dumpParsed, loadParsed
from embedding import embedDoc
from kgBuild import buildEntityLayer
import graphExtract
import graphBuild

if CHUNKER_TYPE == 'semantic':
    from semantic_chunker import chunkDoc, dumpChunks
else:
    from chunker import chunkDoc, dumpChunks

if NER_STRATEGY == 'llm':
    from llmNER import extractEntities, dumpEntities
else:
    from glinerExtract import extractEntities, dumpEntities

OCR_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def runOcr():
    print("\n=== OCR ===")
    for source in sorted(p for p in Path("Documents").iterdir() if p.suffix.lower() in OCR_EXTENSIONS):
        out = Path("Doc_Out") / (source.stem + ".md")
        if out.exists():
            print(f"[skip] {source.name}")
            continue
        print(f"[ocr ] {source.name}")
        runOcrAndDump(str(source))


def runParser():
    print("\n=== Parser ===")
    for source in sorted(Path("Doc_Out").glob("*.md")):
        docName = source.stem.lower()
        if Path(f"parsed/{docName}.json").exists():
            print(f"[skip] {source.name}")
            continue
        print(f"[parse] {source.name}")
        dumpParsed(parseDoc(str(source)), docName)


def runChunker():
    print("\n=== Chunker ===")
    for parsed in sorted(Path("parsed").glob("*.json")):
        docName = parsed.stem
        if Path(f"chunks/{docName}.json").exists():
            print(f"[skip] {docName}")
            continue
        print(f"[chunk] {docName}")
        chunks = chunkDoc(loadParsed(docName))
        dumpChunks(chunks, docName)
        print(f"        -> chunks/{docName}.json  ({len(chunks)} chunks)")


def runEmbed():
    print("\n=== Embed ===")
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        print(f"[embed] {docName}")
        embedDoc(docName)


def runRoute1():
    print(f"\n=== Graph Route 1 (GLiNER + co-mention, NER={NER_STRATEGY}) ===")
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        if not Path(f"extractions/{docName}_entities.json").exists():
            print(f"[ner ] {docName}")
            dumpEntities(extractEntities(docName), docName)
        buildEntityLayer(docName)


def runRoute2():
    print(f"\n=== Graph Route 2 (full-LLM RELATED graph, backend={GRAPH_EXTRACT_BACKEND}) ===")
    for chunk in sorted(Path("chunks").glob("*.json")):
        docName = chunk.stem
        if not Path(f"extractions/{docName}_graph.json").exists():
            print(f"[extract] {docName}")
            graphExtract.dumpElements(graphExtract.extractDoc(docName), docName)
        graphBuild.buildGraph(docName)


def runGraph():
    if GRAPH_ROUTE == '2':
        runRoute2()
    else:
        runRoute1()


if __name__ == '__main__':
    runOcr()
    runParser()
    runChunker()
    runEmbed()
    runGraph()
