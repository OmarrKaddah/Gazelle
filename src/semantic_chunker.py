import hashlib
from typing import List

from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.embeddings import Embeddings

from chunker import Chunk, countTokens, dumpChunks, parseMarkdownTable, tableToSentences, absorbTableHeaders
from parser import ParsedElement
import os
from dotenv import load_dotenv
load_dotenv()


class LocalEmbeddings(Embeddings):
    """Thin wrapper using sentence-transformers if available."""

    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer

        model_path = model_name or os.getenv("BGE_M3_PATH")

        if not model_path:
            raise ValueError("BGE_M3_PATH not found in .env")

        self.model = SentenceTransformer(model_path)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.encode(texts, show_progress_bar=False)]

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([text])[0].tolist()
    
def _generate_chunk_id(doc_name: str, content: str, index: int) -> str:
    raw = f"{doc_name}::{index}::{content[:50]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_prefix(doc_name: str, section_path: list[str]) -> str:
    return (section_path[-1] + ': ') if section_path else ''


def _create_chunk_from_element(
    doc_name: str,
    elem: ParsedElement,
    text: str,
    index: int,
) -> Chunk:
    prefix = _build_prefix(doc_name, elem.sectionPath)
    full = prefix + text
    return Chunk(
        chunkId=_generate_chunk_id(doc_name, text, index),
        docName=doc_name,
        sectionPath=list(elem.sectionPath),
        pages=[elem.page] if elem.page is not None else [],
        text=full,
        elementIds=[elem.elementId],
        accessLevel=elem.accessLevel,
    )


def chunkDoc(elements: List[ParsedElement], breakpoint_threshold_type: str = 'percentile', breakpoint_threshold_amount: float = 95.0) -> List[Chunk]:
    """Semantic chunking using LangChain's SemanticChunker.

    Returns a list of `Chunk` objects compatible with the existing pipeline.
    """
    embeddings = LocalEmbeddings()
    splitter = SemanticChunker(
        embeddings=embeddings,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
    )

    chunks: List[Chunk] = []
    idx = 0

    elements = absorbTableHeaders(elements)
    for elem in elements:
        if not getattr(elem, 'text', '').strip():
            continue
        if elem.elementType == 'heading':
            continue
        if elem.elementType == 'table':
            parsed = parseMarkdownTable(elem.text)
            tableText = tableToSentences(*parsed) if parsed else elem.text
            ch = _create_chunk_from_element(elem.docName, elem, tableText, idx)
            idx += 1
            chunks.append(ch)
            continue

        try:
            docs = splitter.create_documents([elem.text])
            for d in docs:
                ch = _create_chunk_from_element(elem.docName, elem, d.page_content, idx)
                idx += 1
                chunks.append(ch)
        except Exception as e:
            print(f"⚠ Semantic chunking failed for {elem.docName}: {e}. Skipping.")
            continue

    return chunks


def dumpChunksSemantic(chunks: List[Chunk], docName: str) -> None:
    dumpChunks(chunks, docName)
