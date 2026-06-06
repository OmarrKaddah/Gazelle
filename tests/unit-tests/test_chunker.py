import pytest
from chunker import (
    Chunk, countTokens, collectPages, splitText, expandElement,
    tailText, groupBySection, packElements, buildChunk
)
from parser import ParsedElement


class TestCountTokens:
    def test_empty_string(self):
        assert countTokens('') == 0

    def test_single_word(self):
        tokens = countTokens('hello')
        assert tokens > 0

    def test_multiple_words(self):
        text = 'The quick brown fox jumps over the lazy dog'
        tokens = countTokens(text)
        assert tokens > 0

    def test_special_characters(self):
        text = 'Test with special chars: !@#$%^&*()'
        tokens = countTokens(text)
        assert tokens > 0


class TestCollectPages:
    def test_no_pages(self):
        elements = [
            ParsedElement('doc', [], None, 'p', 'text', 'id1', 'internal'),
            ParsedElement('doc', [], None, 'p', 'text', 'id2', 'internal'),
        ]
        assert collectPages(elements) == []

    def test_single_page(self):
        elements = [
            ParsedElement('doc', [], 1, 'p', 'text', 'id1', 'internal'),
            ParsedElement('doc', [], 1, 'p', 'text', 'id2', 'internal'),
        ]
        assert collectPages(elements) == [1]

    def test_multiple_pages(self):
        elements = [
            ParsedElement('doc', [], 1, 'p', 'text', 'id1', 'internal'),
            ParsedElement('doc', [], 2, 'p', 'text', 'id2', 'internal'),
            ParsedElement('doc', [], 3, 'p', 'text', 'id3', 'internal'),
        ]
        assert collectPages(elements) == [1, 2, 3]

    def test_duplicate_pages(self):
        elements = [
            ParsedElement('doc', [], 1, 'p', 'text', 'id1', 'internal'),
            ParsedElement('doc', [], 1, 'p', 'text', 'id2', 'internal'),
            ParsedElement('doc', [], 2, 'p', 'text', 'id3', 'internal'),
        ]
        assert collectPages(elements) == [1, 2]


class TestSplitText:
    def test_short_text(self):
        text = 'Short text'
        result = splitText(text, target=100)
        assert result == ['Short text']

    def test_multiline_split(self):
        text = 'Line 1\nLine 2\nLine 3'
        result = splitText(text, target=10)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_sentence_split(self):
        text = 'First sentence. Second sentence. Third sentence.'
        result = splitText(text, target=5)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_arabic_text(self):
        text = 'نص عربي أول. نص عربي ثاني.'
        result = splitText(text, target=5)
        assert isinstance(result, list)


class TestTailText:
    def test_short_text(self):
        text = 'Short text.'
        result = tailText(text, 100)
        assert result == 'Short text.'

    def test_long_text(self):
        text = 'First sentence. Second sentence. Third sentence. Fourth sentence.'
        result = tailText(text, 5)
        assert len(result) > 0
        assert 'Fourth' in result or 'Third' in result

    def test_empty_string(self):
        result = tailText('', 10)
        assert result == ''


class TestGroupBySection:
    def test_single_section(self, sample_elements):
        groups = groupBySection(sample_elements)
        assert len(groups) == 1
        assert groups[0][0] == ['Chapter 1']

    def test_section_change(self):
        elements = [
            ParsedElement('doc', ['Section 1'], 1, 'p', 'text 1', 'id1', 'internal'),
            ParsedElement('doc', ['Section 1'], 1, 'p', 'text 2', 'id2', 'internal'),
            ParsedElement('doc', ['Section 2'], 2, 'p', 'text 3', 'id3', 'internal'),
        ]
        groups = groupBySection(elements)
        assert len(groups) == 2
        assert groups[0][0] == ['Section 1']
        assert groups[1][0] == ['Section 2']

    def test_skip_headings(self):
        elements = [
            ParsedElement('doc', [], 1, 'heading', 'Heading', 'id1', 'internal'),
            ParsedElement('doc', [], 1, 'p', 'text', 'id2', 'internal'),
        ]
        groups = groupBySection(elements)
        assert len(groups) == 1
        assert len(groups[0][1]) == 1


class TestPackElements:
    def test_single_element(self, sample_element):
        result = packElements([sample_element], target=100)
        assert len(result) > 0
        assert all(isinstance(group, list) for group in result)

    def test_multiple_elements(self, sample_elements):
        result = packElements(sample_elements, target=50)
        assert len(result) > 0
        assert all(isinstance(group, list) for group in result)

    def test_table_handling(self):
        elements = [
            ParsedElement('doc', [], 1, 'table', 'table content', 'id1', 'internal'),
            ParsedElement('doc', [], 1, 'p', 'text', 'id2', 'internal'),
        ]
        result = packElements(elements, target=100)
        assert len(result) > 0


class TestBuildChunk:
    def test_build_basic_chunk(self, sample_elements):
        chunk = buildChunk(sample_elements[1:2], ['Section'], 'test_doc', 1)
        assert isinstance(chunk, Chunk)
        assert chunk.chunkId == 'test_doc-c0001'
        assert chunk.docName == 'test_doc'
        assert chunk.sectionPath == ['Section']

    def test_chunk_with_prefix(self, sample_elements):
        chunk = buildChunk(sample_elements[1:2], ['Chapter 1'], 'doc', 5)
        assert 'Chapter 1:' in chunk.text

    def test_chunk_multiple_elements(self, sample_elements):
        chunk = buildChunk(sample_elements[1:], ['Ch1'], 'doc', 1)
        assert len(chunk.elementIds) > 1
        assert chunk.pages == [1, 2]


class TestChunkDataclass:
    def test_chunk_creation(self, sample_chunk):
        assert sample_chunk.chunkId == 'chunk_001'
        assert sample_chunk.docName == 'test_doc'
        assert len(sample_chunk.pages) == 2

    def test_chunk_empty_pages(self):
        chunk = Chunk(
            chunkId='id',
            docName='doc',
            sectionPath=[],
            pages=[],
            text='content',
            elementIds=[],
            accessLevel='internal',
        )
        assert chunk.pages == []
