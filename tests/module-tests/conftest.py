import sys
import json
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from parser import ParsedElement
from chunker import Chunk


@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / 'Doc_Out').mkdir()
        (tmppath / 'parsed').mkdir()
        (tmppath / 'chunks').mkdir()
        (tmppath / 'extractions').mkdir()
        yield tmppath


@pytest.fixture
def sample_markdown_document(temp_data_dir):
    doc_content = """
# Introduction

This is the introduction section with some content.

## Background

Some background information about the topic.

# Main Content

## Section 1.1

Content for section 1.1 with multiple sentences. This has enough text to be meaningful.

## Section 1.2

More content here with details and information.

# Conclusion

Summary and conclusion of the document.
"""
    markdown_file = temp_data_dir / 'Doc_Out' / 'sample.md'
    markdown_file.write_text(doc_content, encoding='utf-8')
    return markdown_file


@pytest.fixture
def sample_parsed_elements(temp_data_dir):
    elements = [
        ParsedElement(
            docName='sample',
            sectionPath=['Introduction'],
            page=1,
            elementType='heading',
            text='Introduction',
            elementId='sample-0001',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='sample',
            sectionPath=['Introduction'],
            page=1,
            elementType='paragraph',
            text='This is the introduction section with some content. It provides background information.',
            elementId='sample-0002',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='sample',
            sectionPath=['Introduction', 'Background'],
            page=1,
            elementType='paragraph',
            text='Some background information about the topic. Important details here.',
            elementId='sample-0003',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='sample',
            sectionPath=['Main Content'],
            page=2,
            elementType='heading',
            text='Main Content',
            elementId='sample-0004',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='sample',
            sectionPath=['Main Content', 'Section 1.1'],
            page=2,
            elementType='paragraph',
            text='Content for section 1.1 with multiple sentences. This has enough text to be meaningful.',
            elementId='sample-0005',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='sample',
            sectionPath=['Main Content', 'Section 1.2'],
            page=3,
            elementType='paragraph',
            text='More content here with details and information. Additional text for context.',
            elementId='sample-0006',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='sample',
            sectionPath=['Conclusion'],
            page=4,
            elementType='paragraph',
            text='Summary and conclusion of the document.',
            elementId='sample-0007',
            accessLevel='internal',
        ),
    ]
    return elements


@pytest.fixture
def sample_chunks(temp_data_dir):
    chunks = [
        Chunk(
            chunkId='chunk_001',
            docName='sample',
            sectionPath=['Introduction'],
            pages=[1],
            text='Introduction: This is the introduction section with some content.',
            elementIds=['sample-0001', 'sample-0002'],
            accessLevel='internal',
        ),
        Chunk(
            chunkId='chunk_002',
            docName='sample',
            sectionPath=['Introduction', 'Background'],
            pages=[1],
            text='Background: Some background information about the topic.',
            elementIds=['sample-0003'],
            accessLevel='internal',
        ),
        Chunk(
            chunkId='chunk_003',
            docName='sample',
            sectionPath=['Main Content', 'Section 1.1'],
            pages=[2],
            text='Section 1.1: Content for section 1.1 with multiple sentences.',
            elementIds=['sample-0005'],
            accessLevel='internal',
        ),
        Chunk(
            chunkId='chunk_004',
            docName='sample',
            sectionPath=['Main Content', 'Section 1.2'],
            pages=[3],
            text='Section 1.2: More content here with details and information.',
            elementIds=['sample-0006'],
            accessLevel='internal',
        ),
    ]

    chunks_file = temp_data_dir / 'chunks' / 'sample.json'
    chunks_data = [
        {
            'chunkId': c.chunkId,
            'docName': c.docName,
            'sectionPath': c.sectionPath,
            'pages': c.pages,
            'text': c.text,
            'elementIds': c.elementIds,
            'accessLevel': c.accessLevel,
        }
        for c in chunks
    ]
    chunks_file.write_text(json.dumps(chunks_data, ensure_ascii=False, indent=2), encoding='utf-8')
    return chunks


@pytest.fixture
def sample_extracted_entities():
    return [
        {
            'chunkId': 'chunk_001',
            'docName': 'sample',
            'text': 'Introduction',
            'type': 'SECTION_TITLE',
            'start': 0,
            'end': 12,
            'score': 0.98,
        },
        {
            'chunkId': 'chunk_002',
            'docName': 'sample',
            'text': 'Background',
            'type': 'SECTION_TITLE',
            'start': 0,
            'end': 10,
            'score': 0.97,
        },
        {
            'chunkId': 'chunk_003',
            'docName': 'sample',
            'text': 'content',
            'type': 'CONCEPT',
            'start': 22,
            'end': 29,
            'score': 0.92,
        },
    ]


@pytest.fixture
def sample_embeddings():
    return {
        'chunk_001': [0.1, 0.2, 0.3, 0.4, 0.5],
        'chunk_002': [0.2, 0.3, 0.4, 0.5, 0.6],
        'chunk_003': [0.3, 0.4, 0.5, 0.6, 0.7],
        'chunk_004': [0.4, 0.5, 0.6, 0.7, 0.8],
    }
