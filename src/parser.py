import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

# docling is imported lazily inside parseDocx — it pulls heavy, env-fragile deps
# (transformers vision models) that the JSON IO helpers (loadParsed/dumpParsed)
# and the markdown path must not require.


@dataclass
class ParsedElement:
    docName: str
    sectionPath: list[str]
    page: int | None
    elementType: str
    text: str
    elementId: str
    accessLevel: str


def splitBlocks(markdown):
    return [b.strip() for b in re.split(r'\n\s*\n', markdown) if b.strip()]


def classifyBlock(block):
    if block.startswith('#'):
        return 'heading'
    if block.startswith('|'):
        return 'table'
    first = block.splitlines()[0]
    if re.match(r'^([-*+]|\d+\.)\s', first):
        return 'list'
    return 'paragraph'


def headingLevel(block):
    return len(block) - len(block.lstrip('#'))


def headingText(block):
    return block.lstrip('#').strip()


def updateSection(sectionPath, level, text):
    return sectionPath[:level - 1] + [text]


def makeId(docName, counter):
    return f'{docName}-{counter:04d}'


def parseMarkdown(docName):
    pages = json.loads(Path(f'output/{docName}.json').read_text(encoding='utf-8'))
    elements = []
    sectionPath = []
    counter = 0
    for entry in pages:
        for block in splitBlocks(entry['markdown']):
            counter += 1
            kind = classifyBlock(block)
            if kind == 'heading':
                level = headingLevel(block)
                text = headingText(block)
                sectionPath = updateSection(sectionPath, level, text)
            else:
                text = block
            elements.append(ParsedElement(
                docName=docName,
                sectionPath=list(sectionPath),
                page=entry['page'],
                elementType=kind,
                text=text,
                elementId=makeId(docName, counter),
                accessLevel='internal',
            ))
    return elements


def parseDocx(path):
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc import TableItem, TextItem, SectionHeaderItem, ListItem
    docName = Path(path).stem
    doc = DocumentConverter().convert(path).document
    elements = []
    sectionPath = []
    counter = 0
    for item, _ in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
            sectionPath = updateSection(sectionPath, item.level, item.text)
            kind, text = 'heading', item.text
        elif isinstance(item, TableItem):
            kind, text = 'table', item.export_to_markdown()
        elif isinstance(item, ListItem):
            kind, text = 'list', item.text
        elif isinstance(item, TextItem):
            kind, text = 'paragraph', item.text
        else:
            continue
        counter += 1
        elements.append(ParsedElement(
            docName=docName,
            sectionPath=list(sectionPath),
            page=item.prov[0].page_no if item.prov else None,
            elementType=kind,
            text=text,
            elementId=makeId(docName, counter),
            accessLevel='internal',
        ))
    return elements


def parseDoc(path):
    p = Path(path)
    if p.suffix == '.md':
        return parseMarkdown(p.stem)
    if p.suffix == '.docx':
        return parseDocx(p)


def dumpParsed(elements, docName):
    Path('parsed').mkdir(exist_ok=True)
    data = [asdict(e) for e in elements]
    Path(f'parsed/{docName}.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def loadParsed(docName):
    data = json.loads(Path(f'parsed/{docName}.json').read_text(encoding='utf-8'))
    return [ParsedElement(**d) for d in data]
