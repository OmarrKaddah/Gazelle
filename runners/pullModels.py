"""
Pull every Ollama model the Gazelle pipeline needs.

Run on the deployment machine (the bank server) once Ollama is installed:

    python runners/pullModels.py

The model names are read from .env so this stays in sync with what the app
actually loads — set your production choices in .env first, then run this.

────────────────────────────────────────────────────────────────────────────
Pipeline roles and recommended PRODUCTION models for Arabic banking documents
(put your chosen value in .env; defaults below are used if unset):

  OLLAMA_VISION_MODEL   OCR of scanned PDFs / images.
                        Best:     qwen3-vl:30b-a3b-instruct   (needs a GPU / big RAM)
                        Balanced: qwen3-vl:8b-instruct-q4_K_M
  OLLAMA_TEXT_MODEL     Entity extraction (NER).   e.g. qwen2.5:72b-instruct-q4_K_M
  OLLAMA_EXTRACT_MODEL  Relationship extraction.   defaults to OLLAMA_TEXT_MODEL
  OLLAMA_CHAT_MODEL     Chat answering.            e.g. qwen2.5:72b-instruct-q4_K_M
  OLLAMA_EMBED_MODEL    Chunk + entity embeddings. bge-m3   (keep this one)

Notes:
  • Digital PDFs, Word, and text files need NO vision model (text is read
    directly). Only images and scanned PDFs use OLLAMA_VISION_MODEL.
  • The semantic chunker (CHUNKER_TYPE=semantic) downloads BAAI/bge-m3 from
    HuggingFace on first use — that is NOT an Ollama model. With internet it
    is automatic; offline, use CHUNKER_TYPE=default (no model needed).
────────────────────────────────────────────────────────────────────────────
"""

import os
import subprocess

from dotenv import load_dotenv

load_dotenv()

TEXT_MODEL = os.getenv('OLLAMA_TEXT_MODEL', 'qwen2.5:72b-instruct-q4_K_M')

# role -> model name (resolved from .env, with production-grade defaults)
MODELS = {
    'OCR / vision':            os.getenv('OLLAMA_VISION_MODEL', 'qwen3-vl:8b-instruct-q4_K_M'),
    'Embeddings':              os.getenv('OLLAMA_EMBED_MODEL', 'bge-m3'),
    'Entity extraction (NER)': TEXT_MODEL,
    'Relationship extraction': os.getenv('OLLAMA_EXTRACT_MODEL', TEXT_MODEL),
    'Chat / answering':        os.getenv('OLLAMA_CHAT_MODEL', 'qwen2.5:72b-instruct-q4_K_M'),
}


def pull(model):
    print(f'\n>>> ollama pull {model}')
    subprocess.run(['ollama', 'pull', model], check=True)


def main():
    print('Gazelle — required Ollama models:')
    for role, model in MODELS.items():
        print(f'  {role:26} -> {model}')

    pulled = set()
    for model in MODELS.values():
        if model not in pulled:
            pulled.add(model)
            pull(model)

    print(f'\nDone. Pulled {len(pulled)} model(s).')


if __name__ == '__main__':
    main()
