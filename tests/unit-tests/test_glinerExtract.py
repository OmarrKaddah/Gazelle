import pytest
from unittest.mock import patch, MagicMock
import json
from pathlib import Path
import tempfile

from glinerExtract import loadChunks, extractEntities, dumpEntities


class TestLoadChunks:
    def test_load_chunks_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_dir = Path(tmpdir) / 'chunks'
            chunks_dir.mkdir()

            chunk_data = [
                {
                    'chunkId': 'chunk_001',
                    'docName': 'test_doc',
                    'text': 'Sample text',
                    'sectionPath': [],
                    'pages': [1],
                    'elementIds': ['elem_001'],
                    'accessLevel': 'internal',
                },
            ]

            chunk_file = chunks_dir / 'test_doc.json'
            chunk_file.write_text(json.dumps(chunk_data, ensure_ascii=False), encoding='utf-8')

            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)
                result = loadChunks('test_doc')
                assert len(result) == 1
                assert result[0]['chunkId'] == 'chunk_001'
            finally:
                os.chdir(original_cwd)

    def test_load_chunks_missing_file(self):
        with pytest.raises(FileNotFoundError):
            loadChunks('nonexistent')


class TestExtractEntitiesBasic:
    @patch('glinerExtract.loadChunks')
    def test_load_chunks_called(self, mock_load):
        """Test that extractEntities calls loadChunks."""
        mock_load.return_value = []
        result = extractEntities('test_doc')
        mock_load.assert_called_once_with('test_doc')
        assert result == []


class TestDumpEntities:
    def test_dump_entities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                entities = [
                    {
                        'chunkId': 'chunk_001',
                        'docName': 'test_doc',
                        'text': 'Entity 1',
                        'type': 'ORGANIZATION',
                        'score': 0.95,
                        'start': 0,
                        'end': 8,
                    },
                    {
                        'chunkId': 'chunk_002',
                        'docName': 'test_doc',
                        'text': 'Entity 2',
                        'type': 'LOCATION',
                        'score': 0.87,
                        'start': 0,
                        'end': 8,
                    },
                ]

                dumpEntities(entities, 'test_doc')

                output_file = Path('extractions') / 'test_doc_entities.json'
                assert output_file.exists()

                saved_data = json.loads(output_file.read_text(encoding='utf-8'))
                assert len(saved_data) == 2
                assert saved_data[0]['text'] == 'Entity 1'
                assert saved_data[1]['type'] == 'LOCATION'

            finally:
                os.chdir(original_cwd)

    def test_dump_entities_creates_directory(self):
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
                        'type': 'TYPE',
                        'score': 0.9,
                        'start': 0,
                        'end': 6,
                    },
                ]

                assert not (Path('extractions')).exists()
                dumpEntities(entities, 'doc')
                assert (Path('extractions')).exists()

            finally:
                os.chdir(original_cwd)

    def test_dump_entities_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                dumpEntities([], 'test_doc')

                output_file = Path('extractions') / 'test_doc_entities.json'
                assert output_file.exists()
                saved_data = json.loads(output_file.read_text(encoding='utf-8'))
                assert saved_data == []

            finally:
                os.chdir(original_cwd)

    def test_dump_entities_preserves_unicode(self):
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
                        'end': 8,
                    },
                ]

                dumpEntities(entities, 'doc')

                output_file = Path('extractions') / 'doc_entities.json'
                content = output_file.read_text(encoding='utf-8')
                assert 'بنك مصر' in content

            finally:
                os.chdir(original_cwd)
