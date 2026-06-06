import pytest
from unittest.mock import patch, MagicMock
from semantic_chunker import LocalEmbeddings, chunkDoc
from parser import ParsedElement
from chunker import Chunk


class TestLocalEmbeddings:
    @patch('semantic_chunker.SentenceTransformer')
    def test_initialization(self, mock_st):
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        embeddings = LocalEmbeddings('test-model')
        assert embeddings.model == mock_model

    @patch('semantic_chunker.SentenceTransformer')
    def test_embed_documents(self, mock_st):
        mock_model = MagicMock()
        mock_encoding = MagicMock()
        mock_encoding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = [mock_encoding, mock_encoding]
        mock_st.return_value = mock_model

        embeddings = LocalEmbeddings('test-model')
        texts = ['text 1', 'text 2']
        result = embeddings.embed_documents(texts)

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with(texts, show_progress_bar=False)

    @patch('semantic_chunker.SentenceTransformer')
    def test_embed_query(self, mock_st):
        mock_model = MagicMock()
        mock_encoding = MagicMock()
        mock_encoding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = [mock_encoding]
        mock_st.return_value = mock_model

        embeddings = LocalEmbeddings('test-model')
        result = embeddings.embed_query('test query')

        assert result == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with(['test query'])

    @patch('semantic_chunker.SentenceTransformer')
    def test_init_with_env_var(self, mock_st):
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        with patch.dict('os.environ', {'BGE_M3_PATH': 'baai/bge-m3'}):
            embeddings = LocalEmbeddings()
            mock_st.assert_called_once_with('baai/bge-m3')


class TestChunkDoc:
    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_empty_elements(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        elements = []
        result = chunkDoc(elements)

        assert result == []

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_skip_headings(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        elements = [
            ParsedElement('doc', [], 1, 'heading', 'Heading', 'id1', 'internal'),
        ]
        result = chunkDoc(elements)

        assert result == []

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_table_element(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        elements = [
            ParsedElement(
                'test_doc',
                ['Section'],
                1,
                'table',
                'Table content',
                'id1',
                'internal'
            ),
        ]
        result = chunkDoc(elements)

        assert len(result) == 1
        assert isinstance(result[0], Chunk)
        assert result[0].docName == 'test_doc'
        assert 'Table content' in result[0].text

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_paragraph_element(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        mock_doc = MagicMock()
        mock_doc.page_content = 'Chunked content'
        mock_splitter.create_documents.return_value = [mock_doc]

        elements = [
            ParsedElement(
                'test_doc',
                ['Section'],
                1,
                'paragraph',
                'Paragraph text',
                'id1',
                'internal'
            ),
        ]
        result = chunkDoc(elements)

        assert len(result) == 1
        assert isinstance(result[0], Chunk)
        assert 'Chunked content' in result[0].text

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_multiple_documents(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        mock_doc1 = MagicMock()
        mock_doc1.page_content = 'Content 1'
        mock_doc2 = MagicMock()
        mock_doc2.page_content = 'Content 2'
        mock_splitter.create_documents.return_value = [mock_doc1, mock_doc2]

        elements = [
            ParsedElement(
                'test_doc',
                [],
                1,
                'paragraph',
                'Text',
                'id1',
                'internal'
            ),
        ]
        result = chunkDoc(elements)

        assert len(result) == 2

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_with_section_prefix(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        mock_doc = MagicMock()
        mock_doc.page_content = 'Content'
        mock_splitter.create_documents.return_value = [mock_doc]

        elements = [
            ParsedElement(
                'test_doc',
                ['Chapter 1', 'Section 1.1'],
                1,
                'paragraph',
                'Text',
                'id1',
                'internal'
            ),
        ]
        result = chunkDoc(elements)

        assert len(result) == 1
        assert 'Section 1.1:' in result[0].text

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_empty_text_skipped(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings

        elements = [
            ParsedElement('test_doc', [], 1, 'paragraph', '   ', 'id1', 'internal'),
        ]
        result = chunkDoc(elements)

        assert len(result) == 0

    @patch('semantic_chunker.SemanticChunker')
    @patch('semantic_chunker.LocalEmbeddings')
    def test_chunk_preserves_metadata(self, mock_embeddings_class, mock_splitter_class):
        mock_embeddings = MagicMock()
        mock_embeddings_class.return_value = mock_embeddings
        mock_splitter = MagicMock()
        mock_splitter_class.return_value = mock_splitter

        mock_doc = MagicMock()
        mock_doc.page_content = 'Content'
        mock_splitter.create_documents.return_value = [mock_doc]

        elements = [
            ParsedElement(
                'my_doc',
                ['Ch1', 'Sec'],
                5,
                'paragraph',
                'Text',
                'elem_001',
                'confidential'
            ),
        ]
        result = chunkDoc(elements)

        assert len(result) == 1
        chunk = result[0]
        assert chunk.docName == 'my_doc'
        assert chunk.pages == [5]
        assert chunk.elementIds == ['elem_001']
        assert chunk.accessLevel == 'confidential'
