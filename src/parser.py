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

#TODO: handle tables  better 
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


def tableToText(item):

    cells = item.data.table_cells

    if not cells:
        return ''
    num_rows = item.data.num_rows

    num_cols = item.data.num_cols

    grid = [[''] * num_cols for _ in range(num_rows)]
    for cell in cells:
        r = cell.start_row_offset_idx
        c = cell.start_col_offset_idx
        if r < num_rows and c < num_cols:
            grid[r][c] = cell.text.strip().replace('\n', ' ')
    has_header = any(c.column_header for c in cells)
    if has_header:
        header_rows = sorted({c.start_row_offset_idx for c in cells if c.column_header})
        data_row_indices = [r for r in range(num_rows) if r > max(header_rows)]
        if len(header_rows) >= len(data_row_indices):
            has_header = False
    if has_header:
        headers = []
        for col in range(num_cols):
            vals = [grid[r][col] for r in header_rows if grid[r][col]]
            headers.append(' / '.join(vals))
        lines = []
        #put headers with row values
        for row in grid[max(header_rows) + 1:]:
            pairs = []
            for col in range(num_cols):
                if row[col] and headers[col]:
                    pairs.append(f'{headers[col]}: {row[col]}')
                elif row[col]:
                    pairs.append(row[col])
            if pairs:
                lines.append(', '.join(pairs))
        return '\n'.join(lines)
    else:
        lines = []
        for row in grid:

            non_empty = [v for v in row if v]         

            if not non_empty:
                continue
            if len(non_empty) >= 2:
                   
                lines.append(f'{non_empty[0]}: {", ".join(non_empty[1:])}')
            else:
                  
                lines.append(non_empty[0])  

                 
        return ', '.join(lines)


def parseDocx(path):
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc import TableItem, TextItem, SectionHeaderItem, ListItem
    docName = Path(path).stem
    doc = DocumentConverter().convert(path).document
    elements = []
    sectionPath = []
    counter = 0
    header_texts = set()
    for item, _ in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
             
            sectionPath = updateSection(sectionPath, item.level, item.text)
            kind, text = 'heading', item.text
            header_texts = set()
        elif isinstance(item, TableItem):
             
            kind, text = 'table', tableToText(item)
            header_texts = {c.text.strip() for c in item.data.table_cells if c.column_header and c.text.strip()}
        elif isinstance(item, (ListItem, TextItem)):
             
            text =item.text
            if not text.strip():
                continue
            if text.strip() in header_texts:
                continue

            header_texts =set()
            
            kind = 'list' if isinstance(item, ListItem) else 'paragraph'
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
