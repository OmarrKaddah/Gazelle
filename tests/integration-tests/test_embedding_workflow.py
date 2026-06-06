import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestEmbeddingWorkflow:
    """Integration tests for embedding pipeline."""

    @pytest.mark.integration
    @patch('embedding.GraphDatabase.driver')
    @patch('embedding.embedBatch')
    def test_embed_doc_workflow(self, mock_embed_batch, mock_driver_class, integration_data_dir, chunked_document):
        """Test complete document embedding workflow."""
        import os
        original_cwd = Path.cwd()
        try:
            os.chdir(integration_data_dir)

            mock_embed_batch.return_value = [[0.1 * i for i in range(5)] for _ in chunked_document]

            mock_driver = MagicMock()
            mock_session = MagicMock()
            mock_driver_class.return_value = mock_driver
            mock_driver.__enter__.return_value = mock_driver
            mock_driver.session.return_value.__enter__.return_value = mock_session

            from embedding import embedDoc
            embedDoc('banking_guide')

            mock_driver.assert_called()
            mock_session.execute_write.assert_called()

        finally:
            os.chdir(original_cwd)

    @pytest.mark.integration
    def test_token_counting_consistency(self, chunked_document):
        """Verify token counting is consistent across chunks."""
        from chunker import countTokens

        token_counts = []
        for chunk in chunked_document:
            tokens = countTokens(chunk.text)
            token_counts.append(tokens)
            assert tokens > 0

        assert len(token_counts) == len(chunked_document)
        assert all(t > 0 for t in token_counts)

    @pytest.mark.integration
    @patch('embedding._session.post')
    def test_embedding_dimension_consistency(self, mock_post, chunked_document):
        """Test embedding dimensions are consistent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embeddings': [[0.1 * i for i in range(768)] for _ in range(len(chunked_document))]
        }
        mock_post.return_value = mock_response

        from embedding import embedTexts
        texts = [c.text for c in chunked_document]
        embeddings = embedTexts(texts)

        assert len(embeddings) == len(chunked_document)
        assert all(len(emb) == 768 for emb in embeddings)

    @pytest.mark.integration
    def test_chunks_have_required_fields(self, chunked_document):
        """Verify chunks have all required fields for embedding."""
        for chunk in chunked_document:
            assert hasattr(chunk, 'chunkId')
            assert hasattr(chunk, 'text')
            assert chunk.chunkId is not None
            assert len(chunk.text) > 0

    @pytest.mark.integration
    @patch('embedding._session.post')
    def test_query_embedding(self, mock_post):
        """Test query embedding works correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'embeddings': [[0.1, 0.2, 0.3]]}
        mock_post.return_value = mock_response

        from embedding import embedQuery
        result = embedQuery('test query')

        assert isinstance(result, list)
        assert len(result) == 3
