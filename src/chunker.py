import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from transformers import AutoTokenizer
from parser import ParsedElement
from config import BGE_M3_PATH, CHUNK_TARGET_TOKENS
#TODO: use correct tokenizer and add overlap
tokenizer = AutoTokenizer.from_pretrained(BGE_M3_PATH)

TABLE_MERGE_THRESHOLD = 50
OVERLAP_TOKENS = 100



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


def splitText(text, target):

    if countTokens(text) <= target:
        return [text]
    lines = [l for l in text.split('\n') if l.strip()]
    if len(lines) > 1:

        segments, current, tokens = [], [], 0

        for line in lines:
            lt = countTokens(line)
            if current and tokens + lt > target:
                segments.append('\n'.join(current))

                current, tokens = [line], lt
            else:

                current.append(line)
                tokens += lt
        if current:
            segments.append('\n'.join(current))
        return segments
    
    sentences = re.split(r'(?<=[.!?؟])\s+', text.strip())
     
    sentences = [s for s in sentences if s.strip()]
    if len(sentences) > 1:
        segments, current, tokens =[], [], 0
        for sent in sentences:

            st = countTokens(sent)
            if current and tokens + st > target:
                segments.append(' '.join(current))
                current, tokens = [sent], st
            
            else:

                current.append(sent)
                tokens +=st
        if current:
            segments.append(' '.join(current))
        return segments
    
    return [text]


def expandElement(elem, target):
    segs = splitText(elem.text, target)
    if len(segs) == 1:                 
        return [elem]           
    
    return [ParsedElement(
        docName=elem.docName,
        sectionPath=elem.sectionPath,
        page=elem.page,
        elementType=elem.elementType,
        text=seg,
        elementId=elem.elementId,
        accessLevel=elem.accessLevel,

    ) for seg in segs]


def tailText(text, n_tokens):
    sentences = re.split(r'(?<=[.!?؟\n])\s*', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    result, tokens = [], 0

    for sent in reversed(sentences):
        st = countTokens(sent)

        if tokens + st > n_tokens:
            break

        result.append(sent)
        tokens += st
    return ' '.join(reversed(result))


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


def packElements(elems, target):
    expanded = []
    for e in elems:
        expanded.extend(expandElement(e, target))
    chunks = []

    current = []
    currentTokens = 0
    for e in expanded:

        if e.elementType == 'table':
            if current:
                if currentTokens < TABLE_MERGE_THRESHOLD:
                    chunks.append(current + [e])
                else:
                    chunks.append(current)
                    chunks.append([e])
                current = []
                currentTokens = 0
            else:
                chunks.append([e])
            continue

        eTokens = countTokens(e.text)

        if current and currentTokens + eTokens > target:

            chunks.append(current)
            current = [e]
            currentTokens = eTokens
            
        else:

            current.append(e)


            currentTokens += eTokens
    if current:
        chunks.append(current)
    return chunks


def buildChunk(elems, sectionPath, docName, counter, overlap=''):
    prefix = (sectionPath[-1] + ': ') if sectionPath else ''

    body = '\n\n'.join(e.text for e in elems)
    if overlap:
        body = overlap + '\n\n' + body
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
    last_overlap = ''
    for sectionPath, elems in groupBySection(elements):
        last_overlap = ''
        for chunkElems in packElements(elems, target):
            counter += 1
            chunk = buildChunk(chunkElems, sectionPath, docName, counter, overlap=last_overlap)
            chunks.append(chunk)
            chunk_body = '\n\n'.join(e.text for e in chunkElems)
            last_overlap = tailText(chunk_body, OVERLAP_TOKENS)
    return chunks


def dumpChunks(chunks, docName):
    Path('chunks').mkdir(exist_ok=True)
    data = [asdict(c) for c in chunks]
    Path(f'chunks/{docName}.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
