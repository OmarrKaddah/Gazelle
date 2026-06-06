import sys
import json
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from parser import ParsedElement, dumpParsed
from chunker import Chunk, dumpChunks


@pytest.fixture
def integration_data_dir():
    """Create a complete data directory structure for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        (tmppath / 'Doc_Out').mkdir()
        (tmppath / 'parsed').mkdir()
        (tmppath / 'chunks').mkdir()
        (tmppath / 'extractions').mkdir()
        yield tmppath


@pytest.fixture
def sample_document_content():
    """Real document content for integration testing."""
    return {
        'title': 'Banking Regulations Guide',
        'sections': [
            {
                'heading': 'Introduction',
                'content': 'This guide provides comprehensive information about banking regulations and compliance requirements.',
            },
            {
                'heading': 'Chapter 1: Regulatory Framework',
                'content': 'The Central Bank of Egypt is responsible for banking oversight. Banks must comply with international standards.',
            },
            {
                'heading': 'Chapter 2: Customer Protection',
                'subsections': [
                    {
                        'heading': 'Know Your Customer (KYC)',
                        'content': 'All banks must implement KYC procedures to prevent fraud. Customer identification is mandatory.',
                    },
                    {
                        'heading': 'Data Privacy',
                        'content': 'Customer data must be protected according to privacy regulations. Banks must secure sensitive information.',
                    },
                ],
            },
            {
                'heading': 'Conclusion',
                'content': 'Compliance with these regulations ensures a stable banking system.',
            },
        ]
    }


@pytest.fixture
def parsed_document(integration_data_dir, sample_document_content):
    """Create a parsed document in the integration data directory."""
    import os
    original_cwd = Path.cwd()
    try:
        os.chdir(integration_data_dir)

        elements = []
        element_id = 0

        for section in sample_document_content['sections']:
            element_id += 1
            elements.append(ParsedElement(
                docName='banking_guide',
                sectionPath=[section['heading']],
                page=element_id,
                elementType='heading',
                text=section['heading'],
                elementId=f'banking_guide-{element_id:04d}',
                accessLevel='internal',
            ))

            if 'content' in section:
                element_id += 1
                elements.append(ParsedElement(
                    docName='banking_guide',
                    sectionPath=[section['heading']],
                    page=element_id,
                    elementType='paragraph',
                    text=section['content'],
                    elementId=f'banking_guide-{element_id:04d}',
                    accessLevel='internal',
                ))

            if 'subsections' in section:
                for subsection in section['subsections']:
                    element_id += 1
                    elements.append(ParsedElement(
                        docName='banking_guide',
                        sectionPath=[section['heading'], subsection['heading']],
                        page=element_id,
                        elementType='heading',
                        text=subsection['heading'],
                        elementId=f'banking_guide-{element_id:04d}',
                        accessLevel='internal',
                    ))

                    element_id += 1
                    elements.append(ParsedElement(
                        docName='banking_guide',
                        sectionPath=[section['heading'], subsection['heading']],
                        page=element_id,
                        elementType='paragraph',
                        text=subsection['content'],
                        elementId=f'banking_guide-{element_id:04d}',
                        accessLevel='internal',
                    ))

        dumpParsed(elements, 'banking_guide')
        return elements
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def chunked_document(integration_data_dir, parsed_document):
    """Create chunks from parsed document."""
    import os
    original_cwd = Path.cwd()
    try:
        os.chdir(integration_data_dir)

        from chunker import chunkDoc
        chunks = chunkDoc(parsed_document)
        dumpChunks(chunks, 'banking_guide')
        return chunks
    finally:
        os.chdir(original_cwd)
