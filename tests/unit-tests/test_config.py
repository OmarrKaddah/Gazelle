import pytest
from unittest.mock import patch
import os


class TestConfigLoad:
    def test_config_module_imports(self):
        from config import (
            BGE_M3_PATH,
            CHUNK_TARGET_TOKENS,
            GLINER_MODEL,
            GLINER_THRESHOLD,
            NEO4J_URI,
            NEO4J_USER,
            NEO4J_PASSWORD,
            OLLAMA_EMBED_MODEL,
            OLLAMA_CHAT_MODEL,
        )

        assert isinstance(BGE_M3_PATH, str)
        assert isinstance(CHUNK_TARGET_TOKENS, int)
        assert isinstance(GLINER_MODEL, str)
        assert isinstance(GLINER_THRESHOLD, float)
        assert isinstance(NEO4J_URI, str)
        assert isinstance(NEO4J_USER, str)

    def test_default_values_exist(self):
        from config import (
            GLINER_THRESHOLD,
            CHUNK_TARGET_TOKENS,
        )

        assert GLINER_THRESHOLD > 0
        assert CHUNK_TARGET_TOKENS > 0

    def test_thresholds_in_range(self):
        from config import GLINER_THRESHOLD

        assert 0 <= GLINER_THRESHOLD <= 1


class TestEnvironmentVariables:
    @patch.dict(os.environ, {'NEO4J_URI': 'bolt://localhost:7687'})
    def test_neo4j_uri_env(self):
        import importlib
        import config
        importlib.reload(config)

        assert 'neo4j' in config.NEO4J_URI.lower() or 'bolt' in config.NEO4J_URI.lower()

    def test_config_has_model_settings(self):
        from config import OLLAMA_EMBED_MODEL, OLLAMA_CHAT_MODEL

        assert isinstance(OLLAMA_EMBED_MODEL, str)
        assert isinstance(OLLAMA_CHAT_MODEL, str)
        assert len(OLLAMA_EMBED_MODEL) > 0
        assert len(OLLAMA_CHAT_MODEL) > 0


class TestTokenizationConfig:
    def test_chunk_target_tokens_positive(self):
        from config import CHUNK_TARGET_TOKENS

        assert CHUNK_TARGET_TOKENS > 0


class TestModelConfiguration:
    def test_gliner_model_not_empty(self):
        from config import GLINER_MODEL

        assert GLINER_MODEL
        assert isinstance(GLINER_MODEL, str)
        assert len(GLINER_MODEL) > 0

    def test_bge_m3_path_not_empty(self):
        from config import BGE_M3_PATH

        assert BGE_M3_PATH
        assert isinstance(BGE_M3_PATH, str)

    def test_threshold_value(self):
        from config import GLINER_THRESHOLD

        assert isinstance(GLINER_THRESHOLD, (int, float))
        assert 0 <= GLINER_THRESHOLD <= 1
        assert GLINER_THRESHOLD > 0


class TestDatabaseConfig:
    def test_neo4j_uri_format(self):
        from config import NEO4J_URI

        assert NEO4J_URI
        assert 'bolt' in NEO4J_URI or 'neo4j' in NEO4J_URI

    def test_neo4j_credentials_exist(self):
        from config import NEO4J_USER, NEO4J_PASSWORD

        assert NEO4J_USER
        assert NEO4J_PASSWORD

    def test_neo4j_database_specified(self):
        from config import NEO4J_DB

        assert NEO4J_DB
        assert isinstance(NEO4J_DB, str)


class TestOllamaConfig:
    def test_ollama_url_format(self):
        from config import OLLAMA_EMBED_URL

        assert OLLAMA_EMBED_URL
        assert 'http' in OLLAMA_EMBED_URL.lower()

    def test_model_names_not_empty(self):
        from config import OLLAMA_EMBED_MODEL, OLLAMA_CHAT_MODEL

        assert OLLAMA_EMBED_MODEL
        assert OLLAMA_CHAT_MODEL
        assert len(OLLAMA_EMBED_MODEL) > 0
        assert len(OLLAMA_CHAT_MODEL) > 0

    def test_model_names_different(self):
        from config import OLLAMA_EMBED_MODEL, OLLAMA_CHAT_MODEL

        assert OLLAMA_EMBED_MODEL != OLLAMA_CHAT_MODEL


class TestBatchConfig:
    def test_chunk_embed_batch_positive(self):
        from config import CHUNK_EMBED_BATCH

        assert CHUNK_EMBED_BATCH > 0
        assert isinstance(CHUNK_EMBED_BATCH, int)

    def test_reasonable_batch_size(self):
        from config import CHUNK_EMBED_BATCH

        assert CHUNK_EMBED_BATCH <= 1000
