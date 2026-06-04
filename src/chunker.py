import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from transformers import AutoTokenizer
from parser import ParsedElement
from config import BGE_M3_PATH, CHUNK_TARGET_TOKENS

tokenizer = AutoTokenizer.from_pretrained(BGE_M3_PATH)


@dataclass
class Chunk:
    chunkId: str
    docName: str
    sectionPath: list[str]
    pages: list[int]
    text: str
    elementIds: list[str]
    accessLevel: str


def countTokens(text):
    return len(tokenizer.encode(text, add_special_tokens=False))


def collectPages(elems):
    seen = []
    for e in elems:
        if e.page is not None and e.page not in seen:
            seen.append(e.page)
    return seen


def groupBySection(elements):
    groups = []
    current = []
    currentPath = None
    for e in elements:
        if e.elementType == 'heading':
            continue
        if e.sectionPath != currentPath:
            if current:
                groups.append((currentPath, current))
            current = []
            currentPath = e.sectionPath
        current.append(e)
    if current:
        groups.append((currentPath, current))
    return groups


def parseMarkdownTable(text):
    lines = [l for l in text.strip().split('\n') if l.strip()]
    if len(lines) < 3:
        return None
    headers = [c.strip() for c in lines[0].strip('|').split('|')]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)
    return headers, rows


def tableToSentences(headers, rows):
    cleanHeaders = [
        h if '<!-- rich cell -->' not in h else f'col_{i + 1}'
        for i, h in enumerate(headers)
    ]
    out = []
    for row in rows:
        parts = [f"{h}: {v}" for h, v in zip(cleanHeaders, row) if v.strip() and h.strip()]
        if parts:
            out.append(', '.join(parts) + '.')
    return '\n'.join(out)


def absorbTableHeaders(elems):
    """For tables where docling emitted <!-- rich cell --> placeholders, look ahead
    for the N immediately following non-empty paragraphs and use them as column headers."""
    skip = set()
    result = []
    for i, e in enumerate(elems):
        if i in skip:
            continue
        if e.elementType != 'table' or '<!-- rich cell -->' not in e.text.split('\n')[0]:
            result.append(e)
            continue
        richCount = e.text.split('\n')[0].count('<!-- rich cell -->')
        candidates = []
        j = i + 1
        while j < len(elems) and len(candidates) < richCount:
            if elems[j].elementType == 'paragraph' and elems[j].text.strip():
                candidates.append(j)
            j += 1
        if len(candidates) == richCount:
            headerLine = e.text.split('\n')[0]
            for idx in candidates:
                headerLine = headerLine.replace('<!-- rich cell -->', elems[idx].text.strip(), 1)
            lines = e.text.split('\n')
            lines[0] = headerLine
            result.append(ParsedElement(
                docName=e.docName,
                sectionPath=e.sectionPath,
                page=e.page,
                elementType=e.elementType,
                text='\n'.join(lines),
                elementId=e.elementId,
                accessLevel=e.accessLevel,
            ))
            skip.update(candidates)
        else:
            result.append(e)
    return result


def packElements(elems, target):
    chunks = []
    current = []
    currentTokens = 0
    for e in elems:
        if not e.text.strip() and e.elementType != 'table':
            continue
        if e.elementType == 'table':
            if current:
                chunks.append(current)
                current = []
                currentTokens = 0
            chunks.append([e])
            continue
        eTokens = countTokens(e.text)
        if current and currentTokens + eTokens > target:
            chunks.append(current)
            current = [current[-1], e]
            currentTokens = countTokens(current[0].text) + eTokens
        else:
            current.append(e)
            currentTokens += eTokens
    if current:
        chunks.append(current)
    return chunks


def buildChunk(elems, sectionPath, docName, counter):
    prefix = (sectionPath[-1] + ': ') if sectionPath else ''
    parts = []
    for e in elems:
        if e.elementType == 'table':
            parsed = parseMarkdownTable(e.text)
            parts.append(tableToSentences(*parsed) if parsed else e.text)
        else:
            parts.append(e.text)
    body = '\n\n'.join(parts)
    return Chunk(
        chunkId=f'{docName}-c{counter:04d}',
        docName=docName,
        sectionPath=list(sectionPath),
        pages=collectPages(elems),
        text=prefix + body,
        elementIds=[e.elementId for e in elems],
        accessLevel=elems[0].accessLevel,
    )


def chunkDoc(elements, target=CHUNK_TARGET_TOKENS):
    chunks = []
    counter = 0
    docName = elements[0].docName
    for sectionPath, elems in groupBySection(elements):
        cleanedElems = absorbTableHeaders(elems)
        for chunkElems in packElements(cleanedElems, target):
            counter += 1
            chunks.append(buildChunk(chunkElems, sectionPath, docName, counter))
    return chunks


def dumpChunks(chunks, docName):
    Path('chunks').mkdir(exist_ok=True)
    data = [asdict(c) for c in chunks]
    Path(f'chunks/{docName}.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
