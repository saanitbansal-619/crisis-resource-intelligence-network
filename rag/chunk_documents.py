"""
Split the RAG corpus into searchable text chunks.

Run: python -m rag.chunk_documents
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAG_DIR = PROJECT_ROOT / "data" / "rag"
CORPUS_PATH = RAG_DIR / "corpus.json"
CHUNKS_PATH = RAG_DIR / "chunks.json"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def load_corpus(path: Path = CORPUS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Corpus file not found: {path}. Run `python -m rag.build_corpus` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(cleaned):
        end = start + chunk_size
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start += step

    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    chunks: list[dict] = []

    for doc in documents:
        text_chunks = split_text(doc.get("text", ""))
        for index, chunk_text in enumerate(text_chunks):
            chunks.append(
                {
                    "chunk_id": f"{doc['doc_id']}_chunk_{index}",
                    "doc_id": doc.get("doc_id", ""),
                    "source_type": doc.get("source_type", ""),
                    "source_id": doc.get("source_id", ""),
                    "title": doc.get("title", ""),
                    "country": doc.get("country", ""),
                    "event_type": doc.get("event_type", ""),
                    "published_at": doc.get("published_at", ""),
                    "url": doc.get("url", ""),
                    "chunk_index": index,
                    "chunk_text": chunk_text,
                }
            )

    return chunks


def save_chunks(chunks: list[dict]) -> Path:
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    CHUNKS_PATH.write_text(json.dumps(chunks, indent=2, default=str), encoding="utf-8")
    return CHUNKS_PATH


def main() -> None:
    documents = load_corpus()
    chunks = chunk_documents(documents)
    output_path = save_chunks(chunks)

    print("Chunking complete.")
    print(f"Documents loaded: {len(documents)}")
    print(f"Chunks created: {len(chunks)}")
    print(f"Output path: {output_path}")


if __name__ == "__main__":
    main()
