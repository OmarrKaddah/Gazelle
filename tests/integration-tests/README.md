# Integration Tests

End-to-end workflow tests verifying that complete pipelines work correctly with minimal mocking.

## Test Files

- **test_parse_chunk_workflow.py** — Parse → Chunk workflow (10 tests)
  - Full document parsing and chunking
  - Data persistence (JSON saving/loading)
  - Hierarchy preservation
  - Metadata tracking
  - Content integrity

- **test_embedding_workflow.py** — Embedding pipeline (5 tests)
  - Document embedding workflow
  - Token counting consistency
  - Embedding dimension validation
  - Query embedding

## Test Classes

### Parse-Chunk Integration
- `TestParseChunkIntegration` — Complete workflow tests

### Embedding Integration  
- `TestEmbeddingWorkflow` — Embedding pipeline tests

## Running Integration Tests

### Run all integration tests
```bash
pytest tests/integration-tests -v
```

### Run only integration-marked tests
```bash
pytest tests/integration-tests -v -m integration
```

### Run specific test file
```bash
pytest tests/integration-tests/test_parse_chunk_workflow.py -v
```

### Run from Makefile
```bash
make test-integration
```

## Fixtures

Defined in `conftest.py`:

- **integration_data_dir** — Complete temp directory structure
- **sample_document_content** — Real banking document
- **parsed_document** — Parsed elements from sample doc
- **chunked_document** — Chunks from parsed document

## Key Differences: Unit vs Module vs Integration

| Aspect | Unit | Module | Integration |
|--------|------|--------|-------------|
| **Scope** | Single function | Multiple modules | Complete workflow |
| **Mocking** | Heavy | Moderate | Minimal |
| **Focus** | Correctness | Integration | End-to-end |
| **Speed** | Fast | Medium | Slow |
| **Isolation** | Complete | Partial | Minimal |

## Test Markers

Tests use `@pytest.mark.integration` to allow filtering:

```bash
# Run only integration tests
pytest -m integration

# Skip integration tests
pytest -m "not integration"
```

## Workflow Validation

Integration tests verify:

1. **Data Flow** — Data moves correctly through pipeline stages
2. **Persistence** — Data is saved/loaded correctly (JSON)
3. **Metadata** — All metadata is preserved and consistent
4. **Content** — Original content is preserved (no loss)
5. **Structure** — Hierarchy and relationships preserved
6. **Idempotency** — Pipeline produces consistent results

## Coverage Goals

- Parse-Chunk: 100% workflow coverage
- Embedding: 80% (minimal Ollama mocking)

## Running Full Test Suite

```bash
# Unit + Module + Integration
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Just integration
pytest tests/integration-tests -v
```

## Notes

Integration tests:
- Use real document content
- Verify complete workflows
- Test data persistence
- Validate metadata handling
- Are slower but more realistic
- Use `@pytest.mark.integration` for filtering
