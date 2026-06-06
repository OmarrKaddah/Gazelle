import pytest
from pathlib import Path

from parser import ParsedElement
from chunker import chunkDoc, dumpChunks


class TestParserChunkerPipeline:
    def test_parse_to_chunk_flow(self, sample_parsed_elements, temp_data_dir):
        """Test full flow from parsed elements to chunks."""
        elements = sample_parsed_elements
        chunks = chunkDoc(elements)

        assert len(chunks) > 0
        assert all(hasattr(c, 'chunkId') for c in chunks)
        assert all(hasattr(c, 'text') for c in chunks)
        assert all(c.docName == 'sample' for c in chunks)

    def test_chunker_preserves_document_info(self, sample_parsed_elements):
        """Verify chunker preserves document metadata."""
        chunks = chunkDoc(sample_parsed_elements)

        for chunk in chunks:
            assert chunk.docName == 'sample'
            assert chunk.accessLevel == 'internal'
            assert isinstance(chunk.elementIds, list)
            assert len(chunk.elementIds) > 0

    def test_chunker_handles_section_paths(self, sample_parsed_elements):
        """Test that section paths are properly maintained in chunks."""
        chunks = chunkDoc(sample_parsed_elements)

        for chunk in chunks:
            assert isinstance(chunk.sectionPath, list)
            if chunk.sectionPath:
                assert all(isinstance(s, str) for s in chunk.sectionPath)

    def test_chunk_output_format(self, sample_parsed_elements):
        """Verify chunk output has correct structure."""
        chunks = chunkDoc(sample_parsed_elements)

        for chunk in chunks:
            assert chunk.chunkId
            assert isinstance(chunk.chunkId, str)
            assert len(chunk.chunkId) > 0
            assert chunk.docName
            assert chunk.text
            assert isinstance(chunk.pages, list)

    def test_multiple_pages_collected(self, sample_parsed_elements):
        """Test that pages from multiple elements are collected."""
        chunks = chunkDoc(sample_parsed_elements)

        all_pages = set()
        for chunk in chunks:
            all_pages.update(chunk.pages)

        assert len(all_pages) > 1

    def test_element_ids_preserved(self, sample_parsed_elements):
        """Verify element IDs are tracked through chunking."""
        chunks = chunkDoc(sample_parsed_elements)

        original_ids = set(e.elementId for e in sample_parsed_elements if e.elementType != 'heading')
        chunk_ids = set()
        for chunk in chunks:
            chunk_ids.update(chunk.elementIds)

        assert len(chunk_ids) > 0
        assert chunk_ids.issubset(set(e.elementId for e in sample_parsed_elements))

    def test_chunk_text_includes_section_prefix(self, sample_parsed_elements):
        """Test that chunk text includes section prefix when available."""
        chunks = chunkDoc(sample_parsed_elements)

        prefixed_chunks = [c for c in chunks if c.sectionPath]
        for chunk in prefixed_chunks:
            section_name = chunk.sectionPath[-1]
            assert section_name in chunk.text or ':' in chunk.text[:50]

    def test_dumping_chunks_to_file(self, sample_parsed_elements, temp_data_dir):
        """Test dumping chunks to JSON file."""
        import os
        original_cwd = Path.cwd()
        try:
            os.chdir(temp_data_dir)
            chunks = chunkDoc(sample_parsed_elements)
            dumpChunks(chunks, 'sample')

            chunks_file = temp_data_dir / 'chunks' / 'sample.json'
            assert chunks_file.exists()

            import json
            saved_chunks = json.loads(chunks_file.read_text(encoding='utf-8'))
            assert len(saved_chunks) == len(chunks)
            assert all('chunkId' in c for c in saved_chunks)
            assert all('text' in c for c in saved_chunks)

        finally:
            os.chdir(original_cwd)

    def test_consistency_across_runs(self, sample_parsed_elements):
        """Test that chunking is deterministic."""
        chunks1 = chunkDoc(sample_parsed_elements)
        chunks2 = chunkDoc(sample_parsed_elements)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.chunkId == c2.chunkId
            assert c1.text == c2.text

    def test_empty_elements_handling(self):
        """Test that empty or heading-only elements are handled."""
        elements = [
            ParsedElement('doc', [], 1, 'heading', 'Title', 'id1', 'internal'),
            ParsedElement('doc', [], 1, 'heading', 'Subtitle', 'id2', 'internal'),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) == 0

    def test_mixed_element_types(self):
        """Test chunking with mixed element types."""
        elements = [
            ParsedElement('doc', ['Ch1'], 1, 'paragraph', 'Para text', 'id1', 'internal'),
            ParsedElement('doc', ['Ch1'], 1, 'list', '- Item 1\n- Item 2', 'id2', 'internal'),
            ParsedElement('doc', ['Ch1'], 2, 'table', 'Table content', 'id3', 'internal'),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) > 0

    def test_section_hierarchy_preservation(self, sample_parsed_elements):
        """Verify hierarchical section structure is preserved."""
        chunks = chunkDoc(sample_parsed_elements)

        section_paths = [tuple(c.sectionPath) for c in chunks if c.sectionPath]
        assert len(section_paths) > 0

        top_level = [p[0] for p in section_paths if p]
        assert len(set(top_level)) > 1


class TestChunkingEdgeCases:
    def test_very_long_section_path(self):
        """Test handling of deeply nested section paths."""
        long_path = ['Level' + str(i) for i in range(10)]
        elements = [
            ParsedElement('doc', long_path, 1, 'paragraph', 'Content', 'id1', 'internal'),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) == 1
        assert chunks[0].sectionPath == long_path

    def test_special_characters_in_text(self):
        """Test handling of special characters in element text."""
        elements = [
            ParsedElement(
                'doc',
                [],
                1,
                'paragraph',
                'Text with special chars: @#$%^&*()',
                'id1',
                'internal'
            ),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) > 0
        assert any(char in chunks[0].text for char in '@#$%^&*()')

    def test_unicode_content(self):
        """Test handling of Unicode/Arabic content."""
        elements = [
            ParsedElement(
                'doc',
                [],
                1,
                'paragraph',
                'محتوى باللغة العربية مع نصوص متعددة',
                'id1',
                'internal'
            ),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) > 0
        assert 'العربية' in chunks[0].text

    def test_very_large_element(self):
        """Test handling of very large text elements."""
        large_text = ' '.join(['word'] * 1000)
        elements = [
            ParsedElement('doc', [], 1, 'paragraph', large_text, 'id1', 'internal'),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) > 0

    def test_whitespace_handling(self):
        """Test handling of elements with only whitespace."""
        elements = [
            ParsedElement('doc', [], 1, 'paragraph', '   \n\n   ', 'id1', 'internal'),
        ]
        chunks = chunkDoc(elements)
        assert len(chunks) == 0
