import pytest
from unittest.mock import patch, MagicMock
import json
from pathlib import Path
import tempfile

from embedding import embedTexts, embedQuery, loadChunks, writeEmbedding


class TestEmbedTexts:
    @patch('embedding._session.post')
    def test_successful_embed(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embeddings': [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        }
        mock_post.return_value = mock_response

        texts = ['text 1', 'text 2']
        result = embedTexts(texts)

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

    @patch('embedding._session.post')
    def test_embed_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Server error'
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError):
            embedTexts(['text'])

    @patch('embedding._session.post')
    def test_embed_single_text(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embeddings': [[0.1, 0.2, 0.3]]}
        mock_post.return_value = mock_response

        result = embedTexts(['single text'])
        assert len(result) == 1


class TestEmbedQuery:
    @patch('embedding.embedTexts')
    def test_embed_query_success(self, mock_embed):
        mock_embed.return_value = [[0.1, 0.2, 0.3]]
        result = embedQuery('test query')
        assert result == [0.1, 0.2, 0.3]

    @patch('embedding.embedTexts')
    def test_embed_query_nan_fallback(self, mock_embed):
        mock_embed.side_effect = [
            RuntimeError('ollama embed 500: NaN value detected'),
            [[0.1, 0.2, 0.3]]
        ]
        result = embedQuery('test query')
        assert result == [0.1, 0.2, 0.3]
        assert mock_embed.call_count == 2

    @patch('embedding.embedTexts')
    def test_embed_query_other_error(self, mock_embed):
        mock_embed.side_effect = RuntimeError('Connection failed')
        with pytest.raises(RuntimeError):
            embedQuery('test query')


class TestLoadChunks:
    def test_load_chunks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_dir = Path(tmpdir) / 'chunks'
            chunks_dir.mkdir()

            chunk_data = [
                {
                    'chunkId': 'chunk_001',
                    'docName': 'test_doc',
                    'text': 'Sample chunk text',
                    'sectionPath': ['Section 1'],
                    'pages': [1],
                    'elementIds': ['elem_001'],
                    'accessLevel': 'internal',
                },
                {
                    'chunkId': 'chunk_002',
                    'docName': 'test_doc',
                    'text': 'Another chunk',
                    'sectionPath': ['Section 2'],
                    'pages': [2],
                    'elementIds': ['elem_002'],
                    'accessLevel': 'internal',
                }
            ]

            chunk_file = chunks_dir / 'test_doc.json'
            chunk_file.write_text(json.dumps(chunk_data, ensure_ascii=False), encoding='utf-8')

            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)
                result = loadChunks('test_doc')
                assert len(result) == 2
                assert result[0]['chunkId'] == 'chunk_001'
                assert result[1]['chunkId'] == 'chunk_002'
            finally:
                os.chdir(original_cwd)

    def test_load_chunks_missing_file(self):
        with pytest.raises(FileNotFoundError):
            loadChunks('nonexistent_doc')


class TestWriteEmbedding:
    @patch('embedding.GraphDatabase.driver')
    def test_write_embedding(self, mock_driver_class):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()

        mock_driver_class.return_value = mock_driver
        mock_driver.__enter__.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        writeEmbedding(mock_tx, 'chunk_001', [0.1, 0.2, 0.3])

        mock_tx.run.assert_called_once()
        call_args = mock_tx.run.call_args
        assert 'MATCH' in call_args[0][0]
        assert call_args[1]['chunkId'] == 'chunk_001'
        assert call_args[1]['embedding'] == [0.1, 0.2, 0.3]


class TestEmbeddingIntegration:
    @patch('embedding.embedTexts')
    @patch('embedding.GraphDatabase.driver')
    def test_embed_doc_workflow(self, mock_driver_class, mock_embed):
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_dir = Path(tmpdir) / 'chunks'
            chunks_dir.mkdir()

            chunk_data = [
                {
                    'chunkId': 'chunk_001',
                    'docName': 'test_doc',
                    'text': 'Sample text for embedding',
                    'sectionPath': ['Section'],
                    'pages': [1],
                    'elementIds': ['elem_001'],
                    'accessLevel': 'internal',
                }
            ]

            chunk_file = chunks_dir / 'test_doc.json'
            chunk_file.write_text(json.dumps(chunk_data, ensure_ascii=False), encoding='utf-8')

            mock_embed.return_value = [[0.1, 0.2, 0.3]]
            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver_class.return_value = mock_driver
            mock_driver.__enter__.return_value = mock_driver
            mock_driver.session.return_value.__enter__.return_value = mock_session
            mock_session.execute_write = MagicMock()

            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)
                from embedding import embedDoc
                embedDoc('test_doc')

                mock_embed.assert_called_once()
                assert mock_session.execute_write.call_count >= 3
            finally:
                os.chdir(original_cwd)
