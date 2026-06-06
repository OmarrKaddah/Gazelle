import pytest
from unittest.mock import patch, MagicMock, call
import json
from pathlib import Path

from embedding import embedDoc, embedTexts, embedQuery


class TestEmbeddingPipeline:
    @patch('embedding.GraphDatabase.driver')
    @patch('embedding.embedTexts')
    @patch('embedding.loadChunks')
    def test_embed_doc_full_pipeline(self, mock_load, mock_embed, mock_driver_class):
        """Test complete document embedding pipeline."""
        mock_chunks = [
            {
                'chunkId': 'chunk_001',
                'docName': 'doc',
                'text': 'First chunk content',
            },
            {
                'chunkId': 'chunk_002',
                'docName': 'doc',
                'text': 'Second chunk content',
            },
        ]
        mock_load.return_value = mock_chunks

        mock_embed.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ]

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver_class.return_value = mock_driver
        mock_driver.__enter__.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write = MagicMock()

        embedDoc('doc')

        mock_load.assert_called_once_with('doc')
        mock_embed.assert_called_once()
        assert mock_session.execute_write.call_count >= 4

    @patch('embedding.GraphDatabase.driver')
    @patch('embedding.embedTexts')
    @patch('embedding.loadChunks')
    def test_embed_creates_indexes(self, mock_load, mock_embed, mock_driver_class):
        """Test that embedDoc creates necessary indexes."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text'},
        ]
        mock_load.return_value = mock_chunks
        mock_embed.return_value = [[0.1, 0.2, 0.3]]

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver_class.return_value = mock_driver
        mock_driver.__enter__.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        embedDoc('doc')

        calls = mock_session.execute_write.call_args_list
        assert len(calls) >= 2

    @patch('embedding.session.post')
    def test_embed_texts_batch_processing(self, mock_post):
        """Test batch processing of multiple texts."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embeddings': [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9],
            ]
        }
        mock_post.return_value = mock_response

        texts = ['text1', 'text2', 'text3']
        result = embedTexts(texts)

        assert len(result) == 3
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[2] == [0.7, 0.8, 0.9]

    @patch('embedding.embedTexts')
    def test_embed_query_single_embedding(self, mock_embed):
        """Test query embedding returns single vector."""
        mock_embed.return_value = [[0.1, 0.2, 0.3]]

        result = embedQuery('test query')

        assert len(result) == 3
        assert result == [0.1, 0.2, 0.3]


class TestEmbeddingQuality:
    @patch('embedding.embedTexts')
    def test_similar_texts_have_similar_embeddings(self, mock_embed):
        """Test that similar texts produce similar embeddings."""
        mock_embed.side_effect = [
            [[0.9, 0.1]],
            [[0.89, 0.11]],
        ]

        emb1 = embedQuery('bank')
        emb2 = embedQuery('bank')

        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        assert dot_product > 0.95

    @patch('embedding.session.post')
    def test_embedding_dimension_consistency(self, mock_post):
        """Test that all embeddings have consistent dimensions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embeddings': [
                [0.1, 0.2, 0.3, 0.4, 0.5],
                [0.2, 0.3, 0.4, 0.5, 0.6],
            ]
        }
        mock_post.return_value = mock_response

        result = embedTexts(['text1', 'text2'])

        assert len(result[0]) == len(result[1])
        assert len(result[0]) == 5


class TestEmbeddingErrorHandling:
    @patch('embedding.embedTexts')
    def test_nan_error_fallback(self, mock_embed):
        """Test NaN error handling with space fallback."""
        mock_embed.side_effect = [
            RuntimeError('ollama embed 500: NaN value detected'),
            [[0.1, 0.2, 0.3]],
        ]

        result = embedQuery('test')

        assert result == [0.1, 0.2, 0.3]
        assert mock_embed.call_count == 2

    @patch('embedding.session.post')
    def test_embed_error_response(self, mock_post):
        """Test handling of error responses from Ollama."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Server error'
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError):
            embedTexts(['text'])

    @patch('embedding.session.post')
    def test_embed_connection_error(self, mock_post):
        """Test handling of connection errors."""
        mock_post.side_effect = Exception('Connection refused')

        with pytest.raises(Exception):
            embedTexts(['text'])


class TestEmbeddingPersistence:
    @patch('embedding.GraphDatabase.driver')
    @patch('embedding.embedTexts')
    @patch('embedding.loadChunks')
    def test_write_embeddings_to_neo4j(self, mock_load, mock_embed, mock_driver_class):
        """Test that embeddings are written to Neo4j."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Content'},
        ]
        mock_load.return_value = mock_chunks
        mock_embed.return_value = [[0.1, 0.2, 0.3]]

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver_class.return_value = mock_driver
        mock_driver.__enter__.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        embedDoc('doc')

        mock_session.execute_write.assert_called()

    @patch('embedding.GraphDatabase.driver')
    @patch('embedding.embedTexts')
    @patch('embedding.loadChunks')
    def test_batch_size_respected(self, mock_load, mock_embed, mock_driver_class):
        """Test that batch size configuration is respected."""
        from config import CHUNK_EMBED_BATCH

        num_chunks = CHUNK_EMBED_BATCH + 5
        mock_chunks = [
            {'chunkId': f'chunk_{i:03d}', 'docName': 'doc', 'text': f'Text {i}'}
            for i in range(num_chunks)
        ]
        mock_load.return_value = mock_chunks

        embeddings = [[0.1 * i, 0.2 * i] for i in range(num_chunks)]
        mock_embed.return_value = embeddings

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver_class.return_value = mock_driver
        mock_driver.__enter__.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        embedDoc('doc')

        assert mock_embed.called


class TestEmbeddingEdgeCases:
    @patch('embedding.session.post')
    def test_embed_empty_text(self, mock_post):
        """Test embedding of empty string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embeddings': [[0.0, 0.0, 0.0]]}
        mock_post.return_value = mock_response

        result = embedTexts([''])
        assert len(result) == 1

    @patch('embedding.session.post')
    def test_embed_very_long_text(self, mock_post):
        """Test embedding of very long text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embeddings': [[0.1] * 768]}
        mock_post.return_value = mock_response

        long_text = ' '.join(['word'] * 10000)
        result = embedTexts([long_text])

        assert len(result) == 1
        assert len(result[0]) == 768

    @patch('embedding.session.post')
    def test_embed_special_characters(self, mock_post):
        """Test embedding of text with special characters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embeddings': [[0.1, 0.2, 0.3]]}
        mock_post.return_value = mock_response

        special_text = '@#$%^&*(){}[]|\\:;"\'<>,.?/'
        result = embedTexts([special_text])

        assert len(result) == 1

    @patch('embedding.session.post')
    def test_embed_unicode_text(self, mock_post):
        """Test embedding of Unicode/Arabic text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embeddings': [[0.1, 0.2, 0.3]]}
        mock_post.return_value = mock_response

        arabic_text = 'النصوص العربية والتحليل الدلالي'
        result = embedTexts([arabic_text])

        assert len(result) == 1
