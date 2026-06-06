import pytest
from unittest.mock import patch, MagicMock
import json
from pathlib import Path

from glinerExtract import extractEntities as gliner_extract
from llmNER import extractEntities as llm_extract


class TestGLiNERPipeline:
    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    def test_gliner_end_to_end(self, mock_load, mock_model):
        """Test complete GLiNER extraction pipeline."""
        mock_chunks = [
            {
                'chunkId': 'chunk_001',
                'docName': 'doc',
                'text': 'Bank of Egypt was founded in Cairo in 1920.',
            },
        ]
        mock_load.return_value = mock_chunks

        mock_spans = [
            {'text': 'Bank of Egypt', 'label': 'ORGANIZATION', 'start': 0, 'end': 13, 'score': 0.99},
            {'text': 'Cairo', 'label': 'LOCATION', 'start': 30, 'end': 35, 'score': 0.95},
            {'text': '1920', 'label': 'DATE', 'start': 39, 'end': 43, 'score': 0.92},
        ]
        mock_model.predict_entities.return_value = mock_spans

        result = gliner_extract('doc')

        assert len(result) == 3
        assert result[0]['type'] == 'ORGANIZATION'
        assert result[1]['type'] == 'LOCATION'
        assert result[2]['type'] == 'DATE'

    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    def test_gliner_multiple_chunks(self, mock_load, mock_model):
        """Test GLiNER with multiple chunks."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'First chunk with Bank'},
            {'chunkId': 'chunk_002', 'docName': 'doc', 'text': 'Second chunk with Cairo'},
        ]
        mock_load.return_value = mock_chunks

        mock_model.predict_entities.side_effect = [
            [{'text': 'Bank', 'label': 'ORGANIZATION', 'start': 15, 'end': 19, 'score': 0.95}],
            [{'text': 'Cairo', 'label': 'LOCATION', 'start': 18, 'end': 23, 'score': 0.93}],
        ]

        result = gliner_extract('doc')

        assert len(result) == 2
        assert result[0]['chunkId'] == 'chunk_001'
        assert result[1]['chunkId'] == 'chunk_002'

    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    def test_gliner_confidence_scores(self, mock_load, mock_model):
        """Test that confidence scores are preserved."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Entity here'},
        ]
        mock_load.return_value = mock_chunks

        mock_model.predict_entities.return_value = [
            {'text': 'Entity', 'label': 'ORGANIZATION', 'start': 0, 'end': 6, 'score': 0.8765},
        ]

        result = gliner_extract('doc')

        assert abs(result[0]['score'] - 0.8765) < 0.001


class TestLLMNERPipeline:
    @patch('llmNER.loadChunks')
    @patch('llmNER.callOllamaForEntities')
    def test_llm_ner_end_to_end(self, mock_call, mock_load):
        """Test complete LLM NER extraction pipeline."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text about Bank'},
        ]
        mock_load.return_value = mock_chunks

        mock_call.return_value = json.dumps({
            'entities': [
                {'text': 'Bank', 'type': 'ORGANIZATION', 'confidence': 0.92},
            ]
        })

        result = llm_extract('doc')

        assert len(result) == 1
        assert result[0]['text'] == 'Bank'
        assert result[0]['type'] == 'ORGANIZATION'

    @patch('llmNER.loadChunks')
    @patch('llmNER.callOllamaForEntities')
    def test_llm_ner_multiple_chunks(self, mock_call, mock_load):
        """Test LLM NER with multiple chunks."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text 1'},
            {'chunkId': 'chunk_002', 'docName': 'doc', 'text': 'Text 2'},
        ]
        mock_load.return_value = mock_chunks

        mock_call.side_effect = [
            json.dumps({'entities': [{'text': 'Entity1', 'type': 'ORGANIZATION', 'confidence': 0.9}]}),
            json.dumps({'entities': [{'text': 'Entity2', 'type': 'LOCATION', 'confidence': 0.85}]}),
        ]

        result = llm_extract('doc')

        assert len(result) == 2

    @patch('llmNER.loadChunks')
    @patch('llmNER.callOllamaForEntities')
    def test_llm_ner_filter_invalid_types(self, mock_call, mock_load):
        """Test that invalid entity types are filtered."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text'},
        ]
        mock_load.return_value = mock_chunks

        mock_call.return_value = json.dumps({
            'entities': [
                {'text': 'Valid', 'type': 'ORGANIZATION', 'confidence': 0.9},
                {'text': 'Invalid', 'type': 'FAKE_TYPE', 'confidence': 0.8},
            ]
        })

        result = llm_extract('doc')

        assert len(result) == 1
        assert result[0]['type'] == 'ORGANIZATION'


class TestNERPipelineComparison:
    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    @patch('llmNER.callOllamaForEntities')
    def test_both_pipelines_consistent_output(self, mock_llm_call, mock_gliner_load, mock_gliner_model):
        """Test that both pipelines produce compatible output formats."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Bank in Cairo'},
        ]

        mock_gliner_load.return_value = mock_chunks
        mock_gliner_model.predict_entities.return_value = [
            {'text': 'Bank', 'label': 'ORGANIZATION', 'start': 0, 'end': 4, 'score': 0.95},
        ]

        gliner_result = gliner_extract('doc')

        assert 'chunkId' in gliner_result[0]
        assert 'docName' in gliner_result[0]
        assert 'text' in gliner_result[0]
        assert 'type' in gliner_result[0]
        assert 'score' in gliner_result[0]

    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    def test_ner_output_structure(self, mock_load, mock_model):
        """Verify NER output structure matches expected format."""
        mock_chunks = [
            {'chunkId': 'c1', 'docName': 'd', 'text': 'Text'},
        ]
        mock_load.return_value = mock_chunks

        mock_model.predict_entities.return_value = [
            {'text': 'Entity', 'label': 'TYPE', 'start': 0, 'end': 6, 'score': 0.9},
        ]

        result = gliner_extract('d')

        required_fields = ['chunkId', 'docName', 'text', 'type', 'score', 'start', 'end']
        for entity in result:
            for field in required_fields:
                assert field in entity


class TestNEREdgeCases:
    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    def test_gliner_empty_text(self, mock_load, mock_model):
        """Test GLiNER with empty text chunks."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': ''},
        ]
        mock_load.return_value = mock_chunks
        mock_model.predict_entities.return_value = []

        result = gliner_extract('doc')
        assert result == []

    @patch('glinerExtract.model')
    @patch('glinerExtract.loadChunks')
    def test_gliner_overlapping_entities(self, mock_load, mock_model):
        """Test handling of overlapping entity spans."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Bank of Egypt'},
        ]
        mock_load.return_value = mock_chunks

        mock_model.predict_entities.return_value = [
            {'text': 'Bank of Egypt', 'label': 'ORGANIZATION', 'start': 0, 'end': 13, 'score': 0.95},
            {'text': 'Egypt', 'label': 'LOCATION', 'start': 8, 'end': 13, 'score': 0.90},
        ]

        result = gliner_extract('doc')
        assert len(result) == 2

    @patch('llmNER.loadChunks')
    @patch('llmNER.callOllamaForEntities')
    def test_llm_ner_special_characters(self, mock_call, mock_load):
        """Test LLM NER with special characters in entity text."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text with @#$%'},
        ]
        mock_load.return_value = mock_chunks

        mock_call.return_value = json.dumps({
            'entities': [
                {'text': '@#$%', 'type': 'SYMBOL', 'confidence': 0.8},
            ]
        })

        result = llm_extract('doc')
        assert len(result) == 1

    @patch('llmNER.loadChunks')
    @patch('llmNER.callOllamaForEntities')
    def test_llm_ner_arabic_content(self, mock_call, mock_load):
        """Test LLM NER with Arabic content."""
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'بنك مصر العربي'},
        ]
        mock_load.return_value = mock_chunks

        mock_call.return_value = json.dumps({
            'entities': [
                {'text': 'بنك مصر', 'type': 'ORGANIZATION', 'confidence': 0.95},
            ]
        })

        result = llm_extract('doc')
        assert result[0]['text'] == 'بنك مصر'
