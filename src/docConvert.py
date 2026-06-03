from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader


# Convert a .docx into markdown WITHOUT OCR — Word files already carry digital
# text, so we read the document body in order and emit markdown the parser can
# consume the same way it consumes OCR output (Doc_Out/*.md).

def paragraphToMarkdown(para):
    text = para.text.strip()
    if not text:
        return ''
    style = (para.style.name or '').lower()
    if style.startswith('heading'):
        digits = ''.join(ch for ch in style if ch.isdigit())
        level = int(digits) if digits else 2
        return f'{"#" * min(level, 6)} {text}'
    return text


def tableToMarkdown(table):
    rows = [[cell.text.strip().replace('\n', ' ') for cell in row.cells] for row in table.rows]
    if not rows:
        return ''
    header = rows[0]
    lines = ['| ' + ' | '.join(header) + ' |', '| ' + ' | '.join('---' for _ in header) + ' |']
    for row in rows[1:]:
        lines.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(lines)


def docxToMarkdown(path):
    doc = Document(path)
    parts = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            md = paragraphToMarkdown(Paragraph(child, doc))
        elif tag == 'tbl':
            md = tableToMarkdown(Table(child, doc))
        else:
            md = ''
        if md:
            parts.append(md)
    return '\n\n'.join(parts)


# Extract a digital PDF's text layer WITHOUT OCR, one entry per page in the
# same shape the OCR sidecar uses ([{'page': N, 'markdown': ...}, ...]).
# Returns [] for scanned/image PDFs with no extractable text so the caller can
# fall back to OCR.
def pdfPages(path):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or '').strip()
        if text:
            pages.append({'page': i, 'markdown': text})
    return pages
