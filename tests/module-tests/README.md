# Module Integration Tests

Integration and module-level tests for Gazelle's processing pipelines. These tests verify that modules work correctly together, not just in isolation.

## Test Files

- **test_parser_chunker_integration.py** — Parser → Chunker pipeline
  - Full flow from parsed elements to chunks
  - Section path preservation
  - Metadata handling
  - Edge cases (Unicode, special characters, large elements)

- **test_ner_pipeline_integration.py** — NER extraction pipelines
  - GLiNER entity extraction
  - LLM-based NER extraction
  - Output format consistency
  - Error handling and filtering

- **test_embedding_pipeline_integration.py** — Embedding generation pipeline
  - Document embedding workflow
  - Index creation (vector + fulltext)
  - Batch processing
  - Quality validation
  - Persistence to Neo4j

## Test Classes

### Parser-Chunker Integration
- `TestParserChunkerPipeline` — End-to-end chunking workflow
- `TestChunkingEdgeCases` — Boundary conditions

### NER Pipeline
- `TestGLiNERPipeline` — Classical NER extraction
- `TestLLMNERPipeline` — LLM-based NER
- `TestNERPipelineComparison` — Output format validation
- `TestNEREdgeCases` — Special characters, overlaps, Arabic

### Embedding Pipeline
- `TestEmbeddingPipeline` — Full workflow
- `TestEmbeddingQuality` — Semantic quality checks
- `TestEmbeddingErrorHandling` — NaN fallback, error responses
- `TestEmbeddingPersistence` — Neo4j writes, batch handling
- `TestEmbeddingEdgeCases` — Empty text, large text, Unicode

## Running Tests

### Run all module tests
```bash
pytest tests/module-tests
```

### Run specific test file
```bash
pytest tests/module-tests/test_parser_chunker_integration.py
```

### Run specific test class
```bash
pytest tests/module-tests/test_parser_chunker_integration.py::TestParserChunkerPipeline
```

### Run with verbose output
```bash
pytest tests/module-tests -v
```

### Run with coverage
```bash
pytest tests/module-tests --cov=src --cov-report=html
```

### Run from Makefile
```bash
make test-modules
make test-modules-parser
make test-modules-ner
make test-modules-embedding
```

## Test Data

Fixtures are defined in `conftest.py`:

- **temp_data_dir** — Temporary directory with standard structure
- **sample_markdown_document** — Example markdown file
- **sample_parsed_elements** — List of parsed elements
- **sample_chunks** — Chunked document
- **sample_extracted_entities** — NER results
- **sample_embeddings** — Embedding vectors

## Pipeline Stages Tested

```
OCR Output
    ↓
[Parser] → Parsed Elements
    ↓
[Chunker] → Chunks
    ├─ [GLiNER] → Entity extraction
    │
    └─ [LLM NER] → Entity extraction
        ↓
[Embedding] → Vector index
    ↓
[Neo4j] → Graph database
```

## Mocking Strategy

External services are mocked to enable reliable testing:

- **Ollama API** — Mocked in embedding and NER tests
- **Neo4j driver** — Mocked database operations
- **GLiNER model** — Mocked entity prediction

File I/O is tested with `tempfile` for isolation.

## Coverage Goals

- Parser-Chunker: 95%
- NER pipelines: 85%
- Embedding: 80%

Check coverage:
```bash
pytest tests/module-tests --cov=src --cov-report=term-missing
```

## Notes

Module tests are slower than unit tests because they:
- Test multiple functions together
- Use more complex fixtures
- Mock external services realistically

Run module tests after unit tests pass to verify integration.
