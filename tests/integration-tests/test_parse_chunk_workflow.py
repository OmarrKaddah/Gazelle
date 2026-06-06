import pytest
import json
from pathlib import Path


class TestParseChunkIntegration:
    """Integration tests for parse → chunk workflow."""

    @pytest.mark.integration
    def test_full_parse_chunk_workflow(self, integration_data_dir, parsed_document, chunked_document):
        """Test complete workflow from parsing to chunking."""
        assert len(parsed_document) > 0
        assert len(chunked_document) > 0

    @pytest.mark.integration
    def test_parsed_elements_loadable(self, integration_data_dir, parsed_document):
        """Verify parsed elements are saved and loadable."""
        import os
        original_cwd = Path.cwd()
        try:
            os.chdir(integration_data_dir)
            from parser import loadParsed

            loaded = loadParsed('banking_guide')
            assert len(loaded) == len(parsed_document)
            assert loaded[0].docName == 'banking_guide'
        finally:
            os.chdir(original_cwd)

    @pytest.mark.integration
    def test_chunks_saved_correctly(self, integration_data_dir, chunked_document):
        """Verify chunks are saved in correct JSON format."""
        import os
        original_cwd = Path.cwd()
        try:
            os.chdir(integration_data_dir)

            chunk_file = Path('chunks') / 'banking_guide.json'
            assert chunk_file.exists()

            saved_chunks = json.loads(chunk_file.read_text(encoding='utf-8'))
            assert len(saved_chunks) == len(chunked_document)

            for chunk in saved_chunks:
                assert 'chunkId' in chunk
                assert 'docName' in chunk
                assert 'text' in chunk
                assert chunk['docName'] == 'banking_guide'
        finally:
            os.chdir(original_cwd)

    @pytest.mark.integration
    def test_section_hierarchy_preserved(self, parsed_document, chunked_document):
        """Verify section hierarchy is preserved through pipeline."""
        top_level_sections = set()
        for elem in parsed_document:
            if elem.sectionPath:
                top_level_sections.add(elem.sectionPath[0])

        chunk_sections = set()
        for chunk in chunked_document:
            if chunk.sectionPath:
                chunk_sections.add(chunk.sectionPath[0])

        assert len(chunk_sections) > 0
        assert chunk_sections.issubset(top_level_sections)

    @pytest.mark.integration
    def test_element_ids_tracked_through_chunks(self, parsed_document, chunked_document):
        """Verify element IDs are tracked through chunking."""
        parsed_ids = set(e.elementId for e in parsed_document)
        chunk_element_ids = set()
        for chunk in chunked_document:
            chunk_element_ids.update(chunk.elementIds)

        assert len(chunk_element_ids) > 0
        assert chunk_element_ids.issubset(parsed_ids)

    @pytest.mark.integration
    def test_page_numbers_collected(self, chunked_document):
        """Verify page numbers are collected in chunks."""
        pages = set()
        for chunk in chunked_document:
            pages.update(chunk.pages)

        assert len(pages) > 1

    @pytest.mark.integration
    def test_text_content_preserved(self, parsed_document, chunked_document):
        """Verify text content is preserved through chunking."""
        parsed_text = ''.join(e.text for e in parsed_document if e.elementType != 'heading')
        chunked_text = ''.join(c.text for c in chunked_document)

        assert len(chunked_text) > 0
        assert parsed_text.replace(' ', '') in chunked_text.replace(' ', '')

    @pytest.mark.integration
    def test_metadata_consistency(self, chunked_document):
        """Verify chunk metadata is consistent."""
        for chunk in chunked_document:
            assert chunk.chunkId
            assert chunk.docName
            assert chunk.text
            assert isinstance(chunk.sectionPath, list)
            assert isinstance(chunk.pages, list)
            assert isinstance(chunk.elementIds, list)
            assert chunk.accessLevel

    @pytest.mark.integration
    def test_chunks_are_valid(self, chunked_document):
        """Verify all chunks have valid structure."""
        for i, chunk in enumerate(chunked_document):
            assert chunk.chunkId, f"Chunk {i} missing chunkId"
            assert chunk.text.strip(), f"Chunk {i} has empty text"
            assert len(chunk.elementIds) > 0, f"Chunk {i} has no elementIds"

    @pytest.mark.integration
    def test_document_name_consistency(self, parsed_document, chunked_document):
        """Verify document name is consistent."""
        parsed_docs = set(e.docName for e in parsed_document)
        chunk_docs = set(c.docName for c in chunked_document)

        assert parsed_docs == chunk_docs
        assert parsed_docs == {'banking_guide'}
