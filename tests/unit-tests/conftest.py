import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from parser import ParsedElement
from chunker import Chunk


@pytest.fixture
def sample_element():
    return ParsedElement(
        docName='test_doc',
        sectionPath=['Introduction', 'Background'],
        page=1,
        elementType='paragraph',
        text='This is a test paragraph with enough content to be meaningful.',
        elementId='test_doc-0001',
        accessLevel='internal',
    )


@pytest.fixture
def sample_elements():
    return [
        ParsedElement(
            docName='test_doc',
            sectionPath=['Chapter 1'],
            page=1,
            elementType='heading',
            text='Chapter 1: Introduction',
            elementId='test_doc-0001',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='test_doc',
            sectionPath=['Chapter 1'],
            page=1,
            elementType='paragraph',
            text='First paragraph text.',
            elementId='test_doc-0002',
            accessLevel='internal',
        ),
        ParsedElement(
            docName='test_doc',
            sectionPath=['Chapter 1'],
            page=2,
            elementType='paragraph',
            text='Second paragraph text with more content.',
            elementId='test_doc-0003',
            accessLevel='internal',
        ),
    ]


@pytest.fixture
def sample_chunk():
    return Chunk(
        chunkId='chunk_001',
        docName='test_doc',
        sectionPath=['Chapter 1'],
        pages=[1, 2],
        text='Chapter 1: First paragraph text. Second paragraph text.',
        elementIds=['test_doc-0001', 'test_doc-0002'],
        accessLevel='internal',
    )
