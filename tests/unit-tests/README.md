# Unit Tests

Unit tests for Gazelle's core processing pipeline: parser, chunker, and embedding.

## Test Files

- **test_parser.py** — Tests for document parsing functions
  - `TestClassifyBlock` — Block type detection (heading, table, list, paragraph)
  - `TestHeadingLevel` — Markdown heading level extraction
  - `TestHeadingText` — Heading text extraction
  - `TestUpdateSection` — Section path updates
  - `TestMakeId` — Element ID generation
  - `TestParsedElement` — ParsedElement dataclass validation

- **test_chunker.py** — Tests for document chunking
  - `TestCountTokens` — Token counting with BGE-M3 tokenizer
  - `TestCollectPages` — Page number collection
  - `TestSplitText` — Text splitting logic
  - `TestTailText` — Tail text extraction
  - `TestGroupBySection` — Section-based grouping
  - `TestPackElements` — Element packing into chunks
  - `TestBuildChunk` — Chunk creation

- **test_embedding.py** — Tests for embedding operations
  - `TestEmbedTexts` — Text embedding via Ollama API
  - `TestEmbedQuery` — Query embedding with NaN fallback
  - `TestLoadChunks` — Chunk file loading
  - `TestWriteEmbedding` — Neo4j embedding storage
  - `TestEmbeddingIntegration` — Full pipeline integration

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test file
```bash
pytest tests/unit-tests/test_parser.py
```

### Run specific test class
```bash
pytest tests/unit-tests/test_parser.py::TestClassifyBlock
```

### Run specific test
```bash
pytest tests/unit-tests/test_parser.py::TestClassifyBlock::test_heading
```

### Run with verbose output
```bash
pytest -v
```

### Run with coverage
```bash
pytest --cov=src --cov-report=html
```

### Skip slow tests
```bash
pytest -m "not slow"
```

## Dependencies

- pytest
- transformers (for BGE-M3 tokenizer)
- neo4j (for graph operations, mocked in tests)

Install with:
```bash
pip install pytest
```

## Fixtures

Shared fixtures are defined in `conftest.py`:

- **sample_element** — Single ParsedElement
- **sample_elements** — List of ParsedElements
- **sample_chunk** — Single Chunk object

Use them in tests:
```python
def test_something(sample_element):
    assert sample_element.docName == 'test_doc'
```

## Mocking

External services are mocked:
- **Ollama API** — Mocked in `test_embedding.py`
- **Neo4j driver** — Mocked in `test_embedding.py`

File I/O is tested with `tempfile` for isolation.

## Coverage

Target coverage: >80% for core pipeline functions
- Parser: 90%
- Chunker: 85%
- Embedding: 75% (limited by service mocking)

Run coverage report:
```bash
pytest --cov=src --cov-report=term-missing
```
