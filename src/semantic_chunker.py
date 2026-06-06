import hashlib
import os
from typing import List

from dotenv import load_dotenv
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

from chunker import Chunk
from parser import ParsedElement

load_dotenv()


class LocalEmbeddings(Embeddings):
    def __init__(self, model_name: str | None = None):
        model_path = model_name or os.getenv("BGE_M3_PATH")
        self.model = SentenceTransformer(model_path)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.encode(texts, show_progress_bar=False)]

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([text])[0].tolist()


def chunkDoc(elements: List[ParsedElement], breakpoint_threshold_type: str = 'percentile', breakpoint_threshold_amount: float = 95.0) -> List[Chunk]:
    embeddings = LocalEmbeddings()
    splitter = SemanticChunker(
        embeddings=embeddings,
        breakpoint_threshold_type=breakpoint_threshold_type,
        breakpoint_threshold_amount=breakpoint_threshold_amount,
    )

    chunks = []
    idx = 0

    for elem in elements:
        if not elem.text.strip() or elem.elementType == 'heading':
            continue

        prefix = (elem.sectionPath[-1] + ': ') if elem.sectionPath else ''

        if elem.elementType == 'table':
            chunkId = hashlib.sha256(f"{elem.docName}::{idx}::{elem.text[:50]}".encode()).hexdigest()[:16]
            chunks.append(Chunk(
                chunkId=chunkId,
                docName=elem.docName,
                sectionPath=list(elem.sectionPath),
                pages=[elem.page] if elem.page is not None else [],
                text=prefix + elem.text,
                elementIds=[elem.elementId],
                accessLevel=elem.accessLevel,
            ))
            idx += 1
            continue

        docs = splitter.create_documents([elem.text])
        for doc in docs:
            chunkId = hashlib.sha256(f"{elem.docName}::{idx}::{doc.page_content[:50]}".encode()).hexdigest()[:16]
            chunks.append(Chunk(
                chunkId=chunkId,
                docName=elem.docName,
                sectionPath=list(elem.sectionPath),
                pages=[elem.page] if elem.page is not None else [],
                text=prefix + doc.page_content,
                elementIds=[elem.elementId],
                accessLevel=elem.accessLevel,
            ))
            idx += 1

    return chunks
