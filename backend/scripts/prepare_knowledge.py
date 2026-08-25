from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.db import init_db, replace_knowledge_corpus_stats, upsert_knowledge_document
from app.services.openai_client import OpenAIRagError, embed_texts, has_openai_api_key


RAW_ROOT = Path(settings.knowledge_raw_root)
PROCESSED_ROOT = Path(settings.knowledge_processed_root)
CHUNKS_ROOT = Path(settings.knowledge_chunks_root)
KNOWLEDGE_ROOT = BACKEND_DIR / "knowledge"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "document"


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def vendor_for_path(path: Path) -> str:
    try:
        relative = path.relative_to(RAW_ROOT)
        return relative.parts[0]
    except ValueError:
        return "internal"


def extract_pdf_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages).strip(), len(reader.pages)


def extract_markdown_text(path: Path) -> tuple[str, int]:
    return path.read_text(encoding="utf-8"), 1


def document_sources() -> list[Path]:
    markdown_docs = sorted(path for path in KNOWLEDGE_ROOT.glob("*.md") if path.is_file())
    raw_docs = sorted(path for path in RAW_ROOT.rglob("*") if path.is_file() and path.suffix.lower() in {".pdf", ".md"})
    return markdown_docs + raw_docs


def process_document(path: Path) -> tuple[dict, list[dict]]:
    source_type = "pdf" if path.suffix.lower() == ".pdf" else "markdown"
    vendor = vendor_for_path(path) if path.is_relative_to(RAW_ROOT) else "internal"
    title = path.stem.replace("_", " ").strip()
    document_slug = slugify(f"{vendor}-{path.stem}")
    processed_dir = PROCESSED_ROOT / vendor
    chunk_dir = CHUNKS_ROOT / vendor
    processed_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    if source_type == "pdf":
        content, page_count = extract_pdf_text(path)
    else:
        content, page_count = extract_markdown_text(path)

    chunks = split_into_chunks(content)
    processed_path = processed_dir / f"{document_slug}.txt"
    chunk_path = chunk_dir / f"{document_slug}.jsonl"
    processed_path.write_text(content, encoding="utf-8")

    chunk_records = []
    for index, chunk in enumerate(chunks):
        metadata = {
            "vendor": vendor,
            "title": title,
            "source_type": source_type,
            "source_path": str(path),
        }
        record = {
            "chunk_index": index,
            "content": chunk,
            "token_count": len(chunk.split()),
            "tokens": tokenize(chunk),
            "metadata": metadata,
        }
        chunk_records.append(record)

    document_id = slugify(f"{vendor}-{path.stem}-{hashlib.md5(str(path).encode('utf-8')).hexdigest()[:8]}")
    document = {
        "document_id": document_id,
        "title": title,
        "vendor": vendor,
        "source_type": source_type,
        "source_path": str(path),
        "processed_path": str(processed_path),
        "chunk_path": str(chunk_path),
        "page_count": page_count,
        "chunk_count": len(chunk_records),
        "status": "indexed" if chunk_records else "empty",
        "notes": None if chunk_records else "No extractable text found in source document.",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
    return document, chunk_records


def write_chunk_file(chunk_path: str, chunks: list[dict]) -> None:
    output_path = Path(chunk_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=True) + "\n")


def build_corpus_stats(all_chunks: list[dict]) -> dict[str, dict]:
    document_frequency: Counter[str] = Counter()
    chunk_count = len(all_chunks)
    for chunk in all_chunks:
        document_frequency.update(set(chunk.get("tokens", [])))

    stats: dict[str, dict] = {}
    for token, df in document_frequency.items():
        idf = math.log((1 + chunk_count) / (1 + df)) + 1.0
        stats[token] = {
            "token": token,
            "document_frequency": df,
            "idf": idf,
            "chunk_count": chunk_count,
            "updated_at": utc_now_iso(),
        }
    return stats


def attach_vectors(chunks: list[dict], stats: dict[str, dict], top_k: int = 64) -> None:
    for chunk in chunks:
        tokens = chunk.get("tokens", [])
        counts = Counter(tokens)
        total = sum(counts.values()) or 1
        weighted = {
            token: (count / total) * stats[token]["idf"]
            for token, count in counts.items()
            if token in stats
        }
        top_terms = sorted(weighted.items(), key=lambda item: item[1], reverse=True)[:top_k]
        magnitude = math.sqrt(sum(weight * weight for _, weight in top_terms)) or 1.0
        chunk["vector"] = {
            token: round(weight / magnitude, 8)
            for token, weight in top_terms
        }
        chunk.pop("tokens", None)


def attach_embeddings(chunks: list[dict], batch_size: int = 32) -> tuple[str, str | None]:
    if not chunks:
        return "no_chunks", None
    if not has_openai_api_key():
        for chunk in chunks:
            chunk["embedding"] = []
        return "missing_api_key", None

    try:
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            vectors = embed_texts([chunk["content"] for chunk in batch])
            for chunk, vector in zip(batch, vectors, strict=False):
                chunk["embedding"] = vector
        return "openai", None
    except OpenAIRagError as exc:
        for chunk in chunks:
            chunk["embedding"] = []
        return "embedding_failed", str(exc)


def main() -> None:
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    CHUNKS_ROOT.mkdir(parents=True, exist_ok=True)
    init_db()

    prepared_documents: list[tuple[dict, list[dict]]] = []
    all_chunks: list[dict] = []

    for path in document_sources():
        document, chunks = process_document(path)
        prepared_documents.append((document, chunks))
        all_chunks.extend(chunks)

    stats = build_corpus_stats(all_chunks)
    attach_vectors(all_chunks, stats)
    embedding_status, embedding_error = attach_embeddings(all_chunks)
    replace_knowledge_corpus_stats(list(stats.values()))

    for document, chunks in prepared_documents:
        write_chunk_file(document["chunk_path"], chunks)
        upsert_knowledge_document(document, chunks)
        print(
            f"Indexed {document['document_id']} -> {document['chunk_count']} chunks "
            f"from {Path(document['source_path']).name}"
        )

    if embedding_error:
        print(f"Knowledge embedding status: {embedding_status} ({embedding_error})")
    else:
        print(f"Knowledge embedding status: {embedding_status}")


if __name__ == "__main__":
    main()
