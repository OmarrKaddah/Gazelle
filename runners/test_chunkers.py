import _bootstrap  # noqa: F401
import sys
import json
from pathlib import Path

from parser import ParsedElement
from chunker import countTokens

from chunker import chunkDoc as chunker_v2
from semantic_chunker import chunkDoc as chunker_v3


def load_txt_files(file_paths: list[str]) -> list[ParsedElement]:
    elements = []
    for file_path in file_paths:
        p = Path(file_path)
        if not p.exists():
            print(f"⚠ File not found: {file_path}")
            continue
        doc_name = p.stem
        content = p.read_text(encoding='utf-8')
        if not content.strip():
            print(f"⚠ File is empty: {file_path}")
            continue
        elem = ParsedElement(
            docName=doc_name,
            sectionPath=['Content'],
            page=None,
            elementType='paragraph',
            text=content,
            elementId=f'{doc_name}-f01',
            accessLevel='internal',
        )
        elements.append(elem)
        print(f"✓ Loaded: {p.name} ({len(content)} chars)")
    return elements


def normalize_chunk(c):
    # Return a uniform dict for printing/saving
    if hasattr(c, 'chunkId'):
        chunk_id = getattr(c, 'chunkId')
        content = getattr(c, 'text', '')
        doc_name = getattr(c, 'docName', '')
        element_type = getattr(c, 'accessLevel', 'text')
    else:
        # fallback to dict-like
        chunk_id = c.get('chunk_id')
        content = c.get('content', '')
        doc_name = c.get('doc_name', '')
        element_type = c.get('element_type', 'text')
    tokens = countTokens(content) if content else 0
    return {
        'chunk_id': chunk_id,
        'element_type': element_type,
        'token_estimate': tokens,
        'doc_name': doc_name,
        'content': content,
    }


def print_chunk_stats(chunks, title):
    print(f"\n{'='*60}")
    print(title)
    print(f"{'='*60}")
    print(f"Total chunks: {len(chunks)}")
    if not chunks:
        return
    norms = [normalize_chunk(c) for c in chunks]
    type_counts = {}
    token_counts = []
    for n in norms:
        type_counts[n['element_type']] = type_counts.get(n['element_type'], 0) + 1
        token_counts.append(n['token_estimate'])
    print('\nChunk breakdown by type:')
    for k, v in type_counts.items():
        print(f'  {k}: {v}')
    print('\nToken statistics:')
    print(f'  Min: {min(token_counts)}')
    print(f'  Max: {max(token_counts)}')
    print(f'  Avg: {sum(token_counts)/len(token_counts):.1f}')
    print(f'  Total: {sum(token_counts)}')
    print('\nFirst 3 chunks:')
    for i, n in enumerate(norms[:3], 1):
        print(f"\n  Chunk {i}:")
        print(f"    ID: {n['chunk_id']}")
        print(f"    Type: {n['element_type']}")
        print(f"    Tokens: {n['token_estimate']}")
        print(f"    Content preview: {n['content'][:100]}...")


def save_chunks(chunks, output_dir: str, prefix: str):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    norms = [normalize_chunk(c) for c in chunks]
    for i, n in enumerate(norms, 1):
        fname = out / f"{prefix}_chunk_{i:04d}.json"
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(n, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved {len(norms)} chunks to {out}")


def main():
    # Hardcoded input files
    files = [
        "Documents\\doc1.txt",
        
    ]

    # Hardcoded output directory
    outdir = "chunk_tests\\test_results_custom"

    elements = load_txt_files(files)

    if not elements:
        print('No elements loaded; exiting')
        return

    print('\n[1/2] Running chunker_v2 (pack-based)')
    try:
        chunks_v2 = chunker_v2(elements)
    except TypeError:
        chunks_v2 = chunker_v2(elements, 600)
    except Exception as e:
        print(f'V2 failed: {e}')
        chunks_v2 = []

    print_chunk_stats(chunks_v2, 'CHUNKER V2 Results')
    save_chunks(chunks_v2, Path(outdir) / 'v2', 'v2')

    print('\n[2/2] Running chunker_v3 (semantic)')
    try:
        chunks_v3 = chunker_v3(elements)
    except Exception as e:
        print(f'V3 failed: {e}')
        chunks_v3 = []

    print_chunk_stats(chunks_v3, 'CHUNKER V3 Results')
    save_chunks(chunks_v3, Path(outdir) / 'v3', 'v3')

    print('\n' + '='*60)
    print('SUMMARY')
    print('='*60)

    print(f'V2 chunks: {len(chunks_v2)}')
    print(f'V3 chunks: {len(chunks_v3)}')

    if chunks_v2 and chunks_v3:
        v2_tokens = sum(normalize_chunk(c)['token_estimate'] for c in chunks_v2)
        v3_tokens = sum(normalize_chunk(c)['token_estimate'] for c in chunks_v3)

        print(f'V2 total tokens: {v2_tokens}')
        print(f'V3 total tokens: {v3_tokens}')
        print(f'Difference: {abs(v2_tokens - v3_tokens)} tokens')


if __name__ == '__main__':
    main()
