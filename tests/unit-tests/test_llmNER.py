import pytest
from unittest.mock import patch, MagicMock
import json
from pathlib import Path
import tempfile

from llmNER import (
    buildEntityExtractionPrompt,
    callOllamaForEntities,
    extractEntitiesFromChunk,
    extractEntities,
    dumpEntities,
)


class TestBuildEntityExtractionPrompt:
    def test_prompt_contains_text(self):
        text = 'The Central Bank of Egypt'
        prompt = buildEntityExtractionPrompt(text)
        assert text in prompt

    def test_prompt_contains_instructions(self):
        text = 'Sample text'
        prompt = buildEntityExtractionPrompt(text)
        assert 'Extract' in prompt or 'extract' in prompt
        assert 'JSON' in prompt or 'json' in prompt

    def test_prompt_contains_entity_types(self):
        text = 'Sample text'
        prompt = buildEntityExtractionPrompt(text)
        assert 'ENTITY TYPES' in prompt or 'Entity' in prompt

    def test_prompt_well_formed(self):
        text = 'Test text'
        prompt = buildEntityExtractionPrompt(text)
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert '{' in prompt
        assert '}' in prompt


class TestCallOllamaForEntities:
    @patch('llmNER.requests.post')
    def test_call_ollama_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [
                {
                    'message': {
                        'content': '{"entities": [{"text": "Entity", "type": "TYPE", "confidence": 0.9}]}'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        prompt = 'Test prompt'
        result = callOllamaForEntities(prompt)

        assert '{"entities"' in result
        assert '"type"' in result

    @patch('llmNER.requests.post')
    def test_call_ollama_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception('Connection error')
        mock_post.return_value = mock_response

        with pytest.raises(Exception):
            callOllamaForEntities('prompt')

    @patch('llmNER.requests.post')
    def test_call_ollama_empty_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '{"entities": []}'}}]
        }
        mock_post.return_value = mock_response

        result = callOllamaForEntities('prompt')
        assert '{"entities": []}' in result


class TestExtractEntitiesFromChunk:
    @patch('llmNER.callOllamaForEntities')
    @patch('llmNER.buildEntityExtractionPrompt')
    def test_extract_calls_ollama(self, mock_prompt, mock_call):
        mock_prompt.return_value = 'Test prompt'
        mock_call.return_value = json.dumps({'entities': []})

        chunk = {
            'chunkId': 'chunk_001',
            'docName': 'doc',
            'text': 'Text',
        }

        result = extractEntitiesFromChunk(chunk)

        mock_prompt.assert_called_once()
        mock_call.assert_called_once()
        assert result == []


class TestExtractEntities:
    @patch('llmNER.loadChunks')
    @patch('llmNER.extractEntitiesFromChunk')
    def test_extract_entities_success(self, mock_extract_chunk, mock_load):
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text 1'},
            {'chunkId': 'chunk_002', 'docName': 'doc', 'text': 'Text 2'},
        ]
        mock_load.return_value = mock_chunks

        mock_extract_chunk.side_effect = [
            [
                {
                    'chunkId': 'chunk_001',
                    'docName': 'doc',
                    'text': 'Entity1',
                    'type': 'ORGANIZATION',
                    'score': 0.9,
                }
            ],
            [
                {
                    'chunkId': 'chunk_002',
                    'docName': 'doc',
                    'text': 'Entity2',
                    'type': 'LOCATION',
                    'score': 0.85,
                }
            ],
        ]

        result = extractEntities('doc')

        assert len(result) == 2
        assert mock_extract_chunk.call_count == 2

    @patch('llmNER.loadChunks')
    @patch('llmNER.extractEntitiesFromChunk')
    def test_extract_entities_empty(self, mock_extract_chunk, mock_load):
        mock_load.return_value = []
        result = extractEntities('doc')
        assert result == []

    @patch('llmNER.loadChunks')
    @patch('llmNER.extractEntitiesFromChunk')
    def test_extract_entities_accumulates(self, mock_extract_chunk, mock_load):
        mock_chunks = [
            {'chunkId': 'chunk_001', 'docName': 'doc', 'text': 'Text'},
        ]
        mock_load.return_value = mock_chunks

        mock_extract_chunk.return_value = [
            {
                'chunkId': 'chunk_001',
                'docName': 'doc',
                'text': 'Entity',
                'type': 'ORGANIZATION',
                'score': 0.9,
            }
        ]

        result = extractEntities('doc')

        assert len(result) == 1


class TestDumpEntities:
    def test_dump_entities_file_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                entities = [
                    {
                        'chunkId': 'chunk_001',
                        'docName': 'doc',
                        'text': 'Entity',
                        'type': 'ORGANIZATION',
                        'score': 0.9,
                        'start': 0,
                        'end': 6,
                    },
                ]

                dumpEntities(entities, 'doc')

                output_file = Path('extractions') / 'doc_entities.json'
                assert output_file.exists()

                saved = json.loads(output_file.read_text(encoding='utf-8'))
                assert len(saved) == 1
                assert saved[0]['text'] == 'Entity'

            finally:
                os.chdir(original_cwd)

    def test_dump_entities_arabic_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                entities = [
                    {
                        'chunkId': 'chunk_001',
                        'docName': 'doc',
                        'text': 'بنك مصر',
                        'type': 'ORGANIZATION',
                        'score': 0.95,
                        'start': 0,
                        'end': 7,
                    },
                ]

                dumpEntities(entities, 'doc')

                output_file = Path('extractions') / 'doc_entities.json'
                content = output_file.read_text(encoding='utf-8')
                assert 'بنك مصر' in content

            finally:
                os.chdir(original_cwd)
